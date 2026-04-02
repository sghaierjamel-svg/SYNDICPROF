from flask import render_template, redirect, url_for, flash, jsonify
from core import app
from models import Block, Apartment, Payment, Expense, Ticket, UnpaidAlert
from utils import (current_user, current_organization, login_required,
                   subscription_required, get_unpaid_months_count,
                   get_next_unpaid_month, last_n_months, get_month_name)
from datetime import date


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
    total_payments = sum(p.amount for p in Payment.query.filter_by(organization_id=org.id).all())
    total_expenses = sum(e.amount for e in Expense.query.filter_by(organization_id=org.id).all())
    current_month_str = date.today().strftime('%Y-%m')
    encaisse_mois = sum(
        p.amount for p in Payment.query.filter_by(organization_id=org.id).all()
        if p.month_paid == current_month_str
    )
    depense_mois = sum(
        e.amount for e in Expense.query.filter_by(organization_id=org.id).all()
        if e.expense_date.strftime('%Y-%m') == current_month_str
    )
    solde_tresorerie = total_payments - total_expenses
    apts_total = apartments_count
    apts_payes_mois = len(set(
        p.apartment_id for p in Payment.query.filter_by(organization_id=org.id).all()
        if p.month_paid == current_month_str
    ))
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
                         taux_recouvrement=taux_recouvrement)


@app.route('/residents')
@login_required
@subscription_required
def residents_menu():
    user = current_user()
    unpaid_count = 0
    next_month = None
    my_payments = []
    credit = 0.0
    history_6months = []
    apt = None
    if user.apartment_id:
        unpaid_count = get_unpaid_months_count(user.apartment_id)
        next_month = get_next_unpaid_month(user.apartment_id)
        my_payments = Payment.query.filter_by(apartment_id=user.apartment_id).order_by(Payment.payment_date.desc()).limit(10).all()
        apt = Apartment.query.get(user.apartment_id)
        if apt:
            credit = apt.credit_balance
        paid_months = {p.month_paid for p in my_payments}
        months_fr = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                     'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
        for (y, m) in last_n_months(6):
            month_str = f"{y}-{m:02d}"
            paid_entry = next((p for p in my_payments if p.month_paid == month_str), None)
            history_6months.append({
                'label': f"{months_fr[m-1]} {y}",
                'paid': paid_entry is not None,
                'amount': paid_entry.amount if paid_entry else 0,
            })
    org = current_organization()
    konnect_configured = bool(org and org.konnect_api_key and org.konnect_wallet_id)
    return render_template('residents.html', user=user, unpaid_count=unpaid_count,
                           next_month=next_month, my_payments=my_payments, credit=credit,
                           apt=apt, history_6months=history_6months,
                           konnect_configured=konnect_configured)


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
