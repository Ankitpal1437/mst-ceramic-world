// MST Ceramic World - Main JS

function toast(msg) {
  const t = document.getElementById('toast');
  if (!t) return;
  t.textContent = msg;
  t.classList.remove('show');
  void t.offsetWidth;
  t.classList.add('show');
  clearTimeout(window._tt);
  window._tt = setTimeout(() => t.classList.remove('show'), 2500);
}

function fmt(n) {
  if (!n || isNaN(n)) return '—';
  return '₹' + parseFloat(n).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2});
}

function fmtShort(n) {
  if (!n || isNaN(n)) return '—';
  const num = parseFloat(n);
  if (num >= 100000) return '₹' + (num/100000).toFixed(1) + 'L';
  if (num >= 1000) return '₹' + (num/1000).toFixed(1) + 'K';
  return '₹' + num.toFixed(0);
}

function initials(name) {
  if (!name) return '?';
  return name.trim().split(' ').slice(0,2).map(w => w[0]).join('').toUpperCase();
}

function statusBadge(status) {
  const map = {
    'Draft': 'badge-muted', 'Sent': 'badge-blue', 'Negotiating': 'badge-brass',
    'Confirmed': 'badge-green', 'Partial Delivery': 'badge-brass',
    'Delivered': 'badge-green', 'Cancelled': 'badge-red', 'Lost': 'badge-red'
  };
  return `<span class="badge ${map[status]||'badge-muted'}">${status}</span>`;
}

async function api(method, url, data) {
  const opts = {method, headers: {'Content-Type': 'application/json'}};
  if (data) opts.body = JSON.stringify(data);
  const res = await fetch(url, opts);
  return res.json();
}

function showModal(id) { document.getElementById(id).classList.add('open'); }
function hideModal(id) { document.getElementById(id).classList.remove('open'); }

// Nav
function goPage(page) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const pg = document.getElementById('page-' + page);
  if (pg) pg.classList.add('active');
  const nav = document.getElementById('nav-' + page);
  if (nav) nav.classList.add('active');
  if (typeof window['load_' + page] === 'function') window['load_' + page]();
}
