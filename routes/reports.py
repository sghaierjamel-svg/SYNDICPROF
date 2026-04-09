from flask import render_template, send_file, jsonify
from core import app
from models import Apartment, Payment, Expense, MiscReceipt
from utils import (current_user, current_organization, login_required,
                   subscription_required, last_n_months, get_month_name,
                   get_unpaid_months_count, get_next_unpaid_month)
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import pandas as pd
import io


@app.route('/tresorerie')
@login_required
@subscription_required
def tresorerie():
    org = current_organization()
    months = last_n_months(12)
    apartments = Apartment.query.filter_by(organization_id=org.id).order_by(Apartment.block_id, Apartment.number).all()
    expenses = Expense.query.filter_by(organization_id=org.id).all()
    payments = Payment.query.filter_by(organization_id=org.id).all()
    misc_receipts = MiscReceipt.query.filter_by(organization_id=org.id).all()

    data = []
    for apt in apartments:
        row = {'apartment': f"{apt.block.name}-{apt.number}", 'months': {}}
        for year, month in months:
            month_key = f"{year}-{month:02d}"
            total = sum(p.amount for p in payments
                       if p.apartment_id == apt.id
                       and p.payment_date.year == year
                       and p.payment_date.month == month)
            row['months'][month_key] = total
        data.append(row)

    # Ligne encaissements divers
    misc_row = {'apartment': 'ENCAISSEMENTS DIVERS', 'months': {}}
    for year, month in months:
        month_key = f"{year}-{month:02d}"
        misc_row['months'][month_key] = sum(
            m.amount for m in misc_receipts
            if m.payment_date.year == year and m.payment_date.month == month
        )

    expense_row = {'apartment': 'DÉPENSES', 'months': {}}
    for year, month in months:
        month_key = f"{year}-{month:02d}"
        total = sum(e.amount for e in expenses
                   if e.expense_date.year == year
                   and e.expense_date.month == month)
        expense_row['months'][month_key] = total

    solde_row = {'apartment': 'SOLDE', 'months': {}}
    for year, month in months:
        month_key = f"{year}-{month:02d}"
        total_in = sum(row['months'][month_key] for row in data) + misc_row['months'][month_key]
        total_out = expense_row['months'][month_key]
        solde_row['months'][month_key] = total_in - total_out

    return render_template('tresorerie.html',
                         data=data,
                         misc_row=misc_row,
                         expense_row=expense_row,
                         solde_row=solde_row,
                         months=months,
                         user=current_user())


@app.route('/comptable')
@login_required
@subscription_required
def comptable():
    org = current_organization()
    today = date.today()
    all_months = []

    for i in range(11, -1, -1):
        month_date = today - relativedelta(months=i)
        all_months.append((month_date.year, month_date.month))

    for i in range(1, 4):
        month_date = today + relativedelta(months=i)
        all_months.append((month_date.year, month_date.month))

    months = sorted(list(set(all_months)))

    apartments = Apartment.query.filter_by(organization_id=org.id).order_by(Apartment.block_id, Apartment.number).all()
    payments = Payment.query.filter_by(organization_id=org.id).all()
    data = []

    all_paid_months = {}
    for p in payments:
        if p.apartment_id not in all_paid_months:
            all_paid_months[p.apartment_id] = set()
        all_paid_months[p.apartment_id].add(p.month_paid)

    for apt in apartments:
        row = {
            'apartment': f"{apt.block.name}-{apt.number}",
            'monthly_fee': apt.monthly_fee,
            'credit_balance': apt.credit_balance,
            'months': {}
        }

        apt_paid_months = all_paid_months.get(apt.id, set())

        for year, month in months:
            month_key = f"{year}-{month:02d}"
            paid = month_key in apt_paid_months
            amount = apt.monthly_fee if paid else 0
            row['months'][month_key] = {'paid': paid, 'amount': amount}

        row['unpaid_count'] = get_unpaid_months_count(apt.id)
        data.append(row)

    return render_template('comptable.html', data=data, months=months, user=current_user())


@app.route('/export_excel')
@login_required
@subscription_required
def export_excel():
    org = current_organization()
    payments = Payment.query.filter_by(organization_id=org.id).order_by(Payment.payment_date.desc()).all()
    expenses = Expense.query.filter_by(organization_id=org.id).order_by(Expense.expense_date.desc()).all()
    apartments = Apartment.query.filter_by(organization_id=org.id).all()
    df_payments = pd.DataFrame([{
        'ID': p.id,
        'Appartement': f"{p.apartment.block.name}-{p.apartment.number}" if p.apartment else '',
        'Montant': p.amount,
        'Date Paiement': p.payment_date.strftime('%Y-%m-%d'),
        'Mois Payé': p.month_paid,
        'Crédit Utilisé': p.credit_used,
        'Description': p.description
    } for p in payments])
    df_expenses = pd.DataFrame([{
        'ID': e.id,
        'Montant': e.amount,
        'Date': e.expense_date.strftime('%Y-%m-%d'),
        'Catégorie': e.category,
        'Description': e.description
    } for e in expenses])
    df_unpaid = pd.DataFrame([{
        'Appartement': f"{apt.block.name}-{apt.number}",
        'Place Parking': apt.parking_spot or '',
        'Redevance Mensuelle': apt.monthly_fee,
        'Crédit Disponible': apt.credit_balance,
        'Mois Impayés': get_unpaid_months_count(apt.id),
        'Prochain Mois': get_next_unpaid_month(apt.id),
        'Total Dû': apt.monthly_fee * get_unpaid_months_count(apt.id)
    } for apt in apartments])

    # Feuille complète de tous les appartements
    from models import User as UserModel
    residents_by_apt = {u.apartment_id: u for u in UserModel.query.filter_by(organization_id=org.id, role='resident').all()}
    df_apartments = pd.DataFrame([{
        'Bloc': apt.block.name,
        'Appartement': apt.number,
        'Référence': f"{apt.block.name}-{apt.number}",
        'Place Parking': apt.parking_spot or '',
        'Redevance Mensuelle (DT)': apt.monthly_fee,
        'Crédit (DT)': apt.credit_balance,
        'Résident': residents_by_apt[apt.id].name if apt.id in residents_by_apt else '',
        'Email Résident': residents_by_apt[apt.id].email if apt.id in residents_by_apt else '',
        'Téléphone': residents_by_apt[apt.id].phone if apt.id in residents_by_apt else '',
        'Mois Impayés': get_unpaid_months_count(apt.id),
        'Total Dû (DT)': apt.monthly_fee * get_unpaid_months_count(apt.id),
        'Créé le': apt.created_at.strftime('%Y-%m-%d') if apt.created_at else '',
    } for apt in apartments])

    today = date.today()
    all_months = []
    for i in range(11, -1, -1):
        month_date = today - relativedelta(months=i)
        all_months.append((month_date.year, month_date.month))
    for i in range(1, 4):
        month_date = today + relativedelta(months=i)
        all_months.append((month_date.year, month_date.month))
    months = sorted(list(set(all_months)))

    comptable_data = []
    all_paid_months = {}
    for p in payments:
        if p.apartment_id not in all_paid_months:
            all_paid_months[p.apartment_id] = set()
        all_paid_months[p.apartment_id].add(p.month_paid)

    for apt in apartments:
        row = {
            'Appartement': f"{apt.block.name}-{apt.number}",
            'Redevance': apt.monthly_fee,
            'Crédit': apt.credit_balance
        }
        apt_paid_months = all_paid_months.get(apt.id, set())
        for year, month in months:
            month_key = f"{year}-{month:02d}"
            paid = month_key in apt_paid_months
            row[month_key] = 'Payé' if paid else 'Impayé'
        comptable_data.append(row)
    df_comptable = pd.DataFrame(comptable_data)

    if df_payments.empty:
        df_payments = pd.DataFrame(columns=['ID', 'Appartement', 'Montant', 'Date Paiement', 'Mois Payé', 'Crédit Utilisé', 'Description'])
    if df_expenses.empty:
        df_expenses = pd.DataFrame(columns=['ID', 'Montant', 'Date', 'Catégorie', 'Description'])

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_apartments.to_excel(writer, sheet_name='Appartements', index=False)
        df_payments.to_excel(writer, sheet_name='Encaissements', index=False)
        df_expenses.to_excel(writer, sheet_name='Dépenses', index=False)
        df_unpaid.to_excel(writer, sheet_name='Impayés', index=False)
        df_comptable.to_excel(writer, sheet_name='Tableau Comptable', index=False)

    output.seek(0)
    filename = f"SyndicPro_{org.name}_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(output, download_name=filename, as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
