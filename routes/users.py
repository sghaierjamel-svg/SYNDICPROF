from flask import render_template, request, redirect, url_for, flash
from core import app, db
from models import User, Apartment, UnpaidAlert
from utils import (current_user, current_organization, login_required,
                   admin_required, subscription_required, check_unpaid_alerts)


@app.route('/users', methods=['GET', 'POST'])
@login_required
@admin_required
@subscription_required
def users():
    org = current_organization()
    if request.method == 'POST':
        email = request.form['email'].strip().lower()   # HIGH-011 : normaliser l'email
        name = request.form.get('name', '').strip()[:120]
        role = request.form.get('role', 'resident')
        password = request.form.get('password', '').strip()
        apt_id = request.form.get('apartment_id') or None
        if role not in ['admin', 'resident']:
            flash('Rôle invalide.', 'danger')
            return redirect(url_for('users'))
        # MED-013 : minimum 8 caractères
        if not password or len(password) < 8:
            flash('Le mot de passe est obligatoire (8 caractères minimum).', 'danger')
            return redirect(url_for('users'))
        try:
            apt_id = int(apt_id) if apt_id else None
        except ValueError:
            apt_id = None
        if User.query.filter_by(email=email, organization_id=org.id).first():
            flash('Cet email existe déjà', 'danger')
            return redirect(url_for('users'))
        phone = request.form.get('phone', '').strip()
        u = User(
            organization_id=org.id,
            email=email,
            name=name,
            role=role,
            phone=phone or None,
            apartment_id=apt_id
        )
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        # Email identifiants au résident (non bloquant)
        if role == 'resident' and email:
            try:
                from utils_email import send_resident_credentials
                apt_label = ''
                if apt_id:
                    apt_obj = Apartment.query.get(apt_id)
                    if apt_obj and apt_obj.block:
                        apt_label = f"{apt_obj.block.name}-{apt_obj.number}"
                send_resident_credentials(
                    org_name=org.name,
                    resident_name=name or email,
                    email=email,
                    password_temp=password,
                    apt_label=apt_label,
                )
            except Exception as _e:
                print(f"[users] Email résident non envoyé : {_e}")
        flash('Utilisateur créé', 'success')
        return redirect(url_for('users'))
    users_list = User.query.filter_by(organization_id=org.id).all()
    apartments = Apartment.query.filter_by(organization_id=org.id).all()
    return render_template('users.html', users=users_list, apartments=apartments, user=current_user())


@app.route('/user/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
@subscription_required
def edit_user(user_id):
    org = current_organization()
    u = User.query.filter_by(id=user_id, organization_id=org.id).first_or_404()
    apartments = Apartment.query.filter_by(organization_id=org.id).all()
    if request.method == 'POST':
        u.name  = request.form.get('name', '').strip()
        u.email = request.form.get('email', '').strip()
        u.phone = request.form.get('phone', '').strip() or None
        new_role = request.form.get('role', u.role)
        if new_role in ['admin', 'resident']:
            u.role = new_role
        apt_id = request.form.get('apartment_id') or None
        try:
            u.apartment_id = int(apt_id) if apt_id else None
        except ValueError:
            u.apartment_id = None
        new_pwd = request.form.get('new_password', '').strip()
        if new_pwd:
            if len(new_pwd) < 6:
                flash('Mot de passe trop court (6 caractères min).', 'danger')
                return redirect(url_for('edit_user', user_id=user_id))
            u.set_password(new_pwd)
        db.session.commit()
        flash('Utilisateur mis à jour.', 'success')
        return redirect(url_for('users'))
    return render_template('edit_user.html', u=u, apartments=apartments, user=current_user())


@app.route('/user/delete/<int:user_id>', methods=['POST'])
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


@app.route('/alert/mark_sent/<int:alert_id>', methods=['POST'])
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
