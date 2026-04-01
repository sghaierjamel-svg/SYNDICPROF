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
        email = request.form['email']
        name = request.form.get('name', '')
        role = request.form.get('role', 'resident')
        password = request.form.get('password', '').strip()
        apt_id = request.form.get('apartment_id') or None
        # Validation du rôle (sécurité : empêche la création de superadmin)
        if role not in ['admin', 'resident']:
            flash('Rôle invalide.', 'danger')
            return redirect(url_for('users'))
        # Mot de passe obligatoire
        if not password or len(password) < 6:
            flash('Le mot de passe est obligatoire (6 caractères minimum).', 'danger')
            return redirect(url_for('users'))
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
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        flash('Utilisateur créé', 'success')
        return redirect(url_for('users'))
    users_list = User.query.filter_by(organization_id=org.id).all()
    apartments = Apartment.query.filter_by(organization_id=org.id).all()
    return render_template('users.html', users=users_list, apartments=apartments, user=current_user())


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
