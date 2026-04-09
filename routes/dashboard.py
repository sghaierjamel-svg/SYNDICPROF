from flask import render_template, redirect, url_for, flash, jsonify, request
from core import app, db
from models import Block, Apartment, Payment, Expense, Ticket, UnpaidAlert, Announcement, User
from utils import (current_user, current_organization, login_required,
                   subscription_required, get_unpaid_months_count,
                   get_next_unpaid_month, last_n_months, get_month_name)
from datetime import date
from sqlalchemy import func


def _setup_checklist(org, apartments_count):
    """Calcule l'état d'avancement du setup pour le wizard de démarrage."""
    residents_count = User.query.filter_by(
        organization_id=org.id, role='resident').count()
    payments_count = Payment.query.filter_by(
        organization_id=org.id).count()
    steps = [
        {
            'id': 'compte',
            'label': 'Compte créé',
            'done': True,
            'url': None,
            'icon': 'bi-person-check',
        },
        {
            'id': 'residence',
            'label': 'Résidence configurée',
            'desc': 'Ajoutez l\'adresse et le téléphone de votre résidence.',
            'done': bool(org.address and org.phone),
            'url': url_for('settings'),
            'url_label': 'Configurer',
            'icon': 'bi-building',
        },
        {
            'id': 'appartements',
            'label': f'Appartements ajoutés ({apartments_count})',
            'desc': 'Importez vos appartements via Excel ou ajoutez-les manuellement.',
            'done': apartments_count > 0,
            'url': url_for('onboarding_import'),
            'url_label': 'Importer via Excel',
            'url2': url_for('apartments'),
            'url2_label': 'Ajouter manuellement',
            'icon': 'bi-buildings',
        },
        {
            'id': 'residents',
            'label': f'Résidents invités ({residents_count})',
            'desc': 'Créez les comptes de vos résidents pour qu\'ils accèdent à leur espace.',
            'done': residents_count > 0,
            'url': url_for('onboarding_import'),
            'url_label': 'Importer via Excel',
            'url2': url_for('users'),
            'url2_label': 'Ajouter manuellement',
            'icon': 'bi-people',
        },
        {
            'id': 'encaissement',
            'label': 'Premier encaissement enregistré',
            'desc': 'Enregistrez votre premier paiement de charges.',
            'done': payments_count > 0,
            'url': url_for('payments'),
            'url_label': 'Aller aux encaissements',
            'icon': 'bi-cash-coin',
        },
    ]
    done_count = sum(1 for s in steps if s['done'])
    pct = int(done_count / len(steps) * 100)
    return steps, done_count, len(steps), pct


@app.route('/dashboard')
@login_required
@subscription_required
def dashboard():
    user = current_user()
    org = current_organization()
    if not org:
        flash("Erreur: Organisation introuvable", "danger")
        return redirect(url_for('logout'))
    blocks_count = Block.query.filter_by(organization_id=org.id).count()
    apartments_count = Apartment.query.filter_by(organization_id=org.id).count()
    current_month_str = date.today().strftime('%Y-%m')

    # Agrégats SQL — une seule requête par calcul, pas de chargement en mémoire
    total_payments = db.session.query(func.coalesce(func.sum(Payment.amount), 0)).filter_by(
        organization_id=org.id).scalar()
    total_expenses = db.session.query(func.coalesce(func.sum(Expense.amount), 0)).filter_by(
        organization_id=org.id).scalar()
    encaisse_mois = db.session.query(func.coalesce(func.sum(Payment.amount), 0)).filter(
        Payment.organization_id == org.id,
        Payment.month_paid == current_month_str).scalar()
    depense_mois = db.session.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
        Expense.organization_id == org.id,
        func.to_char(Expense.expense_date, 'YYYY-MM') == current_month_str
        if 'postgresql' in str(db.engine.url)
        else func.strftime('%Y-%m', Expense.expense_date) == current_month_str).scalar()
    solde_tresorerie = total_payments - total_expenses
    apts_total = apartments_count
    apts_payes_mois = db.session.query(func.count(func.distinct(Payment.apartment_id))).filter(
        Payment.organization_id == org.id,
        Payment.month_paid == current_month_str).scalar()
    taux_recouvrement = round((apts_payes_mois / apts_total * 100) if apts_total > 0 else 0)
    subscription = org.subscription
    days_left = subscription.days_remaining() if subscription else 0
    unpaid_count = 0
    next_month = None
    credit = 0.0
    if user.role == 'resident' and user.apartment_id:
        unpaid_count = get_unpaid_months_count(user.apartment_id)
        next_month = get_next_unpaid_month(user.apartment_id)
        apt = Apartment.query.get(user.apartment_id)
        if apt:
            credit = apt.credit_balance
    alerts = []
    if user.role == 'admin':
        alerts = UnpaidAlert.query.filter_by(
            organization_id=org.id,
            email_sent=False
        ).order_by(UnpaidAlert.alert_date.desc()).limit(5).all()
    recent_tickets = []
    if user.role == 'admin':
        recent_tickets = Ticket.query.filter(
            Ticket.organization_id == org.id,
            Ticket.status.in_(['ouvert', 'en_cours'])
        ).order_by(Ticket.created_at.desc()).limit(5).all()
    elif user.apartment_id:
        recent_tickets = Ticket.query.filter_by(
            apartment_id=user.apartment_id
        ).order_by(Ticket.created_at.desc()).limit(5).all()
    # Setup wizard (admin uniquement, si pas encore dismissed et setup incomplet)
    setup_steps, setup_done, setup_total, setup_pct = [], 0, 0, 0
    show_setup = False
    if user.role == 'admin' and not org.setup_dismissed:
        setup_steps, setup_done, setup_total, setup_pct = _setup_checklist(org, apartments_count)
        show_setup = setup_pct < 100

    return render_template('dashboard.html',
                         user=user,
                         org=org,
                         subscription=subscription,
                         days_left=days_left,
                         blocks_count=blocks_count,
                         apartments_count=apartments_count,
                         total_payments=total_payments,
                         total_expenses=total_expenses,
                         unpaid_count=unpaid_count,
                         next_month=next_month,
                         credit=credit,
                         alerts=alerts,
                         recent_tickets=recent_tickets,
                         encaisse_mois=encaisse_mois,
                         depense_mois=depense_mois,
                         solde_tresorerie=solde_tresorerie,
                         taux_recouvrement=taux_recouvrement,
                         show_setup=show_setup,
                         setup_steps=setup_steps,
                         setup_done=setup_done,
                         setup_total=setup_total,
                         setup_pct=setup_pct)


@app.route('/residents', methods=['GET', 'POST'])
@login_required
@subscription_required
def residents_menu():
    user = current_user()
    org = current_organization()

    # ── Mise à jour profil résident ──────────────────────────────────────────
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'update_profile':
            new_name  = request.form.get('name', '').strip()
            new_phone = request.form.get('phone', '').strip()
            if new_name:
                user.name = new_name
            user.phone = new_phone or None
            db.session.commit()
            flash('Profil mis à jour.', 'success')
        return redirect(url_for('residents_menu'))

    unpaid_count = 0
    next_month   = None
    credit       = 0.0
    apt          = None
    all_payments = []
    history_6months = []
    annual_total = 0.0
    my_tickets   = []
    months_fr = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                 'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']

    if user.apartment_id:
        unpaid_count = get_unpaid_months_count(user.apartment_id)
        next_month   = get_next_unpaid_month(user.apartment_id)
        apt          = Apartment.query.get(user.apartment_id)
        if apt:
            credit = apt.credit_balance

        # Historique complet trié par date
        all_payments = Payment.query.filter_by(apartment_id=user.apartment_id)\
            .order_by(Payment.payment_date.desc()).all()

        # Récapitulatif annuel (année en cours)
        current_year = date.today().year
        annual_total = sum(p.amount for p in all_payments if p.payment_date.year == current_year)

        # Historique 6 derniers mois (pour la vue rapide)
        paid_months_set = {p.month_paid for p in all_payments}
        for (y, m) in last_n_months(6):
            month_str  = f"{y}-{m:02d}"
            paid_entry = next((p for p in all_payments if p.month_paid == month_str), None)
            history_6months.append({
                'label':  f"{months_fr[m-1]} {y}",
                'paid':   paid_entry is not None,
                'amount': paid_entry.amount if paid_entry else 0,
                'payment_id': paid_entry.id if paid_entry else None,
            })

        my_tickets = Ticket.query.filter_by(apartment_id=user.apartment_id)\
            .order_by(Ticket.created_at.desc()).limit(5).all()

    # Annonces (5 dernières, épinglées en premier)
    announcements = Announcement.query.filter_by(organization_id=org.id)\
        .order_by(Announcement.pinned.desc(), Announcement.created_at.desc()).limit(5).all()

    konnect_configured = bool(org and org.konnect_api_key and org.konnect_wallet_id)
    flouci_configured  = bool(org and org.flouci_app_token and org.flouci_app_secret)
    current_year = date.today().year

    return render_template('residents.html',
                           user=user, org=org,
                           unpaid_count=unpaid_count, next_month=next_month,
                           credit=credit, apt=apt,
                           all_payments=all_payments,
                           history_6months=history_6months,
                           annual_total=annual_total,
                           current_year=current_year,
                           my_tickets=my_tickets,
                           announcements=announcements,
                           konnect_configured=konnect_configured,
                           flouci_configured=flouci_configured)


@app.route('/api/dashboard_data')
@login_required
@subscription_required
def api_dashboard_data():
    org = current_organization()
    months = last_n_months(12)
    payments = Payment.query.filter_by(organization_id=org.id).all()
    expenses = Expense.query.filter_by(organization_id=org.id).all()
    labels = []
    data_pay = []
    data_exp = []
    for (y, m) in months:
        labels.append(f"{get_month_name(m)} {y}")
        s_p = sum(p.amount for p in payments if p.payment_date.year == y and p.payment_date.month == m)
        s_e = sum(e.amount for e in expenses if e.expense_date.year == y and e.expense_date.month == m)
        data_pay.append(round(s_p, 2))
        data_exp.append(round(s_e, 2))
    return jsonify({'labels': labels, 'payments': data_pay, 'expenses': data_exp})


@app.route('/api/notif/seen', methods=['POST'])
@login_required
def api_notif_seen():
    """Marque les notifications comme vues (met à jour notif_seen_at)."""
    from datetime import datetime
    user = current_user()
    user.notif_seen_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'ok': True})
