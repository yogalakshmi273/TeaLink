from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'admin', 'student'
    
    # Student specific fields
    name = db.Column(db.String(100), nullable=True)
    department = db.Column(db.String(100), nullable=True)
    year = db.Column(db.String(50), nullable=True)
    selfie_path = db.Column(db.String(256), nullable=True)
    status = db.Column(db.String(20), default='approved')  # 'pending', 'approved', 'rejected'
    
    # Relationships
    orders = db.relationship('Order', backref='student', lazy=True, cascade="all, delete-orphan")
    cart_items = db.relationship('CartItem', backref='user', lazy=True, cascade="all, delete-orphan")
    password_requests = db.relationship('PasswordResetRequest', backref='user', lazy=True, cascade="all, delete-orphan")
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def can_change_password(self):
        if self.role == 'admin':
            return True
        if not self.department or not self.year:
            return True
        policy = DeptYearPolicy.query.filter_by(
            department=self.department,
            year=self.year
        ).first()
        if policy:
            return policy.allow_password_change
        return True

class DeptYearPolicy(db.Model):
    __tablename__ = 'dept_year_policies'
    
    id = db.Column(db.Integer, primary_key=True)
    department = db.Column(db.String(100), nullable=False)
    year = db.Column(db.String(50), nullable=False)
    allow_password_change = db.Column(db.Boolean, default=True, nullable=False)
    notes = db.Column(db.String(255), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PasswordResetRequest(db.Model):
    __tablename__ = 'password_reset_requests'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    student_name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(80), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    year = db.Column(db.String(50), nullable=False)
    requested_password_hash = db.Column(db.String(256), nullable=False)
    reason = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), default='pending')  # 'pending', 'approved', 'rejected'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Product(db.Model):
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)  # 'HOT DRINKS', 'COLD DRINKS', 'SNACKS', 'BAKERY', 'COMBOS'
    description = db.Column(db.String(255), nullable=True)
    image_path = db.Column(db.String(256), nullable=True)
    available = db.Column(db.Boolean, default=True)

class CartItem(db.Model):
    __tablename__ = 'cart_items'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1, nullable=False)
    
    product = db.relationship('Product')

class Order(db.Model):
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(50), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(30), default='Ordered')  # 'Ordered', 'Accepted', 'Preparing', 'Ready', 'Completed'
    payment_status = db.Column(db.String(30), default='Pending')  # 'Pending', 'Paid', 'Failed'
    payment_id = db.Column(db.String(100), nullable=True)
    delivery_time = db.Column(db.String(100), nullable=True)
    student_notes = db.Column(db.Text, nullable=True)
    rejection_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    items = db.relationship('OrderItem', backref='order', lazy=True, cascade="all, delete-orphan")

class OrderItem(db.Model):
    __tablename__ = 'order_items'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    product_name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)

