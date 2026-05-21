from flask import render_template, send_file, jsonify, request
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

    # 9 mois passés (mois courant inclus)
    for i in range(8, -1, -1):
        month_date = today - relativedelta(months=i)
        all_months.append((month_date.year, month_date.month))

    # 3 mois à venir
    for i in range(1, 4):
        month_date = today + relativedelta(months=i)
        all_months.append((month_date.year, month_date.month))

    months = all_months  # déjà triés chronologiquement

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
    from openpyxl.styles import PatternFill, Font
    from models import User as UserModel

    org = current_organization()
    all_payments = Payment.query.filter_by(organization_id=org.id).all()
    all_expenses = Expense.query.filter_by(organization_id=org.id).all()

    # Collect available years from month_paid (handles advance payments) + expense dates
    years_set = set()
    for p in all_payments:
        if p.month_paid and len(p.month_paid) >= 4:
            years_set.add(p.month_paid[:4])
    for e in all_expenses:
        if e.expense_date:
            years_set.add(str(e.expense_date.year))
    years_set.add(str(date.today().year))
    available_years = sorted(years_set, reverse=True)

    year_param = request.args.get('year', '')
    if year_param not in available_years:
        return render_template('export_excel_choose.html',
                               available_years=available_years,
                               current_year=str(date.today().year),
                               user=current_user())

    year_str = year_param
    year = int(year_str)

    # Filter data for selected year — month_paid drives the year (advance payments land in correct year)
    payments_year = sorted(
        [p for p in all_payments if p.month_paid and p.month_paid.startswith(f"{year_str}-")],
        key=lambda p: (p.payment_date, p.id), reverse=True
    )
    expenses_year = sorted(
        [e for e in all_expenses if e.expense_date and e.expense_date.year == year],
        key=lambda e: e.expense_date, reverse=True
    )
    apartments = Apartment.query.filter_by(organization_id=org.id).order_by(Apartment.block_id, Apartment.number).all()

    # ---- Sheet 1: Appartements (état actuel) ----
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
        'Créé le': apt.created_at.strftime('%d/%m/%Y') if apt.created_at else '',
    } for apt in apartments])

    # ---- Sheet 2: Encaissements YYYY ----
    MODE_LABELS = {'especes': 'Espèces', 'virement': 'Virement', 'cheque': 'Chèque'}
    df_payments = pd.DataFrame([{
        'ID': p.id,
        'Appartement': f"{p.apartment.block.name}-{p.apartment.number}" if p.apartment else '',
        'Montant (DT)': p.amount,
        'Date Paiement': p.payment_date.strftime('%d/%m/%Y'),
        'Mois Payé': p.month_paid,
        'Mode': MODE_LABELS.get(p.payment_mode or 'especes', 'Espèces'),
        'N° Chèque': p.cheque_number or '',
        'Banque': p.cheque_bank or '',
        'Crédit Utilisé': p.credit_used or 0,
        'Description': p.description or '',
    } for p in payments_year])
    if df_payments.empty:
        df_payments = pd.DataFrame(columns=['ID', 'Appartement', 'Montant (DT)', 'Date Paiement', 'Mois Payé', 'Mode', 'N° Chèque', 'Banque', 'Crédit Utilisé', 'Description'])

    # ---- Sheet 3: Dépenses YYYY ----
    df_expenses = pd.DataFrame([{
        'ID': e.id,
        'Montant (DT)': e.amount,
        'Date': e.expense_date.strftime('%d/%m/%Y'),
        'Catégorie': e.category or '',
        'Description': e.description or '',
    } for e in expenses_year])
    if df_expenses.empty:
        df_expenses = pd.DataFrame(columns=['ID', 'Montant (DT)', 'Date', 'Catégorie', 'Description'])

    # ---- Sheet 4: Impayés (état actuel) ----
    df_unpaid = pd.DataFrame([{
        'Appartement': f"{apt.block.name}-{apt.number}",
        'Place Parking': apt.parking_spot or '',
        'Redevance Mensuelle (DT)': apt.monthly_fee,
        'Crédit Disponible (DT)': apt.credit_balance,
        'Mois Impayés': get_unpaid_months_count(apt.id),
        'Prochain Mois': get_next_unpaid_month(apt.id),
        'Total Dû (DT)': apt.monthly_fee * get_unpaid_months_count(apt.id),
    } for apt in apartments if get_unpaid_months_count(apt.id) > 0])
    if df_unpaid.empty:
        df_unpaid = pd.DataFrame(columns=['Appartement', 'Place Parking', 'Redevance Mensuelle (DT)', 'Crédit Disponible (DT)', 'Mois Impayés', 'Prochain Mois', 'Total Dû (DT)'])

    # ---- Sheet 5: Tableau Comptable YYYY (12 mois fixes, avec couleurs) ----
    MONTH_NAMES = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin', 'Juil', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc']

    # Paid months per apartment for the selected year (uses month_paid, not payment_date)
    paid_by_apt = {}
    for p in all_payments:
        if p.month_paid and p.month_paid.startswith(f"{year_str}-"):
            paid_by_apt.setdefault(p.apartment_id, set()).add(p.month_paid)

    comptable_data = []
    for apt in apartments:
        apt_paid = paid_by_apt.get(apt.id, set())
        nb_payes = 0
        total_percu = 0.0
        row = {
            'Appartement': f"{apt.block.name}-{apt.number}",
            'Redevance (DT)': apt.monthly_fee,
        }
        for m in range(1, 13):
            month_key = f"{year_str}-{m:02d}"
            if month_key in apt_paid:
                row[MONTH_NAMES[m - 1]] = 'Payé'
                nb_payes += 1
                total_percu += apt.monthly_fee
            else:
                row[MONTH_NAMES[m - 1]] = 'Impayé'
        nb_impayes = 12 - nb_payes
        row['Nb Payés'] = nb_payes
        row['Nb Impayés'] = nb_impayes
        row['Total Perçu (DT)'] = round(total_percu, 3)
        row['Total Dû (DT)'] = round(apt.monthly_fee * nb_impayes, 3)
        comptable_data.append(row)
    df_comptable = pd.DataFrame(comptable_data)

    # Write Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_apartments.to_excel(writer, sheet_name='Appartements', index=False)
        df_payments.to_excel(writer, sheet_name=f'Encaissements {year_str}', index=False)
        df_expenses.to_excel(writer, sheet_name=f'Dépenses {year_str}', index=False)
        df_unpaid.to_excel(writer, sheet_name='Impayés', index=False)
        df_comptable.to_excel(writer, sheet_name=f'Tableau {year_str}', index=False)

        # Color coding for Tableau sheet
        fill_green = PatternFill(start_color='C6EFCE', end_color='C6EFCE', fill_type='solid')
        font_green = Font(color='276221')
        fill_red = PatternFill(start_color='FFC7CE', end_color='FFC7CE', fill_type='solid')
        font_red = Font(color='9C0006')

        ws_tab = writer.sheets[f'Tableau {year_str}']
        headers = [cell.value for cell in ws_tab[1]]
        month_cols = {h: i + 1 for i, h in enumerate(headers) if h in MONTH_NAMES}

        for row_idx in range(2, ws_tab.max_row + 1):
            for col_idx in month_cols.values():
                cell = ws_tab.cell(row=row_idx, column=col_idx)
                if cell.value == 'Payé':
                    cell.fill = fill_green
                    cell.font = font_green
                elif cell.value == 'Impayé':
                    cell.fill = fill_red
                    cell.font = font_red

        ws_tab.freeze_panes = 'C2'

        # Auto-fit column widths on all sheets
        for ws in writer.sheets.values():
            for col in ws.columns:
                max_len = max((len(str(cell.value)) for cell in col if cell.value), default=8)
                ws.column_dimensions[col[0].column_letter].width = min(max_len + 3, 32)

    output.seek(0)
    filename = f"SyndicPro_{org.name}_{year_str}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(output, download_name=filename, as_attachment=True,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
