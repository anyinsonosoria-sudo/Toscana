from datetime import datetime, timezone
from extensions import db
from flask_login import UserMixin
import bcrypt

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    full_name = db.Column(db.String(120))
    role = db.Column(db.String(20), nullable=False, default='operator')
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    last_login = db.Column(db.DateTime)
    photo_url = db.Column(db.String(255))
    phone = db.Column(db.String(20))
    
    def check_password(self, password):
        if not self.password_hash:
            return False
        password_bytes = password.encode('utf-8') if isinstance(password, str) else password
        hash_bytes = self.password_hash.encode('utf-8') if isinstance(self.password_hash, str) else self.password_hash
        return bcrypt.checkpw(password_bytes, hash_bytes)
    
    def set_password(self, password):
        password_bytes = password.encode('utf-8') if isinstance(password, str) else password
        salt = bcrypt.gensalt()
        hash_bytes = bcrypt.hashpw(password_bytes, salt)
        self.password_hash = hash_bytes.decode('utf-8')
        
    def is_admin(self):
        return self.role == 'admin'
        
    def is_operator(self):
        return self.role == 'operator'
        
    def is_resident(self):
        return self.role == 'resident'
        
    def get_id(self):
        return str(self.id)
        
    def __repr__(self):
        return f"<User {self.username} ({self.role})>"


class Apartment(db.Model):
    __tablename__ = 'apartments'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    floor = db.Column(db.String(50))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    resident_name = db.Column(db.String(120))
    resident_role = db.Column(db.String(50), default='tenant')
    resident_email = db.Column(db.String(120))
    resident_phone = db.Column(db.String(50))
    payment_terms = db.Column(db.Integer, default=30)
    
    invoices = db.relationship('Invoice', backref='apartment', lazy=True)
    extra_residents = db.relationship('Resident', backref='apartment', lazy=True, cascade="all, delete-orphan")


class Resident(db.Model):
    __tablename__ = 'residents'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    unit_id = db.Column(db.Integer, db.ForeignKey('apartments.id', ondelete='CASCADE'), index=True)
    name = db.Column(db.String(120))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(50))
    role = db.Column(db.String(50))
    role_other = db.Column(db.String(120))
    payment_terms = db.Column(db.Integer, default=30)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Invoice(db.Model):
    __tablename__ = 'invoices'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    unit_id = db.Column(db.Integer, db.ForeignKey('apartments.id', ondelete='SET NULL'))
    description = db.Column(db.Text)
    amount = db.Column(db.Float)
    issued_date = db.Column(db.String(50), default=lambda: datetime.now(timezone.utc).isoformat())
    due_date = db.Column(db.String(50), index=True)
    paid = db.Column(db.Boolean, default=False)
    pending_amount = db.Column(db.Float, default=0.0)
    recurring_sale_id = db.Column(db.Integer)
    notes = db.Column(db.Text)
    
    payments = db.relationship('Payment', backref='invoice', lazy=True, cascade="all, delete-orphan")


class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id', ondelete='CASCADE'))
    amount = db.Column(db.Float)
    paid_date = db.Column(db.String(50), default=lambda: datetime.now(timezone.utc).isoformat())
    method = db.Column(db.String(50))
    notes = db.Column(db.Text)


class ReportedPayment(db.Model):
    """Pagos reportados por los residentes, pendientes de validación por admin."""
    __tablename__ = 'reported_payments'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id', ondelete='CASCADE'))
    resident_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'))
    amount = db.Column(db.Float)
    reference = db.Column(db.String(120))
    date_reported = db.Column(db.String(50), default=lambda: datetime.now(timezone.utc).isoformat())
    status = db.Column(db.String(20), default='pending') # pending, approved, rejected
    
    invoice = db.relationship('Invoice', backref='reported_payments')
    resident = db.relationship('User', backref='reported_payments')


class Supplier(db.Model):
    __tablename__ = 'suppliers'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(120), nullable=False)
    contact = db.Column(db.String(120))
    contact_name = db.Column(db.String(120))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(50))
    address = db.Column(db.Text)
    supplier_type = db.Column(db.String(50), default='general')
    supplier_type_other = db.Column(db.String(50))
    tax_id = db.Column(db.String(50))
    payment_terms = db.Column(db.Integer, default=30)
    created_at = db.Column(db.String(50), default=lambda: datetime.now(timezone.utc).isoformat())
    
    expenses = db.relationship('Expense', backref='supplier', lazy=True)


class Expense(db.Model):
    __tablename__ = 'expenses'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    description = db.Column(db.Text)
    amount = db.Column(db.Float)
    category = db.Column(db.String(100))
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id', ondelete='SET NULL'))
    date = db.Column(db.String(50))
    payment_method = db.Column(db.String(50))
    notes = db.Column(db.Text)
    receipt_path = db.Column(db.String(255))
    created_at = db.Column(db.String(50), default=lambda: datetime.now(timezone.utc).isoformat())


class ProductService(db.Model):
    __tablename__ = 'products_services'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    code = db.Column(db.String(50), unique=True)
    name = db.Column(db.String(120), nullable=False)
    type = db.Column(db.String(20)) # 'product' or 'service'
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False, default=0.0)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.String(50), default=lambda: datetime.now(timezone.utc).isoformat())


class AccountingTransaction(db.Model):
    __tablename__ = 'accounting_transactions'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    type = db.Column(db.String(20)) # 'income', 'expense', 'transfer'
    description = db.Column(db.Text)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(100))
    reference = db.Column(db.String(100))
    date = db.Column(db.String(50))
    notes = db.Column(db.Text)
    created_at = db.Column(db.String(50), default=lambda: datetime.now(timezone.utc).isoformat())


class RecurringSale(db.Model):
    __tablename__ = 'recurring_sales'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    unit_id = db.Column(db.Integer, db.ForeignKey('apartments.id', ondelete='CASCADE'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('products_services.id'))
    amount = db.Column(db.Float, nullable=False)
    frequency = db.Column(db.String(50), nullable=False)
    billing_day = db.Column(db.Integer, default=1)
    billing_time = db.Column(db.String(10), default='08:00')
    start_date = db.Column(db.String(50), nullable=False)
    end_date = db.Column(db.String(50))
    description = db.Column(db.Text)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.String(50), default=lambda: datetime.now(timezone.utc).isoformat())
    
    # rels
    apartment = db.relationship('Apartment', backref='recurring_sales', lazy=True)
    service = db.relationship('ProductService', backref='recurring_sales', lazy=True)
