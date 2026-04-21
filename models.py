from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(100))
    hourly_rate = db.Column(db.Float, default=0.0)

class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    address = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Deal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'))
    stage = db.Column(db.String(50), default='new')  # new, negotiation, proposal, won, lost
    value = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    closed_at = db.Column(db.DateTime)
    client = db.relationship('Client', backref='deals')
    case_number = db.Column(db.String(50))
    description = db.Column(db.Text)

class TimeEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    deal_id = db.Column(db.Integer, db.ForeignKey('deal.id'))
    date = db.Column(db.DateTime, default=datetime.utcnow)
    hours = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)
    user = db.relationship('User', backref='time_entries')
    deal = db.relationship('Deal', backref='time_entries')

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    deal_id = db.Column(db.Integer, db.ForeignKey('deal.id'))
    date = db.Column(db.DateTime, default=datetime.utcnow)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(100))
    description = db.Column(db.Text)
    deal = db.relationship('Deal', backref='expenses')

class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    deal_id = db.Column(db.Integer, db.ForeignKey('deal.id'))
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'))
    type = db.Column(db.String(20))  # hourly, fixed, subscription
    amount = db.Column(db.Float)
    status = db.Column(db.String(20), default='unpaid')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.DateTime)
    description = db.Column(db.Text)
    deal = db.relationship('Deal', backref='invoices')
    client = db.relationship('Client', backref='invoices')

class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'))
    monthly_fee = db.Column(db.Float, nullable=False)
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    end_date = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    client = db.relationship('Client', backref='subscriptions')

class CalendarEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    event_type = db.Column(db.String(50))
    deal_id = db.Column(db.Integer, db.ForeignKey('deal.id'))
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime)
    location = db.Column(db.String(200))
    description = db.Column(db.Text)
    deal = db.relationship('Deal', backref='events')

class DocumentTemplate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class GeneratedDocument(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey('document_template.id'))
    deal_id = db.Column(db.Integer, db.ForeignKey('deal.id'))
    content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    template = db.relationship('DocumentTemplate', backref='generated_docs')
    deal = db.relationship('Deal', backref='generated_docs')