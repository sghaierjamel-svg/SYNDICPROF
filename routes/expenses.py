from flask import render_template, request, redirect, url_for, flash
from core import app, db
from models import Expense
from utils import (current_user, current_organization, login_required,
                   admin_required, subscription_required)
from datetime import datetime


@app.route('/expenses', methods=['GET', 'POST'])
@login_required
@admin_required
@subscription_required
def expenses():
    org = current_organization()
    if request.method == 'POST':
        try:
            amount = float(request.form['amount'])
            expense_date = datetime.strptime(request.form['expense_date'], '%Y-%m-%d').date()
            category = request.form.get('category', 'Autre')
            description = request.form.get('description', '')
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
