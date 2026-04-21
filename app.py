from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from datetime import datetime, timedelta
from models import db, User, Client, Deal, TimeEntry, Expense, Invoice, Subscription, CalendarEvent, DocumentTemplate, GeneratedDocument
import hashlib

app = Flask(__name__)
app.config['SECRET_KEY'] = 'crm-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///crm.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ---------- Вспомогательные функции ----------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def create_default_user():
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', password=hash_password('admin123'), name='Administrator', hourly_rate=100)
        db.session.add(admin)
        db.session.commit()
        print('Default user created: admin / admin123')

def create_default_templates():
    templates = [
        ('Договор оказания услуг', 
         'ДОГОВОР № {{ deal.id }}\n\nг. Москва, {{ now }}\n\n{{ client.name }} в лице {{ client.phone }}\n\nПредмет: {{ deal.title }}\nСтоимость: {{ deal.value }} руб.\n\nПодписи: __________________'),
        ('Акт выполненных работ',
         'АКТ № {{ deal.id }}\n\nЗаказчик: {{ client.name }}\nВыполнены работы по сделке: {{ deal.title }}\nНа сумму: {{ deal.value }} руб.\n\nДата: {{ now }}')
    ]
    for name, content in templates:
        if not DocumentTemplate.query.filter_by(name=name).first():
            t = DocumentTemplate(name=name, content=content)
            db.session.add(t)
    db.session.commit()

# ---------- Маршруты аутентификации ----------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = hash_password(request.form['password'])
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            login_user(user)
            return redirect(url_for('index'))
        flash('Неверные имя пользователя или пароль')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ---------- Главная страница (дашборд) ----------
@app.route('/')
@login_required
def index():
    total_deals = Deal.query.count()
    won_deals = Deal.query.filter_by(stage='won').count()
    total_time = db.session.query(db.func.sum(TimeEntry.hours)).scalar() or 0
    total_expenses = db.session.query(db.func.sum(Expense.amount)).scalar() or 0
    total_invoiced = db.session.query(db.func.sum(Invoice.amount)).filter(Invoice.status=='paid').scalar() or 0
    recent_events = CalendarEvent.query.order_by(CalendarEvent.start_time).limit(5).all()
    return render_template('index.html', total_deals=total_deals, won_deals=won_deals,
                           total_time=total_time, total_expenses=total_expenses,
                           total_invoiced=total_invoiced, recent_events=recent_events)

# ---------- Клиенты (с поддержкой телефона) ----------
@app.route('/clients/add', methods=['GET', 'POST'])
@login_required
def add_client():
    if request.method == 'POST':
        client = Client(
            name=request.form['name'],
            phone=request.form['phone'],
            email=request.form['email'],
            address=request.form['address']
        )
        db.session.add(client)
        db.session.commit()
        flash('Клиент добавлен')
        return redirect(url_for('index'))
    return render_template('clients/add_edit.html')

# ---------- Сделки и воронка ----------
@app.route('/deals')
@login_required
def deals_list():
    deals = Deal.query.all()
    return render_template('deals/list.html', deals=deals)

@app.route('/deals/create', methods=['GET', 'POST'])
@login_required
def create_deal():
    clients = Client.query.all()
    if request.method == 'POST':
        deal = Deal(
            title=request.form['title'],
            client_id=request.form['client_id'] or None,
            stage=request.form['stage'],
            value=float(request.form['value']) if request.form['value'] else 0,
            case_number=request.form.get('case_number'),
            description=request.form.get('description')
        )
        db.session.add(deal)
        db.session.commit()
        flash('Сделка создана')
        return redirect(url_for('deals_list'))
    return render_template('deals/create.html', clients=clients)

@app.route('/deals/<int:deal_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_deal(deal_id):
    deal = Deal.query.get_or_404(deal_id)
    clients = Client.query.all()
    if request.method == 'POST':
        deal.title = request.form['title']
        deal.client_id = request.form['client_id'] or None
        deal.stage = request.form['stage']
        deal.value = float(request.form['value']) if request.form['value'] else 0
        deal.case_number = request.form.get('case_number')
        deal.description = request.form.get('description')
        db.session.commit()
        flash('Сделка обновлена')
        return redirect(url_for('deals_list'))
    return render_template('deals/edit.html', deal=deal, clients=clients)

@app.route('/deals/<int:deal_id>')
@login_required
def view_deal(deal_id):
    deal = Deal.query.get_or_404(deal_id)
    time_entries = TimeEntry.query.filter_by(deal_id=deal_id).all()
    expenses = Expense.query.filter_by(deal_id=deal_id).all()
    invoices = Invoice.query.filter_by(deal_id=deal_id).all()
    events = CalendarEvent.query.filter_by(deal_id=deal_id).all()
    total_time_cost = sum(t.hours * (t.user.hour_rate if t.user else 0) for t in time_entries)
    total_expenses_sum = sum(e.amount for e in expenses)
    total_invoiced = sum(i.amount for i in invoices if i.status=='paid')
    profitability = total_invoiced - total_time_cost - total_expenses_sum
    return render_template('deals/view.html', deal=deal, time_entries=time_entries,
                           expenses=expenses, invoices=invoices, events=events,
                           total_time_cost=total_time_cost, total_expenses_sum=total_expenses_sum,
                           profitability=profitability)

# ---------- Учёт времени ----------
@app.route('/deals/<int:deal_id>/add_time', methods=['GET', 'POST'])
@login_required
def add_time_entry(deal_id):
    deal = Deal.query.get_or_404(deal_id)
    if request.method == 'POST':
        entry = TimeEntry(
            user_id=current_user.id,
            deal_id=deal_id,
            hours=float(request.form['hours']),
            description=request.form['description'],
            date=datetime.strptime(request.form['date'], '%Y-%m-%d') if request.form['date'] else datetime.utcnow()
        )
        db.session.add(entry)
        db.session.commit()
        flash('Время добавлено')
        return redirect(url_for('view_deal', deal_id=deal_id))
    return render_template('time_entries/add.html', deal=deal)

# ---------- Расходы ----------
@app.route('/deals/<int:deal_id>/add_expense', methods=['GET', 'POST'])
@login_required
def add_expense(deal_id):
    if request.method == 'POST':
        expense = Expense(
            deal_id=deal_id,
            amount=float(request.form['amount']),
            category=request.form['category'],
            description=request.form['description'],
            date=datetime.strptime(request.form['date'], '%Y-%m-%d') if request.form['date'] else datetime.utcnow()
        )
        db.session.add(expense)
        db.session.commit()
        flash('Расход добавлен')
        return redirect(url_for('view_deal', deal_id=deal_id))
    return render_template('expenses/add.html', deal_id=deal_id)

# ---------- Биллинг: счета и абонементы ----------
@app.route('/billing/invoices')
@login_required
def invoices_list():
    invoices = Invoice.query.all()
    return render_template('billing/invoices.html', invoices=invoices)

@app.route('/billing/create_invoice', methods=['GET', 'POST'])
@login_required
def create_invoice():
    deals = Deal.query.all()
    clients = Client.query.all()
    if request.method == 'POST':
        inv_type = request.form['type']
        amount = float(request.form['amount']) if request.form['amount'] else 0
        # для почасовой: можно рассчитать автоматически на основе time_entries
        if inv_type == 'hourly' and request.form.get('deal_id'):
            deal = Deal.query.get(int(request.form['deal_id']))
            if deal:
                total_hours = sum(t.hours for t in deal.time_entries)
                hourly_rate = current_user.hourly_rate or 100
                amount = total_hours * hourly_rate
        invoice = Invoice(
            deal_id=request.form['deal_id'] or None,
            client_id=request.form['client_id'] or None,
            type=inv_type,
            amount=amount,
            due_date=datetime.strptime(request.form['due_date'], '%Y-%m-%d') if request.form['due_date'] else None,
            description=request.form['description']
        )
        db.session.add(invoice)
        db.session.commit()
        flash('Счёт создан')
        return redirect(url_for('invoices_list'))
    return render_template('billing/create_invoice.html', deals=deals, clients=clients)

@app.route('/billing/invoice/<int:inv_id>/pay')
@login_required
def pay_invoice(inv_id):
    inv = Invoice.query.get_or_404(inv_id)
    inv.status = 'paid'
    db.session.commit()
    flash('Счёт оплачен')
    return redirect(url_for('invoices_list'))

@app.route('/billing/subscriptions')
@login_required
def subscriptions_list():
    subs = Subscription.query.all()
    return render_template('billing/subscriptions.html', subscriptions=subs)

@app.route('/billing/create_subscription', methods=['POST'])
@login_required
def create_subscription():
    sub = Subscription(
        client_id=request.form['client_id'],
        monthly_fee=float(request.form['monthly_fee']),
        start_date=datetime.strptime(request.form['start_date'], '%Y-%m-%d') if request.form['start_date'] else datetime.utcnow(),
        end_date=datetime.strptime(request.form['end_date'], '%Y-%m-%d') if request.form['end_date'] else None
    )
    db.session.add(sub)
    db.session.commit()
    flash('Абонентское обслуживание добавлено')
    return redirect(url_for('subscriptions_list'))

# ---------- Календарь судебных дел ----------
@app.route('/calendar')
@login_required
def calendar():
    events = CalendarEvent.query.all()
    return render_template('calendar.html', events=events)

@app.route('/api/events')
@login_required
def api_events():
    events = CalendarEvent.query.all()
    event_list = []
    for e in events:
        event_list.append({
            'id': e.id,
            'title': e.title,
            'start': e.start_time.isoformat(),
            'end': e.end_time.isoformat() if e.end_time else None,
            'description': e.description
        })
    return jsonify(event_list)

@app.route('/events/add', methods=['POST'])
@login_required
def add_event():
    event = CalendarEvent(
        title=request.form['title'],
        event_type=request.form['event_type'],
        deal_id=request.form.get('deal_id') or None,
        start_time=datetime.strptime(request.form['start_time'], '%Y-%m-%dT%H:%M'),
        end_time=datetime.strptime(request.form['end_time'], '%Y-%m-%dT%H:%M') if request.form['end_time'] else None,
        location=request.form.get('location'),
        description=request.form.get('description')
    )
    db.session.add(event)
    db.session.commit()
    flash('Событие добавлено')
    return redirect(url_for('calendar'))

# ---------- Документы по шаблонам ----------
@app.route('/documents/templates')
@login_required
def document_templates():
    templates = DocumentTemplate.query.all()
    return render_template('documents/templates.html', templates=templates)

@app.route('/documents/generate/<int:template_id>', methods=['GET', 'POST'])
@login_required
def generate_document(template_id):
    template = DocumentTemplate.query.get_or_404(template_id)
    deals = Deal.query.all()
    if request.method == 'POST':
        deal_id = request.form['deal_id']
        deal = Deal.query.get(deal_id)
        client = deal.client if deal else None
        # Простая замена переменных
        from datetime import datetime
        now = datetime.now().strftime('%Y-%m-%d %H:%M')
        content = template.content
        content = content.replace('{{ deal.id }}', str(deal.id) if deal else '')
        content = content.replace('{{ deal.title }}', deal.title if deal else '')
        content = content.replace('{{ deal.value }}', str(deal.value) if deal else '')
        content = content.replace('{{ client.name }}', client.name if client else '')
        content = content.replace('{{ client.phone }}', client.phone if client else '')
        content = content.replace('{{ now }}', now)
        doc = GeneratedDocument(template_id=template_id, deal_id=deal_id, content=content)
        db.session.add(doc)
        db.session.commit()
        flash('Документ сгенерирован')
        return render_template('documents/generate.html', content=content, template=template)
    return render_template('documents/generate.html', template=template, deals=deals)

# ---------- Запуск приложения ----------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_default_user()
        create_default_templates()
    app.run(host='0.0.0.0', debug=True)