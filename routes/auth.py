from flask import render_template, request, redirect, url_for, session, flash
from core import app, limiter
from models import User, Organization, Subscription, Apartment, Block
from utils import current_user
from datetime import datetime, timedelta
import re
import secrets


@app.route('/')
def index():
    """Page d'accueil avec choix : Se connecter ou S'inscrire"""
    if current_user():
        user = current_user()
        if user.role == 'superadmin':
            return redirect(url_for('superadmin_dashboard'))
        else:
            return redirect(url_for('dashboard'))
    return render_template('index.html')


@app.route('/demo')
def demo():
    """Page de démonstration publique"""
    return render_template('demo.html')


@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute", error_message="Trop de tentatives. Réessayez dans 1 minute.")
def login():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        pwd = request.form['password']
        # Cherche TOUS les comptes avec cet email (multi-résidences)
        candidates = User.query.filter_by(email=email).all()
        matched = [u for u in candidates if u.check_password(pwd)]

        if not matched:
            flash('Email ou mot de passe incorrect', 'danger')
            return render_template('login.html')

        # Cas 1 : un seul compte → connexion directe
        if len(matched) == 1:
            return _do_login(matched[0])

        # Cas 2 : plusieurs résidences → sélection
        session['pending_user_ids'] = [u.id for u in matched]
        return redirect(url_for('select_org'))

    return render_template('login.html')


def _do_login(user):
    """Finalise la connexion pour un utilisateur donné."""
    if user.role != 'superadmin':
        if not user.organization_id:
            flash('Utilisateur non affecté à une organisation.', 'danger')
            return redirect(url_for('login'))
        org = Organization.query.get(user.organization_id)
        if not org or not org.is_active:
            flash('Organisation désactivée. Contactez le support.', 'danger')
            return redirect(url_for('login'))
    session.pop('pending_user_ids', None)
    session['user_id'] = user.id
    session.permanent = True
    session['last_activity'] = datetime.utcnow().isoformat()
    user.last_login_at = datetime.utcnow()
    from core import db as _db
    _db.session.commit()
    flash('Connecté avec succès', 'success')
    if user.role == 'superadmin':
        return redirect(url_for('superadmin_dashboard'))
    return redirect(url_for('dashboard'))


@app.route('/select-org', methods=['GET', 'POST'])
def select_org():
    """Page de sélection de résidence quand un email est lié à plusieurs organisations."""
    pending_ids = session.get('pending_user_ids', [])
    if not pending_ids:
        return redirect(url_for('login'))

    users = User.query.filter(User.id.in_(pending_ids)).all()
    # Enrichit avec l'organisation
    choices = []
    for u in users:
        org = Organization.query.get(u.organization_id) if u.organization_id else None
        if org and org.is_active:
            choices.append({'user': u, 'org': org})

    if not choices:
        session.pop('pending_user_ids', None)
        flash('Aucune organisation active trouvée.', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        chosen_id = request.form.get('user_id', type=int)
        user = next((c['user'] for c in choices if c['user'].id == chosen_id), None)
        if not user:
            flash('Sélection invalide.', 'danger')
            return render_template('select_org.html', choices=choices)
        return _do_login(user)

    return render_template('select_org.html', choices=choices)


@app.route('/logout')
def logout():
    session.clear()
    flash('Déconnecté', 'info')
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
@limiter.limit("3 per minute", methods=['POST'], error_message="Trop de tentatives. Réessayez dans 1 minute.")
def register():
    from core import db
    if request.method == 'POST':
        org_name = request.form['org_name'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()
        if len(password) < 8:
            flash('Le mot de passe doit contenir au moins 8 caractères.', 'danger')
            return redirect(url_for('register'))
        if not re.search(r'[0-9]', password):
            flash('Le mot de passe doit contenir au moins 1 chiffre.', 'danger')
            return redirect(url_for('register'))
        if not re.search(r'[A-Z]', password):
            flash('Le mot de passe doit contenir au moins 1 lettre majuscule.', 'danger')
            return redirect(url_for('register'))
        # Si l'email existe déjà, le mot de passe DOIT correspondre à l'existant
        # (toutes les résidences d'un même email partagent le même mot de passe)
        existing_user = User.query.filter_by(email=email).first()
        if existing_user and not existing_user.check_password(password):
            flash('Cet email gère déjà une résidence SyndicPro. Utilisez votre mot de passe habituel pour créer une nouvelle résidence.', 'warning')
            return redirect(url_for('register'))
        # Un même email peut gérer plusieurs résidences — pas de blocage global
        base_slug = org_name.lower().replace(' ', '-').replace('é', 'e').replace('è', 'e')
        slug = base_slug
        counter = 1
        while Organization.query.filter_by(slug=slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1
        # Générer un code d'invitation unique pour les résidents
        invite_code = secrets.token_hex(4).upper()
        while Organization.query.filter_by(invite_code=invite_code).first():
            invite_code = secrets.token_hex(4).upper()

        org = Organization(
            name=org_name,
            slug=slug,
            email=email,
            phone=phone,
            address=address,
            is_active=True,
            invite_code=invite_code,
        )
        db.session.add(org)
        db.session.flush()
        subscription = Subscription(
            organization_id=org.id,
            plan='trial',
            status='active',
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=90),
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
        try:
            from utils_email import send_welcome_admin
            send_welcome_admin(org_name=org_name, email=email, days_trial=90)
        except Exception as _e:
            print(f"[register] Email bienvenue non envoyé : {_e}")
        return redirect(url_for('bienvenue', org=org_name, email=email))
    return render_template('register.html')


# ─────────────────────────────────────────────────────────────────────────────
#  Auto-inscription résident via code de résidence
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/register-resident', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=['POST'], error_message="Trop de tentatives. Réessayez dans 1 minute.")
def register_resident():
    from core import db
    if current_user():
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email        = request.form.get('email', '').strip().lower()
        invite_code  = request.form.get('invite_code', '').strip().upper()
        apt_input    = request.form.get('apartment', '').strip()   # ex: "A-101" ou "101"

        # ── Validation de base ──────────────────────────────────────────────
        if not email or not invite_code or not apt_input:
            flash("Tous les champs sont obligatoires.", "danger")
            return render_template('register_resident.html')

        # ── Trouver l'organisation via le code ──────────────────────────────
        org = Organization.query.filter_by(invite_code=invite_code).first()
        if not org or not org.is_active:
            flash("Code de résidence invalide ou résidence inactive.", "danger")
            return render_template('register_resident.html')

        # ── Retrouver l'appartement ─────────────────────────────────────────
        # Format accepté : "A-101" (bloc-numéro) ou "101" (numéro seul)
        block_name = None
        apt_number = apt_input
        if '-' in apt_input:
            parts = apt_input.split('-', 1)
            block_name = parts[0].strip().upper()
            apt_number = parts[1].strip()

        # Chercher dans les appartements de l'org
        query = (Apartment.query
                 .join(Block, Apartment.block_id == Block.id)
                 .filter(Apartment.organization_id == org.id,
                         Apartment.number == apt_number))
        if block_name:
            query = query.filter(Block.name.ilike(block_name))

        candidates = query.all()

        if not candidates:
            flash(f"Appartement « {apt_input} » introuvable dans cette résidence. "
                  "Vérifiez le format (ex: A-101 ou 101).", "danger")
            return render_template('register_resident.html')

        if len(candidates) > 1:
            flash(f"Plusieurs appartements correspondent à « {apt_number} ». "
                  "Précisez le bloc (ex: A-101).", "warning")
            return render_template('register_resident.html')

        apt = candidates[0]

        # ── Vérifier qu'aucun résident n'occupe déjà cet appartement ────────
        existing_resident = User.query.filter_by(
            apartment_id=apt.id, role='resident'
        ).first()
        if existing_resident:
            flash("Cet appartement possède déjà un compte résident. "
                  "Contactez votre syndic si vous pensez qu'il y a une erreur.", "warning")
            return render_template('register_resident.html')

        # ── Vérifier que l'email n'existe pas déjà dans cette org ───────────
        existing_email = User.query.filter_by(
            email=email, organization_id=org.id
        ).first()
        if existing_email:
            flash("Un compte existe déjà pour cet email dans cette résidence. "
                  "Connectez-vous directement.", "warning")
            return redirect(url_for('login'))

        # ── Créer le compte résident avec mot de passe temporaire ────────────
        temp_password = secrets.token_urlsafe(10)
        apt_label = f"{apt.block.name}-{apt.number}" if apt.block else apt.number

        resident = User(
            organization_id=org.id,
            email=email,
            name=f"Résident {apt_label}",
            role='resident',
            apartment_id=apt.id,
        )
        resident.set_password(temp_password)
        db.session.add(resident)
        db.session.commit()

        # ── Envoyer les identifiants par email ───────────────────────────────
        try:
            from utils_email import send_resident_credentials
            send_resident_credentials(
                org_name=org.name,
                resident_name=f"Résident {apt_label}",
                email=email,
                password_temp=temp_password,
                apt_label=apt_label,
            )
        except Exception as _e:
            app.logger.error(f"[register_resident] Email non envoyé : {_e}", exc_info=True)

        flash(
            f"Compte créé pour {apt_label} — {org.name} ! "
            "Vos identifiants ont été envoyés par email. "
            "Pensez à changer votre mot de passe après la première connexion.",
            "success"
        )
        return redirect(url_for('login'))

    return render_template('register_resident.html')
