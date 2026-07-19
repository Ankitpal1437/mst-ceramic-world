"""
MST Ceramic World — Complete Business Management System v2
Flask app with Supabase backend. New price format (3 generations) + order tracking.
"""
import os, json, sqlite3, hashlib
from datetime import datetime, date, timedelta
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, g
import urllib.request, urllib.error

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'mst-ceramic-secret-2026-xk9q')

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://habwesaoixrefalzkubw.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')

def sb(method, table, data=None, params=''):
    url = f"{SUPABASE_URL}/rest/v1/{table}{params}"
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json',
        'Prefer': 'return=representation'
    }
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            raw = res.read()
            return json.loads(raw) if raw else []
    except urllib.error.HTTPError as e:
        print(f"SB error {e.code}: {e.read().decode()[:200]}")
        return None
    except Exception as e:
        print(f"SB exception: {e}")
        return None

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PRODUCTS_DB = os.path.join(APP_DIR, 'mst.db')

def get_pdb():
    if 'pdb' not in g:
        g.pdb = sqlite3.connect(PRODUCTS_DB)
        g.pdb.row_factory = sqlite3.Row
    return g.pdb

@app.teardown_appcontext
def close_pdb(e):
    pdb = g.pop('pdb', None)
    if pdb: pdb.close()

def hash_pw(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Unauthorized'}), 401
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated

# ================= PAGES =================
@app.route('/')
def root():
    return redirect(url_for('home')) if session.get('user_id') else redirect(url_for('login_page'))

@app.route('/login')
def login_page():
    if session.get('user_id'): return redirect(url_for('home'))
    return render_template('login.html')

@app.route('/register')
def register_page():
    return render_template('register.html')

@app.route('/home')
@login_required
def home():
    return render_template('home.html', user=session)

@app.route('/search')
@login_required
def search_page():
    return render_template('search.html', user=session)

@app.route('/quotation')
@login_required
def quotation_page():
    return render_template('quotation.html', user=session)

@app.route('/quotation/<qid>')
@login_required
def quotation_view(qid):
    return render_template('quotation_view.html', user=session, qid=qid)

@app.route('/customers')
@login_required
def customers_page():
    return render_template('customers.html', user=session)

@app.route('/customers/<cid>')
@login_required
def customer_detail(cid):
    return render_template('customer_detail.html', user=session, cid=cid)

@app.route('/visitors')
@login_required
def visitors_page():
    return render_template('visitors.html', user=session)

@app.route('/followups')
@login_required
def followups_page():
    return render_template('followups.html', user=session)

@app.route('/orders')
@login_required
def orders_page():
    return render_template('orders.html', user=session)

@app.route('/admin')
@login_required
def admin_page():
    if session.get('role') != 'admin': return redirect(url_for('home'))
    return render_template('admin.html', user=session)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

# ================= AUTH =================
@app.route('/api/auth/register', methods=['POST'])
def api_register():
    data = request.json
    name, phone, email, password = data.get('name','').strip(), data.get('phone','').strip(), data.get('email','').strip(), data.get('password','').strip()
    if not name or not password or (not phone and not email):
        return jsonify({'ok':False,'error':'Name, password aur phone/email zaroori hai'})
    result = sb('POST','mst_users',{'name':name,'phone':phone or None,'email':email or None,'password_hash':hash_pw(password),'role':'staff','status':'pending'})
    if result:
        return jsonify({'ok':True,'message':'Registration ho gaya! Ankit se approval lena hoga.'})
    return jsonify({'ok':False,'error':'Registration failed — phone/email already exists'})

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.json
    identifier, password = data.get('identifier','').strip(), data.get('password','').strip()
    if not identifier or not password:
        return jsonify({'ok':False,'error':'Phone/email aur password daalo'})
    users = sb('GET','mst_users',params=f'?or=(phone.eq.{identifier},email.eq.{identifier})&select=*&limit=1')
    if not users:
        return jsonify({'ok':False,'error':'User nahi mila'})
    user = users[0]
    if user['password_hash'] != hash_pw(password):
        return jsonify({'ok':False,'error':'Password galat hai'})
    if user['status'] == 'pending':
        return jsonify({'ok':False,'error':'Account pending approval hai. Ankit se baat karo.'})
    if user['status'] in ('rejected','inactive'):
        return jsonify({'ok':False,'error':'Account inactive hai.'})
    session.permanent = True
    session['user_id'] = user['id']
    session['name'] = user['name']
    session['role'] = user['role']
    return jsonify({'ok':True,'name':user['name'],'role':user['role']})

# ================= PRODUCT SEARCH =================
@app.route('/api/search')
@login_required
def api_search():
    q = request.args.get('q','').strip().lower()
    if len(q) < 2: return jsonify({'results':[],'count':0})
    try:
        db = get_pdb()
        exact = db.execute("SELECT * FROM products WHERE code_norm=? LIMIT 20",(q,)).fetchall()
        ends = db.execute("SELECT * FROM products WHERE code_norm LIKE ? AND code_norm!=? LIMIT 20",('%'+q,q)).fetchall()
        starts = db.execute("SELECT * FROM products WHERE code_norm LIKE ? AND code_norm NOT LIKE ? LIMIT 20",(q+'%','%'+q)).fetchall()
        contains = db.execute("SELECT * FROM products WHERE code_norm LIKE ? AND code_norm NOT LIKE ? LIMIT 20",('%'+q+'%',q+'%')).fetchall()
        desc = db.execute("SELECT * FROM products WHERE desc_norm LIKE ? AND code_norm NOT LIKE ? LIMIT 20",('%'+q+'%','%'+q+'%')).fetchall()
        seen=set(); merged=[]
        for bucket in (exact,ends,starts,contains,desc):
            for row in bucket:
                if row['id'] not in seen:
                    seen.add(row['id']); merged.append(dict(row))
        return jsonify({'results':merged[:30],'count':len(merged)})
    except Exception as e:
        return jsonify({'results':[],'count':0,'error':str(e)})

@app.route('/api/stats')
@login_required
def api_stats():
    try:
        db = get_pdb()
        total = db.execute("SELECT COUNT(*) c FROM products").fetchone()['c']
        fittings = db.execute("SELECT COUNT(*) c FROM products WHERE source='FITTINGS'").fetchone()['c']
        lighting = db.execute("SELECT COUNT(*) c FROM products WHERE source='LIGHTING'").fetchone()['c']
        return jsonify({'total':total,'fittings':fittings,'lighting':lighting})
    except:
        return jsonify({'total':101526,'fittings':83198,'lighting':18328})

# ================= CUSTOMERS =================
@app.route('/api/customers', methods=['GET','POST'])
@login_required
def api_customers():
    if request.method == 'POST':
        data = request.json
        data['created_at'] = datetime.now().isoformat()
        result = sb('POST','mst_customers',data)
        if result: return jsonify({'ok':True,'id':result[0]['id']})
        return jsonify({'ok':False,'error':'Failed'})
    role, uid = session.get('role'), session.get('user_id')
    if role=='admin':
        custs = sb('GET','mst_customers',params='?select=*&order=created_at.desc') or []
    else:
        custs = sb('GET','mst_customers',params=f'?assigned_to=eq.{uid}&select=*&order=created_at.desc') or []
    return jsonify({'customers':custs})

@app.route('/api/customers/phone/<phone>')
@login_required
def api_cust_phone(phone):
    custs = sb('GET','mst_customers',params=f'?phone=eq.{phone}&select=*') or []
    if not custs: return jsonify({'found':False})
    c = custs[0]
    quotes = sb('GET','mst_quotations',params=f'?customer_id=eq.{c["id"]}&select=quot_number,grand_total,status,created_at&order=created_at.desc') or []
    visits = sb('GET','mst_visitors',params=f'?phone=eq.{phone}&select=*&order=check_in.desc&limit=5') or []
    return jsonify({'found':True,'customer':c,'quotations':quotes,'visits':visits})

@app.route('/api/customers/<cid>', methods=['GET','PUT'])
@login_required
def api_cust_detail(cid):
    if request.method == 'PUT':
        result = sb('PATCH','mst_customers',request.json,params=f'?id=eq.{cid}')
        return jsonify({'ok':result is not None})
    cust = sb('GET','mst_customers',params=f'?id=eq.{cid}&select=*')
    if not cust: return jsonify({'error':'Not found'}),404
    quotes = sb('GET','mst_quotations',params=f'?customer_id=eq.{cid}&select=*&order=created_at.desc') or []
    visits = sb('GET','mst_visitors',params=f'?customer_id=eq.{cid}&select=*&order=check_in.desc&limit=10') or []
    followups = sb('GET','mst_followups',params=f'?customer_id=eq.{cid}&select=*&order=followup_date.asc') or []
    return jsonify({'customer':cust[0],'quotations':quotes,'visits':visits,'followups':followups})

@app.route('/api/customers/<cid>/reassign', methods=['POST'])
@login_required
def api_reassign(cid):
    if session.get('role') != 'admin': return jsonify({'error':'Admin only'}),403
    data = request.json
    result = sb('PATCH','mst_customers',{'assigned_to':data['user_id'],'assigned_name':data['user_name']},params=f'?id=eq.{cid}')
    return jsonify({'ok':result is not None})

# ================= VISITORS =================
@app.route('/api/visitors', methods=['GET','POST'])
@login_required
def api_visitors():
    if request.method == 'POST':
        data = request.json
        data['check_in'] = datetime.now().isoformat()
        data['visit_date'] = date.today().isoformat()
        data['handled_by'] = session['user_id']
        data['handled_by_name'] = session['name']
        result = sb('POST','mst_visitors',data)
        return jsonify({'ok':bool(result)})
    today = date.today().isoformat()
    visitors = sb('GET','mst_visitors',params=f'?visit_date=eq.{today}&select=*&order=check_in.desc') or []
    inside = [v for v in visitors if not v.get('check_out')]
    return jsonify({'visitors':visitors,'today_count':len(visitors),'inside_count':len(inside)})

@app.route('/api/visitors/<vid>/checkout', methods=['POST'])
@login_required
def api_checkout(vid):
    data = request.json or {}
    sb('PATCH','mst_visitors',{'check_out':datetime.now().isoformat(),'remarks':data.get('remarks','')},params=f'?id=eq.{vid}')
    return jsonify({'ok':True})

# ================= QUOTATIONS =================
def can_access_quote(quote):
    """Admin can access everything. Others only their own (created_by)."""
    if session.get('role') == 'admin':
        return True
    return quote.get('created_by') == session.get('user_id')

@app.route('/api/quotations', methods=['GET','POST'])
@login_required
def api_quotations():
    if request.method == 'POST':
        data = request.json
        data['assigned_to'] = session['user_id']
        data['assigned_name'] = session['name']
        data['created_by'] = session['user_id']
        data['created_at'] = datetime.now().isoformat()
        data['valid_until'] = (date.today()+timedelta(days=15)).isoformat()
        if isinstance(data.get('bathrooms'),(list,dict)):
            data['bathrooms'] = json.dumps(data['bathrooms'])
        result = sb('POST','mst_quotations',data)
        if result:
            r = result[0]
            return jsonify({'ok':True,'id':r['id'],'quot_number':r.get('quot_number','')})
        return jsonify({'ok':False,'error':'Failed'})
    role, uid = session.get('role'), session.get('user_id')
    if role=='admin':
        quotes = sb('GET','mst_quotations',params='?select=*&order=created_at.desc&limit=150') or []
    else:
        quotes = sb('GET','mst_quotations',params=f'?created_by=eq.{uid}&select=*&order=created_at.desc&limit=150') or []
    for q in quotes:
        if isinstance(q.get('bathrooms'),str):
            try: q['bathrooms']=json.loads(q['bathrooms'])
            except: q['bathrooms']=[]
    return jsonify({'quotations':quotes})

@app.route('/api/quotations/<qid>', methods=['GET','PUT','DELETE'])
@login_required
def api_quot_detail(qid):
    existing = sb('GET','mst_quotations',params=f'?id=eq.{qid}&select=*')
    if not existing: return jsonify({'error':'Not found'}),404
    quote_record = existing[0]

    if not can_access_quote(quote_record):
        return jsonify({'ok':False,'error':'You can only access your own quotations'}),403

    if request.method == 'DELETE':
        sb('DELETE','mst_quotations',params=f'?id=eq.{qid}')
        return jsonify({'ok':True})

    if request.method == 'PUT':
        data = request.json
        reason = data.pop('edit_reason','')
        curr = quote_record.get('status','')
        if curr != 'Draft' and not reason:
            return jsonify({'ok':False,'error':'A reason is required to edit a quotation once it has been sent'})
        sb('POST','mst_quotation_logs',{'quotation_id':qid,'action':'Edited','old_status':curr,'new_status':data.get('status',curr),'reason':reason,'done_by':session['user_id'],'done_by_name':session['name']})
        if isinstance(data.get('bathrooms'),(list,dict)):
            data['bathrooms']=json.dumps(data['bathrooms'])
        result = sb('PATCH','mst_quotations',data,params=f'?id=eq.{qid}')
        return jsonify({'ok':result is not None})

    q=quote_record
    if isinstance(q.get('bathrooms'),str):
        try: q['bathrooms']=json.loads(q['bathrooms'])
        except: q['bathrooms']=[]
    if isinstance(q.get('delivery_status'),str):
        try: q['delivery_status']=json.loads(q['delivery_status'])
        except: q['delivery_status']={}
    logs = sb('GET','mst_quotation_logs',params=f'?quotation_id=eq.{qid}&select=*&order=created_at.desc') or []
    payments = sb('GET','mst_payments',params=f'?quotation_id=eq.{qid}&select=*&order=payment_date.desc') or []
    return jsonify({'quotation':q,'logs':logs,'payments':payments})

@app.route('/api/quotations/<qid>/status', methods=['POST'])
@login_required
def api_quot_status(qid):
    existing = sb('GET','mst_quotations',params=f'?id=eq.{qid}&select=*')
    if not existing: return jsonify({'error':'Not found'}),404
    if not can_access_quote(existing[0]):
        return jsonify({'ok':False,'error':'You can only manage your own quotations'}),403
    data = request.json
    new_status, reason = data.get('status'), data.get('reason','')
    old_status = existing[0]['status']
    update = {'status':new_status}
    if new_status=='Confirmed': update['confirmed_at']=datetime.now().isoformat()
    sb('PATCH','mst_quotations',update,params=f'?id=eq.{qid}')
    sb('POST','mst_quotation_logs',{'quotation_id':qid,'action':'Status Changed','old_status':old_status,'new_status':new_status,'reason':reason,'done_by':session['user_id'],'done_by_name':session['name']})
    return jsonify({'ok':True})

@app.route('/api/quotations/<qid>/delivery', methods=['POST'])
@login_required
def api_quot_delivery(qid):
    """Update per-product delivery status: Ready / Ordered / Delivered"""
    existing = sb('GET','mst_quotations',params=f'?id=eq.{qid}&select=*')
    if not existing: return jsonify({'error':'Not found'}),404
    if not can_access_quote(existing[0]):
        return jsonify({'ok':False,'error':'Not authorized'}),403
    data = request.json
    item_key = data.get('item_key')
    status = data.get('status')
    cur_status = existing[0].get('delivery_status','{}')
    if isinstance(cur_status,str):
        try: cur_status=json.loads(cur_status)
        except: cur_status={}
    cur_status[item_key] = status
    sb('PATCH','mst_quotations',{'delivery_status':json.dumps(cur_status)},params=f'?id=eq.{qid}')
    return jsonify({'ok':True})

# ================= PAYMENTS =================
@app.route('/api/payments', methods=['GET','POST'])
@login_required
def api_payments():
    if request.method == 'POST':
        data = request.json
        data['recorded_by'] = session['user_id']
        data['recorded_by_name'] = session['name']
        data['created_at'] = datetime.now().isoformat()
        result = sb('POST','mst_payments',data)
        return jsonify({'ok':bool(result)})
    qid = request.args.get('quotation_id','')
    if qid:
        payments = sb('GET','mst_payments',params=f'?quotation_id=eq.{qid}&select=*&order=payment_date.desc') or []
    else:
        payments = sb('GET','mst_payments',params='?select=*&order=payment_date.desc&limit=100') or []
    return jsonify({'payments':payments})

# Summary: product-wise quantities across bathrooms for a quotation
@app.route('/api/quotations/<qid>/summary')
@login_required
def api_quot_summary(qid):
    quote = sb('GET','mst_quotations',params=f'?id=eq.{qid}&select=bathrooms')
    if not quote: return jsonify({'error':'Not found'}),404
    baths = quote[0].get('bathrooms','[]')
    if isinstance(baths,str):
        try: baths=json.loads(baths)
        except: baths=[]
    product_map = {}
    total_items = 0
    for b in baths:
        bname = b.get('name','Bathroom')
        for area_key, items in (b.get('areas') or {}).items():
            for it in items:
                key = it.get('code') or it.get('name') or 'Custom'
                if key not in product_map:
                    product_map[key] = {'description': it.get('description') or it.get('name',''), 'total_qty':0, 'bathrooms':[]}
                qty = it.get('qty',1)
                product_map[key]['total_qty'] += qty
                product_map[key]['bathrooms'].append({'bathroom':bname,'qty':qty,'area':area_key})
                total_items += qty
    return jsonify({'products':product_map,'total_items':total_items,'bathroom_count':len(baths)})

# ================= ORDER TRACKING (Vashi supplier) =================
@app.route('/api/orders', methods=['GET','POST'])
@login_required
def api_orders():
    if request.method == 'POST':
        # Bulk create order items from a quotation
        data = request.json
        items = data.get('items',[])
        created = []
        for it in items:
            it['ordered_date'] = date.today().isoformat()
            it['ordered_by'] = session['user_id']
            it['ordered_by_name'] = session['name']
            it['created_at'] = datetime.now().isoformat()
            result = sb('POST','mst_order_items',it)
            if result: created.append(result[0])
        return jsonify({'ok':True,'created':len(created)})
    status_filter = request.args.get('status','')
    params = '?select=*&order=ordered_date.desc'
    if status_filter:
        params = f'?status=eq.{status_filter}&select=*&order=ordered_date.desc'
    orders = sb('GET','mst_order_items',params=params) or []
    return jsonify({'orders':orders})

@app.route('/api/orders/pending-search')
@login_required
def api_orders_pending_search():
    q = request.args.get('q','').strip()
    if len(q) < 2: return jsonify({'results':[]})
    orders = sb('GET','mst_order_items',params=f'?status=neq.Received&product_code=ilike.*{q}*&select=*&order=ordered_date.desc') or []
    if not orders:
        orders = sb('GET','mst_order_items',params=f'?status=neq.Received&product_d
