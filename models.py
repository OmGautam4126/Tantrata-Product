from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    description = db.Column(db.String(255))
    unit_price = db.Column(db.Float)
    quantity = db.Column(db.Integer)

    # 👇 If a product is deleted, its sale_items will also be deleted
    sale_items = db.relationship('SaleItem', backref='product', cascade='all, delete')

class Batch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    quantity = db.Column(db.Integer)
    date_added = db.Column(db.DateTime, default=datetime.utcnow)

    product = db.relationship('Product')

class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    total_amount = db.Column(db.Float)
    tax = db.Column(db.Float)
    discount = db.Column(db.Float)
    final_amount = db.Column(db.Float)

    items = db.relationship('SaleItem', backref='sale', cascade='all, delete')

class SaleItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sale.id'))
    
    # 👇 Enable cascade delete on foreign key
    product_id = db.Column(db.Integer, db.ForeignKey('product.id', ondelete='CASCADE'))
    
    quantity = db.Column(db.Integer)
    price_per_unit = db.Column(db.Float)

    # Note: backref is already handled from Product

