from flask import Blueprint, request, jsonify, session
from models import db, User
from app import bcrypt
from functools import wraps

auth_bp = Blueprint('auth', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Please login first'}), 401
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.json
    mobile = data.get('mobile')
    name = data.get('name')
    password = data.get('password')
    
    if not mobile or not name:
        return jsonify({'error': 'Name and mobile are required'}), 400
    
    if User.query.filter_by(mobile=mobile).first():
        return jsonify({'error': 'Mobile number already registered'}), 400
    
    user = User(
        name=name,
        mobile=mobile,
        role='staff',
        status='pending'
    )
    
    if password:
        user.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    
    db.session.add(user)
    db.session.commit()
    
    return jsonify({
        'message': 'Registration successful. Pending approval. Contact Ankit.'
    }), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.json
    mobile = data.get('mobile')
    password = data.get('password')
    
    user = User.query.filter_by(mobile=mobile).first()
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    if user.status == 'pending':
        return jsonify({'error': 'Account pending approval'}), 403
    
    if password:
        if not bcrypt.check_password_hash(user.password_hash, password):
            return jsonify({'error': 'Invalid password'}), 401
    
    session['user_id'] = user.id
    session['user_role'] = user.role
    session.permanent = True
    
    return jsonify({
        'message': 'Login successful',
        'user': {
            'id': user.id,
            'name': user.name,
            'role': user.role
        }
    })

@auth_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logged out'})

@auth_bp.route('/me', methods=['GET'])
@login_required
def get_current_user():
    user = User.query.get(session['user_id'])
    return jsonify({
        'id': user.id,
        'name': user.name,
        'mobile': user.mobile,
        'role': user.role,
        'status': user.status
    })
