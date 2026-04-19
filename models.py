from datetime import datetime

from flask_login import UserMixin

from extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    orders = db.relationship("Order", backref="user", lazy=True, cascade="all, delete-orphan")


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Integer, nullable=False, default=0)
    file_path = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    order_items = db.relationship("OrderItem", backref="product", lazy=True, cascade="all, delete-orphan")


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")
    payment_status = db.Column(db.String(30), nullable=True, default=None)
    payment_provider = db.Column(db.String(30), nullable=True, default=None)
    merchant_trade_no = db.Column(db.String(30), nullable=True, unique=True, index=True)
    gateway_trade_no = db.Column(db.String(30), nullable=True, index=True)
    paid_at = db.Column(db.DateTime, nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    payment_raw_payload = db.Column(db.Text, nullable=True)
    buyer_name = db.Column(db.String(120), nullable=False, default="")
    buyer_phone = db.Column(db.String(40), nullable=False, default="")
    buyer_email = db.Column(db.String(255), nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    items = db.relationship("OrderItem", backref="order", lazy=True, cascade="all, delete-orphan")


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Integer, nullable=False, default=0)


class SiteStat(db.Model):
    __tablename__ = "site_stats"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False, index=True)
    value = db.Column(db.Integer, nullable=False, default=0)
