from core import db, BASE_DIR
from datetime import datetime, timedelta
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
    whatsapp_token = db.Column(db.String(200))    # token API fonnte.com

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
        # BUG-F004 : grace period 24h après expiration
        return datetime.utcnow() > (self.end_date + timedelta(hours=24))

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
    phone = db.Column(db.String(20))              # numéro WhatsApp résident
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartment.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login_at = db.Column(db.DateTime, nullable=True)

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
    # BUG-F003 : cascade supprimé — supprimer un appartement ne détruit plus l'historique financier
    payments = db.relationship('Payment', backref='apartment', lazy=True, cascade='save-update, merge')
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


class KonnectPayment(db.Model):
    """Lien de paiement Konnect généré pour un résident"""
    __tablename__ = 'konnect_payment'
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartment.id'), nullable=False)
    month_target = db.Column(db.String(7), nullable=False)   # YYYY-MM
    amount = db.Column(db.Float, nullable=False)
    konnect_payment_ref = db.Column(db.String(100), unique=True)
    pay_url = db.Column(db.String(500))
    status = db.Column(db.String(20), default='pending')     # pending / completed / failed
    created_by = db.Column(db.String(20), default='resident')  # resident / admin
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    paid_at = db.Column(db.DateTime)
    apartment = db.relationship('Apartment', backref='konnect_payments', lazy=True)


class UnpaidAlert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartment.id'), nullable=False)
    months_unpaid = db.Column(db.Integer, nullable=False)
    alert_date = db.Column(db.DateTime, default=datetime.utcnow)
    email_sent = db.Column(db.Boolean, default=False)
    apartment = db.relationship('Apartment', backref='alerts')


class Announcement(db.Model):
    """Annonces publiées par l'admin, visibles par les résidents"""
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    pinned = db.Column(db.Boolean, default=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    author = db.relationship('User', backref='announcements', lazy=True)


class AnnouncementRead(db.Model):
    """Trace la lecture d'une annonce par un résident"""
    __tablename__ = 'announcement_read'
    id = db.Column(db.Integer, primary_key=True)
    announcement_id = db.Column(db.Integer, db.ForeignKey('announcement.id', ondelete='CASCADE'), nullable=False)
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartment.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    read_at = db.Column(db.DateTime, default=datetime.utcnow)
    notified_admin = db.Column(db.Boolean, default=False)

    announcement = db.relationship('Announcement', backref='reads', lazy=True)
    apartment = db.relationship('Apartment', backref='announcement_reads', lazy=True)

    __table_args__ = (db.UniqueConstraint('announcement_id', 'user_id', name='uq_ann_read_user'),)


class AccessLog(db.Model):
    """Registre des entrées/sorties de la résidence"""
    __tablename__ = 'access_log'
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    visitor_name = db.Column(db.String(120), nullable=False)
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartment.id'), nullable=True)
    direction = db.Column(db.String(10), default='entree')   # entree / sortie
    reason = db.Column(db.String(200))
    logged_at = db.Column(db.DateTime, default=datetime.utcnow)
    logged_by = db.Column(db.String(120))
    apartment = db.relationship('Apartment', backref='access_logs', lazy=True)


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

    # Migration : nouvelles colonnes Organization (SQLite + PostgreSQL)
    is_postgres = 'postgresql' in str(db.engine.url)
    try:
        with db.engine.connect() as conn:
            if is_postgres:
                # PostgreSQL supporte ADD COLUMN IF NOT EXISTS
                pg_cols = {
                    'konnect_api_key': 'VARCHAR(200)',
                    'konnect_wallet_id': 'VARCHAR(100)',
                    'whatsapp_enabled': 'BOOLEAN DEFAULT FALSE',
                    'whatsapp_admin_phone': 'VARCHAR(20)',
                    'whatsapp_token': 'VARCHAR(200)',
                }
                for col, col_type in pg_cols.items():
                    conn.execute(db.text(
                        f"ALTER TABLE organization ADD COLUMN IF NOT EXISTS {col} {col_type}"
                    ))
                conn.commit()
                print("Migration PostgreSQL organization : colonnes Konnect/WhatsApp vérifiées.")
            else:
                # SQLite : vérification via PRAGMA
                result = conn.execute(db.text("PRAGMA table_info(organization)"))
                cols = [row[1] for row in result]
                sqlite_cols = {
                    'konnect_api_key': 'VARCHAR(200)',
                    'konnect_wallet_id': 'VARCHAR(100)',
                    'whatsapp_enabled': 'BOOLEAN DEFAULT 0',
                    'whatsapp_admin_phone': 'VARCHAR(20)',
                    'whatsapp_token': 'VARCHAR(200)',
                }
                for col, col_type in sqlite_cols.items():
                    if col not in cols:
                        conn.execute(db.text(f"ALTER TABLE organization ADD COLUMN {col} {col_type}"))
                conn.commit()
    except Exception as e:
        print(f"Migration organization : {e}")

    # Migration : table access_log
    try:
        with db.engine.connect() as conn:
            if is_postgres:
                conn.execute(db.text("""
                    CREATE TABLE IF NOT EXISTS access_log (
                        id SERIAL PRIMARY KEY,
                        organization_id INTEGER REFERENCES organization(id),
                        visitor_name VARCHAR(120) NOT NULL,
                        apartment_id INTEGER REFERENCES apartment(id),
                        direction VARCHAR(10) DEFAULT 'entree',
                        reason VARCHAR(200),
                        logged_at TIMESTAMP DEFAULT NOW(),
                        logged_by VARCHAR(120)
                    )
                """))
                conn.commit()
                print("Migration PostgreSQL : table access_log vérifiée.")
    except Exception as e:
        print(f"Migration access_log : {e}")

    # Migration : colonnes phone + last_login_at sur user
    try:
        with db.engine.connect() as conn:
            if is_postgres:
                conn.execute(db.text(
                    "ALTER TABLE \"user\" ADD COLUMN IF NOT EXISTS phone VARCHAR(20)"
                ))
                conn.execute(db.text(
                    "ALTER TABLE \"user\" ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMP"
                ))
                conn.commit()
            else:
                result = conn.execute(db.text("PRAGMA table_info(user)"))
                cols = [row[1] for row in result]
                if 'phone' not in cols:
                    conn.execute(db.text("ALTER TABLE \"user\" ADD COLUMN phone VARCHAR(20)"))
                if 'last_login_at' not in cols:
                    conn.execute(db.text("ALTER TABLE \"user\" ADD COLUMN last_login_at DATETIME"))
                conn.commit()
    except Exception as e:
        print(f"Migration user.phone/last_login_at : {e}")

    # Migration : table konnect_payment (db.create_all gère la création)
    try:
        with db.engine.connect() as conn:
            if is_postgres:
                conn.execute(db.text("""
                    CREATE TABLE IF NOT EXISTS konnect_payment (
                        id SERIAL PRIMARY KEY,
                        organization_id INTEGER REFERENCES organization(id),
                        apartment_id INTEGER REFERENCES apartment(id),
                        month_target VARCHAR(7) NOT NULL,
                        amount FLOAT NOT NULL,
                        konnect_payment_ref VARCHAR(100) UNIQUE,
                        pay_url VARCHAR(500),
                        status VARCHAR(20) DEFAULT 'pending',
                        created_by VARCHAR(20) DEFAULT 'resident',
                        created_at TIMESTAMP DEFAULT NOW(),
                        paid_at TIMESTAMP
                    )
                """))
                conn.commit()
                print("Migration PostgreSQL : table konnect_payment vérifiée.")
    except Exception as e:
        print(f"Migration konnect_payment : {e}")

    # Migration : table announcement
    try:
        with db.engine.connect() as conn:
            if is_postgres:
                conn.execute(db.text("""
                    CREATE TABLE IF NOT EXISTS announcement (
                        id SERIAL PRIMARY KEY,
                        organization_id INTEGER REFERENCES organization(id),
                        title VARCHAR(200) NOT NULL,
                        body TEXT NOT NULL,
                        pinned BOOLEAN DEFAULT FALSE,
                        created_by_id INTEGER REFERENCES "user"(id),
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """))
                conn.commit()
                print("Migration PostgreSQL : table announcement verifiee.")
    except Exception as e:
        print(f"Migration announcement : {e}")

    # Migration : table announcement_read
    try:
        with db.engine.connect() as conn:
            if is_postgres:
                conn.execute(db.text("""
                    CREATE TABLE IF NOT EXISTS announcement_read (
                        id SERIAL PRIMARY KEY,
                        announcement_id INTEGER REFERENCES announcement(id) ON DELETE CASCADE,
                        apartment_id INTEGER REFERENCES apartment(id),
                        user_id INTEGER REFERENCES "user"(id),
                        read_at TIMESTAMP DEFAULT NOW(),
                        notified_admin BOOLEAN DEFAULT FALSE,
                        CONSTRAINT uq_ann_read_user UNIQUE (announcement_id, user_id)
                    )
                """))
                conn.commit()
                print("Migration PostgreSQL : table announcement_read vérifiée.")
    except Exception as e:
        print(f"Migration announcement_read : {e}")

    # Migration sécurité : activer RLS sur toutes les tables publiques (PostgreSQL)
    # Bloque l'accès anonyme via l'URL Supabase — l'appli Flask (postgres superuser) n'est pas affectée
    try:
        with db.engine.connect() as conn:
            if is_postgres:
                tables = [
                    'organization', 'subscription', '"user"', 'block', 'apartment',
                    'payment', 'expense', 'ticket', 'super_admin_settings',
                    'konnect_payment', 'unpaid_alert', 'announcement', 'announcement_read', 'access_log'
                ]
                for table in tables:
                    conn.execute(db.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
                conn.commit()
                print("RLS activé sur toutes les tables — accès anonyme bloqué.")
    except Exception as e:
        print(f"Migration RLS : {e}")

    if not User.query.filter_by(email='superadmin@syndicpro.tn').first():
        # CRIT-003 : SUPERADMIN_PASSWORD obligatoire et >= 16 caractères
        _sa_pwd = os.environ.get('SUPERADMIN_PASSWORD', '')
        if not _sa_pwd or len(_sa_pwd) < 16:
            raise RuntimeError(
                "ERREUR CRITIQUE : SUPERADMIN_PASSWORD doit être défini "
                "dans les variables d'environnement et contenir >= 16 caractères."
            )
        superadmin = User(
            email='superadmin@syndicpro.tn',
            name='Super Administrateur',
            role='superadmin',
            organization_id=None
        )
        superadmin.set_password(_sa_pwd)
        db.session.add(superadmin)
        db.session.commit()
        print("Super Admin créé: superadmin@syndicpro.tn")
