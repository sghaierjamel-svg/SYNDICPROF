from flask import render_template, request, redirect, url_for, flash, jsonify
from core import app, db
from models import Apartment, Payment
from utils import (current_user, current_organization, login_required,
                   admin_required, subscription_required,
                   get_unpaid_months_count, get_next_unpaid_month)
from datetime import datetime
from dateutil.relativedelta import relativedelta


@app.route('/payments', methods=['GET', 'POST'])
@login_required
@admin_required
@subscription_required
def payments():
    org = current_organization()
    apartments = Apartment.query.filter_by(organization_id=org.id).all()

    if request.method == 'POST':
        try:
            apartment_id = int(request.form['apartment_id'])
            amount = float(request.form['amount'])
            payment_date = datetime.strptime(request.form['payment_date'], '%Y-%m-%d').date()
            description = request.form.get('description', 'Redevance')
            start_month_str = request.form.get('start_month', '').strip()

            apt = Apartment.query.get(apartment_id)
            if not apt:
                flash("Appartement introuvable", "danger")
                return redirect(url_for('payments'))

            monthly_fee = apt.monthly_fee

            # Ajouter le crédit existant au montant payé
            credit_used = apt.credit_balance
            total_available = amount + credit_used

            if credit_used > 0:
                flash(f"Crédit utilisé : {credit_used:.2f} DT", "info")

            months_to_pay = int(total_available // monthly_fee)
            new_remainder = total_available % monthly_fee

            if months_to_pay == 0:
                apt.credit_balance = total_available
                db.session.commit()
                flash(f"Montant ajouté au crédit : {amount:.2f} DT", "info")
                flash(f"Crédit total : {apt.credit_balance:.2f} DT (sera utilisé au prochain paiement)", "success")
                return redirect(url_for('payments'))

            # Déterminer le mois de départ
            if start_month_str:
                try:
                    start_month_date = datetime.strptime(start_month_str, "%Y-%m").date().replace(day=1)
                    flash(f"Mode manuel : Paiement à partir de {start_month_str}", "info")
                except ValueError:
                    flash("Format de mois invalide (utilisez YYYY-MM)", "danger")
                    return redirect(url_for('payments'))
            else:
                next_month_str = get_next_unpaid_month(apartment_id)
                start_month_date = datetime.strptime(next_month_str, "%Y-%m").date().replace(day=1)
                flash(f"Mode automatique : Paiement à partir du premier mois impayé ({next_month_str})", "info")

            # Récupérer les mois déjà payés
            existing_paid_months = set(
                p.month_paid for p in Payment.query.filter_by(apartment_id=apartment_id).all()
            )

            months_actually_paid = 0
            total_recorded_amount = 0.0
            paid_months_list = []

            for i in range(months_to_pay):
                month_paid_date = start_month_date + relativedelta(months=i)
                month_paid_str = month_paid_date.strftime("%Y-%m")

                # VÉRIFICATION ANTI-DOUBLON
                if month_paid_str in existing_paid_months:
                    flash(f"Le mois {month_paid_str} est déjà payé, il sera ignoré", "warning")
                    new_remainder += monthly_fee
                    continue

                # Enregistrer le paiement
                p = Payment(
                    organization_id=org.id,
                    apartment_id=apartment_id,
                    amount=monthly_fee,
                    payment_date=payment_date,
                    month_paid=month_paid_str,
                    description=f"Redevance {month_paid_str}",
                    credit_used=credit_used if i == 0 else 0.0
                )
                db.session.add(p)
                months_actually_paid += 1
                total_recorded_amount += monthly_fee
                paid_months_list.append(month_paid_str)

                # Réinitialiser credit_used après le premier mois
                if i == 0:
                    credit_used = 0.0

            # Mettre à jour le crédit résiduel
            apt.credit_balance = new_remainder
            db.session.commit()

            # Messages de confirmation détaillés
            if months_actually_paid > 0:
                months_display = ", ".join(paid_months_list)
                flash(f"Paiement enregistré avec succès !", "success")
                flash(f"{months_actually_paid} mois payé(s) : {months_display}", "success")
                flash(f"Montant total : {total_recorded_amount:.2f} DT", "info")
            else:
                flash("Aucun nouveau mois n'a été payé (tous les mois étaient déjà payés)", "warning")

            if new_remainder > 0:
                flash(f"Nouveau crédit : {new_remainder:.2f} DT (sera utilisé automatiquement au prochain paiement)", "success")
            elif apt.credit_balance == 0 and months_actually_paid > 0:
                flash(f"Montant exact, aucun crédit résiduel", "info")

        except Exception as e:
            print(f"ERREUR paiement: {str(e)}")
            flash('Une erreur est survenue. Réessayez.', 'danger')

        return redirect(url_for('payments'))

    # Préparer les données pour l'affichage
    for apt in apartments:
        apt.next_unpaid = get_next_unpaid_month(apt.id)
        apt.unpaid_count = get_unpaid_months_count(apt.id)

    payments_list = Payment.query.filter_by(organization_id=org.id).order_by(Payment.payment_date.desc()).all()
    return render_template('payments.html', apartments=apartments, payments=payments_list, user=current_user())


@app.route('/api/next_unpaid/<int:apartment_id>')
@login_required
@subscription_required
def api_next_unpaid(apartment_id):
    org = current_organization()
    apt = Apartment.query.filter_by(id=apartment_id, organization_id=org.id).first_or_404()
    next_month = get_next_unpaid_month(apartment_id)
    unpaid_count = get_unpaid_months_count(apartment_id)
    return jsonify({
        'next_month': next_month,
        'unpaid_count': unpaid_count,
        'monthly_fee': apt.monthly_fee,
        'credit_balance': apt.credit_balance
    })


@app.route('/payment/edit/<int:payment_id>', methods=['GET', 'POST'])
@login_required
@admin_required
@subscription_required
def edit_payment(payment_id):
    org = current_organization()
    p = Payment.query.filter_by(id=payment_id, organization_id=org.id).first_or_404()
    apartments = Apartment.query.filter_by(organization_id=org.id).all()
    if request.method == 'POST':
        p.apartment_id = int(request.form['apartment_id'])
        p.amount = float(request.form['amount'])
        p.payment_date = datetime.strptime(request.form['payment_date'], '%Y-%m-%d').date()
        p.month_paid = request.form['month_paid']
        p.description = request.form.get('description', '')
        db.session.commit()
        flash('Encaissement modifié', 'success')
        return redirect(url_for('payments'))
    return render_template('edit_payment.html', payment=p, apartments=apartments, user=current_user())


@app.route('/payment/delete/<int:payment_id>', methods=['POST'])
@login_required
@admin_required
@subscription_required
def delete_payment(payment_id):
    org = current_organization()
    p = Payment.query.filter_by(id=payment_id, organization_id=org.id).first_or_404()
    db.session.delete(p)
    db.session.commit()
    flash('Encaissement supprimé', 'success')
    return redirect(url_for('payments'))
