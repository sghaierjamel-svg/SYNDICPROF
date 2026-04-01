from core import db, BASE_DIR
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import os


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
    # Paramètres Konnect (paiements résidents → compte du syndic)
    konnect_api_key = db.Column(db.String(200))
    konnect_wallet_id = db.Column(db.String(100))
    # Paramètres WhatsApp
    whatsapp_enabled = db.Column(db.Boolean, default=False)
    whatsapp_admin_phone = db.Column(db.String(20))

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
    credit_balance = db.Column(db.Float, default=0.0)
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
    credit_used = db.Column(db.Float, default=0.0)


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


class SuperAdminSettings(db.Model):
    """Paramètres globaux de SyndicPro (un seul enregistrement)"""
    id = db.Column(db.Integer, primary_key=True)
    konnect_api_key = db.Column(db.String(200))
    konnect_wallet_id = db.Column(db.String(100))

    @staticmethod
    def get():
        s = SuperAdminSettings.query.first()
        if not s:
            s = SuperAdminSettings()
            db.session.add(s)
            db.session.commit()
        return s


class UnpaidAlert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartment.id'), nullable=False)
    months_unpaid = db.Column(db.Integer, nullable=False)
    alert_date = db.Column(db.DateTime, default=datetime.utcnow)
    email_sent = db.Column(db.Boolean, default=False)
    apartment = db.relationship('Apartment', backref='alerts')


def init_db():
    """Initialise la base de données multi-tenant"""
    db_dir = os.path.join(BASE_DIR, 'database')
    os.makedirs(db_dir, exist_ok=True)
    db.create_all()

    # Migration : Ajouter credit_balance si la colonne n'existe pas
    try:
        with db.engine.connect() as conn:
            result = conn.execute(db.text("PRAGMA table_info(apartment)"))
            columns = [row[1] for row in result]
            if 'credit_balance' not in columns:
                conn.execute(db.text("ALTER TABLE apartment ADD COLUMN credit_balance REAL DEFAULT 0.0"))
                conn.commit()
                print("Colonne credit_balance ajoutée à la table apartment")

            # Ajouter credit_used à Payment si n'existe pas
            result = conn.execute(db.text("PRAGMA table_info(payment)"))
            columns = [row[1] for row in result]
            if 'credit_used' not in columns:
                conn.execute(db.text("ALTER TABLE payment ADD COLUMN credit_used REAL DEFAULT 0.0"))
                conn.commit()
                print("Colonne credit_used ajoutée à la table payment")
    except Exception as e:
        print(f"Erreur lors de la migration : {e}")

    # Migration : nouvelles colonnes Organization
    try:
        with db.engine.connect() as conn:
            result = conn.execute(db.text("PRAGMA table_info(organization)"))
            cols = [row[1] for row in result]
            new_cols = {
                'konnect_api_key': 'VARCHAR(200)',
                'konnect_wallet_id': 'VARCHAR(100)',
                'whatsapp_enabled': 'BOOLEAN DEFAULT 0',
                'whatsapp_admin_phone': 'VARCHAR(20)',
            }
            for col, col_type in new_cols.items():
                if col not in cols:
                    conn.execute(db.text(f"ALTER TABLE organization ADD COLUMN {col} {col_type}"))
                    conn.commit()
    except Exception:
        pass  # PostgreSQL : db.create_all() gère les nouvelles tables

    if not User.query.filter_by(email='superadmin@syndicpro.tn').first():
        superadmin = User(
            email='superadmin@syndicpro.tn',
            name='Super Administrateur',
            role='superadmin',
            organization_id=None
        )
        superadmin.set_password(os.environ.get('SUPERADMIN_PASSWORD', 'changez-moi'))
        db.session.add(superadmin)
        db.session.commit()
        print("Super Admin créé: superadmin@syndicpro.tn")
        print("Mot de passe défini via variable d'environnement SUPERADMIN_PASSWORD")
