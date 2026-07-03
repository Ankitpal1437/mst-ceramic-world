"""
MST Ceramic World — Complete Business Management System
Flask app with Supabase backend
"""
import os, json, sqlite3, secrets, hashlib
from datetime import datetime, date, timedelta
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, g
import urllib.request, urllib.error

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'mst-ceramic-secret-2026-xk9q')

# ── SUPABASE CONFIG ──────────────────────────────────────────
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://habwesaoixrefalzkubw.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhhYndlc2FvaXhyZWZhbHprdWJ3Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4MjYyODE3NiwiZXhwIjoyMDk4MjA0MTc2fQ.zv0Jex5q263-QZdkKiRpKNLsxDSZttIWlT3njAAKE0c')

def sb(method, table, data=None, params='', returning='representation'):
    """Supabase REST API helper"""
    url = f"{SUPABASE_URL}/rest/v1/{table}{params}"
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json',
        'Prefer': f'return={returning}'
    }
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            raw = res.read()
            return json.loads(raw) if raw else []
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"Supabase error {e.code}: {err}")
        return None
    except Exception as e:
        print(f"Supabase exception: {e}")
        return None

# ── PRODUCTS DB (SQLite - local) ─────────────────────────────
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

# ── AUTH HELPERS ─────────────────────────────────────────────
def hash_password(pwd):
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

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'admin':
            return jsonify({'error': 'Admin only'}), 403
        return f(*args, **kwargs)
    return decorated

# ── PAGES ────────────────────────────────────────────────────
@app.route('/')
def root():
    if session.get('user_id'):
        return redirect(url_for('home'))
    return redirect(url_for('login_page'))

@app.route('/login')
def login_page():
    if session.get('user_id'):
        return redirect(url_for('home'))
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

@app.route('/admin')
@login_required
def admin_page():
    if session.get('role') != 'admin':
        return redirect(url_for('home'))
    return render_template('admin.html', user=session)

@app.route('/logout')
def logout():
    # Delete session from DB
    token = session.get('token')
    if token:
        sb('DELETE', 'mst_sessions', params=f'?token=eq.{token}')
    session.clear()
    return redirect(url_for('login_page'))

# ── AUTH APIs ─────────────────────────────────────────────────
@app.route('/api/auth/register', methods=['POST'])
def api_register():
    data = request.json
    name = data.get('name', '').strip()
    phone = data.get('phone', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()
    if not name or not password:
        return jsonify({'ok': False, 'error': 'Name and password required'})
    if not phone and not email:
        return jsonify({'ok': False, 'error': 'Phone or email required'})

    # Check existing
    if phone:
        existing = sb('GET', 'mst_users', params=f'?phone=eq.{phone}&select=id')
        if existing:
            return jsonify({'ok': False, 'error': 'Phone already registered'})
    if email:
        existing = sb('GET', 'mst_users', params=f'?email=eq.{email}&select=id')
        if existing:
            return jsonify({'ok': False, 'error': 'Email already registered'})

    result = sb('POST', 'mst_users', {
        'name': name, 'phone': phone or None, 'email': email or None,
        'password_hash': hash_password(password),
        'role': 'staff', 'status': 'pending'
    })
    if result:
        # Log activity
        sb('POST', 'mst_activity_log', {'action': 'New Registration', 'module': 'Auth', 'user_name': name, 'details': f'New user {name} registered, awaiting approval'})
        return jsonify({'ok': True, 'message': 'Registration successful! Waiting for admin approval.'})
    return jsonify({'ok': False, 'error': 'Registration failed'})

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.json
    identifier = data.get('identifier', '').strip()
    password = data.get('password', '').strip()
    if not identifier or not password:
        return jsonify({'ok': False, 'error': 'Required fields missing'})

    # Find user by phone or email
    users = sb('GET', 'mst_users', params=f'?or=(phone.eq.{identifier},email.eq.{identifier})&select=*')
    if not users:
        return jsonify({'ok': False, 'error': 'User not found'})

    user = users[0]
    if user['password_hash'] != hash_password(password):
        return jsonify({'ok': False, 'error': 'Wrong password'})
    if user['status'] == 'pending':
        return jsonify({'ok': False, 'error': 'Account pending approval. Contact Ankit.'})
    if user['status'] == 'rejected':
        return jsonify({'ok': False, 'error': 'Account rejected. Contact Ankit.'})
    if user['status'] == 'inactive':
        return jsonify({'ok': False, 'error': 'Account deactivated.'})

    # Create session token
    token = secrets.token_urlsafe(32)
    sb('POST', 'mst_sessions', {'user_id': user['id'], 'token': token})
    sb('PATCH', 'mst_users', {'last_login': datetime.now().isoformat()}, params=f'?id=eq.{user["id"]}') if False else None

    # Set session
    session.permanent = True
    session['user_id'] = user['id']
    session['name'] = user['name']
    session['role'] = user['role']
    session['token'] = token

    # Log
    sb('POST', 'mst_activity_log', {'user_id': user['id'], 'user_name': user['name'], 'action': 'Login', 'module': 'Auth'})
    return jsonify({'ok': True, 'name': user['name'], 'role': user['role']})

# ── ADMIN APIs ────────────────────────────────────────────────
@app.route('/api/admin/pending-users')
@login_required
def api_pending_users():
    if session.get('role') != 'admin':
        return jsonify({'error': 'Admin only'}), 403
    users = sb('GET', 'mst_users', params='?status=eq.pending&select=*&order=created_at.desc') or []
    return jsonify({'users': users})

@app.route('/api/admin/all-users')
@login_required
def api_all_users():
    if session.get('role') != 'admin':
        return jsonify({'error': 'Admin only'}), 403
    users = sb('GET', 'mst_users', params='?select=*&order=created_at.desc') or []
    return jsonify({'users': users})

@app.route('/api/admin/approve-user/<uid>', methods=['POST'])
@login_required
def api_approve_user(uid):
    if session.get('role') != 'admin':
        return jsonify({'error': 'Admin only'}), 403
    sb('PATCH', 'mst_users', {'status': 'approved', 'approved_at': datetime.now().isoformat()}, params=f'?id=eq.{uid}')
    sb('POST', 'mst_activity_log', {'user_id': session['user_id'], 'user_name': session['name'], 'action': 'User Approved', 'module': 'Admin', 'details': f'Approved user {uid}'})
    return jsonify({'ok': True})

@app.route('/api/admin/reject-user/<uid>', methods=['POST'])
@login_required
def api_reject_user(uid):
    if session.get('role') != 'admin':
        return jsonify({'error': 'Admin only'}), 403
    sb('PATCH', 'mst_users', {'status': 'rejected'}, params=f'?id=eq.{uid}')
    return jsonify({'ok': True})

@app.route('/api/admin/stats')
@login_required
def api_admin_stats():
    if session.get('role') != 'admin':
        return jsonify({'error': 'Admin only'}), 403
    today = date.today().isoformat()
    week_ago = (date.today() - timedelta(days=7)).isoformat()
    month_ago = (date.today() - timedelta(days=30)).isoformat()

    all_quotes = sb('GET', 'mst_quotations', params='?select=status,grand_total,assigned_name,created_at') or []
    all_customers = sb('GET', 'mst_customers', params='?select=id') or []
    today_visitors = sb('GET', 'mst_visitors', params=f'?visit_date=eq.{today}&select=id') or []
    pending_fups = sb('GET', 'mst_followups', params=f'?status=eq.Pending&select=id') or []
    overdue_fups = sb('GET', 'mst_followups', params=f'?status=eq.Pending&followup_date=lt.{today}&select=id') or []

    confirmed = [q for q in all_quotes if q['status'] == 'Confirmed']
    total_value = sum(float(q.get('grand_total') or 0) for q in confirmed)

    # Staff performance
    staff_stats = {}
    for q in all_quotes:
        name = q.get('assigned_name', 'Unknown')
        if name not in staff_stats:
            staff_stats[name] = {'quotes': 0, 'confirmed': 0, 'value': 0}
        staff_stats[name]['quotes'] += 1
        if q['status'] == 'Confirmed':
            staff_stats[name]['confirmed'] += 1
            staff_stats[name]['value'] += float(q.get('grand_total') or 0)

    return jsonify({
        'total_quotes': len(all_quotes),
        'confirmed_orders': len(confirmed),
        'total_value': total_value,
        'total_customers': len(all_customers),
        'today_visitors': len(today_visitors),
        'pending_followups': len(pending_fups),
        'overdue_followups': len(overdue_fups),
        'staff_stats': staff_stats,
        'recent_quotes': all_quotes[:5]
    })

@app.route('/api/admin/activity-log')
@login_required
def api_activity_log():
    if session.get('role') != 'admin':
        return jsonify({'error': 'Admin only'}), 403
    logs = sb('GET', 'mst_activity_log', params='?select=*&order=created_at.desc&limit=50') or []
    return jsonify({'logs': logs})

# ── PRODUCT SEARCH API ─────────────────────────────────────────
@app.route('/api/search')
@login_required
def api_search():
    q = request.args.get('q', '').strip().lower()
    if len(q) < 2:
        return jsonify({'results': [], 'count': 0})
    try:
        db = get_pdb()
        exact = db.execute("SELECT * FROM products WHERE code_norm=? LIMIT 20", (q,)).fetchall()
        ends = db.execute("SELECT * FROM products WHERE code_norm LIKE ? AND code_norm!=? LIMIT 20", ('%'+q, q)).fetchall()
        starts = db.execute("SELECT * FROM products WHERE code_norm LIKE ? AND code_norm NOT LIKE ? LIMIT 20", (q+'%', '%'+q)).fetchall()
        contains = db.execute("SELECT * FROM products WHERE code_norm LIKE ? AND code_norm NOT LIKE ? LIMIT 20", ('%'+q+'%', q+'%')).fetchall()
        desc = db.execute("SELECT * FROM products WHERE desc_norm LIKE ? AND code_norm NOT LIKE ? LIMIT 20", ('%'+q+'%', '%'+q+'%')).fetchall()
        seen = set(); merged = []
        for bucket in (exact, ends, starts, contains, desc):
            for row in bucket:
                if row['id'] not in seen:
                    seen.add(row['id']); merged.append(dict(row))
        return jsonify({'results': merged[:30], 'count': len(merged)})
    except Exception as e:
        return jsonify({'results': [], 'count': 0, 'error': str(e)})

@app.route('/api/stats')
@login_required
def api_stats():
    try:
        db = get_pdb()
        total = db.execute("SELECT COUNT(*) c FROM products").fetchone()['c']
        fittings = db.execute("SELECT COUNT(*) c FROM products WHERE source='FITTINGS'").fetchone()['c']
        lighting = db.execute("SELECT COUNT(*) c FROM products WHERE source='LIGHTING'").fetchone()['c']
        return jsonify({'total': total, 'fittings': fittings, 'lighting': lighting})
    except:
        return jsonify({'total': 72171, 'fittings': 59007, 'lighting': 13164})

# ── CUSTOMERS APIs ─────────────────────────────────────────────
@app.route('/api/customers', methods=['GET', 'POST'])
@login_required
def api_customers():
    if request.method == 'POST':
        data = request.json
        data['created_at'] = datetime.now().isoformat()
        result = sb('POST', 'mst_customers', data)
        if result:
            sb('POST', 'mst_activity_log', {'user_id': session['user_id'], 'user_name': session['name'], 'action': 'Customer Created', 'module': 'Customers', 'details': f"Customer: {data.get('name')}"})
            return jsonify({'ok': True, 'id': result[0]['id'] if isinstance(result, list) else result.get('id')})
        return jsonify({'ok': False, 'error': 'Failed to create customer'})

    # GET — filter by role
    role = session.get('role')
    uid = session.get('user_id')
    if role == 'admin':
        customers = sb('GET', 'mst_customers', params='?select=*&order=created_at.desc') or []
    else:
        customers = sb('GET', 'mst_customers', params=f'?assigned_to=eq.{uid}&select=*&order=created_at.desc') or []
    return jsonify({'customers': customers})

@app.route('/api/customers/phone/<phone>')
@login_required
def api_customer_by_phone(phone):
    customers = sb('GET', 'mst_customers', params=f'?phone=eq.{phone}&select=*') or []
    if not customers:
        return jsonify({'found': False})
    c = customers[0]
    # Get their quotations
    quotes = sb('GET', 'mst_quotations', params=f'?customer_id=eq.{c["id"]}&select=quot_number,grand_total,status,created_at&order=created_at.desc') or []
    # Get visits
    visits = sb('GET', 'mst_visitors', params=f'?phone=eq.{phone}&select=*&order=check_in.desc&limit=10') or []
    return jsonify({'found': True, 'customer': c, 'quotations': quotes, 'visits': visits})

@app.route('/api/customers/<cid>', methods=['GET', 'PUT'])
@login_required
def api_customer_detail(cid):
    if request.method == 'PUT':
        data = request.json
        result = sb('PATCH', 'mst_customers', data, params=f'?id=eq.{cid}')
        if result is not None:
            sb('POST', 'mst_activity_log', {'user_id': session['user_id'], 'user_name': session['name'], 'action': 'Customer Updated', 'module': 'Customers', 'details': f'Customer {cid} updated'})
            return jsonify({'ok': True})
        return jsonify({'ok': False})

    customer = sb('GET', 'mst_customers', params=f'?id=eq.{cid}&select=*')
    if not customer:
        return jsonify({'error': 'Not found'}), 404
    quotes = sb('GET', 'mst_quotations', params=f'?customer_id=eq.{cid}&select=*&order=created_at.desc') or []
    visits = sb('GET', 'mst_visitors', params=f'?customer_id=eq.{cid}&select=*&order=check_in.desc&limit=20') or []
    followups = sb('GET', 'mst_followups', params=f'?customer_id=eq.{cid}&select=*&order=followup_date.asc') or []
    return jsonify({'customer': customer[0], 'quotations': quotes, 'visits': visits, 'followups': followups})

@app.route('/api/customers/<cid>/reassign', methods=['POST'])
@login_required
def api_reassign_customer(cid):
    if session.get('role') != 'admin':
        return jsonify({'error': 'Admin only'}), 403
    data = request.json
    result = sb('PATCH', 'mst_customers', {'assigned_to': data['user_id'], 'assigned_name': data['user_name']}, params=f'?id=eq.{cid}')
    if result is not None:
        return jsonify({'ok': True})
    return jsonify({'ok': False})

# ── VISITORS APIs ──────────────────────────────────────────────
@app.route('/api/visitors', methods=['GET', 'POST'])
@login_required
def api_visitors():
    if request.method == 'POST':
        data = request.json
        data['check_in'] = datetime.now().isoformat()
        data['visit_date'] = date.today().isoformat()
        data['handled_by'] = session['user_id']
        data['handled_by_name'] = session['name']
        result = sb('POST', 'mst_visitors', data)
        return jsonify({'ok': bool(result)})

    today = date.today().isoformat()
    visitors = sb('GET', 'mst_visitors', params=f'?visit_date=eq.{today}&select=*&order=check_in.desc') or []
    inside = [v for v in visitors if not v.get('check_out')]
    return jsonify({'visitors': visitors, 'today_count': len(visitors), 'inside_count': len(inside)})

@app.route('/api/visitors/<vid>/checkout', methods=['POST'])
@login_required
def api_checkout(vid):
    data = request.json or {}
    sb('PATCH', 'mst_visitors', {'check_out': datetime.now().isoformat(), 'remarks': data.get('remarks', '')}, params=f'?id=eq.{vid}')
    return jsonify({'ok': True})

# ── QUOTATIONS APIs ────────────────────────────────────────────
@app.route('/api/quotations', methods=['GET', 'POST'])
@login_required
def api_quotations():
    if request.method == 'POST':
        data = request.json
        data['assigned_to'] = data.get('assigned_to') or session['user_id']
        data['assigned_name'] = data.get('assigned_name') or session['name']
        data['created_at'] = datetime.now().isoformat()
        data['valid_until'] = (date.today() + timedelta(days=15)).isoformat()
        if isinstance(data.get('bathrooms'), (list, dict)):
            data['bathrooms'] = json.dumps(data['bathrooms'])
        result = sb('POST', 'mst_quotations', data)
        if result:
            qid = result[0]['id'] if isinstance(result, list) else result.get('id')
            qnum = result[0].get('quot_number', '') if isinstance(result, list) else result.get('quot_number', '')
            sb('POST', 'mst_activity_log', {'user_id': session['user_id'], 'user_name': session['name'], 'action': 'Quotation Created', 'module': 'Quotations', 'details': f'Quote {qnum} for {data.get("customer_name")}'})
            return jsonify({'ok': True, 'id': qid, 'quot_number': qnum})
        return jsonify({'ok': False, 'error': 'Failed'})

    role = session.get('role')
    uid = session.get('user_id')
    if role == 'admin':
        quotes = sb('GET', 'mst_quotations', params='?select=*&order=created_at.desc&limit=100') or []
    else:
        quotes = sb('GET', 'mst_quotations', params=f'?assigned_to=eq.{uid}&select=*&order=created_at.desc&limit=100') or []

    for q in quotes:
        if isinstance(q.get('bathrooms'), str):
            try: q['bathrooms'] = json.loads(q['bathrooms'])
            except: q['bathrooms'] = []
    return jsonify({'quotations': quotes})

@app.route('/api/quotations/<qid>', methods=['GET', 'PUT'])
@login_required
def api_quotation_detail(qid):
    if request.method == 'PUT':
        data = request.json
        reason = data.pop('edit_reason', '')

        # Check if or
