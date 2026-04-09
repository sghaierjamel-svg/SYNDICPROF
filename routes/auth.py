from flask import render_template, request, redirect, url_for, session, flash
from core import app, limiter
from models import User, Organization, Subscription
from utils import current_user
from datetime import datetime, timedelta
import re


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
        # Un même email peut gérer plusieurs résidences — pas de blocage global
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
        # Email de bienvenue (non bloquant)
        try:
            from utils_email import send_welcome_admin
            send_welcome_admin(org_name=org_name, email=email, days_trial=30)
        except Exception as _e:
            print(f"[register] Email bienvenue non envoyé : {_e}")
        flash(f'Organisation créée avec succès ! Essai gratuit de 30 jours activé.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')
