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


@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute", error_message="Trop de tentatives. Réessayez dans 1 minute.")
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
            session.permanent = True
            session['last_activity'] = datetime.utcnow().isoformat()
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
        flash(f'Organisation créée avec succès ! Essai gratuit de 30 jours activé.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')
