from flask import render_template, request, redirect, url_for, flash
from core import app, db
from models import Expense
from utils import (current_user, current_organization, login_required,
                   admin_required, subscription_required)
from datetime import datetime, date


@app.route('/expenses', methods=['GET', 'POST'])
@login_required
@admin_required
@subscription_required
def expenses():
    org = current_organization()
    if request.method == 'POST':
        try:
            amount = float(request.form['amount'])
            # HIGH-006 : validation montant
            if amount <= 0 or amount > 9_999_999:
                flash('Montant invalide (doit être > 0 et < 10 000 000 DT).', 'danger')
                return redirect(url_for('expenses'))
            expense_date = datetime.strptime(request.form['expense_date'], '%Y-%m-%d').date()
            category = request.form.get('category', 'Autre')
            description = request.form.get('description', '')[:300]
            e = Expense(
                organization_id=org.id,
                amount=amount,
                expense_date=expense_date,
                category=category,
                description=description
            )
            db.session.add(e)
            db.session.commit()
            flash('Dépense enregistrée', 'success')
        except Exception as e:
            print(f"ERREUR dépense: {str(e)}")
            flash('Une erreur est survenue. Réessayez.', 'danger')
        return redirect(url_for('expenses'))
    expenses_list = Expense.query.filter_by(organization_id=org.id).order_by(Expense.expense_date.desc()).all()
    return render_template('expenses.html', expenses=expenses_list, user=current_user())


@app.route('/expense/edit/<int:expense_id>', methods=['GET', 'POST'])
@login_required
@admin_required
@subscription_required
def edit_expense(expense_id):
    org = current_organization()
    e = Expense.query.filter_by(id=expense_id, organization_id=org.id).first_or_404()
    if request.method == 'POST':
        e.amount = float(request.form['amount'])
        e.expense_date = datetime.strptime(request.form['expense_date'], '%Y-%m-%d').date()
        e.category = request.form.get('category', 'Autre')
        e.description = request.form.get('description', '')
        db.session.commit()
        flash('Dépense modifiée', 'success')
        return redirect(url_for('expenses'))
    return render_template('edit_expense.html', expense=e, user=current_user())


@app.route('/expense/nouvelle-immobilisation', methods=['GET', 'POST'])
@login_required
@admin_required
@subscription_required
def nouvelle_immobilisation():
    org = current_organization()
    if request.method == 'POST':
        try:
            amount        = float(request.form['amount'])
            expense_date  = datetime.strptime(request.form['expense_date'], '%Y-%m-%d').date()
            asset_name    = request.form.get('asset_name', '').strip()
            supplier      = request.form.get('supplier', '').strip()
            invoice_num   = request.form.get('invoice_number', '').strip()
            duration      = request.form.get('duration_years', '5')
            notes         = request.form.get('notes', '').strip()

            # Calcul dotation annuelle
            try:
                taux = round(1 / int(duration) * 100, 1)
                dotation = round(amount / int(duration), 3)
            except (ValueError, ZeroDivisionError):
                taux, dotation = 20.0, round(amount / 5, 3)

            # Stockage structuré dans description
            parts = [f"Bien: {asset_name}"]
            if supplier:
                parts.append(f"Fourn.: {supplier}")
            if invoice_num:
                parts.append(f"Facture: {invoice_num}")
            parts.append(f"Amort.: {duration} ans ({taux}%) - Dot./an: {dotation:.3f} DT")
            if notes:
                parts.append(f"Note: {notes}")
            description = " | ".join(parts)

            e = Expense(
                organization_id=org.id,
                amount=amount,
                expense_date=expense_date,
                category='Immobilisation',
                description=description
            )
            db.session.add(e)
            db.session.commit()
            flash(f'Immobilisation "{asset_name}" enregistrée ({amount:.3f} DT, amort. {duration} ans).', 'success')
        except Exception as ex:
            print(f"ERREUR immobilisation: {ex}")
            flash('Une erreur est survenue. Réessayez.', 'danger')
        return redirect(url_for('expenses'))

    # GET : pré-remplir depuis les paramètres URL transmis par le formulaire dépenses
    prefill_amount = request.args.get('amount', '')
    prefill_date   = request.args.get('date', date.today().strftime('%Y-%m-%d'))
    return render_template('new_asset.html',
                           user=current_user(),
                           prefill_amount=prefill_amount,
                           prefill_date=prefill_date)


@app.route('/expense/delete/<int:expense_id>', methods=['POST'])
@login_required
@admin_required
@subscription_required
def delete_expense(expense_id):
    org = current_organization()
    e = Expense.query.filter_by(id=expense_id, organization_id=org.id).first_or_404()
    db.session.delete(e)
    db.session.commit()
    flash('Dépense supprimée', 'success')
    return redirect(url_for('expenses'))
