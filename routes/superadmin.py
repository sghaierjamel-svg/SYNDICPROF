from flask import render_template, request, redirect, url_for, flash, jsonify, session, Response
from core import app, db
from models import Organization, Apartment, User, SuperAdminSettings, Payment, Ticket, Expense, Subscription
from utils import current_user, login_required, superadmin_required
from datetime import datetime, timedelta, date
from sqlalchemy import func
import requests as http
import csv
import io


# ─── Dashboard principal ──────────────────────────────────────────────────────

@app.route('/superadmin')
@login_required
@superadmin_required
def superadmin_dashboard():
    organizations = Organization.query.order_by(Organization.created_at.desc()).all()
    today = datetime.utcnow()
    this_month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_start = (this_month_start - timedelta(days=1)).replace(day=1)

    # ── Exclusion orgs de test (Les Jasmins) — appliquée à tous les KPIs ────
    test_org_ids = set()
    for o in organizations:
        name_l = (o.name or '').lower()
        slug_l = (o.slug or '').lower()
        if 'jasmin' in name_l or 'jasmin' in slug_l:
            test_org_ids.add(o.id)
    real_orgs = [o for o in organizations if o.id not in test_org_ids]

    # ── KPIs globaux ──────────────────────────────────────────────────────────
    total_orgs  = len(real_orgs)
    active_orgs = sum(1 for o in real_orgs if o.is_active)

    # MRR = somme des prix mensuels des abonnements actifs non expirés
    mrr = sum(
        o.subscription.monthly_price
        for o in real_orgs
        if o.subscription and o.subscription.status == 'active' and not o.subscription.is_expired()
    )
    arr = mrr * 12

    # Nouvelles orgs ce mois / mois dernier
    new_this_month = sum(1 for o in real_orgs if o.created_at >= this_month_start)
    new_last_month = sum(1 for o in real_orgs if last_month_start <= o.created_at < this_month_start)

    # Total appartements & résidents sur toute la plateforme
    total_apartments = db.session.query(func.count(Apartment.id)).scalar() or 0
    total_residents  = db.session.query(func.count(User.id)).filter(User.role == 'resident').scalar() or 0

    # Abonnements qui expirent dans <= 7 jours (alerte)
    expiring_soon = [
        o for o in real_orgs
        if o.subscription and o.subscription.end_date and o.is_active
        and 0 < o.subscription.days_remaining() <= 7
    ]

    # Abonnements déjà expirés mais org encore active
    expired_active = [
        o for o in real_orgs
        if o.is_active and o.subscription and o.subscription.is_expired()
    ]

    # Orgs inactives depuis > 30 jours (dernière connexion admin)
    rows = db.session.query(User.organization_id, func.max(User.last_login_at)).filter(
        User.role == 'admin', User.organization_id.isnot(None)
    ).group_by(User.organization_id).all()
    last_login_map = {org_id: last_login for org_id, last_login in rows}

    inactive_30d = [
        o for o in real_orgs
        if o.is_active and (
            last_login_map.get(o.id) is None or
            last_login_map.get(o.id) < today - timedelta(days=30)
        )
    ]

    # Churn ce mois (abonnements expirés ce mois)
    churn_this_month = sum(
        1 for o in real_orgs
        if o.subscription and o.subscription.end_date and
        o.subscription.end_date >= this_month_start and
        o.subscription.is_expired()
    )

    # Taux de conversion trial → payant
    trial_orgs = sum(1 for o in real_orgs if o.subscription and o.subscription.plan == 'trial')
    paying_orgs = total_orgs - trial_orgs

    # ── Historique MRR + Churn par mois (12 derniers mois) ───────────────────
    mrr_history = []
    churn_history = []
    for i in range(11, -1, -1):
        month_dt = (today.replace(day=1) - timedelta(days=i * 30)).replace(day=1)
        month_end = month_dt + timedelta(days=32)
        month_end = month_end.replace(day=1)
        label = month_dt.strftime('%b %Y')
        month_mrr = sum(
            o.subscription.monthly_price
            for o in real_orgs
            if o.subscription and o.subscription.monthly_price > 0
            and o.subscription.start_date <= month_dt + timedelta(days=31)
            and (not o.subscription.end_date or o.subscription.end_date >= month_dt)
        )
        month_churn = sum(
            1 for o in real_orgs
            if o.subscription and o.subscription.end_date
            and month_dt <= o.subscription.end_date < month_end
            and o.subscription.is_expired()
        )
        mrr_history.append({'label': label, 'mrr': round(month_mrr, 2)})
        churn_history.append({'label': label, 'churn': month_churn})

    # ── LTV estimé par plan ──────────────────────────────────────────────────
    ltv_by_plan = {}
    for o in real_orgs:
        sub = o.subscription
        if not sub or not sub.monthly_price or sub.monthly_price <= 0:
            continue
        plan = sub.plan or 'inconnu'
        if sub.end_date:
            duration_months = max((sub.end_date - sub.start_date).days / 30, 1)
        else:
            duration_months = max((today - sub.start_date).days / 30, 1)
        ltv = sub.monthly_price * duration_months
        if plan not in ltv_by_plan:
            ltv_by_plan[plan] = {'total': 0, 'count': 0}
        ltv_by_plan[plan]['total'] += ltv
        ltv_by_plan[plan]['count'] += 1
    ltv_per_plan = {
        plan: round(v['total'] / v['count'], 0)
        for plan, v in ltv_by_plan.items()
    }
    avg_ltv = round(
        sum(ltv_per_plan.values()) / len(ltv_per_plan), 0
    ) if ltv_per_plan else 0

    # ── Volume plateforme (paiements résidents enregistrés) ──────────────────
    total_platform_volume = db.session.query(func.sum(Payment.amount))\
        .filter(Payment.organization_id.notin_(test_org_ids) if test_org_ids else db.true())\
        .scalar() or 0.0

    volume_this_month = db.session.query(func.sum(Payment.amount))\
        .filter(
            Payment.payment_date >= this_month_start,
            Payment.organization_id.notin_(test_org_ids) if test_org_ids else db.true()
        ).scalar() or 0.0

    volume_last_month = db.session.query(func.sum(Payment.amount))\
        .filter(
            Payment.payment_date >= last_month_start,
            Payment.payment_date < this_month_start,
            Payment.organization_id.notin_(test_org_ids) if test_org_ids else db.true()
        ).scalar() or 0.0

    total_transactions = db.session.query(func.count(Payment.id))\
        .filter(Payment.organization_id.notin_(test_org_ids) if test_org_ids else db.true())\
        .scalar() or 0

    # ── Score d'engagement par organisation ──────────────────────────────────
    engagement_scores = {}
    for o in real_orgs:
        if not o.is_active:
            engagement_scores[o.id] = 0
            continue
        score = 0
        last_login = last_login_map.get(o.id)
        if last_login:
            days_ago = (today - last_login).days
            if days_ago <= 7:
                score += 40
            elif days_ago <= 14:
                score += 25
            elif days_ago <= 30:
                score += 10
        pmts = Payment.query.filter(
            Payment.organization_id == o.id,
            Payment.payment_date >= this_month_start
        ).count()
        if pmts > 0:
            score += 30
        if pmts > 5:
            score += 10
        if Ticket.query.filter_by(organization_id=o.id).count() > 0:
            score += 10
        if Expense.query.filter_by(organization_id=o.id).count() > 0:
            score += 10
        engagement_scores[o.id] = min(score, 100)

    return render_template(
        'superadmin/dashboard.html',
        organizations=real_orgs,
        total_orgs=total_orgs,
        active_orgs=active_orgs,
        mrr=mrr, arr=arr,
        new_this_month=new_this_month,
        new_last_month=new_last_month,
        total_apartments=total_apartments,
        total_residents=total_residents,
        expiring_soon=expiring_soon,
        expired_active=expired_active,
        inactive_30d=inactive_30d,
        churn_this_month=churn_this_month,
        trial_orgs=trial_orgs,
        paying_orgs=paying_orgs,
        last_login_map=last_login_map,
        mrr_history=mrr_history,
        churn_history=churn_history,
        ltv_per_plan=ltv_per_plan,
        avg_ltv=avg_ltv,
        total_platform_volume=total_platform_volume,
        volume_this_month=volume_this_month,
        volume_last_month=volume_last_month,
        total_transactions=total_transactions,
        engagement_scores=engagement_scores,
    )


# ─── Détail organisation ──────────────────────────────────────────────────────

@app.route('/superadmin/organization/<int:org_id>')
@login_required
@superadmin_required
def superadmin_org_detail(org_id):
    org = Organization.query.get_or_404(org_id)

    apartments_count = Apartment.query.filter_by(organization_id=org.id).count()
    users_count      = User.query.filter_by(organization_id=org.id).count()
    residents_count  = User.query.filter_by(organization_id=org.id, role='resident').count()

    # Métriques d'usage réelles
    payments_count  = Payment.query.filter_by(organization_id=org.id).count()
    tickets_count   = Ticket.query.filter_by(organization_id=org.id).count()
    expenses_count  = Expense.query.filter_by(organization_id=org.id).count()

    last_payment = Payment.query.filter_by(organization_id=org.id)\
        .order_by(Payment.payment_date.desc()).first()
    last_ticket  = Ticket.query.filter_by(organization_id=org.id)\
        .order_by(Ticket.created_at.desc()).first()

    # Paiements ce mois
    this_month = date.today().replace(day=1)
    payments_this_month = Payment.query.filter(
        Payment.organization_id == org.id,
        Payment.payment_date >= this_month
    ).count()

    # Montant total encaissé
    total_revenue_org = db.session.query(func.sum(Payment.amount))\
        .filter(Payment.organization_id == org.id).scalar() or 0.0

    # Admin de l'org
    admin_user = User.query.filter_by(organization_id=org.id, role='admin').first()

    return render_template(
        'superadmin/org_detail.html',
        org=org,
        apartments_count=apartments_count,
        users_count=users_count,
        residents_count=residents_count,
        payments_count=payments_count,
        tickets_count=tickets_count,
        expenses_count=expenses_count,
        last_payment=last_payment,
        last_ticket=last_ticket,
        payments_this_month=payments_this_month,
        total_revenue_org=total_revenue_org,
        admin_user=admin_user,
    )


# ─── Notes internes ───────────────────────────────────────────────────────────

@app.route('/superadmin/organization/<int:org_id>/notes', methods=['POST'])
@login_required
@superadmin_required
def superadmin_save_notes(org_id):
    org = Organization.query.get_or_404(org_id)
    org.superadmin_notes = request.form.get('notes', '').strip() or None
    db.session.commit()
    flash('Notes enregistrées.', 'success')
    return redirect(url_for('superadmin_org_detail', org_id=org_id))


# ─── Envoi d'email à l'admin de l'org ────────────────────────────────────────

@app.route('/superadmin/organization/<int:org_id>/send-email', methods=['POST'])
@login_required
@superadmin_required
def superadmin_send_email_org(org_id):
    org = Organization.query.get_or_404(org_id)
    subject = request.form.get('subject', '').strip()
    body    = request.form.get('body', '').strip()
    if not subject or not body:
        flash('Sujet et corps de l\'email sont obligatoires.', 'danger')
        return redirect(url_for('superadmin_org_detail', org_id=org_id))
    try:
        from utils_email import send_email
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;padding:20px;">
            <div style="background:#00C896;padding:15px 20px;border-radius:8px 8px 0 0;">
                <h2 style="color:#0A0E1A;margin:0;">SyndicPro</h2>
            </div>
            <div style="background:#111827;padding:25px;border-radius:0 0 8px 8px;color:#F9FAFB;">
                <p style="white-space:pre-wrap;">{body}</p>
                <hr style="border-color:#374151;margin:20px 0;">
                <p style="color:#9CA3AF;font-size:0.85rem;">
                    Message envoyé depuis SyndicPro — syndicpro.tn
                </p>
            </div>
        </div>
        """
        ok, err = send_email(to=org.email, subject=subject, html=html)
        if ok:
            flash(f'Email envoyé à {org.email}.', 'success')
        else:
            flash(f'Erreur envoi email : {err}', 'danger')
    except Exception as e:
        flash(f'Erreur : {e}', 'danger')
    return redirect(url_for('superadmin_org_detail', org_id=org_id))


# ─── Impersonation (connexion en tant qu'admin) ───────────────────────────────

@app.route('/superadmin/organization/<int:org_id>/login-as', methods=['POST'])
@login_required
@superadmin_required
def superadmin_login_as(org_id):
    """Connecte le superadmin en tant qu'admin de cette organisation (support)."""
    org = Organization.query.get_or_404(org_id)
    admin = User.query.filter_by(organization_id=org.id, role='admin').first()
    if not admin:
        flash('Aucun admin trouvé pour cette organisation.', 'danger')
        return redirect(url_for('superadmin_org_detail', org_id=org_id))
    # Sauvegarder l'identité superadmin pour pouvoir revenir
    session['superadmin_return_id'] = session.get('user_id')
    session['user_id']     = admin.id
    session['org_slug']    = org.slug
    session['impersonating'] = True
    flash(f'Connecté en tant que {admin.email} ({org.name}). Retournez à /superadmin pour reprendre votre session.', 'info')
    return redirect(url_for('dashboard'))


@app.route('/superadmin/return-from-impersonation')
@login_required
def superadmin_return():
    """Revenir à la session superadmin après impersonation."""
    original_id = session.pop('superadmin_return_id', None)
    session.pop('impersonating', None)
    if not original_id:
        return redirect(url_for('login'))
    session['user_id']  = original_id
    session['org_slug'] = None
    flash('Retour à la session superadmin.', 'success')
    return redirect(url_for('superadmin_dashboard'))


# ─── Export CSV ───────────────────────────────────────────────────────────────

@app.route('/superadmin/export-csv')
@login_required
@superadmin_required
def superadmin_export_csv():
    organizations = Organization.query.order_by(Organization.created_at.desc()).all()
    today = datetime.utcnow()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow([
        'ID', 'Nom', 'Email', 'Téléphone', 'Adresse',
        'Plan', 'Statut', 'Prix DT/mois',
        'Date création', 'Date expiration', 'Jours restants',
        'Appartements', 'Résidents',
        'Paiements total', 'Notes superadmin'
    ])
    for org in organizations:
        apts = Apartment.query.filter_by(organization_id=org.id).count()
        res  = User.query.filter_by(organization_id=org.id, role='resident').count()
        pmts = Payment.query.filter_by(organization_id=org.id).count()
        sub  = org.subscription
        writer.writerow([
            org.id, org.name, org.email, org.phone or '',
            (org.address or '').replace('\n', ' '),
            sub.plan if sub else '', 'actif' if org.is_active else 'inactif',
            sub.monthly_price if sub else 0,
            org.created_at.strftime('%d/%m/%Y'),
            sub.end_date.strftime('%d/%m/%Y') if sub and sub.end_date else '',
            sub.days_remaining() if sub else '',
            apts, res, pmts,
            (org.superadmin_notes or '').replace('\n', ' '),
        ])

    output.seek(0)
    filename = f"syndicpro_clients_{today.strftime('%Y%m%d')}.csv"
    return Response(
        output.getvalue().encode('utf-8-sig'),  # BOM pour Excel
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )


# ─── Suppression ─────────────────────────────────────────────────────────────

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
            conn.execute(t("DELETE FROM announcement_read WHERE announcement_id IN (SELECT id FROM announcement WHERE organization_id=:o)"), {"o": oid})
            conn.execute(t("DELETE FROM ag_vote WHERE item_id IN (SELECT i.id FROM ag_item i JOIN assembly_general a ON i.assembly_id=a.id WHERE a.organization_id=:o)"), {"o": oid})
            conn.execute(t("DELETE FROM ag_item WHERE assembly_id IN (SELECT id FROM assembly_general WHERE organization_id=:o)"), {"o": oid})
            conn.execute(t("DELETE FROM litige_document WHERE litige_id IN (SELECT id FROM autre_litige WHERE organization_id=:o)"), {"o": oid})
            conn.execute(t("DELETE FROM appel_fonds_quota WHERE appel_id IN (SELECT id FROM appel_fonds WHERE organization_id=:o)"), {"o": oid})
            conn.execute(t("DELETE FROM appel_fonds_paiement WHERE organization_id=:o"), {"o": oid})
            conn.execute(t("DELETE FROM appel_fonds_depense WHERE organization_id=:o"), {"o": oid})
            conn.execute(t("DELETE FROM payment_request WHERE organization_id=:o"), {"o": oid})
            conn.execute(t("DELETE FROM push_subscription WHERE organization_id=:o"), {"o": oid})
            for table in [
                'announcement', 'assembly_general', 'litige', 'autre_litige',
                'appel_fonds', 'camera', 'access_log', 'misc_receipt',
                'konnect_payment', 'flouci_payment', 'direct_message',
                'unpaid_alert', 'ticket', 'payment', 'expense', 'intervenant',
                'lift_incident', 'lift',
            ]:
                conn.execute(t(f"DELETE FROM {table} WHERE organization_id=:o"), {"o": oid})
            conn.execute(t('DELETE FROM apartment WHERE organization_id=:o'), {"o": oid})
            conn.execute(t('DELETE FROM block WHERE organization_id=:o'), {"o": oid})
            conn.execute(t('DELETE FROM "user" WHERE organization_id=:o'), {"o": oid})
            conn.execute(t('DELETE FROM subscription WHERE organization_id=:o'), {"o": oid})
            conn.execute(t('DELETE FROM organization WHERE id=:o'), {"o": oid})
        flash(f'Organisation « {org_name} » supprimée définitivement.', 'success')
    except Exception as e:
        flash(f'Erreur lors de la suppression : {e}', 'danger')
    return redirect(url_for('superadmin_dashboard'))


# ─── Toggle actif/inactif ─────────────────────────────────────────────────────

@app.route('/superadmin/organization/<int:org_id>/toggle', methods=['POST'])
@login_required
@superadmin_required
def superadmin_toggle_org(org_id):
    org = Organization.query.get_or_404(org_id)
    org.is_active = not org.is_active
    db.session.commit()
    flash(f'Organisation {org.name} {"activée" if org.is_active else "désactivée"}.', 'success')
    return redirect(url_for('superadmin_org_detail', org_id=org_id))


# ─── Prolonger abonnement ─────────────────────────────────────────────────────

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
        flash(f'Abonnement prolongé de {days} jours pour {org.name}.', 'success')
    return redirect(url_for('superadmin_org_detail', org_id=org_id))


# ─── Modifier plan ────────────────────────────────────────────────────────────

@app.route('/superadmin/organization/<int:org_id>/update-plan', methods=['POST'])
@login_required
@superadmin_required
def superadmin_update_plan(org_id):
    org = Organization.query.get_or_404(org_id)
    if org.subscription:
        plan = request.form.get('plan', 'trial')
        try:
            price = float(request.form.get('monthly_price', 0.0))
        except ValueError:
            flash('Prix mensuel invalide.', 'danger')
            return redirect(url_for('superadmin_org_detail', org_id=org_id))
        org.subscription.plan = plan
        org.subscription.monthly_price = price
        db.session.commit()
        plan_labels = {'trial': 'Essai', 'starter': 'Starter', 'standard': 'Standard',
                       'premium': 'Premium', 'pro': 'Pro'}
        flash(f'Plan mis à jour : {plan_labels.get(plan, plan)} — {price:.0f} DT/mois.', 'success')
    return redirect(url_for('superadmin_org_detail', org_id=org_id))


# ─── Modifier limite appartements ─────────────────────────────────────────────

@app.route('/superadmin/organization/<int:org_id>/update-limits', methods=['POST'])
@login_required
@superadmin_required
def superadmin_update_limits(org_id):
    org = Organization.query.get_or_404(org_id)
    if org.subscription:
        val = request.form.get('max_apartments', '').strip()
        org.subscription.max_apartments = int(val) if val else 999999
        db.session.commit()
        flash(f'Limite mise à jour : {"Illimité" if not val else val + " appts"}.', 'success')
    return redirect(url_for('superadmin_org_detail', org_id=org_id))


# ─── Reset mot de passe admin ─────────────────────────────────────────────────

@app.route('/superadmin/organization/<int:org_id>/reset-admin-password', methods=['POST'])
@login_required
@superadmin_required
def superadmin_reset_admin_password(org_id):
    org = Organization.query.get_or_404(org_id)
    new_password = request.form.get('new_password', '').strip()
    if len(new_password) < 8:
        flash('Mot de passe trop court (min 8 caractères).', 'danger')
        return redirect(url_for('superadmin_org_detail', org_id=org_id))
    admin = User.query.filter_by(organization_id=org.id, role='admin').first()
    if not admin:
        flash('Aucun admin trouvé.', 'danger')
        return redirect(url_for('superadmin_org_detail', org_id=org_id))
    admin.set_password(new_password)
    for u in User.query.filter_by(email=admin.email).all():
        u.password_hash = admin.password_hash
    db.session.commit()
    flash(f'Mot de passe réinitialisé pour {admin.email}.', 'success')
    return redirect(url_for('superadmin_org_detail', org_id=org_id))


# ─── Changement MDP superadmin ────────────────────────────────────────────────

@app.route('/superadmin/change-password', methods=['GET', 'POST'])
@login_required
@superadmin_required
def superadmin_change_password():
    if request.method == 'POST':
        user = current_user()
        if not user.check_password(request.form['current_password']):
            flash('Mot de passe actuel incorrect.', 'danger')
            return redirect(url_for('superadmin_change_password'))
        new_pwd = request.form['new_password']
        if new_pwd != request.form['confirm_password']:
            flash('Les mots de passe ne correspondent pas.', 'danger')
            return redirect(url_for('superadmin_change_password'))
        if len(new_pwd) < 8:
            flash('Minimum 8 caractères.', 'danger')
            return redirect(url_for('superadmin_change_password'))
        user.set_password(new_pwd)
        db.session.commit()
        flash('Mot de passe changé.', 'success')
        return redirect(url_for('superadmin_dashboard'))
    return render_template('superadmin/change_password.html')


# ─── Paramètres + test email/konnect ─────────────────────────────────────────

@app.route('/superadmin/settings', methods=['GET', 'POST'])
@login_required
@superadmin_required
def superadmin_settings():
    settings = SuperAdminSettings.get()
    if request.method == 'POST':
        settings.konnect_api_key  = request.form.get('konnect_api_key', '').strip()
        settings.konnect_wallet_id = request.form.get('konnect_wallet_id', '').strip()
        db.session.commit()
        flash('Paramètres enregistrés.', 'success')
        return redirect(url_for('superadmin_settings'))
    return render_template('superadmin/settings.html', settings=settings, user=current_user())


@app.route('/superadmin/test-email', methods=['POST'])
@login_required
@superadmin_required
def superadmin_test_email():
    try:
        from utils_email import send_email, RESEND_API_KEY, FROM_EMAIL
        to = request.form.get('to', '').strip()
        if not to:
            return jsonify({'ok': False, 'error': 'Adresse email manquante.'})
        ok, err = send_email(
            to=to,
            subject='Test email SyndicPro',
            html=(f'<p>Test email SyndicPro.</p><p>Expéditeur : <b>{FROM_EMAIL}</b><br>'
                  f'Clé API : <b>{"OK" if RESEND_API_KEY else "MANQUANTE"}</b></p>')
        )
        return jsonify({'ok': ok, 'msg': f'Email envoyé à {to}.' if ok else None, 'error': err if not ok else None})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@app.route('/superadmin/test-konnect')
@login_required
@superadmin_required
def superadmin_test_konnect():
    settings = SuperAdminSettings.get()
    if not settings.konnect_api_key or not settings.konnect_wallet_id:
        return jsonify({'ok': False, 'message': 'Clé API ou Wallet ID manquant.'})
    try:
        resp = http.get('https://api.konnect.network/api/v2/account/me',
                        headers={'x-api-key': settings.konnect_api_key}, timeout=8)
        if resp.status_code == 200:
            return jsonify({'ok': True, 'message': 'Connexion Konnect réussie ✅'})
        return jsonify({'ok': False, 'message': f'Erreur Konnect ({resp.status_code}).'})
    except Exception:
        return jsonify({'ok': False, 'message': 'Impossible de joindre Konnect.'})
