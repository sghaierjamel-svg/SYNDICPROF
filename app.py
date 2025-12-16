
"""
SyndicPro - Application Multi-Tenant de gestion de syndic
Version 3.0.5 - SYSTÈME DE CRÉDIT INTÉGRÉ

NOUVEAUTÉS V3.0.5:
- 💳 Système de crédit résiduel automatique
- ✅ Aucune perte d'argent sur les montants non utilisés
- 🔄 Application automatique du crédit au prochain paiement
- 📊 Affichage du crédit disponible dans l'interface
- 🎯 Transparence totale pour les résidents et admins

CORRECTIONS V3.0.4:
- ✅ Ajout d'un champ "Mois de redevance" pour choisir le mois de départ
- ✅ Mode AUTO : Si non rempli, détection automatique du premier mois impayé
- ✅ Mode MANUEL : Si rempli, commence au mois spécifié par l'admin

TARIFICATION:
- Essai gratuit: 30 jours
- < 20 appartements: 30 DT/mois
- 20-75 appartements: 50 DT/mois  
- > 75 appartements: 75 DT/mois

Super Admin: superadmin@syndicpro.tn / SuperAdmin2024! (à changer)
"""

# ----- Vérification des dépendances -----
missing = []
try:
    import flask
except Exception:
    missing.append('Flask')
try:
    import flask_sqlalchemy
except Exception:
    missing.append('Flask-SQLAlchemy')
try:
    import pandas
except Exception:
    missing.append('pandas')
try:
    import openpyxl
except Exception:
    missing.append('openpyxl')
try:
    import werkzeug
except Exception:
    missing.append('Werkzeug')

if missing:
    msg = ("Dépendances manquantes : " + ", ".join(missing) + ".\n" +
           "Exécutez : pip install -r requirements.txt\n")
    print(msg)
    if __name__ == '__main__':
        import sys
        sys.exit(1)

from flask import Flask, render_template, request, redirect, url_for, session, send_file, jsonify, flash, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
import pandas as pd
import io
import os
import calendar
import secrets

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)

# 🔥 CONFIGURATION POUR RENDER 🔥
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')

# Configuration de la base de données
database_url = os.environ.get('DATABASE_URL')

# Si pas de DATABASE_URL (en local), utiliser SQLite
if not database_url:
    # Créer le dossier database s'il n'existe pas
    database_dir = os.path.join(BASE_DIR, 'database')
    if not os.path.exists(database_dir):
        os.makedirs(database_dir)
    database_url = 'sqlite:///' + os.path.join(database_dir, 'syndicpro.db')

# Si on utilise PostgreSQL sur Render, corriger l'URL
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# -------- Models Multi-Tenant --------

class Organization(db.Model):
    """Organisation = 1 Syndic client"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20))
    address = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    subscription = db.relationship('Subscription', backref='organization', uselist=False, lazy=True)
    users = db.relationship('User', backref='organization', lazy=True)
    blocks = db.relationship('Block', backref='organization', lazy=True, cascade='all, delete-orphan')
    apartments = db.relationship('Apartment', backref='organization', lazy=True, cascade='all, delete-orphan')
    payments = db.relationship('Payment', backref='organization', lazy=True, cascade='all, delete-orphan')
    expenses = db.relationship('Expense', backref='organization', lazy=True, cascade='all, delete-orphan')
    tickets = db.relationship('Ticket', backref='organization', lazy=True, cascade='all, delete-orphan')
    alerts = db.relationship('UnpaidAlert', backref='organization', lazy=True, cascade='all, delete-orphan')

class Subscription(db.Model):
    """Abonnement de l'organisation"""
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    plan = db.Column(db.String(20), default='trial')
    status = db.Column(db.String(20), default='active')
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    end_date = db.Column(db.DateTime)
    monthly_price = db.Column(db.Float, default=0.0)
    max_apartments = db.Column(db.Integer, default=20)
    
    def is_expired(self):
        if not self.end_date:
            return False
        return datetime.utcnow() > self.end_date
    
    def days_remaining(self):
        if not self.end_date:
            return 0
        delta = self.end_date - datetime.utcnow()
        return max(0, delta.days)
    
    def calculate_price(self, apartment_count):
        """Calcule le prix selon le nombre d'appartements"""
        if apartment_count < 20:
            return 30.0
        elif apartment_count <= 75:
            return 50.0
        else:
            return 75.0

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=True)
    email = db.Column(db.String(120), nullable=False)
    name = db.Column(db.String(120))
    password_hash = db.Column(db.String(256))
    role = db.Column(db.String(20))
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartment.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, pwd):
        self.password_hash = generate_password_hash(pwd)

    def check_password(self, pwd):
        return check_password_hash(self.password_hash, pwd)

class Block(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    apartments = db.relationship('Apartment', backref='block', lazy=True)

class Apartment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    number = db.Column(db.String(20), nullable=False)
    block_id = db.Column(db.Integer, db.ForeignKey('block.id'), nullable=False)
    monthly_fee = db.Column(db.Float, default=100.0)
    credit_balance = db.Column(db.Float, default=0.0)  # 🆕 NOUVEAU : Crédit résiduel
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  
    residents = db.relationship('User', backref='apartment', lazy=True)
    payments = db.relationship('Payment', backref='apartment', lazy=True, cascade='all, delete-orphan')
    tickets = db.relationship('Ticket', backref='apartment', lazy=True)

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartment.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    month_paid = db.Column(db.String(7), nullable=False)
    description = db.Column(db.String(200))
    credit_used = db.Column(db.Float, default=0.0)  # 🆕 NOUVEAU : Crédit utilisé pour ce paiement

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    expense_date = db.Column(db.Date, nullable=False)
    category = db.Column(db.String(120))
    description = db.Column(db.String(300))

class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartment.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='ouvert')
    priority = db.Column(db.String(20), default='normale')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    admin_response = db.Column(db.Text)
    user = db.relationship('User', backref='tickets')

class UnpaidAlert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartment.id'), nullable=False)
    months_unpaid = db.Column(db.Integer, nullable=False)
    alert_date = db.Column(db.DateTime, default=datetime.utcnow)
    email_sent = db.Column(db.Boolean, default=False)
    apartment = db.relationship('Apartment', backref='alerts')

# -------- Fonctions utilitaires --------

def init_db():
    """Initialise la base de données multi-tenant"""
    db_dir = os.path.join(BASE_DIR, 'database')
    os.makedirs(db_dir, exist_ok=True)
    db.create_all()
    
    # 🆕 Migration : Ajouter credit_balance si la colonne n'existe pas
    try:
        with db.engine.connect() as conn:
            result = conn.execute(db.text("PRAGMA table_info(apartment)"))
            columns = [row[1] for row in result]
            if 'credit_balance' not in columns:
                conn.execute(db.text("ALTER TABLE apartment ADD COLUMN credit_balance REAL DEFAULT 0.0"))
                conn.commit()
                print("✅ Colonne credit_balance ajoutée à la table apartment")
            
            # Ajouter credit_used à Payment si n'existe pas
            result = conn.execute(db.text("PRAGMA table_info(payment)"))
            columns = [row[1] for row in result]
            if 'credit_used' not in columns:
                conn.execute(db.text("ALTER TABLE payment ADD COLUMN credit_used REAL DEFAULT 0.0"))
                conn.commit()
                print("✅ Colonne credit_used ajoutée à la table payment")
    except Exception as e:
        print(f"⚠️ Erreur lors de la migration : {e}")
    
    if not User.query.filter_by(email='superadmin@syndicpro.tn').first():
        superadmin = User(
            email='superadmin@syndicpro.tn',
            name='Super Administrateur',
            role='superadmin',
            organization_id=None
        )
        superadmin.set_password('SuperAdmin2024!')
        db.session.add(superadmin)
        db.session.commit()
        print("✅ Super Admin créé: superadmin@syndicpro.tn / SuperAdmin2024!")
        print("⚠️  CHANGEZ CE MOT DE PASSE après la première connexion!")

def current_user():
    uid = session.get('user_id')
    if not uid:
        return None
    return User.query.get(uid)

def current_organization():
    user = current_user()
    if not user:
        return None
    if user.role == 'superadmin':
        return None
    return Organization.query.get(user.organization_id)

def check_subscription():
    org = current_organization()
    if not org:
        return True
    if not org.subscription:
        return False
    return not org.subscription.is_expired() and org.subscription.status == 'active'

def login_required(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user():
            flash("Veuillez vous connecter.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper

def subscription_required(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = current_user()
        if user and user.role == 'superadmin':
            return f(*args, **kwargs)
        if not check_subscription():
            flash("Votre abonnement a expiré. Veuillez le renouveler.", "danger")
            return redirect(url_for('subscription_status'))
        return f(*args, **kwargs)
    return wrapper

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user or user.role not in ['admin', 'superadmin']:
            flash("Accès administrateur requis.", "danger")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return wrapper

def superadmin_required(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user or user.role != 'superadmin':
            flash("Accès super administrateur requis.", "danger")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return wrapper

def get_unpaid_months_count(apartment_id):
    """Compte le nombre de mois impayés DEPUIS LA CRÉATION de l'appartement"""
    apt = Apartment.query.get(apartment_id)
    if not apt:
        return 0
    
    payments = Payment.query.filter_by(apartment_id=apartment_id).all()
    paid_months = set(p.month_paid for p in payments)
    
    if apt.created_at:
        start_date = apt.created_at.date().replace(day=1)
    else:
        start_date = date.today().replace(day=1)
    
    current = start_date
    end_date = date.today().replace(day=1)
    
    unpaid_count = 0
    while current <= end_date:
        month_str = current.strftime('%Y-%m')
        if month_str not in paid_months:
            unpaid_count += 1
        current += relativedelta(months=1)
    
    return unpaid_count

def get_next_unpaid_month(apartment_id):
    """
    Retourne le premier mois (YYYY-MM) non couvert par un paiement
    depuis la création de l'appartement, en regardant jusqu'à 3 mois dans le futur.
    """
    apt = Apartment.query.get(apartment_id)
    if not apt:
        return date.today().strftime('%Y-%m')
    
    payments = Payment.query.filter_by(apartment_id=apartment_id).all()
    paid_months = set(p.month_paid for p in payments)
    
    if apt.created_at:
        start_date = apt.created_at.date().replace(day=1)
    else:
        start_date = date.today().replace(day=1)
    
    current = start_date
    end_check_date = date.today().replace(day=1) + relativedelta(months=3)

    while current <= end_check_date:
        month_str = current.strftime('%Y-%m')
        if month_str not in paid_months:
            return month_str
        current += relativedelta(months=1)
    
    return (end_check_date + relativedelta(months=1)).strftime('%Y-%m')

def check_unpaid_alerts():
    org = current_organization()
    if not org:
        return []
    apartments = Apartment.query.filter_by(organization_id=org.id).all()
    alerts_created = []
    for apt in apartments:
        unpaid_count = get_unpaid_months_count(apt.id)
        if unpaid_count >= 3:
            recent_alert = UnpaidAlert.query.filter_by(
                apartment_id=apt.id
            ).filter(
                UnpaidAlert.alert_date > datetime.utcnow() - timedelta(days=30)
            ).first()
            if not recent_alert:
                alert = UnpaidAlert(
                    organization_id=org.id,
                    apartment_id=apt.id,
                    months_unpaid=unpaid_count
                )
                db.session.add(alert)
                alerts_created.append(apt)
    if alerts_created:
        db.session.commit()
    return alerts_created

def last_n_months(n=12):
    today = date.today()
    months = []
    for i in range(n-1, -1, -1):
        month_date = today - relativedelta(months=i)
        months.append((month_date.year, month_date.month))
    return months

def get_month_name(month_num):
    months_fr = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin', 
                 'Juil', 'Août', 'Sep', 'Oct', 'Nov', 'Déc']
    return months_fr[month_num - 1]

# -------- Routes --------

@app.route('/')
def index():
    """Page d'accueil avec choix : Se connecter ou S'inscrire"""
    # Si l'utilisateur est déjà connecté, rediriger vers le dashboard approprié
    if current_user():
        user = current_user()
        if user.role == 'superadmin':
            return redirect(url_for('superadmin_dashboard'))
        else:
            return redirect(url_for('dashboard'))
    # Sinon afficher la page d'accueil
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        pwd = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(pwd):
            if user.role != 'superadmin':
                if not user.organization_id:
                    flash('Utilisateur non affecté à une organisation.', 'danger')
                    return redirect(url_for('login'))
                org = Organization.query.get(user.organization_id)
                if not org or not org.is_active:
                    flash('Organisation désactivée. Contactez le support.', 'danger')
                    return redirect(url_for('login'))
            session['user_id'] = user.id
            flash('Connecté avec succès', 'success')
            if user.role == 'superadmin':
                return redirect(url_for('superadmin_dashboard'))
            else:
                return redirect(url_for('dashboard'))
        flash('Email ou mot de passe incorrect', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Déconnecté', 'info')
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        org_name = request.form['org_name'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()
        if User.query.filter_by(email=email).first():
            flash('Cet email est déjà utilisé.', 'danger')
            return redirect(url_for('register'))
        base_slug = org_name.lower().replace(' ', '-').replace('é', 'e').replace('è', 'e')
        slug = base_slug
        counter = 1
        while Organization.query.filter_by(slug=slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1
        org = Organization(
            name=org_name,
            slug=slug,
            email=email,
            phone=phone,
            address=address,
            is_active=True
        )
        db.session.add(org)
        db.session.flush()
        subscription = Subscription(
            organization_id=org.id,
            plan='trial',
            status='active',
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=30),
            monthly_price=0.0,
            max_apartments=999999
        )
        db.session.add(subscription)
        admin = User(
            organization_id=org.id,
            email=email,
            name='Administrateur',
            role='admin'
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        flash(f'✅ Organisation créée avec succès ! Essai gratuit de 30 jours activé.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/dashboard')
@login_required
@subscription_required
def dashboard():
    user = current_user()
    org = current_organization()
    if not org:
        flash("Erreur: Organisation introuvable", "danger")
        return redirect(url_for('logout'))
    blocks_count = Block.query.filter_by(organization_id=org.id).count()
    apartments_count = Apartment.query.filter_by(organization_id=org.id).count()
    total_payments = sum(p.amount for p in Payment.query.filter_by(organization_id=org.id).all())
    total_expenses = sum(e.amount for e in Expense.query.filter_by(organization_id=org.id).all())
    subscription = org.subscription
    days_left = subscription.days_remaining() if subscription else 0
    unpaid_count = 0
    next_month = None
    credit = 0.0
    if user.role == 'resident' and user.apartment_id:
        unpaid_count = get_unpaid_months_count(user.apartment_id)
        next_month = get_next_unpaid_month(user.apartment_id)
        apt = Apartment.query.get(user.apartment_id)
        if apt:
            credit = apt.credit_balance
    alerts = []
    if user.role == 'admin':
        alerts = UnpaidAlert.query.filter_by(
            organization_id=org.id,
            email_sent=False
        ).order_by(UnpaidAlert.alert_date.desc()).limit(5).all()
    recent_tickets = []
    if user.role == 'admin':
        recent_tickets = Ticket.query.filter(
            Ticket.organization_id == org.id,
            Ticket.status.in_(['ouvert', 'en_cours'])
        ).order_by(Ticket.created_at.desc()).limit(5).all()
    elif user.apartment_id:
        recent_tickets = Ticket.query.filter_by(
            apartment_id=user.apartment_id
        ).order_by(Ticket.created_at.desc()).limit(5).all()
    return render_template('dashboard.html', 
                         user=user,
                         org=org,
                         subscription=subscription,
                         days_left=days_left,
                         blocks_count=blocks_count,
                         apartments_count=apartments_count,
                         total_payments=total_payments,
                         total_expenses=total_expenses,
                         unpaid_count=unpaid_count,
                         next_month=next_month,
                         credit=credit,
                         alerts=alerts,
                         recent_tickets=recent_tickets)

@app.route('/apartments', methods=['GET', 'POST'])
@login_required
@admin_required
@subscription_required
def apartments():
    org = current_organization()
    blocks = Block.query.filter_by(organization_id=org.id).all()
    if request.method == 'POST':
        if request.form.get('action') == 'add_block':
            name = request.form['block_name'].strip()
            if name and not Block.query.filter_by(organization_id=org.id, name=name).first():
                b = Block(name=name, organization_id=org.id)
                db.session.add(b)
                db.session.commit()
                flash(f'Bloc {name} ajouté', 'success')
        elif request.form.get('action') == 'add_apartment':
            current_count = Apartment.query.filter_by(organization_id=org.id).count()
            if org.subscription and current_count >= org.subscription.max_apartments:
                flash(f'Limite atteinte: {org.subscription.max_apartments} appartements max pour votre plan', 'warning')
                return redirect(url_for('apartments'))
            number = request.form['apt_number'].strip()
            block_id = request.form.get('block_id')
            monthly_fee = request.form.get('monthly_fee', 100.0)
            if number and block_id:
                try:
                    a = Apartment(
                        organization_id=org.id,
                        number=number, 
                        block_id=int(block_id),
                        monthly_fee=float(monthly_fee),
                        credit_balance=0.0
                    )
                    db.session.add(a)
                    db.session.commit()
                    flash(f'Appartement {number} ajouté', 'success')
                except ValueError:
                    flash('Erreur de saisie', 'danger')
        return redirect(url_for('apartments'))
    for block in blocks:
        for apt in block.apartments:
            apt.unpaid_count = get_unpaid_months_count(apt.id)
            apt.next_unpaid = get_next_unpaid_month(apt.id)
    return render_template('apartments.html', blocks=blocks, user=current_user(), org=org)

@app.route('/apartment/edit/<int:apartment_id>', methods=['GET', 'POST'])
@login_required
@admin_required
@subscription_required
def edit_apartment(apartment_id):
    org = current_organization()
    apt = Apartment.query.filter_by(id=apartment_id, organization_id=org.id).first_or_404()
    blocks = Block.query.filter_by(organization_id=org.id).all()
    if request.method == 'POST':
        apt.number = request.form['apt_number']
        apt.block_id = int(request.form['block_id'])
        apt.monthly_fee = float(request.form.get('monthly_fee', 100.0))
        db.session.commit()
        flash('Appartement modifié', 'success')
        return redirect(url_for('apartments'))
    return render_template('edit_apartment.html', apartment=apt, blocks=blocks, user=current_user())

@app.route('/apartment/delete/<int:apartment_id>')
@login_required
@admin_required
@subscription_required
def delete_apartment(apartment_id):
    org = current_organization()
    apt = Apartment.query.filter_by(id=apartment_id, organization_id=org.id).first_or_404()
    db.session.delete(apt)
    db.session.commit()
    flash('Appartement supprimé', 'success')
    return redirect(url_for('apartments'))

@app.route('/payments', methods=['GET', 'POST'])
@login_required
@admin_required
@subscription_required
def payments():
    org = current_organization()
    apartments = Apartment.query.filter_by(organization_id=org.id).all()
    
    if request.method == 'POST':
        try:
            apartment_id = int(request.form['apartment_id'])
            amount = float(request.form['amount'])
            payment_date = datetime.strptime(request.form['payment_date'], '%Y-%m-%d').date()
            description = request.form.get('description', 'Redevance')
            start_month_str = request.form.get('start_month', '').strip()
            
            apt = Apartment.query.get(apartment_id)
            if not apt:
                flash("Appartement introuvable", "danger")
                return redirect(url_for('payments'))
            
            monthly_fee = apt.monthly_fee
            
            # 💳 NOUVEAU : Ajouter le crédit existant au montant payé
            credit_used = apt.credit_balance
            total_available = amount + credit_used
            
            if credit_used > 0:
                flash(f"💳 Crédit utilisé : {credit_used:.2f} DT", "info")
            
            months_to_pay = int(total_available // monthly_fee)
            new_remainder = total_available % monthly_fee

            if months_to_pay == 0:
                # Si le montant total ne couvre pas un mois complet, on met tout en crédit
                apt.credit_balance = total_available
                db.session.commit()
                flash(f"💰 Montant ajouté au crédit : {amount:.2f} DT", "info")
                flash(f"💳 Crédit total : {apt.credit_balance:.2f} DT (sera utilisé au prochain paiement)", "success")
                return redirect(url_for('payments'))
            
            # Déterminer le mois de départ
            if start_month_str:
                try:
                    start_month_date = datetime.strptime(start_month_str, "%Y-%m").date().replace(day=1)
                    flash(f"📅 Mode manuel : Paiement à partir de {start_month_str}", "info")
                except ValueError:
                    flash("❌ Format de mois invalide (utilisez YYYY-MM)", "danger")
                    return redirect(url_for('payments'))
            else:
                next_month_str = get_next_unpaid_month(apartment_id)
                start_month_date = datetime.strptime(next_month_str, "%Y-%m").date().replace(day=1)
                flash(f"🤖 Mode automatique : Paiement à partir du premier mois impayé ({next_month_str})", "info")
            
            # Récupérer les mois déjà payés
            existing_paid_months = set(
                p.month_paid for p in Payment.query.filter_by(apartment_id=apartment_id).all()
            )
            
            months_actually_paid = 0
            total_recorded_amount = 0.0
            paid_months_list = []

            for i in range(months_to_pay):
                month_paid_date = start_month_date + relativedelta(months=i)
                month_paid_str = month_paid_date.strftime("%Y-%m")
                
                # VÉRIFICATION ANTI-DOUBLON
                if month_paid_str in existing_paid_months:
                    flash(f"⚠️ Le mois {month_paid_str} est déjà payé, il sera ignoré", "warning")
                    new_remainder += monthly_fee
                    continue
                
                # Enregistrer le paiement
                p = Payment(
                    organization_id=org.id,
                    apartment_id=apartment_id,
                    amount=monthly_fee,
                    payment_date=payment_date,
                    month_paid=month_paid_str,
                    description=f"Redevance {month_paid_str}",
                    credit_used=credit_used if i == 0 else 0.0  # Le crédit est utilisé pour le 1er mois
                )
                db.session.add(p)
                months_actually_paid += 1
                total_recorded_amount += monthly_fee
                paid_months_list.append(month_paid_str)
                
                # Réinitialiser credit_used après le premier mois
                if i == 0:
                    credit_used = 0.0

            # 💳 NOUVEAU : Mettre à jour le crédit résiduel
            apt.credit_balance = new_remainder
            db.session.commit()
            
            # Messages de confirmation détaillés
            if months_actually_paid > 0:
                months_display = ", ".join(paid_months_list)
                flash(f"✅ Paiement enregistré avec succès !", "success")
                flash(f"💰 {months_actually_paid} mois payé(s) : {months_display}", "success")
                flash(f"📊 Montant total : {total_recorded_amount:.2f} DT", "info")
            else:
                flash("❌ Aucun nouveau mois n'a été payé (tous les mois étaient déjà payés)", "warning")
            
            if new_remainder > 0:
                flash(f"💳 Nouveau crédit : {new_remainder:.2f} DT (sera utilisé automatiquement au prochain paiement)", "success")
            elif apt.credit_balance == 0 and months_actually_paid > 0:
                flash(f"✅ Montant exact, aucun crédit résiduel", "info")
        
        except Exception as e:
            flash(f'❌ Erreur: {str(e)}', 'danger')
        
        return redirect(url_for('payments'))

    # Préparer les données pour l'affichage
    for apt in apartments:
        apt.next_unpaid = get_next_unpaid_month(apt.id)
        apt.unpaid_count = get_unpaid_months_count(apt.id)
        
    payments_list = Payment.query.filter_by(organization_id=org.id).order_by(Payment.payment_date.desc()).all()
    return render_template('payments.html', apartments=apartments, payments=payments_list, user=current_user())

@app.route('/api/next_unpaid/<int:apartment_id>')
@login_required
@subscription_required
def api_next_unpaid(apartment_id):
    org = current_organization()
    apt = Apartment.query.filter_by(id=apartment_id, organization_id=org.id).first_or_404()
    next_month = get_next_unpaid_month(apartment_id)
    unpaid_count = get_unpaid_months_count(apartment_id)
    return jsonify({
        'next_month': next_month,
        'unpaid_count': unpaid_count,
        'monthly_fee': apt.monthly_fee,
        'credit_balance': apt.credit_balance  # 🆕 NOUVEAU
    })

@app.route('/payment/edit/<int:payment_id>', methods=['GET', 'POST'])
@login_required
@admin_required
@subscription_required
def edit_payment(payment_id):
    org = current_organization()
    p = Payment.query.filter_by(id=payment_id, organization_id=org.id).first_or_404()
    apartments = Apartment.query.filter_by(organization_id=org.id).all()
    if request.method == 'POST':
        p.apartment_id = int(request.form['apartment_id'])
        p.amount = float(request.form['amount'])
        p.payment_date = datetime.strptime(request.form['payment_date'], '%Y-%m-%d').date()
        p.month_paid = request.form['month_paid']
        p.description = request.form.get('description', '')
        db.session.commit()
        flash('Encaissement modifié', 'success')
        return redirect(url_for('payments'))
    return render_template('edit_payment.html', payment=p, apartments=apartments, user=current_user())

@app.route('/payment/delete/<int:payment_id>')
@login_required
@admin_required
@subscription_required
def delete_payment(payment_id):
    org = current_organization()
    p = Payment.query.filter_by(id=payment_id, organization_id=org.id).first_or_404()
    db.session.delete(p)
    db.session.commit()
    flash('Encaissement supprimé', 'success')
    return redirect(url_for('payments'))

@app.route('/expenses', methods=['GET', 'POST'])
@login_required
@admin_required
@subscription_required
def expenses():
    org = current_organization()
    if request.method == 'POST':
        try:
            amount = float(request.form['amount'])
            expense_date = datetime.strptime(request.form['expense_date'], '%Y-%m-%d').date()
            category = request.form.get('category', 'Autre')
            description = request.form.get('description', '')
            e = Expense(
                organization_id=org.id,
                amount=amount,
                expense_date=expense_date,
                category=category,
                description=description
            )
            db.session.add(e)
            db.session.commit()
            flash('Dépense enregistrée', 'success')
        except Exception as e:
            flash(f'Erreur: {str(e)}', 'danger')
        return redirect(url_for('expenses'))
    expenses = Expense.query.filter_by(organization_id=org.id).order_by(Expense.expense_date.desc()).all()
    return render_template('expenses.html', expenses=expenses, user=current_user())

@app.route('/expense/edit/<int:expense_id>', methods=['GET', 'POST'])
@login_required
@admin_required
@subscription_required
def edit_expense(expense_id):
    org = current_organization()
    e = Expense.query.filter_by(id=expense_id, organization_id=org.id).first_or_404()
    if request.method == 'POST':
        e.amount = float(request.form['amount'])
        e.expense_date = datetime.strptime(request.form['expense_date'], '%Y-%m-%d').date()
        e.category = request.form.get('category', 'Autre')
        e.description = request.form.get('description', '')
        db.session.commit()
        flash('Dépense modifiée', 'success')
        return redirect(url_for('expenses'))
    return render_template('edit_expense.html', expense=e, user=current_user())

@app.route('/expense/delete/<int:expense_id>')
@login_required
@admin_required
@subscription_required
def delete_expense(expense_id):
    org = current_organization()
    e = Expense.query.filter_by(id=expense_id, organization_id=org.id).first_or_404()
    db.session.delete(e)
    db.session.commit()
    flash('Dépense supprimée', 'success')
    return redirect(url_for('expenses'))

@app.route('/tresorerie')
@login_required
@subscription_required
def tresorerie():
    org = current_organization()
    months = last_n_months(12)
    apartments = Apartment.query.filter_by(organization_id=org.id).order_by(Apartment.block_id, Apartment.number).all()
    expenses = Expense.query.filter_by(organization_id=org.id).all()
    payments = Payment.query.filter_by(organization_id=org.id).all()
    data = []
    for apt in apartments:
        row = {'apartment': f"{apt.block.name}-{apt.number}", 'months': {}}
        for year, month in months:
            month_key = f"{year}-{month:02d}"
            total = sum(p.amount for p in payments 
                       if p.apartment_id == apt.id 
                       and p.payment_date.year == year 
                       and p.payment_date.month == month)
            row['months'][month_key] = total
        data.append(row)
    expense_row = {'apartment': 'DÉPENSES', 'months': {}}
    for year, month in months:
        month_key = f"{year}-{month:02d}"
        total = sum(e.amount for e in expenses 
                   if e.expense_date.year == year 
                   and e.expense_date.month == month)
        expense_row['months'][month_key] = total
    solde_row = {'apartment': 'SOLDE', 'months': {}}
    for year, month in months:
        month_key = f"{year}-{month:02d}"
        total_in = sum(row['months'][month_key] for row in data)
        total_out = expense_row['months'][month_key]
        solde_row['months'][month_key] = total_in - total_out
    return render_template('tresorerie.html', 
                         data=data,
                         expense_row=expense_row,
                         solde_row=solde_row,
                         months=months,
                         user=current_user())

@app.route('/comptable')
@login_required
@subscription_required
def comptable():
    org = current_organization()
    today = date.today()
    all_months = []
    
    for i in range(11, -1, -1):
        month_date = today - relativedelta(months=i)
        all_months.append((month_date.year, month_date.month))
    
    for i in range(1, 4):
        month_date = today + relativedelta(months=i)
        all_months.append((month_date.year, month_date.month))
    
    months = sorted(list(set(all_months)))

    apartments = Apartment.query.filter_by(organization_id=org.id).order_by(Apartment.block_id, Apartment.number).all()
    payments = Payment.query.filter_by(organization_id=org.id).all()
    data = []
    
    all_paid_months = {}
    for p in payments:
        if p.apartment_id not in all_paid_months:
            all_paid_months[p.apartment_id] = set()
        all_paid_months[p.apartment_id].add(p.month_paid)

    for apt in apartments:
        row = {
            'apartment': f"{apt.block.name}-{apt.number}",
            'monthly_fee': apt.monthly_fee,
            'credit_balance': apt.credit_balance,  # 🆕 NOUVEAU
            'months': {}
        }
        
        apt_paid_months = all_paid_months.get(apt.id, set())
        
        for year, month in months:
            month_key = f"{year}-{month:02d}"
            paid = month_key in apt_paid_months
            amount = apt.monthly_fee if paid else 0
            row['months'][month_key] = {'paid': paid, 'amount': amount}
        
        row['unpaid_count'] = get_unpaid_months_count(apt.id)
        data.append(row)
        
    return render_template('comptable.html', data=data, months=months, user=current_user())

@app.route('/tickets', methods=['GET', 'POST'])
@login_required
@subscription_required
def tickets():
    user = current_user()
    org = current_organization()
    if request.method == 'POST':
        if not user.apartment_id:
            flash('Vous devez être affecté à un appartement', 'danger')
            return redirect(url_for('tickets'))
        subject = request.form['subject']
        message = request.form['message']
        priority = request.form.get('priority', 'normale')
        ticket = Ticket(
            organization_id=org.id,
            apartment_id=user.apartment_id,
            user_id=user.id,
            subject=subject,
            message=message,
            priority=priority
        )
        db.session.add(ticket)
        db.session.commit()
        flash('Ticket créé avec succès', 'success')
        return redirect(url_for('tickets'))
    if user.role == 'admin':
        tickets_list = Ticket.query.filter_by(organization_id=org.id).order_by(Ticket.created_at.desc()).all()
    else:
        tickets_list = Ticket.query.filter_by(apartment_id=user.apartment_id).order_by(Ticket.created_at.desc()).all()
    return render_template('tickets.html', tickets=tickets_list, user=user)

@app.route('/ticket/<int:ticket_id>', methods=['GET', 'POST'])
@login_required
@subscription_required
def ticket_detail(ticket_id):
    org = current_organization()
    ticket = Ticket.query.filter_by(id=ticket_id, organization_id=org.id).first_or_404()
    user = current_user()
    if user.role != 'admin' and ticket.apartment_id != user.apartment_id:
        flash('Accès non autorisé', 'danger')
        return redirect(url_for('tickets'))
    if request.method == 'POST' and user.role == 'admin':
        ticket.status = request.form.get('status', ticket.status)
        ticket.admin_response = request.form.get('admin_response', ticket.admin_response)
        ticket.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Ticket mis à jour', 'success')
        return redirect(url_for('ticket_detail', ticket_id=ticket_id))
    return render_template('ticket_detail.html', ticket=ticket, user=user)

@app.route('/ticket/delete/<int:ticket_id>')
@login_required
@admin_required
@subscription_required
def delete_ticket(ticket_id):
    org = current_organization()
    ticket = Ticket.query.filter_by(id=ticket_id, organization_id=org.id).first_or_404()
    db.session.delete(ticket)
    db.session.commit()
    flash('Ticket supprimé', 'success')
    return redirect(url_for('tickets'))

@app.route('/alerts')
@login_required
@admin_required
@subscription_required
def alerts():
    org = current_organization()
    new_alerts = check_unpaid_alerts()
    if new_alerts:
        flash(f'{len(new_alerts)} nouvelle(s) alerte(s) d\'impayés créée(s)', 'warning')
    all_alerts = UnpaidAlert.query.filter_by(organization_id=org.id).order_by(UnpaidAlert.alert_date.desc()).all()
    return render_template('alerts.html', alerts=all_alerts, user=current_user())

@app.route('/alert/mark_sent/<int:alert_id>')
@login_required
@admin_required
@subscription_required
def mark_alert_sent(alert_id):
    org = current_organization()
    alert = UnpaidAlert.query.filter_by(id=alert_id, organization_id=org.id).first_or_404()
    alert.email_sent = True
    db.session.commit()
    flash('Alerte marquée comme envoyée', 'success')
    return redirect(url_for('alerts'))

@app.route('/users', methods=['GET', 'POST'])
@login_required
@admin_required
@subscription_required
def users():
    org = current_organization()
    if request.method == 'POST':
        email = request.form['email']
        name = request.form.get('name', '')
        role = request.form.get('role', 'resident')
        apt_id = request.form.get('apartment_id') or None
        try:
            apt_id = int(apt_id) if apt_id else None
        except ValueError:
            apt_id = None
        if User.query.filter_by(email=email, organization_id=org.id).first():
            flash('Cet email existe déjà', 'danger')
            return redirect(url_for('users'))
        u = User(
            organization_id=org.id,
            email=email,
            name=name,
            role=role,
            apartment_id=apt_id
        )
        u.set_password(request.form.get('password', 'resident123'))
        db.session.add(u)
        db.session.commit()
        flash('Utilisateur créé', 'success')
        return redirect(url_for('users'))
    users_list = User.query.filter_by(organization_id=org.id).all()
    apartments = Apartment.query.filter_by(organization_id=org.id).all()
    return render_template('users.html', users=users_list, apartments=apartments, user=current_user())

@app.route('/user/delete/<int:user_id>')
@login_required
@admin_required
@subscription_required
def delete_user(user_id):
    org = current_organization()
    if user_id == current_user().id:
        flash('Vous ne pouvez pas supprimer votre propre compte', 'danger')
        return redirect(url_for('users'))
    user = User.query.filter_by(id=user_id, organization_id=org.id).first_or_404()
    db.session.delete(user)
    db.session.commit()
    flash('Utilisateur supprimé', 'success')
    return redirect(url_for('users'))

@app.route('/residents')
@login_required
@subscription_required
def residents_menu():
    user = current_user()
    unpaid_count = 0
    next_month = None
    my_payments = []
    credit = 0.0
    if user.apartment_id:
        unpaid_count = get_unpaid_months_count(user.apartment_id)
        next_month = get_next_unpaid_month(user.apartment_id)
        my_payments = Payment.query.filter_by(apartment_id=user.apartment_id).order_by(Payment.payment_date.desc()).limit(10).all()
        apt = Apartment.query.get(user.apartment_id)
        if apt:
            credit = apt.credit_balance
    return render_template('residents.html', user=user, unpaid_count=unpaid_count, next_month=next_month, my_payments=my_payments, credit=credit)

@app.route('/api/dashboard_data')
@login_required
@subscription_required
def api_dashboard_data():
    org = current_organization()
    months = last_n_months(12)
    payments = Payment.query.filter_by(organization_id=org.id).all()
    expenses = Expense.query.filter_by(organization_id=org.id).all()
    labels = []
    data_pay = []
    data_exp = []
    for (y, m) in months:
        labels.append(f"{get_month_name(m)} {y}")
        s_p = sum(p.amount for p in payments if p.payment_date.year == y and p.payment_date.month == m)
        s_e = sum(e.amount for e in expenses if e.expense_date.year == y and e.expense_date.month == m)
        data_pay.append(round(s_p, 2))
        data_exp.append(round(s_e, 2))
    return jsonify({'labels': labels, 'payments': data_pay, 'expenses': data_exp})

@app.route('/export_excel')
@login_required
@subscription_required
def export_excel():
    org = current_organization()
    payments = Payment.query.filter_by(organization_id=org.id).order_by(Payment.payment_date.desc()).all()
    expenses = Expense.query.filter_by(organization_id=org.id).order_by(Expense.expense_date.desc()).all()
    apartments = Apartment.query.filter_by(organization_id=org.id).all()
    df_payments = pd.DataFrame([{
        'ID': p.id,
        'Appartement': f"{p.apartment.block.name}-{p.apartment.number}" if p.apartment else '',
        'Montant': p.amount,
        'Date Paiement': p.payment_date.strftime('%Y-%m-%d'),
        'Mois Payé': p.month_paid,
        'Crédit Utilisé': p.credit_used,  # 🆕 NOUVEAU
        'Description': p.description
    } for p in payments])
    df_expenses = pd.DataFrame([{
        'ID': e.id,
        'Montant': e.amount,
        'Date': e.expense_date.strftime('%Y-%m-%d'),
        'Catégorie': e.category,
        'Description': e.description
    } for e in expenses])
    df_unpaid = pd.DataFrame([{
        'Appartement': f"{apt.block.name}-{apt.number}",
        'Redevance Mensuelle': apt.monthly_fee,
        'Crédit Disponible': apt.credit_balance,  # 🆕 NOUVEAU
        'Mois Impayés': get_unpaid_months_count(apt.id),
        'Prochain Mois': get_next_unpaid_month(apt.id),
        'Total Dû': apt.monthly_fee * get_unpaid_months_count(apt.id)
    } for apt in apartments])
    
    today = date.today()
    all_months = []
    for i in range(11, -1, -1):
        month_date = today - relativedelta(months=i)
        all_months.append((month_date.year, month_date.month))
    for i in range(1, 4):
        month_date = today + relativedelta(months=i)
        all_months.append((month_date.year, month_date.month))
    months = sorted(list(set(all_months)))

    comptable_data = []
    all_paid_months = {}
    for p in payments:
        if p.apartment_id not in all_paid_months:
            all_paid_months[p.apartment_id] = set()
        all_paid_months[p.apartment_id].add(p.month_paid)

    for apt in apartments:
        row = {
            'Appartement': f"{apt.block.name}-{apt.number}", 
            'Redevance': apt.monthly_fee,
            'Crédit': apt.credit_balance  # 🆕 NOUVEAU
        }
        apt_paid_months = all_paid_months.get(apt.id, set())
        for year, month in months:
            month_key = f"{year}-{month:02d}"
            paid = month_key in apt_paid_months
            row[month_key] = 'Payé' if paid else 'Impayé'
        comptable_data.append(row)
    df_comptable = pd.DataFrame(comptable_data)
    
    if df_payments.empty:
        df_payments = pd.DataFrame(columns=['ID', 'Appartement', 'Montant', 'Date Paiement', 'Mois Payé', 'Crédit Utilisé', 'Description'])
    if df_expenses.empty:
        df_expenses = pd.DataFrame(columns=['ID', 'Montant', 'Date', 'Catégorie', 'Description'])
        
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_payments.to_excel(writer, sheet_name='Encaissements', index=False)
        df_expenses.to_excel(writer, sheet_name='Dépenses', index=False)
        df_unpaid.to_excel(writer, sheet_name='Impayés', index=False)
        df_comptable.to_excel(writer, sheet_name='Tableau Comptable', index=False)
        
    output.seek(0)
    filename = f"SyndicPro_{org.name}_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(output, download_name=filename, as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/superadmin')
@login_required
@superadmin_required
def superadmin_dashboard():
    organizations = Organization.query.order_by(Organization.created_at.desc()).all()
    total_orgs = len(organizations)
    active_orgs = len([o for o in organizations if o.is_active])
    total_revenue = 0
    for org in organizations:
        if org.subscription and org.subscription.status == 'active':
            total_revenue += org.subscription.monthly_price
    return render_template('superadmin/dashboard.html', organizations=organizations, total_orgs=total_orgs, active_orgs=active_orgs, total_revenue=total_revenue)

@app.route('/superadmin/organization/<int:org_id>')
@login_required
@superadmin_required
def superadmin_org_detail(org_id):
    org = Organization.query.get_or_404(org_id)
    apartments_count = Apartment.query.filter_by(organization_id=org.id).count()
    users_count = User.query.filter_by(organization_id=org.id).count()
    return render_template('superadmin/org_detail.html', org=org, apartments_count=apartments_count, users_count=users_count)

@app.route('/superadmin/organization/<int:org_id>/toggle', methods=['POST'])
@login_required
@superadmin_required
def superadmin_toggle_org(org_id):
    org = Organization.query.get_or_404(org_id)
    org.is_active = not org.is_active
    db.session.commit()
    status = "activée" if org.is_active else "désactivée"
    flash(f'Organisation {org.name} {status}', 'success')
    return redirect(url_for('superadmin_org_detail', org_id=org_id))

@app.route('/superadmin/subscription/<int:org_id>/extend', methods=['POST'])
@login_required
@superadmin_required
def superadmin_extend_subscription(org_id):
    org = Organization.query.get_or_404(org_id)
    days = int(request.form.get('days', 30))
    if org.subscription:
        if org.subscription.end_date and org.subscription.end_date > datetime.utcnow():
            org.subscription.end_date += timedelta(days=days)
        else:
            org.subscription.end_date = datetime.utcnow() + timedelta(days=days)
        org.subscription.status = 'active'
        db.session.commit()
        flash(f'Abonnement prolongé de {days} jours pour {org.name}', 'success')
    return redirect(url_for('superadmin_org_detail', org_id=org_id))
@app.route('/superadmin/organization/<int:org_id>/update-limits', methods=['POST'])
@login_required
@superadmin_required
def superadmin_update_limits(org_id):
    """
    Permet au superadmin de modifier la limite d'appartements d'une organisation.
    Si le champ est vide, la limite devient illimitée (999999).
    """
    org = Organization.query.get_or_404(org_id)
    
    if org.subscription:
        max_apartments_str = request.form.get('max_apartments', '').strip()
        
        # Si le champ est vide, mettre illimité
        if not max_apartments_str:
            max_apartments = 999999
            flash('✅ Limite d\'appartements : Illimité', 'success')
        else:
            try:
                max_apartments = int(max_apartments_str)
                flash(f'✅ Limite d\'appartements mise à jour : {max_apartments}', 'success')
            except ValueError:
                flash('❌ Erreur : Veuillez entrer un nombre valide', 'danger')
                return redirect(url_for('superadmin_org_detail', org_id=org_id))
        
        org.subscription.max_apartments = max_apartments
        db.session.commit()
    else:
        flash('❌ Cette organisation n\'a pas d\'abonnement', 'danger')
    
    return redirect(url_for('superadmin_org_detail', org_id=org_id))


@app.route('/superadmin/organization/<int:org_id>/update-plan', methods=['POST'])
@login_required
@superadmin_required
def superadmin_update_plan(org_id):
    """
    Permet au superadmin de modifier le plan et le prix mensuel d'une organisation.
    """
    org = Organization.query.get_or_404(org_id)
    
    if org.subscription:
        plan = request.form.get('plan', 'trial')
        
        try:
            price = float(request.form.get('monthly_price', 0.0))
        except ValueError:
            flash('❌ Erreur : Prix mensuel invalide', 'danger')
            return redirect(url_for('superadmin_org_detail', org_id=org_id))
        
        # Mettre à jour le plan et le prix
        org.subscription.plan = plan
        org.subscription.monthly_price = price
        db.session.commit()
        
        # Message de confirmation avec emoji
        plan_names = {
            'trial': 'Essai Gratuit',
            'starter': 'Starter',
            'pro': 'Pro',
            'enterprise': 'Enterprise'
        }
        plan_display = plan_names.get(plan, plan)
        
        flash(f'✅ Plan mis à jour : {plan_display} ({price:.2f} DT/mois)', 'success')
    else:
        flash('❌ Cette organisation n\'a pas d\'abonnement', 'danger')
    
    return redirect(url_for('superadmin_org_detail', org_id=org_id))

@app.route('/superadmin/change-password', methods=['GET', 'POST'])
@login_required
@superadmin_required
def superadmin_change_password():
    if request.method == 'POST':
        current_pwd = request.form['current_password']
        new_pwd = request.form['new_password']
        confirm_pwd = request.form['confirm_password']
        user = current_user()
        if not user.check_password(current_pwd):
            flash('Mot de passe actuel incorrect', 'danger')
            return redirect(url_for('superadmin_change_password'))
        if new_pwd != confirm_pwd:
            flash('Les nouveaux mots de passe ne correspondent pas', 'danger')
            return redirect(url_for('superadmin_change_password'))
        if len(new_pwd) < 8:
            flash('Le mot de passe doit contenir au moins 8 caractères', 'danger')
            return redirect(url_for('superadmin_change_password'))
        user.set_password(new_pwd)
        db.session.commit()
        flash('✅ Mot de passe changé avec succès !', 'success')
        return redirect(url_for('superadmin_dashboard'))
    return render_template('superadmin/change_password.html')

@app.route('/subscription')
@login_required
def subscription_status():
    user = current_user()
    org = current_organization()
    if not org:
        return redirect(url_for('dashboard'))
    subscription = org.subscription
    apartments_count = Apartment.query.filter_by(organization_id=org.id).count()
    recommended_price = subscription.calculate_price(apartments_count) if subscription else 0
    return render_template('subscription_status.html', user=user, org=org, subscription=subscription, apartments_count=apartments_count, recommended_price=recommended_price)

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500

# Créer templates/404.html
"""
{% extends "base.html" %}
{% block content %}
<div class="text-center py-5">
    <h1>404 - Page Non Trouvée</h1>
    <p>La page que vous recherchez n'existe pas.</p>
    <a href="{{ url_for('dashboard') }}" class="btn btn-primary">Retour au Tableau de Bord</a>
</div>
{% endblock %}
"""

# Créer templates/500.html  
"""
{% extends "base.html" %}
{% block content %}
<div class="text-center py-5">
    <h1>500 - Erreur Serveur</h1>
    <p>Une erreur interne s'est produite.</p>
    <a href="{{ url_for('dashboard') }}" class="btn btn-primary">Retour au Tableau de Bord</a>
</div>
{% endblock %}
"""
if __name__ == "__main__":
    with app.app_context():
        init_db()
    print("="*60)
    print("🚀 SYNDICPRO MULTI-TENANT - VERSION 3.0.5")
    print("="*60)
    print("💳 NOUVEAU : Système de crédit résiduel intégré")
    print("✅ Aucune perte d'argent sur les montants non utilisés")
    print("🔄 Application automatique du crédit au prochain paiement")
    print("📊 Affichage du crédit dans toute l'interface")
    print("🔧 Super Admin: superadmin@syndicpro.tn")
    print("🔑 Mot de passe: SuperAdmin2024!")
    print("⚠️  CHANGEZ CE MOT DE PASSE après connexion!")
    print("="*60)
    app.run(debug=True, host='0.0.0.0', port=5000)