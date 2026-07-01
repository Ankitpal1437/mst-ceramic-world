from __future__ import annotations
import csv, os, sqlite3, secrets, hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv('DATA_DIR', ROOT / 'data'))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / 'mst.db'
PRODUCT_CSV = Path(os.getenv('PRODUCT_CSV', DATA_DIR / 'products.csv'))
SESSION_DAYS = 30

app = FastAPI(title='MST Ceramic World API')
app.add_middleware(CORSMiddleware, allow_origins=os.getenv('CORS_ORIGINS','http://localhost:5173').split(','), allow_credentials=True, allow_methods=['*'], allow_headers=['*'])

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def norm(v): return (v or '').strip().lower()
def money(v):
    try: return float(str(v or 0).replace(',',''))
    except Exception: return 0.0

def hash_pw(pw, salt=None):
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac('sha256', pw.encode(), salt.encode(), 120000).hex()
    return f'{salt}${h}'
def verify_pw(pw, stored):
    try:
        salt, h = stored.split('$',1)
        return hash_pw(pw, salt).split('$',1)[1] == h
    except Exception: return False

def init_db():
    con=db(); cur=con.cursor()
    cur.executescript('''
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE, mobile TEXT UNIQUE, password_hash TEXT, role TEXT DEFAULT 'staff', status TEXT DEFAULT 'pending', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id INTEGER, expires_at TEXT);
    CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY, code TEXT, description TEXT, ewp REAL, mdp REAL, sdp REAL, npp REAL, nrp REAL, mrp REAL, old_nrp REAL, old_mrp REAL, source TEXT, code_norm TEXT, desc_norm TEXT);
    CREATE INDEX IF NOT EXISTS idx_products_code_norm ON products(code_norm);
    CREATE INDEX IF NOT EXISTS idx_products_desc_norm ON products(desc_norm);
    CREATE TABLE IF NOT EXISTS customers(id INTEGER PRIMARY KEY, name TEXT NOT NULL, mobile TEXT UNIQUE, alt_phone TEXT, address TEXT, site_name TEXT, architect_name TEXT, referred_by TEXT, budget_range TEXT, assigned_staff_id INTEGER, notes TEXT, status TEXT DEFAULT 'New Inquiry', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS visitors(id INTEGER PRIMARY KEY, name TEXT, phone TEXT, purpose TEXT, visitor_type TEXT, check_in TEXT DEFAULT CURRENT_TIMESTAMP, check_out TEXT, remarks TEXT);
    CREATE TABLE IF NOT EXISTS local_products(id INTEGER PRIMARY KEY, name TEXT NOT NULL, description TEXT, code TEXT, unit_price REAL NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS quotations(id INTEGER PRIMARY KEY, quotation_no TEXT UNIQUE, customer_id INTEGER, customer_name TEXT, customer_mobile TEXT, staff_id INTEGER, pricing_mode TEXT NOT NULL, discount_percent REAL DEFAULT 0, show_discount INTEGER DEFAULT 0, show_gst INTEGER DEFAULT 0, include_images INTEGER DEFAULT 0, status TEXT DEFAULT 'Draft', subtotal REAL DEFAULT 0, discount_amount REAL DEFAULT 0, gst_amount REAL DEFAULT 0, final_total REAL DEFAULT 0, payload TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS quotation_history(id INTEGER PRIMARY KEY, quotation_id INTEGER, user_id INTEGER, action TEXT, reason TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS followups(id INTEGER PRIMARY KEY, customer_id INTEGER, assigned_staff_id INTEGER, due_at TEXT, followup_type TEXT, notes TEXT, status TEXT DEFAULT 'Upcoming', completed_at TEXT);
    CREATE TABLE IF NOT EXISTS activity_log(id INTEGER PRIMARY KEY, user_id INTEGER, action TEXT, entity TEXT, entity_id INTEGER, details TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    ''')
    cur.execute("SELECT COUNT(*) c FROM users")
    if cur.fetchone()['c']==0:
        cur.execute("INSERT INTO users(name,email,mobile,password_hash,role,status) VALUES(?,?,?,?,?,?)",('Ankit','ankit@mst.local','9999999999',hash_pw('admin123'),'admin','approved'))
    cur.execute("SELECT COUNT(*) c FROM local_products")
    if cur.fetchone()['c']==0:
        for n,p in [('Allen Key Set',150),('Rack Bolt (per piece)',25),('Chair Bracket (pair)',200),('CP Nippal (per piece)',35),('Tile Insert',180),('Waste Coupling (Surya)',450),('PVC Pipe (per foot)',45),('Teflon Tape (roll)',15)]:
            cur.execute('INSERT INTO local_products(name,description,unit_price) VALUES(?,?,?)',(n,n,p))
    con.commit(); con.close()

def import_products_if_needed():
    con=db(); cur=con.cursor(); cur.execute('SELECT COUNT(*) c FROM products')
    if cur.fetchone()['c'] or not PRODUCT_CSV.exists(): con.close(); return
    with PRODUCT_CSV.open(newline='', encoding='utf-8-sig') as f:
        rows=[]
        for r in csv.DictReader(f):
            rows.append((r.get('CODE'),r.get('DESCRIPTION'),money(r.get('EWP')),money(r.get('MDP')),money(r.get('SDP')),money(r.get('NPP')),money(r.get('NRP')),money(r.get('MRP')),money(r.get('OLD_NRP')),money(r.get('OLD_MRP')),r.get('SOURCE'),norm(r.get('CODE')),norm(r.get('DESCRIPTION'))))
            if len(rows)>=1000:
                cur.executemany('INSERT INTO products(code,description,ewp,mdp,sdp,npp,nrp,mrp,old_nrp,old_mrp,source,code_norm,desc_norm) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)', rows); rows=[]
        if rows: cur.executemany('INSERT INTO products(code,description,ewp,mdp,sdp,npp,nrp,mrp,old_nrp,old_mrp,source,code_norm,desc_norm) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)', rows)
    con.commit(); con.close()

@app.on_event('startup')
def startup(): init_db(); import_products_if_needed()

def current_user(req:Request):
    token=req.cookies.get('mst_session') or req.headers.get('X-Session-Token')
    if not token: raise HTTPException(401,'Login required')
    con=db(); row=con.execute("SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires_at>?",(token,datetime.utcnow().isoformat())).fetchone(); con.close()
    if not row: raise HTTPException(401,'Invalid session')
    return dict(row)

def admin(u=Depends(current_user)):
    if u['role']!='admin': raise HTTPException(403,'Admin only')
    return u

class Register(BaseModel): name:str; email:Optional[str]=None; mobile:Optional[str]=None; password:str
class Login(BaseModel): identifier:str; password:str; remember:bool=True
@app.post('/api/auth/register')
def register(x:Register):
    if not x.email and not x.mobile: raise HTTPException(400,'Email or mobile required')
    con=db()
    try: con.execute('INSERT INTO users(name,email,mobile,password_hash) VALUES(?,?,?,?)',(x.name,x.email,x.mobile,hash_pw(x.password))); con.commit()
    except sqlite3.IntegrityError: raise HTTPException(409,'User already exists')
    finally: con.close()
    return {'message':'Your account is pending approval. Please contact Ankit.'}
@app.post('/api/auth/login')
def login(x:Login, resp:Response):
    con=db(); row=con.execute('SELECT * FROM users WHERE email=? OR mobile=?',(x.identifier,x.identifier)).fetchone()
    if not row or not verify_pw(x.password,row['password_hash'] or ''): raise HTTPException(401,'Invalid credentials')
    if row['status']!='approved': raise HTTPException(403,'Your account is pending approval. Please contact Ankit.')
    token=secrets.token_urlsafe(32); exp=datetime.utcnow()+timedelta(days=SESSION_DAYS if x.remember else 1)
    con.execute('INSERT INTO sessions(token,user_id,expires_at) VALUES(?,?,?)',(token,row['id'],exp.isoformat())); con.commit(); con.close()
    resp.set_cookie('mst_session',token,max_age=int((exp-datetime.utcnow()).total_seconds()),httponly=True,samesite='lax')
    return {'token':token,'user':dict(row)}
@app.get('/api/me')
def me(u=Depends(current_user)): return u

@app.get('/api/products/search')
def search_products(q:str='', limit:int=30, u=Depends(current_user)):
    qn=norm(q)
    if len(qn)<2: return {'results':[], 'count':0}
    like=f'%{qn}%'; starts=f'{qn}%'; ends=f'%{qn}'
    sql='''SELECT *, CASE WHEN code_norm=? THEN 1 WHEN code_norm LIKE ? THEN 2 WHEN code_norm LIKE ? THEN 3 WHEN code_norm LIKE ? THEN 4 WHEN desc_norm LIKE ? THEN 5 ELSE 9 END priority FROM products WHERE code_norm LIKE ? OR desc_norm LIKE ? ORDER BY priority, code_norm LIMIT ?'''
    con=db(); rows=[dict(r) for r in con.execute(sql,(qn,ends,starts,like,like,like,like,limit)).fetchall()]; con.close()
    return {'results':rows,'count':len(rows),'priority':'Exact code > code ends > code starts > code contains > description contains'}

@app.get('/api/local-products')
def local_products(u=Depends(current_user)):
    con=db(); rows=[dict(r) for r in con.execute('SELECT * FROM local_products ORDER BY name').fetchall()]; con.close(); return rows
@app.post('/api/customers')
def save_customer(x:dict,u=Depends(current_user)):
    con=db(); staff=x.get('assigned_staff_id') or u['id']
    cur=con.execute('INSERT INTO customers(name,mobile,alt_phone,address,site_name,architect_name,referred_by,budget_range,assigned_staff_id,notes,status) VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(mobile) DO UPDATE SET name=excluded.name, alt_phone=excluded.alt_phone, address=excluded.address, site_name=excluded.site_name, architect_name=excluded.architect_name, referred_by=excluded.referred_by, budget_range=excluded.budget_range, assigned_staff_id=excluded.assigned_staff_id, notes=excluded.notes, status=excluded.status RETURNING id',(x.get('name'),x.get('mobile'),x.get('alt_phone'),x.get('address'),x.get('site_name'),x.get('architect_name'),x.get('referred_by'),x.get('budget_range'),staff,x.get('notes'),x.get('status','New Inquiry')))
    con.commit(); out={'id':cur.fetchone()['id']}; con.close(); return out
@app.get('/api/customers')
def customers(q:str='',u=Depends(current_user)):
    con=db(); params=[]; where=[]
    if u['role']!='admin': where.append('assigned_staff_id=?'); params.append(u['id'])
    if q: where.append('(name LIKE ? OR mobile LIKE ?)'); params += [f'%{q}%',f'%{q}%']
    rows=[dict(r) for r in con.execute('SELECT * FROM customers '+('WHERE '+ ' AND '.join(where) if where else '')+' ORDER BY created_at DESC',params).fetchall()]; con.close(); return rows
@app.post('/api/visitors')
def visitor(x:dict,u=Depends(current_user)):
    con=db(); cur=con.execute('INSERT INTO visitors(name,phone,purpose,visitor_type,remarks) VALUES(?,?,?,?,?)',(x.get('name'),x.get('phone'),x.get('purpose'),x.get('visitor_type'),x.get('remarks'))); con.commit(); id=cur.lastrowid; con.close(); return {'id':id}
@app.get('/api/dashboard')
def dashboard(u=Depends(current_user)):
    con=db(); today=datetime.utcnow().date().isoformat();
    data={'quotations_today':con.execute('SELECT COUNT(*) c FROM quotations WHERE date(created_at)=?',(today,)).fetchone()['c'],'visitors_today':con.execute('SELECT COUNT(*) c FROM visitors WHERE date(check_in)=?',(today,)).fetchone()['c'],'confirmed_value':con.execute("SELECT COALESCE(SUM(final_total),0) s FROM quotations WHERE status LIKE '%Confirmed%'").fetchone()['s'],'pending_followups':con.execute("SELECT COUNT(*) c FROM followups WHERE status!='Completed'").fetchone()['c']}
    con.close(); return data

def next_no(con):
    y=datetime.utcnow().year; prefix=f'MST-{y}-'; row=con.execute('SELECT quotation_no FROM quotations WHERE quotation_no LIKE ? ORDER BY quotation_no DESC LIMIT 1',(prefix+'%',)).fetchone(); n=int(row['quotation_no'].split('-')[-1])+1 if row else 1; return f'{prefix}{n:04d}'
@app.post('/api/quotations')
def quote(x:dict,u=Depends(current_user)):
    con=db(); qno=x.get('quotation_no') or next_no(con); import json
    cur=con.execute('INSERT INTO quotations(quotation_no,customer_id,customer_name,customer_mobile,staff_id,pricing_mode,discount_percent,show_discount,show_gst,include_images,subtotal,discount_amount,gst_amount,final_total,payload) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(qno,x.get('customer_id'),x.get('customer_name'),x.get('customer_mobile'),x.get('staff_id') or u['id'],x.get('pricing_mode'),x.get('discount_percent',0),int(x.get('show_discount',0)),int(x.get('show_gst',0)),int(x.get('include_images',0)),x.get('subtotal',0),x.get('discount_amount',0),x.get('gst_amount',0),x.get('final_total',0),json.dumps(x)))
    con.commit(); id=cur.lastrowid; con.close(); return {'id':id,'quotation_no':qno}
@app.get('/api/quotations')
def quotations(u=Depends(current_user)):
    con=db(); rows=[dict(r) for r in con.execute('SELECT * FROM quotations ORDER BY created_at DESC').fetchall()]; con.close(); return rows
@app.get('/api/quotations/{qid}/print', response_class=HTMLResponse)
def print_quote(qid:int,u=Depends(current_user)):
    import json
    con=db(); r=con.execute('SELECT * FROM quotations WHERE id=?',(qid,)).fetchone(); con.close()
    if not r: raise HTTPException(404,'Not found')
    data=json.loads(r['payload']); rows=''; sn=1
    for b in data.get('bathrooms',[]):
        rows += f"<tr class='bath'><td colspan='7'>{b.get('name','BATHROOM').upper()}</td></tr>"
        for area in b.get('areas',[]):
            if not area.get('items'): continue
            rows += f"<tr class='area'><td colspan='7'>{area.get('name','AREA').upper()}</td></tr>"
            for it in area.get('items',[]):
                img=f"<img src='{it.get('image_url','')}'/>" if data.get('include_images') and it.get('image_url') else ''
                rows += f"<tr><td>{sn}</td><td>{it.get('description') or it.get('name')}</td><td>{it.get('code','')}</td><td>{img}</td><td>{it.get('qty')}</td><td>₹{it.get('rate',0):,.0f}</td><td>₹{it.get('total',0):,.0f}</td></tr>"; sn+=1
        rows += f"<tr class='sub'><td colspan='6'>TOTAL -</td><td>₹{b.get('total',0):,.0f}</td></tr><tr class='spacer'><td colspan='7'></td></tr>"
    disc = f"<div>DISCOUNT - ₹{r['discount_amount']:,.0f}</div>" if r['show_discount'] else ''
    gst = f"<div>GST @ 18% - ₹{r['gst_amount']:,.0f}</div>" if r['show_gst'] else ''
    return f"""<html><head><title>{r['quotation_no']}</title><style>body{{font-family:Arial;margin:24px;color:#15171c}}.head{{display:flex;justify-content:space-between;align-items:center}}.co h1{{color:#c0392b;margin:0}}.logo{{width:130px;height:85px;border:2px solid #b8762f;display:grid;place-items:center;font-weight:bold}}h2{{text-align:center;text-decoration:underline}}table{{width:100%;border-collapse:collapse}}td,th{{border:1px solid #999;padding:7px;font-size:12px}}th{{background:#eee}}.bath td{{background:#15171c;color:white;text-align:center;font-weight:bold}}.area td{{background:#eee;border-left:5px solid #b8762f;font-weight:bold}}.sub td{{font-weight:bold;text-align:right}}.spacer td{{height:10px;border:0}}img{{max-width:70px;max-height:55px}}.totals{{float:right;width:310px;font-weight:bold;text-align:right}}.final{{background:#15171c;color:#d8a657;padding:10px}}.foot{{display:flex;gap:30px;margin-top:40px}}@media print{{button{{display:none}}}}</style></head><body><button onclick='print()'>Print / Save PDF</button><div class='head'><div class='co'><h1>MST CERAMIC WORLD</h1><div>Lalji Arcade, Opp Saibaba Temple, Santoshi Mata Road, Kalyan-West</div><div>Tel: 0251-2208090 | mstceramics@gmail.com | GST: 27AABFM8508N1ZV</div></div><div class='logo'>MST LOGO</div></div><h2>QUOTATION</h2><div style='display:flex;justify-content:space-between'><b>TO,<br>{(r['customer_name'] or 'WALK-IN').upper()}<br>MOB - {r['customer_mobile'] or ''}</b><b>DATE - {datetime.fromisoformat(r['created_at']).strftime('%d/%m/%Y')}<br>Quot. No: {r['quotation_no']}</b></div><table><tr><th>S.no</th><th>Description</th><th>Product Code</th><th>Product Image</th><th>Qty</th><th>Rate</th><th>Total Amt.</th></tr>{rows}</table><div class='totals'><div>GRAND TOTAL - ₹{r['subtotal']:,.0f}</div>{disc}{gst}<div class='final'>FINAL - ₹{r['final_total']:,.0f}</div></div><div style='clear:both'></div><h3>TERMS & CONDITION:</h3><ol><li>TRANPORTATION CHARGES WILL BE EXTRA</li><li>ONCE ORDER PLACED CAN NOT MODIFIED OR CHANGE</li><li>MATERIAL MUST CHECK BY PERSON AVAILABLE AT SITE AFTER THAT, RESPONSIBILITY OF THEM</li><li>DELIVERY AT GROUND LEVEL & UNLOADING IN CUSTOMERS SCOPE</li><li>ABOVE QUOTATION IS VALID TILL 15 DAYS</li><li>GST IS INCLUDED IN THE PRICE OF ALL PRODUCTS</li></ol><div class='foot'><div>Thanks & Regards,<br>Yours Sincerely,<br><b>FOR MST CERAMIC WORLD</b><br><br>Stamp Image<br>GST NO. 27AABFM8508N1ZV</div><div><b>BANK DETAILS:</b><br>Bank of Baroda<br>A/C: 99140400000293<br>IFSC: BARB0DBKYAN (FIFTH CHARACTER ZERO)<br>Branch: Shivaji Chowk-Kalyan West</div></div></body></html>"""
