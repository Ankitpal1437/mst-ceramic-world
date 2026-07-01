from flask import Flask
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from models import db
from datetime import timedelta
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'mst-ceramic-world-secret-key-2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mst_ceramic.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

CORS(app, supports_credentials=True)
db.init_app(app)
bcrypt = Bcrypt(app)

# Import routes
from routes.auth import auth_bp
from routes.products import products_bp
from routes.admin import admin_bp

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(products_bp, url_prefix='/api/products')
app.register_blueprint(admin_bp, url_prefix='/api/admin')

@app.route('/')
def home():
    return {'message': 'MST Ceramic World API is running!', 'status': 'ok'}

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)
