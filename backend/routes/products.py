from flask import Blueprint, request, jsonify
from models import Product
from sqlalchemy import or_

products_bp = Blueprint('products', __name__)

@products_bp.route('/search', methods=['GET'])
def search_products():
    query = request.args.get('q', '')
    
    if len(query) < 2:
        return jsonify([])
    
    query_norm = query.lower().replace('-', '').replace(' ', '')
    
    # Search with priority
    results = Product.query.filter(
        or_(
            Product.code_norm == query_norm,
            Product.code_norm.endswith(query_norm),
            Product.code_norm.startswith(query_norm),
            Product.code_norm.contains(query_norm),
            Product.desc_norm.contains(query_norm)
        )
    ).limit(20).all()
    
    return jsonify([{
        'id': p.id,
        'code': p.code,
        'description': p.description,
        'ewp': p.ewp,
        'mdp': p.mdp,
        'sdp': p.sdp,
        'npp': p.npp,
        'nrp': p.nrp,
        'mrp': p.mrp,
        'old_nrp': p.old_nrp,
        'old_mrp': p.old_mrp,
        'source': p.source
    } for p in results])

@products_bp.route('/<code>', methods=['GET'])
def get_product(code):
    product = Product.query.filter_by(code=code).first()
    if not product:
        return jsonify({'error': 'Product not found'}), 404
    
    return jsonify({
        'code': product.code,
        'description': product.description,
        'sdp': product.sdp,
        'nrp': product.nrp,
        'mrp': product.mrp,
        'source': product.source
    })
