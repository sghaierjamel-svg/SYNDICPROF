from flask import render_template, request, redirect, url_for, flash, jsonify
from core import app, db
from models import Organization, Apartment, User, SuperAdminSettings
from utils import (current_user, login_required, superadmin_required)
from datetime import datetime, timedelta
from sqlalchemy import func
import requests as http


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

    # Dernière connexion de l'admin principal de chaque organisation (une seule requête)
    rows = db.session.query(User.organization_id, func.max(User.last_login_at)).filter(
        User.role == 'admin', User.organization_id.isnot(None)
    ).group_by(User.organization_id).all()
    last_login_map = {org_id: last_login for org_id, last_login in rows}

    return render_template('superadmin/dashboard.html',
                           organizations=organizations,
                           total_orgs=total_orgs,
                           active_orgs=active_orgs,
                           total_revenue=total_revenue,
                           last_login_map=last_login_map)


@app.route('/superadmin/organization/<int:org_id>')
@login_required
@superadmin_required
def superadmin_org_detail(org_id):
    org = Organization.query.get_or_404(org_id)
    apartments_count = Apartment.query.filter_by(organization_id=org.id).count()
    users_count = User.query.filter_by(organization_id=org.id).count()
    return render_template('superadmin/org_detail.html', org=org, apartments_count=apartments_count, users_count=users_count)


@app.route('/superadmin/organization/<int:org_id>/delete', methods=['POST'])
@login_required
@superadmin_required
def superadmin_delete_org(org_id):
    org = Organization.query.get_or_404(org_id)
    org_name = org.name
    try:
        oid = org_id
        with db.engine.begin() as conn:
            t = db.text
            # Niveau 3 — enfants des enfants
            conn.execute(t("DELETE FROM announcement_read WHERE announcement_id IN (SELECT id FROM announcement WHERE organization_id=:o)"), {"o": oid})
            conn.execute(t("DELETE FROM ag_vote WHERE item_id IN (SELECT i.id FROM ag_item i JOIN assembly_general a ON i.assembly_id=a.id WHERE a.organization_id=:o)"), {"o": oid})
            conn.execute(t("DELETE FROM ag_item WHERE assembly_id IN (SELECT id FROM assembly_general WHERE organization_id=:o)"), {"o": oid})
            conn.execute(t("DELETE FROM litige_document WHERE litige_id IN (SELECT id FROM autre_litige WHERE organization_id=:o)"), {"o": oid})
            conn.execute(t("DELETE FROM appel_fonds_quota WHERE appel_id IN (SELECT id FROM appel_fonds WHERE organization_id=:o)"), {"o": oid})
            conn.execute(t("DELETE FROM appel_fonds_paiement WHERE organization_id=:o"), {"o": oid})
            conn.execute(t("DELETE FROM appel_fonds_depense WHERE organization_id=:o"), {"o": oid})
            # Niveau 2 — tables directement liées à l'org
            for table in [
                'announcement', 'assembly_general', 'litige', 'autre_litige',
                'appel_fonds', 'camera', 'access_log', 'misc_receipt',
                'konnect_payment', 'flouci_payment', 'direct_message',
                'unpaid_alert', 'ticket', 'payment', 'expense', 'intervenant',
            ]:
                conn.execute(t(f"DELETE FROM {table} WHERE organization_id=:o"), {"o": oid})
            # Niveau 1 — appartements, blocs, users (après avoir vidé leurs dépendances)
            conn.execute(t('DELETE FROM apartment WHERE organization_id=:o'), {"o": oid})
            conn.execute(t('DELETE FROM block WHERE organization_id=:o'), {"o": oid})
            conn.execute(t('DELETE FROM "user" WHERE organization_id=:o'), {"o": oid})
            conn.execute(t('DELETE FROM subscription WHERE organization_id=:o'), {"o": oid})
            # Organisation elle-même
            conn.execute(t('DELETE FROM organization WHERE id=:o'), {"o": oid})
        flash(f'Organisation « {org_name} » supprimée définitivement.', 'success')
    except Exception as e:
        flash(f'Erreur lors de la suppression : {e}', 'danger')
    return redirect(url_for('superadmin_dashboard'))


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


@app.route('/superadmin/test-email', methods=['POST'])
@login_required
@superadmin_required
def superadmin_test_email():
    from utils_email import send_email, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS
    to = request.form.get('to', '').strip()
    if not to:
        return jsonify({'ok': False, 'error': 'Adresse email manquante.'})
    ok, err = send_email(
        to=to,
        subject='Test email SyndicPro',
        html=f'<p>Ceci est un email de test envoyé depuis SyndicPro.</p>'
             f'<p>Serveur : <b>{SMTP_HOST}:{SMTP_PORT}</b><br>'
             f'Compte : <b>{SMTP_USER}</b><br>'
             f'Mot de passe configuré : <b>{"Oui" if SMTP_PASS else "NON — variable manquante"}</b></p>'
    )
    if ok:
        return jsonify({'ok': True, 'msg': f'Email envoyé à {to} avec succès.'})
    return jsonify({'ok': False, 'error': err})


@app.route('/superadmin/settings', methods=['GET', 'POST'])
@login_required
@superadmin_required
def superadmin_settings():
    settings = SuperAdminSettings.get()
    if request.method == 'POST':
        settings.konnect_api_key = request.form.get('konnect_api_key', '').strip()
        settings.konnect_wallet_id = request.form.get('konnect_wallet_id', '').strip()
        db.session.commit()
        flash('Paramètres enregistrés.', 'success')
        return redirect(url_for('superadmin_settings'))
    return render_template('superadmin/settings.html', settings=settings, user=current_user())


@app.route('/superadmin/test-konnect')
@login_required
@superadmin_required
def superadmin_test_konnect():
    settings = SuperAdminSettings.get()
    if not settings.konnect_api_key or not settings.konnect_wallet_id:
        return jsonify({'ok': False, 'message': 'Clé API ou Wallet ID manquant.'})
    try:
        resp = http.get(
            'https://api.konnect.network/api/v2/account/me',
            headers={'x-api-key': settings.konnect_api_key},
            timeout=8
        )
        if resp.status_code == 200:
            return jsonify({'ok': True, 'message': 'Connexion Konnect réussie ✅'})
        elif resp.status_code == 401:
            return jsonify({'ok': False, 'message': 'Clé API invalide ou expirée.'})
        else:
            return jsonify({'ok': False, 'message': f'Erreur Konnect ({resp.status_code}).'})
    except Exception:
        return jsonify({'ok': False, 'message': 'Impossible de joindre Konnect. Vérifiez votre connexion.'})
