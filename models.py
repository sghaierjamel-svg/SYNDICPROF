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
    # Paramètres Flouci (alternative à Konnect)
    flouci_app_token = db.Column(db.String(200))
    flouci_app_secret = db.Column(db.String(200))
    # Paramètres WhatsApp
    whatsapp_enabled = db.Column(db.Boolean, default=False)
    whatsapp_admin_phone = db.Column(db.String(20))
    whatsapp_token = db.Column(db.String(200))    # token API fonnte.com
    # Onboarding
    setup_dismissed = db.Column(db.Boolean, default=False)
    # Notes internes superadmin
    superadmin_notes = db.Column(db.Text, nullable=True)
    # Clé API lecteurs de badges (IoT)
    badges_api_key = db.Column(db.String(64), nullable=True)
    # Code d'invitation résident (auto-inscription)
    invite_code = db.Column(db.String(8), nullable=True, unique=True)

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
    notif_seen_at = db.Column(db.DateTime, nullable=True)   # dernière ouverture cloche

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
    parking_spot = db.Column(db.String(20), nullable=True)
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


class MiscReceipt(db.Model):
    """Encaissements divers (badges, télécommandes, clés, pénalités...)"""
    __tablename__ = 'misc_receipt'
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    libelle = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AppelFonds(db.Model):
    """Campagne d'appel de fonds pour grands travaux / réparations exceptionnelles"""
    __tablename__ = 'appel_fonds'
    id              = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    titre           = db.Column(db.String(200), nullable=False)
    description     = db.Column(db.Text)
    budget_total    = db.Column(db.Float, default=0.0)
    date_lancement  = db.Column(db.Date, nullable=True)
    date_echeance   = db.Column(db.Date, nullable=True)
    status          = db.Column(db.String(20), default='ouvert')   # ouvert / clos
    # Devis du projet (fichier joint)
    devis_data      = db.Column(db.Text)       # base64
    devis_mime      = db.Column(db.String(30))
    devis_nom       = db.Column(db.String(200))
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    quotas    = db.relationship('AppelFondsQuota',    backref='appel', cascade='all, delete-orphan', lazy=True)
    paiements = db.relationship('AppelFondsPaiement', backref='appel', cascade='all, delete-orphan', lazy=True)
    depenses  = db.relationship('AppelFondsDepense',  backref='appel', cascade='all, delete-orphan', lazy=True)


class AppelFondsQuota(db.Model):
    """Quote-part d'un appartement pour un appel de fonds"""
    __tablename__ = 'appel_fonds_quota'
    id           = db.Column(db.Integer, primary_key=True)
    appel_id     = db.Column(db.Integer, db.ForeignKey('appel_fonds.id'), nullable=False)
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartment.id'), nullable=False)
    montant_attendu = db.Column(db.Float, default=0.0)
    apartment = db.relationship('Apartment', backref='quotas_appels', lazy=True)


class AppelFondsPaiement(db.Model):
    """Paiement d'un copropriétaire pour un appel de fonds"""
    __tablename__ = 'appel_fonds_paiement'
    id              = db.Column(db.Integer, primary_key=True)
    appel_id        = db.Column(db.Integer, db.ForeignKey('appel_fonds.id'), nullable=False)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    apartment_id    = db.Column(db.Integer, db.ForeignKey('apartment.id'), nullable=False)
    amount          = db.Column(db.Float, nullable=False)
    payment_date    = db.Column(db.Date, nullable=False)
    notes           = db.Column(db.String(300))
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    apartment = db.relationship('Apartment', backref='appel_fonds_paiements', lazy=True)


class AppelFondsDepense(db.Model):
    """Dépense imputée à un fonds de travaux (paiement entrepreneur, matériau...)"""
    __tablename__ = 'appel_fonds_depense'
    id              = db.Column(db.Integer, primary_key=True)
    appel_id        = db.Column(db.Integer, db.ForeignKey('appel_fonds.id'), nullable=False)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    amount          = db.Column(db.Float, nullable=False)
    date            = db.Column(db.Date, nullable=False)
    libelle         = db.Column(db.String(200), nullable=False)
    notes           = db.Column(db.Text)
    # Facture / devis joint
    facture_data    = db.Column(db.Text)       # base64
    facture_mime    = db.Column(db.String(30))
    facture_nom     = db.Column(db.String(200))
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)


class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    expense_date = db.Column(db.Date, nullable=False)
    category = db.Column(db.String(120))
    description = db.Column(db.String(300))
    intervenant_id = db.Column(db.Integer, db.ForeignKey('intervenant.id'), nullable=True)
    facture_data = db.Column(db.Text, nullable=True)   # base64
    facture_mime = db.Column(db.String(30), nullable=True)
    facture_nom  = db.Column(db.String(200), nullable=True)
    intervenant  = db.relationship('Intervenant', backref='expenses', lazy=True)


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
    photo_data = db.Column(db.Text, nullable=True)   # base64 encodé
    photo_mime = db.Column(db.String(30), nullable=True)  # image/jpeg etc.
    user = db.relationship('User', backref='tickets')


class SuperAdminSettings(db.Model):
    """Paramètres globaux de SyndicPro (un seul enregistrement)"""
    id = db.Column(db.Integer, primary_key=True)
    konnect_api_key = db.Column(db.String(200))
    konnect_wallet_id = db.Column(db.String(100))
    last_reminder_check = db.Column(db.Date, nullable=True)  # date du dernier passage de rappels abonnement

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
    months_json = db.Column(db.Text, nullable=True)   # JSON liste mois pour paiement groupé
    apartment = db.relationship('Apartment', backref='konnect_payments', lazy=True)


class FlouciPayment(db.Model):
    """Lien de paiement Flouci généré pour un résident"""
    __tablename__ = 'flouci_payment'
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartment.id'), nullable=False)
    month_target = db.Column(db.String(7), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    flouci_payment_id = db.Column(db.String(100), unique=True)
    pay_url = db.Column(db.String(500))
    status = db.Column(db.String(20), default='pending')   # pending / completed / failed
    created_by = db.Column(db.String(20), default='resident')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    paid_at = db.Column(db.DateTime)
    apartment = db.relationship('Apartment', backref='flouci_payments', lazy=True)


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


class PushSubscription(db.Model):
    """Abonnements Web Push des utilisateurs (un par navigateur/appareil)"""
    __tablename__ = 'push_subscription'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=True)
    endpoint = db.Column(db.Text, nullable=False)
    p256dh = db.Column(db.Text, nullable=False)
    auth = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='push_subscriptions')


class DirectMessage(db.Model):
    """Messagerie directe admin ↔ résident (par appartement)"""
    __tablename__ = 'direct_message'
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartment.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    read_at = db.Column(db.DateTime, nullable=True)
    sender = db.relationship('User', backref='sent_messages', lazy=True)
    apartment = db.relationship('Apartment', backref='messages', lazy=True)


class AssemblyGeneral(db.Model):
    """Assemblée Générale de copropriété"""
    __tablename__ = 'assembly_general'
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    meeting_date = db.Column(db.DateTime, nullable=False)
    location = db.Column(db.String(200))
    status = db.Column(db.String(20), default='ouverte')  # ouverte / cloturee
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    items = db.relationship('AGItem', backref='assembly', lazy=True, cascade='all, delete-orphan')
    author = db.relationship('User', backref='assemblies', lazy=True)


class AGItem(db.Model):
    """Point à l'ordre du jour d'une AG"""
    __tablename__ = 'ag_item'
    id = db.Column(db.Integer, primary_key=True)
    assembly_id = db.Column(db.Integer, db.ForeignKey('assembly_general.id'), nullable=False)
    question = db.Column(db.String(500), nullable=False)
    order_num = db.Column(db.Integer, default=1)
    votes = db.relationship('AGVote', backref='item', lazy=True, cascade='all, delete-orphan')


class AGVote(db.Model):
    """Vote d'un résident sur un point de l'ordre du jour"""
    __tablename__ = 'ag_vote'
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('ag_item.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartment.id'), nullable=False)
    vote = db.Column(db.String(15), nullable=False)  # pour / contre / abstention
    voted_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('item_id', 'user_id', name='uq_ag_vote_user'),)


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


class Litige(db.Model):
    """Litige impayé lié à un appartement"""
    __tablename__ = 'litige'
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    apartment_id    = db.Column(db.Integer, db.ForeignKey('apartment.id'), nullable=False)
    status          = db.Column(db.String(20), default='ouvert')  # ouvert / en_cours / resolu
    opened_at       = db.Column(db.DateTime, default=datetime.utcnow)
    unpaid_count    = db.Column(db.Integer, default=0)
    amount_due      = db.Column(db.Float, default=0.0)
    huissier_id     = db.Column(db.Integer, db.ForeignKey('intervenant.id'), nullable=True)
    letter_content  = db.Column(db.Text, nullable=True)
    letter_sent_at  = db.Column(db.DateTime, nullable=True)
    accuse_data     = db.Column(db.Text, nullable=True)   # base64
    accuse_mime     = db.Column(db.String(30), nullable=True)
    accuse_nom      = db.Column(db.String(200), nullable=True)
    decharge_data   = db.Column(db.Text, nullable=True)   # base64
    decharge_mime   = db.Column(db.String(30), nullable=True)
    decharge_nom    = db.Column(db.String(200), nullable=True)
    notes           = db.Column(db.Text, nullable=True)
    apartment       = db.relationship('Apartment', backref='litiges', lazy=True)
    huissier        = db.relationship('Intervenant', backref='litiges_geres', lazy=True)


class AutreLitige(db.Model):
    """Dossier de litige divers (voisinage, sinistre, prestataire...)"""
    __tablename__ = 'autre_litige'
    id              = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    titre           = db.Column(db.String(200), nullable=False)
    description     = db.Column(db.Text, nullable=True)
    status          = db.Column(db.String(20), default='ouvert')  # ouvert / en_cours / resolu
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    documents       = db.relationship('LitigeDocument', backref='dossier', lazy=True,
                                      cascade='all, delete-orphan')


class LitigeDocument(db.Model):
    """Document scanné rattaché à un dossier de litige"""
    __tablename__ = 'litige_document'
    id          = db.Column(db.Integer, primary_key=True)
    litige_id   = db.Column(db.Integer, db.ForeignKey('autre_litige.id'), nullable=False)
    nom         = db.Column(db.String(200), nullable=False)
    data        = db.Column(db.Text, nullable=False)   # base64
    mime        = db.Column(db.String(30), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


class Camera(db.Model):
    """Caméra de surveillance de la résidence"""
    __tablename__ = 'camera'
    id              = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    nom             = db.Column(db.String(100), nullable=False)
    localisation    = db.Column(db.String(200))
    marque          = db.Column(db.String(100))
    url_acces       = db.Column(db.String(500))      # interface web ou lien cloud
    url_snapshot    = db.Column(db.String(500))      # URL image/snapshot directe
    identifiant     = db.Column(db.String(100))
    mot_de_passe    = db.Column(db.String(200))
    notes           = db.Column(db.Text)
    actif           = db.Column(db.Boolean, default=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)


class Intervenant(db.Model):
    """Annuaire des prestataires et intervenants de la résidence"""
    __tablename__ = 'intervenant'
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    categorie = db.Column(db.String(60), nullable=False)
    nom_societe = db.Column(db.String(200))
    prenom = db.Column(db.String(100))
    nom = db.Column(db.String(100))
    telephone = db.Column(db.String(25))
    email = db.Column(db.String(120))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Lift(db.Model):
    """Ascenseur d'une résidence"""
    __tablename__ = 'lift'
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    block_id = db.Column(db.Integer, db.ForeignKey('block.id'), nullable=True)
    name = db.Column(db.String(100), nullable=False)          # ex: "Ascenseur Bât A"
    location = db.Column(db.String(200))                       # ex: "Entrée principale"
    status = db.Column(db.String(20), default='ok')            # ok / warning / down
    iot_api_key = db.Column(db.String(64), unique=True)        # clé secrète capteur IoT
    last_maintenance = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    block = db.relationship('Block', backref='lifts', lazy=True)
    incidents = db.relationship('LiftIncident', backref='lift', lazy=True, cascade='all, delete-orphan')


class LiftIncident(db.Model):
    """Incident / panne signalé sur un ascenseur"""
    __tablename__ = 'lift_incident'
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    lift_id = db.Column(db.Integer, db.ForeignKey('lift.id'), nullable=False)
    reported_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)   # résident ou admin
    intervenant_id = db.Column(db.Integer, db.ForeignKey('intervenant.id'), nullable=True)  # réparateur assigné
    source = db.Column(db.String(20), default='manuel')        # manuel / iot
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='ouvert')        # ouvert / en_cours / resolu
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)
    admin_notes = db.Column(db.Text)
    reported_by = db.relationship('User', backref='lift_incidents', lazy=True)
    intervenant = db.relationship('Intervenant', backref='lift_incidents', lazy=True)


class PaymentRequest(db.Model):
    """Demande de virement bancaire soumise par un résident — confirmée par l'admin en 1 clic"""
    __tablename__ = 'payment_request'
    id              = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    apartment_id    = db.Column(db.Integer, db.ForeignKey('apartment.id'), nullable=False)
    user_id         = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    month_target    = db.Column(db.String(7), nullable=False)    # YYYY-MM
    amount_declared = db.Column(db.Float, nullable=False)        # montant déclaré par le résident
    bank_reference  = db.Column(db.String(200))                  # référence virement
    # Photo de la décharge / reçu bancaire
    photo_data      = db.Column(db.Text)                         # base64
    photo_mime      = db.Column(db.String(30))
    # Token sécurisé pour lien de confirmation admin
    confirm_token   = db.Column(db.String(64), unique=True, nullable=False)
    # Statut : en_attente / confirme / rejete
    status          = db.Column(db.String(20), default='en_attente')
    # Données de confirmation (remplies par admin)
    amount_confirmed = db.Column(db.Float)                       # montant réellement reçu
    bank_fees        = db.Column(db.Float, default=0.0)          # frais bancaires déduits
    admin_notes      = db.Column(db.Text)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    confirmed_at    = db.Column(db.DateTime)
    apartment = db.relationship('Apartment', backref='payment_requests', lazy=True)
    user      = db.relationship('User', backref='payment_requests', lazy=True)


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


class Badge(db.Model):
    """Badge d'accès physique (carte, clé RFID) attribué à un résident"""
    __tablename__ = 'badge'
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    badge_number = db.Column(db.String(50), nullable=False)   # numéro imprimé sur le badge
    resident_id   = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    status = db.Column(db.String(20), default='actif')        # actif / bloqué / perdu / révoqué
    issued_at  = db.Column(db.DateTime, default=datetime.utcnow)
    blocked_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    resident = db.relationship('User', backref='badges', lazy=True)


class BadgeAccessLog(db.Model):
    """Journal automatique des passages enregistrés par les lecteurs de badges"""
    __tablename__ = 'badge_access_log'
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    badge_id      = db.Column(db.Integer, db.ForeignKey('badge.id'), nullable=True)
    badge_number  = db.Column(db.String(50), nullable=False)  # conservé même si badge inconnu
    access_point  = db.Column(db.String(100), nullable=False) # entree_principale / ascenseur_A / parking…
    direction     = db.Column(db.String(10), default='entree')# entree / sortie
    access_granted = db.Column(db.Boolean, default=True)      # autorisé ou refusé
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    badge = db.relationship('Badge', backref='access_logs', lazy=True)


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
            if 'parking_spot' not in columns:
                conn.execute(db.text("ALTER TABLE apartment ADD COLUMN parking_spot VARCHAR(20)"))
                conn.commit()
                print("Colonne parking_spot ajoutée à la table apartment")

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
                    'flouci_app_token': 'VARCHAR(200)',
                    'flouci_app_secret': 'VARCHAR(200)',
                    'setup_dismissed': 'BOOLEAN DEFAULT FALSE',
                    'badges_api_key': 'VARCHAR(64)',
                    'invite_code': 'VARCHAR(8)',
                }
                for col, col_type in pg_cols.items():
                    conn.execute(db.text(
                        f"ALTER TABLE organization ADD COLUMN IF NOT EXISTS {col} {col_type}"
                    ))
                conn.commit()
                print("Migration PostgreSQL organization : colonnes Konnect/WhatsApp/setup vérifiées.")
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
                    'flouci_app_token': 'VARCHAR(200)',
                    'flouci_app_secret': 'VARCHAR(200)',
                    'setup_dismissed': 'BOOLEAN DEFAULT 0',
                    'badges_api_key': 'VARCHAR(64)',
                    'invite_code': 'VARCHAR(8)',
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

    # Migration : tables badge + badge_access_log (PostgreSQL)
    try:
        with db.engine.connect() as conn:
            if is_postgres:
                conn.execute(db.text("""
                    CREATE TABLE IF NOT EXISTS badge (
                        id SERIAL PRIMARY KEY,
                        organization_id INTEGER REFERENCES organization(id),
                        badge_number VARCHAR(50) NOT NULL,
                        resident_id INTEGER REFERENCES "user"(id),
                        status VARCHAR(20) DEFAULT 'actif',
                        issued_at TIMESTAMP DEFAULT NOW(),
                        blocked_at TIMESTAMP,
                        notes TEXT
                    )
                """))
                conn.execute(db.text("""
                    CREATE TABLE IF NOT EXISTS badge_access_log (
                        id SERIAL PRIMARY KEY,
                        organization_id INTEGER REFERENCES organization(id),
                        badge_id INTEGER REFERENCES badge(id),
                        badge_number VARCHAR(50) NOT NULL,
                        access_point VARCHAR(100) NOT NULL,
                        direction VARCHAR(10) DEFAULT 'entree',
                        access_granted BOOLEAN DEFAULT TRUE,
                        timestamp TIMESTAMP DEFAULT NOW()
                    )
                """))
                conn.commit()
                print("Migration PostgreSQL : tables badge + badge_access_log vérifiées.")
    except Exception as e:
        print(f"Migration badge : {e}")

    # Migration : colonne parking_spot sur apartment (PostgreSQL)
    try:
        with db.engine.connect() as conn:
            if is_postgres:
                conn.execute(db.text(
                    "ALTER TABLE apartment ADD COLUMN IF NOT EXISTS parking_spot VARCHAR(20)"
                ))
                conn.commit()
                print("Migration PostgreSQL apartment.parking_spot : OK")
    except Exception as e:
        print(f"Migration apartment.parking_spot : {e}")

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
                conn.execute(db.text(
                    "ALTER TABLE \"user\" ADD COLUMN IF NOT EXISTS notif_seen_at TIMESTAMP"
                ))
                conn.commit()
            else:
                result = conn.execute(db.text("PRAGMA table_info(user)"))
                cols = [row[1] for row in result]
                if 'phone' not in cols:
                    conn.execute(db.text("ALTER TABLE \"user\" ADD COLUMN phone VARCHAR(20)"))
                if 'last_login_at' not in cols:
                    conn.execute(db.text("ALTER TABLE \"user\" ADD COLUMN last_login_at DATETIME"))
                if 'notif_seen_at' not in cols:
                    conn.execute(db.text("ALTER TABLE \"user\" ADD COLUMN notif_seen_at DATETIME"))
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

    # Migration : colonne months_json sur konnect_payment (paiement groupé)
    try:
        with db.engine.connect() as conn:
            if is_postgres:
                conn.execute(db.text(
                    "ALTER TABLE konnect_payment ADD COLUMN IF NOT EXISTS months_json TEXT"
                ))
                conn.commit()
            else:
                result = conn.execute(db.text("PRAGMA table_info(konnect_payment)"))
                if 'months_json' not in [r[1] for r in result]:
                    conn.execute(db.text("ALTER TABLE konnect_payment ADD COLUMN months_json TEXT"))
                    conn.commit()
    except Exception as e:
        print(f"Migration konnect_payment.months_json : {e}")

    # Générer invite_code pour les organisations qui n'en ont pas encore
    try:
        import secrets as _secrets
        orgs_sans_code = Organization.query.filter(Organization.invite_code.is_(None)).all()
        for _org in orgs_sans_code:
            _code = _secrets.token_hex(4).upper()
            while Organization.query.filter_by(invite_code=_code).first():
                _code = _secrets.token_hex(4).upper()
            _org.invite_code = _code
        if orgs_sans_code:
            db.session.commit()
            print(f"invite_code généré pour {len(orgs_sans_code)} organisation(s).")
    except Exception as e:
        print(f"Génération invite_code : {e}")

    # Migration : table flouci_payment
    try:
        with db.engine.connect() as conn:
            if is_postgres:
                conn.execute(db.text("""
                    CREATE TABLE IF NOT EXISTS flouci_payment (
                        id SERIAL PRIMARY KEY,
                        organization_id INTEGER REFERENCES organization(id),
                        apartment_id INTEGER REFERENCES apartment(id),
                        month_target VARCHAR(7) NOT NULL,
                        amount FLOAT NOT NULL,
                        flouci_payment_id VARCHAR(100) UNIQUE,
                        pay_url VARCHAR(500),
                        status VARCHAR(20) DEFAULT 'pending',
                        created_by VARCHAR(20) DEFAULT 'resident',
                        created_at TIMESTAMP DEFAULT NOW(),
                        paid_at TIMESTAMP
                    )
                """))
                conn.commit()
                print("Migration PostgreSQL : table flouci_payment vérifiée.")
    except Exception as e:
        print(f"Migration flouci_payment : {e}")

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

    # Migration : colonnes photo sur ticket
    try:
        with db.engine.connect() as conn:
            if is_postgres:
                conn.execute(db.text("ALTER TABLE ticket ADD COLUMN IF NOT EXISTS photo_data TEXT"))
                conn.execute(db.text("ALTER TABLE ticket ADD COLUMN IF NOT EXISTS photo_mime VARCHAR(30)"))
                conn.commit()
            else:
                result = conn.execute(db.text("PRAGMA table_info(ticket)"))
                cols = [row[1] for row in result]
                if 'photo_data' not in cols:
                    conn.execute(db.text("ALTER TABLE ticket ADD COLUMN photo_data TEXT"))
                if 'photo_mime' not in cols:
                    conn.execute(db.text("ALTER TABLE ticket ADD COLUMN photo_mime VARCHAR(30)"))
                conn.commit()
    except Exception as e:
        print(f"Migration ticket photo : {e}")

    # Migration : table direct_message
    try:
        with db.engine.connect() as conn:
            if is_postgres:
                conn.execute(db.text("""
                    CREATE TABLE IF NOT EXISTS direct_message (
                        id SERIAL PRIMARY KEY,
                        organization_id INTEGER REFERENCES organization(id),
                        apartment_id INTEGER REFERENCES apartment(id),
                        sender_id INTEGER REFERENCES "user"(id),
                        body TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT NOW(),
                        read_at TIMESTAMP
                    )
                """))
            else:
                conn.execute(db.text("""
                    CREATE TABLE IF NOT EXISTS direct_message (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        organization_id INTEGER REFERENCES organization(id),
                        apartment_id INTEGER REFERENCES apartment(id),
                        sender_id INTEGER REFERENCES user(id),
                        body TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        read_at TIMESTAMP
                    )
                """))
            conn.commit()
    except Exception as e:
        print(f"Migration direct_message : {e}")

    # Migration : tables AG
    try:
        with db.engine.connect() as conn:
            if is_postgres:
                conn.execute(db.text("""
                    CREATE TABLE IF NOT EXISTS assembly_general (
                        id SERIAL PRIMARY KEY,
                        organization_id INTEGER REFERENCES organization(id),
                        title VARCHAR(200) NOT NULL,
                        description TEXT,
                        meeting_date TIMESTAMP NOT NULL,
                        location VARCHAR(200),
                        status VARCHAR(20) DEFAULT 'ouverte',
                        created_at TIMESTAMP DEFAULT NOW(),
                        created_by_id INTEGER REFERENCES "user"(id)
                    )
                """))
                conn.execute(db.text("""
                    CREATE TABLE IF NOT EXISTS ag_item (
                        id SERIAL PRIMARY KEY,
                        assembly_id INTEGER REFERENCES assembly_general(id) ON DELETE CASCADE,
                        question VARCHAR(500) NOT NULL,
                        order_num INTEGER DEFAULT 1
                    )
                """))
                conn.execute(db.text("""
                    CREATE TABLE IF NOT EXISTS ag_vote (
                        id SERIAL PRIMARY KEY,
                        item_id INTEGER REFERENCES ag_item(id) ON DELETE CASCADE,
                        user_id INTEGER REFERENCES "user"(id),
                        apartment_id INTEGER REFERENCES apartment(id),
                        vote VARCHAR(15) NOT NULL,
                        voted_at TIMESTAMP DEFAULT NOW(),
                        CONSTRAINT uq_ag_vote_user UNIQUE (item_id, user_id)
                    )
                """))
                conn.commit()
                print("Migration PostgreSQL : tables AG créées.")
    except Exception as e:
        print(f"Migration AG : {e}")

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

    # Migration : table misc_receipt
    try:
        with db.engine.connect() as conn:
            if is_postgres:
                conn.execute(db.text("""
                    CREATE TABLE IF NOT EXISTS misc_receipt (
                        id SERIAL PRIMARY KEY,
                        organization_id INTEGER REFERENCES organization(id),
                        amount FLOAT NOT NULL,
                        payment_date DATE NOT NULL,
                        libelle VARCHAR(100) NOT NULL,
                        description VARCHAR(300),
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """))
                conn.commit()
                print("Migration PostgreSQL : table misc_receipt créée.")
    except Exception as e:
        print(f"Migration misc_receipt : {e}")

    # Migration : colonnes facture + intervenant_id sur expense (PostgreSQL)
    try:
        with db.engine.connect() as conn:
            if is_postgres:
                conn.execute(db.text("ALTER TABLE expense ADD COLUMN IF NOT EXISTS intervenant_id INTEGER REFERENCES intervenant(id)"))
                conn.execute(db.text("ALTER TABLE expense ADD COLUMN IF NOT EXISTS facture_data TEXT"))
                conn.execute(db.text("ALTER TABLE expense ADD COLUMN IF NOT EXISTS facture_mime VARCHAR(30)"))
                conn.execute(db.text("ALTER TABLE expense ADD COLUMN IF NOT EXISTS facture_nom VARCHAR(200)"))
                conn.commit()
                print("Migration PostgreSQL expense : colonnes facture/intervenant OK")
            else:
                result = conn.execute(db.text("PRAGMA table_info(expense)"))
                cols = [row[1] for row in result]
                for col, col_type in [
                    ('intervenant_id', 'INTEGER'),
                    ('facture_data', 'TEXT'),
                    ('facture_mime', 'VARCHAR(30)'),
                    ('facture_nom', 'VARCHAR(200)'),
                ]:
                    if col not in cols:
                        conn.execute(db.text(f"ALTER TABLE expense ADD COLUMN {col} {col_type}"))
                conn.commit()
    except Exception as e:
        print(f"Migration expense facture : {e}")

    # Migration : tables litiges
    try:
        with db.engine.connect() as conn:
            if is_postgres:
                conn.execute(db.text("""
                    CREATE TABLE IF NOT EXISTS litige (
                        id SERIAL PRIMARY KEY,
                        organization_id INTEGER REFERENCES organization(id),
                        apartment_id INTEGER REFERENCES apartment(id),
                        status VARCHAR(20) DEFAULT 'ouvert',
                        opened_at TIMESTAMP DEFAULT NOW(),
                        unpaid_count INTEGER DEFAULT 0,
                        amount_due FLOAT DEFAULT 0,
                        huissier_id INTEGER REFERENCES intervenant(id),
                        letter_content TEXT,
                        letter_sent_at TIMESTAMP,
                        accuse_data TEXT, accuse_mime VARCHAR(30), accuse_nom VARCHAR(200),
                        decharge_data TEXT, decharge_mime VARCHAR(30), decharge_nom VARCHAR(200),
                        notes TEXT
                    )
                """))
                conn.execute(db.text("""
                    CREATE TABLE IF NOT EXISTS autre_litige (
                        id SERIAL PRIMARY KEY,
                        organization_id INTEGER REFERENCES organization(id),
                        titre VARCHAR(200) NOT NULL,
                        description TEXT,
                        status VARCHAR(20) DEFAULT 'ouvert',
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """))
                conn.execute(db.text("""
                    CREATE TABLE IF NOT EXISTS litige_document (
                        id SERIAL PRIMARY KEY,
                        litige_id INTEGER REFERENCES autre_litige(id) ON DELETE CASCADE,
                        nom VARCHAR(200) NOT NULL,
                        data TEXT NOT NULL,
                        mime VARCHAR(30) NOT NULL,
                        uploaded_at TIMESTAMP DEFAULT NOW()
                    )
                """))
                conn.commit()
                print("Migration PostgreSQL : tables litiges créées.")
    except Exception as e:
        print(f"Migration litiges : {e}")

    # Migration : tables appel de fonds
    try:
        with db.engine.connect() as conn:
            if is_postgres:
                conn.execute(db.text("""
                    CREATE TABLE IF NOT EXISTS appel_fonds (
                        id SERIAL PRIMARY KEY,
                        organization_id INTEGER REFERENCES organization(id),
                        titre VARCHAR(200) NOT NULL,
                        description TEXT,
                        budget_total FLOAT DEFAULT 0,
                        date_lancement DATE,
                        date_echeance DATE,
                        status VARCHAR(20) DEFAULT 'ouvert',
                        devis_data TEXT,
                        devis_mime VARCHAR(30),
                        devis_nom VARCHAR(200),
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """))
                conn.execute(db.text("""
                    CREATE TABLE IF NOT EXISTS appel_fonds_quota (
                        id SERIAL PRIMARY KEY,
                        appel_id INTEGER REFERENCES appel_fonds(id) ON DELETE CASCADE,
                        apartment_id INTEGER REFERENCES apartment(id) ON DELETE CASCADE,
                        montant_attendu FLOAT DEFAULT 0
                    )
                """))
                conn.execute(db.text("""
                    CREATE TABLE IF NOT EXISTS appel_fonds_paiement (
                        id SERIAL PRIMARY KEY,
                        appel_id INTEGER REFERENCES appel_fonds(id) ON DELETE CASCADE,
                        organization_id INTEGER REFERENCES organization(id),
                        apartment_id INTEGER REFERENCES apartment(id),
                        amount FLOAT NOT NULL,
                        payment_date DATE NOT NULL,
                        notes VARCHAR(300),
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """))
                conn.execute(db.text("""
                    CREATE TABLE IF NOT EXISTS appel_fonds_depense (
                        id SERIAL PRIMARY KEY,
                        appel_id INTEGER REFERENCES appel_fonds(id) ON DELETE CASCADE,
                        organization_id INTEGER REFERENCES organization(id),
                        amount FLOAT NOT NULL,
                        date DATE NOT NULL,
                        libelle VARCHAR(200) NOT NULL,
                        notes TEXT,
                        facture_data TEXT,
                        facture_mime VARCHAR(30),
                        facture_nom VARCHAR(200),
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """))
                conn.commit()
                print("Migration PostgreSQL : tables appel_fonds créées.")
    except Exception as e:
        print(f"Migration appel_fonds : {e}")

    # Migration : table camera
    try:
        with db.engine.connect() as conn:
            if is_postgres:
                conn.execute(db.text("""
                    CREATE TABLE IF NOT EXISTS camera (
                        id SERIAL PRIMARY KEY,
                        organization_id INTEGER REFERENCES organization(id),
                        nom VARCHAR(100) NOT NULL,
                        localisation VARCHAR(200),
                        marque VARCHAR(100),
                        url_acces VARCHAR(500),
                        url_snapshot VARCHAR(500),
                        identifiant VARCHAR(100),
                        mot_de_passe VARCHAR(200),
                        notes TEXT,
                        actif BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """))
                conn.commit()
                print("Migration PostgreSQL : table camera créée.")
    except Exception as e:
        print(f"Migration camera : {e}")

    # Migration : table intervenant
    try:
        with db.engine.connect() as conn:
            if is_postgres:
                conn.execute(db.text("""
                    CREATE TABLE IF NOT EXISTS intervenant (
                        id SERIAL PRIMARY KEY,
                        organization_id INTEGER REFERENCES organization(id),
                        categorie VARCHAR(60) NOT NULL,
                        nom_societe VARCHAR(200),
                        prenom VARCHAR(100),
                        nom VARCHAR(100),
                        telephone VARCHAR(25),
                        email VARCHAR(120),
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """))
                conn.commit()
                print("Migration PostgreSQL : table intervenant créée.")
    except Exception as e:
        print(f"Migration intervenant : {e}")

    # Migration : table push_subscription
    try:
        with db.engine.connect() as conn:
            if is_postgres:
                conn.execute(db.text("""
                    CREATE TABLE IF NOT EXISTS push_subscription (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER REFERENCES "user"(id) ON DELETE CASCADE,
                        organization_id INTEGER REFERENCES organization(id) ON DELETE CASCADE,
                        endpoint TEXT NOT NULL,
                        p256dh TEXT NOT NULL,
                        auth TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """))
                conn.commit()
            else:
                conn.execute(db.text("""
                    CREATE TABLE IF NOT EXISTS push_subscription (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER REFERENCES user(id),
                        organization_id INTEGER REFERENCES organization(id),
                        endpoint TEXT NOT NULL,
                        p256dh TEXT NOT NULL,
                        auth TEXT NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                conn.commit()
    except Exception as e:
        print(f"Migration push_subscription : {e}")

    # Migration : tables lift + lift_incident
    try:
        with db.engine.connect() as conn:
            if is_postgres:
                conn.execute(db.text("""
                    CREATE TABLE IF NOT EXISTS lift (
                        id SERIAL PRIMARY KEY,
                        organization_id INTEGER REFERENCES organization(id) ON DELETE CASCADE,
                        block_id INTEGER REFERENCES block(id) ON DELETE SET NULL,
                        name VARCHAR(100) NOT NULL,
                        location VARCHAR(200),
                        status VARCHAR(20) DEFAULT 'ok',
                        iot_api_key VARCHAR(64) UNIQUE,
                        last_maintenance DATE,
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """))
                conn.execute(db.text("""
                    CREATE TABLE IF NOT EXISTS lift_incident (
                        id SERIAL PRIMARY KEY,
                        organization_id INTEGER REFERENCES organization(id) ON DELETE CASCADE,
                        lift_id INTEGER REFERENCES lift(id) ON DELETE CASCADE,
                        reported_by_id INTEGER REFERENCES "user"(id) ON DELETE SET NULL,
                        intervenant_id INTEGER REFERENCES intervenant(id) ON DELETE SET NULL,
                        source VARCHAR(20) DEFAULT 'manuel',
                        description TEXT NOT NULL,
                        status VARCHAR(20) DEFAULT 'ouvert',
                        created_at TIMESTAMP DEFAULT NOW(),
                        resolved_at TIMESTAMP,
                        admin_notes TEXT
                    )
                """))
                conn.commit()
            else:
                conn.execute(db.text("""
                    CREATE TABLE IF NOT EXISTS lift (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        organization_id INTEGER, block_id INTEGER,
                        name VARCHAR(100) NOT NULL, location VARCHAR(200),
                        status VARCHAR(20) DEFAULT 'ok', iot_api_key VARCHAR(64),
                        last_maintenance DATE, notes TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                conn.execute(db.text("""
                    CREATE TABLE IF NOT EXISTS lift_incident (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        organization_id INTEGER, lift_id INTEGER,
                        reported_by_id INTEGER, intervenant_id INTEGER,
                        source VARCHAR(20) DEFAULT 'manuel',
                        description TEXT NOT NULL, status VARCHAR(20) DEFAULT 'ouvert',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        resolved_at DATETIME, admin_notes TEXT
                    )
                """))
                conn.commit()
            print("Migration : tables lift + lift_incident OK")
    except Exception as e:
        print(f"Migration lift : {e}")

    # Migration : colonne last_reminder_check sur super_admin_settings
    try:
        with db.engine.connect() as conn:
            if is_postgres:
                conn.execute(db.text(
                    "ALTER TABLE super_admin_settings ADD COLUMN IF NOT EXISTS last_reminder_check DATE"
                ))
                conn.commit()
            else:
                result = conn.execute(db.text("PRAGMA table_info(super_admin_settings)"))
                cols = [row[1] for row in result]
                if 'last_reminder_check' not in cols:
                    conn.execute(db.text("ALTER TABLE super_admin_settings ADD COLUMN last_reminder_check DATE"))
                    conn.commit()
    except Exception as e:
        print(f"Migration super_admin_settings last_reminder_check : {e}")

    # Migration : colonne superadmin_notes sur organization
    try:
        with db.engine.connect() as conn:
            if is_postgres:
                conn.execute(db.text(
                    "ALTER TABLE organization ADD COLUMN IF NOT EXISTS superadmin_notes TEXT"
                ))
                conn.commit()
            else:
                result = conn.execute(db.text("PRAGMA table_info(organization)"))
                cols = [row[1] for row in result]
                if 'superadmin_notes' not in cols:
                    conn.execute(db.text("ALTER TABLE organization ADD COLUMN superadmin_notes TEXT"))
                    conn.commit()
    except Exception as e:
        print(f"Migration organization.superadmin_notes : {e}")

    # Migration : table payment_request
    try:
        with db.engine.connect() as conn:
            if is_postgres:
                conn.execute(db.text("""
                    CREATE TABLE IF NOT EXISTS payment_request (
                        id SERIAL PRIMARY KEY,
                        organization_id INTEGER REFERENCES organization(id) ON DELETE CASCADE,
                        apartment_id INTEGER REFERENCES apartment(id) ON DELETE CASCADE,
                        user_id INTEGER REFERENCES "user"(id) ON DELETE CASCADE,
                        month_target VARCHAR(7) NOT NULL,
                        amount_declared FLOAT NOT NULL,
                        bank_reference VARCHAR(200),
                        photo_data TEXT,
                        photo_mime VARCHAR(30),
                        confirm_token VARCHAR(64) UNIQUE NOT NULL,
                        status VARCHAR(20) DEFAULT 'en_attente',
                        amount_confirmed FLOAT,
                        bank_fees FLOAT DEFAULT 0,
                        admin_notes TEXT,
                        created_at TIMESTAMP DEFAULT NOW(),
                        confirmed_at TIMESTAMP
                    )
                """))
                conn.commit()
            else:
                conn.execute(db.text("""
                    CREATE TABLE IF NOT EXISTS payment_request (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        organization_id INTEGER, apartment_id INTEGER, user_id INTEGER,
                        month_target VARCHAR(7) NOT NULL,
                        amount_declared FLOAT NOT NULL,
                        bank_reference VARCHAR(200),
                        photo_data TEXT, photo_mime VARCHAR(30),
                        confirm_token VARCHAR(64) UNIQUE NOT NULL,
                        status VARCHAR(20) DEFAULT 'en_attente',
                        amount_confirmed FLOAT, bank_fees FLOAT DEFAULT 0,
                        admin_notes TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        confirmed_at DATETIME
                    )
                """))
                conn.commit()
            print("Migration : table payment_request OK")
    except Exception as e:
        print(f"Migration payment_request : {e}")

    # Migration sécurité : activer RLS sur toutes les tables publiques (PostgreSQL)
    # Bloque l'accès anonyme via l'URL Supabase — l'appli Flask (postgres superuser) n'est pas affectée
    try:
        with db.engine.connect() as conn:
            if is_postgres:
                tables = [
                    'organization', 'subscription', '"user"', 'block', 'apartment',
                    'payment', 'expense', 'ticket', 'super_admin_settings',
                    'konnect_payment', 'flouci_payment', 'unpaid_alert', 'announcement', 'announcement_read', 'access_log',
                    'direct_message', 'assembly_general', 'ag_item', 'ag_vote', 'intervenant',
                    'litige', 'autre_litige', 'litige_document', 'misc_receipt', 'camera',
                    'appel_fonds', 'appel_fonds_quota', 'appel_fonds_paiement', 'appel_fonds_depense',
                    'payment_request'
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
