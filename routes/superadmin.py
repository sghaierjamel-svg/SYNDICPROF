from flask import render_template, request, redirect, url_for, flash
from core import app, db
from models import Organization, Apartment, User
from utils import (current_user, login_required, superadmin_required)
from datetime import datetime, timedelta


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

        if not max_apartments_str:
            max_apartments = 999999
            flash('Limite d\'appartements : Illimité', 'success')
        else:
            try:
                max_apartments = int(max_apartments_str)
                flash(f'Limite d\'appartements mise à jour : {max_apartments}', 'success')
            except ValueError:
                flash('Erreur : Veuillez entrer un nombre valide', 'danger')
                return redirect(url_for('superadmin_org_detail', org_id=org_id))

        org.subscription.max_apartments = max_apartments
        db.session.commit()
    else:
        flash('Cette organisation n\'a pas d\'abonnement', 'danger')

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
            flash('Erreur : Prix mensuel invalide', 'danger')
            return redirect(url_for('superadmin_org_detail', org_id=org_id))

        org.subscription.plan = plan
        org.subscription.monthly_price = price
        db.session.commit()

        plan_names = {
            'trial': 'Essai Gratuit',
            'starter': 'Starter',
            'pro': 'Pro',
            'enterprise': 'Enterprise'
        }
        plan_display = plan_names.get(plan, plan)

        flash(f'Plan mis à jour : {plan_display} ({price:.2f} DT/mois)', 'success')
    else:
        flash('Cette organisation n\'a pas d\'abonnement', 'danger')

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
        flash('Mot de passe changé avec succès !', 'success')
        return redirect(url_for('superadmin_dashboard'))
    return render_template('superadmin/change_password.html')
