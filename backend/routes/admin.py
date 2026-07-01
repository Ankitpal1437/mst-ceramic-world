from flask import Blueprint, request, jsonify, session
from models import db, User, Customer, Quotation, Visit, FollowUp, ActivityLog
from routes.auth import login_required
from functools import wraps
from datetime import datetime

admin_bp = Blueprint('admin', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Please login first'}), 401
        user = User.query.get(session['user_id'])
        if not user or user.role != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function

# ============ USER MANAGEMENT ============

@admin_bp.route('/users/pending', methods=['GET'])
@admin_required
def get_pending_users():
    """Get all users pending approval"""
    users = User.query.filter_by(status='pending').all()
    return jsonify([{
        'id': u.id,
        'name': u.name,
        'mobile': u.mobile,
        'email': u.email,
        'created_at': u.created_at.isoformat() if u.created_at else None
    } for u in users])

@admin_bp.route('/users/<int:user_id>/approve', methods=['POST'])
@admin_required
def approve_user(user_id):
    """Approve a user"""
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    user.status = 'active'
    
    # Log activity
    log = ActivityLog(
        user_id=session['user_id'],
        action='approve_user',
        entity_type='user',
        entity_id=user_id,
        details=f'Approved user: {user.name} ({user.mobile})'
    )
    db.session.add(log)
    db.session.commit()
    
    return jsonify({'message': f'User {user.name} approved successfully'})

@admin_bp.route('/users/<int:user_id>/reject', methods=['POST'])
@admin_required
def reject_user(user_id):
    """Reject a user"""
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    user.status = 'rejected'
    
    log = ActivityLog(
        user_id=session['user_id'],
        action='reject_user',
        entity_type='user',
        entity_id=user_id,
        details=f'Rejected user: {user.name} ({user.mobile})'
    )
    db.session.add(log)
    db.session.commit()
    
    return jsonify({'message': f'User {user.name} rejected'})

@admin_bp.route('/users', methods=['GET'])
@admin_required
def get_all_users():
    """Get all users"""
    users = User.query.all()
    return jsonify([{
        'id': u.id,
        'name': u.name,
        'mobile': u.mobile,
        'email': u.email,
        'role': u.role,
        'status': u.status,
        'created_at': u.created_at.isoformat() if u.created_at else None,
        'last_login': u.last_login.isoformat() if u.last_login else None
    } for u in users])

@admin_bp.route('/users/<int:user_id>/role', methods=['PUT'])
@admin_required
def change_user_role(user_id):
    """Change user role (admin/staff)"""
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    data = request.json
    new_role = data.get('role')
    
    if new_role not in ['admin', 'staff']:
        return jsonify({'error': 'Invalid role'}), 400
    
    old_role = user.role
    user.role = new_role
    
    log = ActivityLog(
        user_id=session['user_id'],
        action='change_role',
        entity_type='user',
        entity_id=user_id,
        details=f'Changed role from {old_role} to {new_role} for {user.name}'
    )
    db.session.add(log)
    db.session.commit()
    
    return jsonify({'message': f'Role updated to {new_role}'})

# ============ CUSTOMER MANAGEMENT ============

@admin_bp.route('/customers', methods=['GET'])
@admin_required
def get_all_customers():
    """Admin sees all customers"""
    customers = Customer.query.order_by(Customer.created_at.desc()).all()
    return jsonify([{
        'id': c.id,
        'name': c.name,
        'mobile': c.mobile,
        'area': c.area,
        'status': c.status,
        'assigned_staff': c.assigned_staff.name if c.assigned_staff else None,
        'assigned_staff_id': c.assigned_staff_id,
        'created_at': c.created_at.isoformat() if c.created_at else None
    } for c in customers])

@admin_bp.route('/customers/<int:customer_id>/assign', methods=['PUT'])
@admin_required
def assign_customer_to_staff(customer_id):
    """Assign customer to a staff member"""
    customer = Customer.query.get(customer_id)
    if not customer:
        return jsonify({'error': 'Customer not found'}), 404
    
    data = request.json
    staff_id = data.get('staff_id')
    
    staff = User.query.get(staff_id)
    if not staff:
        return jsonify({'error': 'Staff not found'}), 404
    
    old_staff = customer.assigned_staff.name if customer.assigned_staff else 'None'
    customer.assigned_staff_id = staff_id
    
    log = ActivityLog(
        user_id=session['user_id'],
        action='reassign_customer',
        entity_type='customer',
        entity_id=customer_id,
        details=f'Reassigned {customer.name} from {old_staff} to {staff.name}'
    )
    db.session.add(log)
    db.session.commit()
    
    return jsonify({'message': f'Customer assigned to {staff.name}'})

# ============ DASHBOARD ============

@admin_bp.route('/dashboard', methods=['GET'])
@login_required
def get_dashboard():
    """Get dashboard statistics"""
    today = datetime.utcnow().date()
    
    # Today's quotations
    today_quotes = Quotation.query.filter(
        db.func.date(Quotation.created_at) == today
    ).count()
    
    # Confirmed orders
    confirmed_orders = Quotation.query.filter_by(status='order_confirmed').count()
    
    # Pending follow-ups
    pending_followups = FollowUp.query.filter(
        FollowUp.status == 'pending',
        FollowUp.scheduled_date <= datetime.utcnow()
    ).count()
    
    # Today's visitors
    today_visitors = Visit.query.filter(
        db.func.date(Visit.check_in) == today
    ).count()
    
    # Recent quotations
    recent_quotations = Quotation.query.order_by(
        Quotation.created_at.desc()
    ).limit(5).all()
    
    return jsonify({
        'stats': {
            'todayQuotes': today_quotes,
            'confirmedOrders': confirmed_orders,
            'pendingFollowUps': pending_followups,
            'visitorsToday': today_visitors
        },
        'recent_quotations': [{
            'id': q.id,
            'quotation_number': q.quotation_number,
            'customer_name': q.customer.name if q.customer else 'Walk-in',
            'grand_total': q.grand_total,
            'status': q.status,
            'created_at': q.created_at.isoformat() if q.created_at else None
        } for q in recent_quotations]
    })

@admin_bp.route('/staff-performance', methods=['GET'])
@admin_required
def get_staff_performance():
    """Get performance data for all staff"""
    staff_members = User.query.filter_by(role='staff').all()
    performance = []
    
    for staff in staff_members:
        total_quotes = Quotation.query.filter_by(created_by_id=staff.id).count()
        confirmed = Quotation.query.filter_by(
            created_by_id=staff.id, 
            status='order_confirmed'
        ).count()
        
        total_value = db.session.query(
            db.func.sum(Quotation.grand_total)
        ).filter_by(
            created_by_id=staff.id,
            status='order_confirmed'
        ).scalar() or 0
        
        conversion = round((confirmed / total_quotes * 100), 1) if total_quotes > 0 else 0
        
        performance.append({
            'id': staff.id,
            'name': staff.name,
            'total_quotations': total_quotes,
            'confirmed_orders': confirmed,
            'total_value': total_value,
            'conversion_rate': conversion
        })
    
    return jsonify(performance)

# ============ ACTIVITY LOG ============

@admin_bp.route('/activity-log', methods=['GET'])
@admin_required
def get_activity_log():
    """Get recent activity logs"""
    logs = ActivityLog.query.order_by(
        ActivityLog.timestamp.desc()
    ).limit(50).all()
    
    return jsonify([{
        'id': log.id,
        'user': log.user.name if log.user else 'System',
        'action': log.action,
        'entity_type': log.entity_type,
        'entity_id': log.entity_id,
        'details': log.details,
        'timestamp': log.timestamp.isoformat() if log.timestamp else None
    } for log in logs])
