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
@app.route('/api/quotations', methods=['GET','POST'])
@login_required
def api_quotations():
    if request.method == 'POST':
        data = request.json
        data['assigned_to'] = data.get('assigned_to') or session['user_id']
        data['assigned_name'] = data.get('assigned_name') or session['name']
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
        quotes = sb('GET','mst_quotations',params=f'?assigned_to=eq.{uid}&select=*&order=created_at.desc&limit=150') or []
    for q in quotes:
        if isinstance(q.get('bathrooms'),str):
            try: q['bathrooms']=json.loads(q['bathrooms'])
            except: q['bathrooms']=[]
    return jsonify({'quotations':quotes})

@app.route('/api/quotations/<qid>', methods=['GET','PUT'])
@login_required
def api_quot_detail(qid):
    if request.method == 'PUT':
        data = request.json
        reason = data.pop('edit_reason','')
        existing = sb('GET','mst_quotations',params=f'?id=eq.{qid}&select=status')
        if existing:
            curr = existing[0].get('status','')
            if curr in ('Confirmed','Partial Delivery','Delivered') and not reason:
                return jsonify({'ok':False,'error':'Reason zaroori hai confirmed order edit karne ke liye'})
            sb('POST','mst_quotation_logs',{'quotation_id':qid,'action':'Edited','old_status':curr,'new_status':data.get('status',curr),'reason':reason,'done_by':session['user_id'],'done_by_name':session['name']})
        if isinstance(data.get('bathrooms'),(list,dict)):
            data['bathrooms']=json.dumps(data['bathrooms'])
        result = sb('PATCH','mst_quotations',data,params=f'?id=eq.{qid}')
        return jsonify({'ok':result is not None})
    quote = sb('GET','mst_quotations',params=f'?id=eq.{qid}&select=*')
    if not quote: return jsonify({'error':'Not found'}),404
    q=quote[0]
    if isinstance(q.get('bathrooms'),str):
        try: q['bathrooms']=json.loads(q['bathrooms'])
        except: q['bathrooms']=[]
    logs = sb('GET','mst_quotation_logs',params=f'?quotation_id=eq.{qid}&select=*&order=created_at.desc') or []
    return jsonify({'quotation':q,'logs':logs})

@app.route('/api/quotations/<qid>/status', methods=['POST'])
@login_required
def api_quot_status(qid):
    data = request.json
    new_status, reason = data.get('status'), data.get('reason','')
    existing = sb('GET','mst_quotations',params=f'?id=eq.{qid}&select=status')
    old_status = existing[0]['status'] if existing else ''
    update = {'status':new_status}
    if new_status=='Confirmed': update['confirmed_at']=datetime.now().isoformat()
    sb('PATCH','mst_quotations',update,params=f'?id=eq.{qid}')
    sb('POST','mst_quotation_logs',{'quotation_id':qid,'action':'Status Changed','old_status':old_status,'new_status':new_status,'reason':reason,'done_by':session['user_id'],'done_by_name':session['name']})
    return jsonify({'ok':True})

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
        orders = sb('GET','mst_order_items',params=f'?status=neq.Received&product_description=ilike.*{q}*&select=*&order=ordered_date.desc') or []
    return jsonify({'results':orders})

@app.route('/api/orders/<oid>/receive', methods=['POST'])
@login_required
def api_order_receive(oid):
    data = request.json or {}
    qty_received = data.get('qty_received', 1)
    order = sb('GET','mst_order_items',params=f'?id=eq.{oid}&select=*')
    if not order: return jsonify({'ok':False,'error':'Not found'})
    o = order[0]
    total_received = (o.get('qty_received') or 0) + qty_received
    new_status = 'Received' if total_received >= o.get('qty_ordered',1) else 'Partially Received'
    sb('PATCH','mst_order_items',{
        'qty_received': total_received, 'status': new_status,
        'received_date': date.today().isoformat()
    }, params=f'?id=eq.{oid}')
    return jsonify({'ok':True,'status':new_status})

@app.route('/api/orders/generate-list/<qid>')
@login_required
def api_orders_generate_list(qid):
    """Generate WhatsApp-friendly order text + create pending order_items"""
    quote = sb('GET','mst_quotations',params=f'?id=eq.{qid}&select=*')
    if not quote: return jsonify({'error':'Not found'}),404
    q = quote[0]
    baths = q.get('bathrooms','[]')
    if isinstance(baths,str):
        try: baths=json.loads(baths)
        except: baths=[]

    lines = [f"📋 Order List - {date.today().strftime('%d %b %Y')}", f"Customer: {q.get('customer_name','')}", ""]
    items_to_create = []
    sno = 1
    for b in baths:
        bname = b.get('name','Bathroom')
        for area_key, items in (b.get('areas') or {}).items():
            for it in items:
                code = it.get('code','')
                desc = it.get('description') or it.get('name','')
                qty = it.get('qty',1)
                lines.append(f"{sno}. {code} — {desc} — Qty {qty}")
                lines.append(f"   Customer: {q.get('customer_name','')} — {bname}")
                lines.append("")
                items_to_create.append({
                    'quotation_id': qid, 'customer_name': q.get('customer_name',''),
                    'bathroom_name': bname, 'product_code': code, 'product_description': desc,
                    'qty_ordered': qty, 'status': 'Pending'
                })
                sno += 1

    text = '\n'.join(lines)
    return jsonify({'text': text, 'items': items_to_create})

# ================= FOLLOWUPS =================
@app.route('/api/followups', methods=['GET','POST'])
@login_required
def api_followups():
    if request.method == 'POST':
        data = request.json
        data['assigned_to'] = data.get('assigned_to') or session['user_id']
        data['assigned_name'] = data.get('assigned_name') or session['name']
        data['created_at'] = datetime.now().isoformat()
        result = sb('POST','mst_followups',data)
        return jsonify({'ok':bool(result)})
    today = date.today().isoformat()
    role, uid = session.get('role'), session.get('user_id')
    if role=='admin':
        all_f = sb('GET','mst_followups',params='?status=eq.Pending&select=*&order=followup_date.asc') or []
    else:
        all_f = sb('GET','mst_followups',params=f'?status=eq.Pending&assigned_to=eq.{uid}&select=*&order=followup_date.asc') or []
    overdue=[f for f in all_f if f['followup_date']<today]
    today_f=[f for f in all_f if f['followup_date']==today]
    upcoming=[f for f in all_f if f['followup_date']>today]
    return jsonify({'overdue':overdue,'today':today_f,'upcoming':upcoming})

@app.route('/api/followups/<fid>/done', methods=['POST'])
@login_required
def api_fup_done(fid):
    data=request.json or {}
    sb('PATCH','mst_followups',{'status':'Done','done_notes':data.get('notes',''),'done_at':datetime.now().isoformat()},params=f'?id=eq.{fid}')
    return jsonify({'ok':True})

# ================= LOCAL PRODUCTS =================
@app.route('/api/local-products', methods=['GET','POST'])
@login_required
def api_local_products():
    if request.method=='POST':
        result=sb('POST','mst_local_products',request.json)
        return jsonify({'ok':bool(result)})
    prods=sb('GET','mst_local_products',params='?is_active=eq.true&select=*&order=name.asc') or []
    return jsonify({'products':prods})

# ================= DASHBOARD =================
@app.route('/api/dashboard')
@login_required
def api_dashboard():
    today=date.today().isoformat()
    uid, role = session['user_id'], session['role']
    visitors=sb('GET','mst_visitors',params=f'?visit_date=eq.{today}&select=*&order=check_in.desc') or []
    inside=[v for v in visitors if not v.get('check_out')]
    if role=='admin':
        today_f=sb('GET','mst_followups',params=f'?status=eq.Pending&followup_date=eq.{today}&select=*') or []
        overdue=sb('GET','mst_followups',params=f'?status=eq.Pending&followup_date=lt.{today}&select=*') or []
        recent_q=sb('GET','mst_quotations',params='?select=id,quot_number,customer_name,grand_total,status,assigned_name,created_at&order=created_at.desc&limit=10') or []
    else:
        today_f=sb('GET','mst_followups',params=f'?status=eq.Pending&followup_date=eq.{today}&assigned_to=eq.{uid}&select=*') or []
        overdue=sb('GET','mst_followups',params=f'?status=eq.Pending&followup_date=lt.{today}&assigned_to=eq.{uid}&select=*') or []
        recent_q=sb('GET','mst_quotations',params=f'?assigned_to=eq.{uid}&select=id,quot_number,customer_name,grand_total,status,created_at&order=created_at.desc&limit=10') or []
    pending_orders = sb('GET','mst_order_items',params='?status=neq.Received&select=id') or []
    return jsonify({'visitors':visitors,'inside':inside,'today_followups':today_f,'overdue_followups':overdue,'recent_quotes':recent_q,'today_visitor_count':len(visitors),'inside_count':len(inside),'pending_orders_count':len(pending_orders)})

# ================= USERS / ADMIN =================
@app.route('/api/users/approved')
@login_required
def api_approved_users():
    users=sb('GET','mst_users',params='?status=eq.approved&select=id,name,role') or []
    return jsonify({'users':users})

@app.route('/api/admin/pending-users')
@login_required
def api_pending():
    if session.get('role')!='admin': return jsonify({'error':'Admin only'}),403
    users=sb('GET','mst_users',params='?status=eq.pending&select=*&order=created_at.desc') or []
    return jsonify({'users':users})

@app.route('/api/admin/all-users')
@login_required
def api_all_users():
    if session.get('role')!='admin': return jsonify({'error':'Admin only'}),403
    users=sb('GET','mst_users',params='?select=*&order=created_at.desc') or []
    return jsonify({'users':users})

@app.route('/api/admin/approve-user/<uid>', methods=['POST'])
@login_required
def api_approve(uid):
    if session.get('role')!='admin': return jsonify({'error':'Admin only'}),403
    sb('PATCH','mst_users',{'status':'approved','approved_at':datetime.now().isoformat()},params=f'?id=eq.{uid}')
    return jsonify({'ok':True})

@app.route('/api/admin/reject-user/<uid>', methods=['POST'])
@login_required
def api_reject(uid):
    if session.get('role')!='admin': return jsonify({'error':'Admin only'}),403
    sb('PATCH','mst_users',{'status':'rejected'},params=f'?id=eq.{uid}')
    return jsonify({'ok':True})

@app.route('/api/admin/block-user/<uid>', methods=['POST'])
@login_required
def api_block_user(uid):
    if session.get('role')!='admin': return jsonify({'error':'Admin only'}),403
    sb('PATCH','mst_users',{'status':'inactive'},params=f'?id=eq.{uid}')
    return jsonify({'ok':True})

@app.route('/api/admin/unblock-user/<uid>', methods=['POST'])
@login_required
def api_unblock_user(uid):
    if session.get('role')!='admin': return jsonify({'error':'Admin only'}),403
    sb('PATCH','mst_users',{'status':'approved'},params=f'?id=eq.{uid}')
    return jsonify({'ok':True})

@app.route('/api/admin/delete-user/<uid>', methods=['POST'])
@login_required
def api_delete_user(uid):
    if session.get('role')!='admin': return jsonify({'error':'Admin only'}),403
    sb('DELETE','mst_users',params=f'?id=eq.{uid}')
    return jsonify({'ok':True})

@app.route('/api/admin/all-quotations')
@login_required
def api_admin_all_quotations():
    if session.get('role')!='admin': return jsonify({'error':'Admin only'}),403
    quotes = sb('GET','mst_quotations',params='?select=*&order=created_at.desc&limit=300') or []
    for q in quotes:
        if isinstance(q.get('bathrooms'),str):
            try: q['bathrooms']=json.loads(q['bathrooms'])
            except: q['bathrooms']=[]
    return jsonify({'quotations':quotes})

@app.route('/api/admin/stats')
@login_required
def api_admin_stats():
    if session.get('role')!='admin': return jsonify({'error':'Admin only'}),403
    today=date.today().isoformat()
    all_q=sb('GET','mst_quotations',params='?select=status,grand_total,assigned_name') or []
    all_c=sb('GET','mst_customers',params='?select=id') or []
    today_v=sb('GET','mst_visitors',params=f'?visit_date=eq.{today}&select=id') or []
    pend_f=sb('GET','mst_followups',params='?status=eq.Pending&select=id') or []
    pend_o=sb('GET','mst_order_items',params='?status=neq.Received&select=id') or []
    confirmed=[q for q in all_q if q['status']=='Confirmed']
    total_val=sum(float(q.get('grand_total') or 0) for q in confirmed)
    staff={}
    for q in all_q:
        n=q.get('assigned_name','Unknown')
        if n not in staff: staff[n]={'quotes':0,'confirmed':0,'value':0}
        staff[n]['quotes']+=1
        if q['status']=='Confirmed':
            staff[n]['confirmed']+=1
            staff[n]['value']+=float(q.get('grand_total') or 0)
    return jsonify({'total_quotes':len(all_q),'confirmed_orders':len(confirmed),'total_value':total_val,'total_customers':len(all_c),'today_visitors':len(today_v),'pending_followups':len(pend_f),'pending_orders':len(pend_o),'staff_stats':staff})

@app.route('/api/admin/activity-log')
@login_required
def api_activity():
    if session.get('role')!='admin': return jsonify({'error':'Admin only'}),403
    logs=sb('GET','mst_activity_log',params='?select=*&order=created_at.desc&limit=50') or []
    return jsonify({'logs':logs})

if __name__=='__main__':
    port=int(os.environ.get('PORT',5000))
    app.run(host='0.0.0.0',port=port,debug=False)
