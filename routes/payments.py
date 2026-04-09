from flask import render_template, request, redirect, url_for, flash, jsonify, send_file
import io
from core import app, db
from models import Apartment, Payment, User, MiscReceipt, KonnectPayment, FlouciPayment
from utils import (current_user, current_organization, login_required,
                   admin_required, subscription_required,
                   get_unpaid_months_count, get_next_unpaid_month)
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from utils_whatsapp import notify_payment


@app.route('/payments', methods=['GET', 'POST'])
@login_required
@admin_required
@subscription_required
def payments():
    org = current_organization()
    apartments = Apartment.query.filter_by(organization_id=org.id).all()

    if request.method == 'POST':
        try:
            from datetime import date as date_cls
            apartment_id = int(request.form['apartment_id'])
            amount = float(request.form['amount'])
            # HIGH-005 : validation montant et date
            if amount <= 0 or amount > 9_999_999:
                flash('Montant invalide (doit être > 0 et < 10 000 000 DT).', 'danger')
                return redirect(url_for('payments'))
            payment_date = datetime.strptime(request.form['payment_date'], '%Y-%m-%d').date()
            if payment_date > date_cls.today():
                flash('La date de paiement ne peut pas être dans le futur.', 'danger')
                return redirect(url_for('payments'))
            description = request.form.get('description', 'Redevance')[:200]
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
                # Notification WhatsApp + Push → admin
                try:
                    resident = User.query.filter_by(apartment_id=apartment_id).first()
                    notify_payment(org, apt, paid_months_list[-1], total_recorded_amount, resident)
                except Exception:
                    pass
                try:
                    from utils_push import push_to_admins
                    apt_label = f"{apt.block.name}-{apt.number}"
                    months_str = ", ".join(paid_months_list) if len(paid_months_list) <= 3 else f"{paid_months_list[0]} … {paid_months_list[-1]}"
                    push_to_admins(
                        org.id,
                        title=f"💰 Paiement reçu — {apt_label}",
                        body=f"{total_recorded_amount:.2f} DT — {months_str}",
                        url="/payments",
                    )
                except Exception:
                    pass
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

    # Encaissements divers
    misc_list = MiscReceipt.query.filter_by(organization_id=org.id).order_by(MiscReceipt.payment_date.desc()).all()

    # Charger TOUS les paiements de l'org en UNE seule requête (évite le N+1)
    payments_list = Payment.query.filter_by(organization_id=org.id).order_by(Payment.payment_date.desc()).all()

    # Grouper les mois payés par appartement en mémoire (pas de requêtes supplémentaires)
    paid_months_by_apt = {}
    for p in payments_list:
        paid_months_by_apt.setdefault(p.apartment_id, set()).add(p.month_paid)

    today_month = date.today().replace(day=1)

    for apt in apartments:
        paid = paid_months_by_apt.get(apt.id, set())
        start = apt.created_at.date().replace(day=1) if apt.created_at else today_month
        end_count = today_month
        end_next = today_month + relativedelta(months=3)

        # Calcul impayés
        unpaid = 0
        cur = start
        while cur <= end_count:
            if cur.strftime('%Y-%m') not in paid:
                unpaid += 1
            cur += relativedelta(months=1)
        apt.unpaid_count = unpaid

        # Premier mois impayé
        apt.next_unpaid = (end_next + relativedelta(months=1)).strftime('%Y-%m')
        cur = start
        while cur <= end_next:
            if cur.strftime('%Y-%m') not in paid:
                apt.next_unpaid = cur.strftime('%Y-%m')
                break
            cur += relativedelta(months=1)

    konnect_links = KonnectPayment.query.filter_by(organization_id=org.id)\
        .order_by(KonnectPayment.created_at.desc()).all()
    flouci_links = FlouciPayment.query.filter_by(organization_id=org.id)\
        .order_by(FlouciPayment.created_at.desc()).all()

    return render_template('payments.html', apartments=apartments, payments=payments_list,
                           misc_list=misc_list, konnect_links=konnect_links,
                           flouci_links=flouci_links, org=org, user=current_user())


@app.route('/misc-receipt/add', methods=['POST'])
@login_required
@admin_required
@subscription_required
def add_misc_receipt():
    org = current_organization()
    try:
        amount = float(request.form['amount'])
        if amount <= 0 or amount > 9_999_999:
            flash('Montant invalide.', 'danger')
            return redirect(url_for('payments') + '#divers')
        payment_date = datetime.strptime(request.form['payment_date'], '%Y-%m-%d').date()
        libelle = request.form.get('libelle', '').strip()[:100]
        if not libelle:
            flash('Le libellé est obligatoire.', 'danger')
            return redirect(url_for('payments') + '#divers')
        description = request.form.get('description', '').strip()[:300]
        m = MiscReceipt(
            organization_id=org.id,
            amount=amount,
            payment_date=payment_date,
            libelle=libelle,
            description=description or None,
        )
        db.session.add(m)
        db.session.commit()
        flash(f'Encaissement divers "{libelle}" enregistré ({amount:.2f} DT).', 'success')
    except Exception as e:
        print(f"ERREUR misc_receipt: {e}")
        flash('Une erreur est survenue.', 'danger')
    return redirect(url_for('payments') + '#divers')


@app.route('/misc-receipt/edit/<int:receipt_id>', methods=['POST'])
@login_required
@admin_required
@subscription_required
def edit_misc_receipt(receipt_id):
    org = current_organization()
    m = MiscReceipt.query.filter_by(id=receipt_id, organization_id=org.id).first_or_404()
    try:
        amount = float(request.form['amount'])
        if amount <= 0 or amount > 9_999_999:
            flash('Montant invalide.', 'danger')
            return redirect(url_for('payments') + '#divers')
        m.amount = amount
        m.payment_date = datetime.strptime(request.form['payment_date'], '%Y-%m-%d').date()
        libelle = request.form.get('libelle', '').strip()[:100]
        if not libelle:
            flash('Le libellé est obligatoire.', 'danger')
            return redirect(url_for('payments') + '#divers')
        m.libelle = libelle
        m.description = request.form.get('description', '').strip()[:300] or None
        db.session.commit()
        flash('Encaissement modifié.', 'success')
    except Exception as e:
        print(f"ERREUR edit_misc_receipt: {e}")
        flash('Une erreur est survenue.', 'danger')
    return redirect(url_for('payments') + '#divers')


@app.route('/misc-receipt/delete/<int:receipt_id>', methods=['POST'])
@login_required
@admin_required
@subscription_required
def delete_misc_receipt(receipt_id):
    org = current_organization()
    m = MiscReceipt.query.filter_by(id=receipt_id, organization_id=org.id).first_or_404()
    db.session.delete(m)
    db.session.commit()
    flash('Encaissement supprimé.', 'success')
    return redirect(url_for('payments') + '#divers')


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


@app.route('/payment/<int:payment_id>/recu.pdf')
@login_required
@subscription_required
def payment_receipt(payment_id):
    """Reçu PDF d'un paiement — accessible par le résident concerné et les admins."""
    from fpdf import FPDF
    org = current_organization()
    user = current_user()
    p = Payment.query.filter_by(id=payment_id, organization_id=org.id).first_or_404()
    # Sécurité : résident ne peut télécharger que ses propres reçus
    if user.role == 'resident' and p.apartment_id != user.apartment_id:
        flash('Accès non autorisé.', 'danger')
        from flask import redirect
        return redirect(url_for('residents_menu'))

    apt = p.apartment
    resident = apt.residents[0] if apt.residents else None

    def _s(t):
        if not t: return ''
        return (str(t)
            .replace('\u2014', '-').replace('\u2013', '-')
            .replace('\u2019', "'").replace('\u2018', "'")
            .encode('latin-1', errors='replace').decode('latin-1'))

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # En-tête — fond blanc, bandeau vert
    pdf.set_fill_color(0, 180, 130)
    pdf.rect(0, 0, 210, 32, 'F')
    pdf.set_xy(0, 5)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Helvetica', 'B', 22)
    pdf.cell(0, 11, 'SyndicPro', ln=True, align='C')
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(0, 6, _s(org.name), ln=True, align='C')
    pdf.ln(6)

    # Titre reçu
    pdf.set_fill_color(240, 253, 250)
    pdf.set_draw_color(0, 180, 130)
    pdf.set_line_width(0.5)
    pdf.set_text_color(0, 120, 90)
    pdf.set_font('Helvetica', 'B', 13)
    pdf.cell(0, 10, f'  RECU DE PAIEMENT  N\xb0 {p.id:05d}', ln=True, fill=True, border=1)
    pdf.ln(6)

    def line(label, value, accent=False):
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(60, 7, _s(label))
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(0, 140, 100) if accent else pdf.set_text_color(40, 40, 40)
        pdf.cell(0, 7, _s(str(value)), ln=True)

    line('Appartement :', f"{apt.block.name}-{apt.number}")
    line('Resident :', resident.name if resident else '-')
    line('Mois paye :', p.month_paid)
    line('Date de paiement :', p.payment_date.strftime('%d/%m/%Y'))
    if p.description:
        line('Description :', p.description)
    pdf.ln(4)
    pdf.set_draw_color(200, 200, 200)
    pdf.set_line_width(0.3)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)

    # Montant
    pdf.set_fill_color(0, 180, 130)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 13, f'  MONTANT PAYE : {p.amount:.3f} DT', ln=True, fill=True)
    if p.credit_used and p.credit_used > 0:
        pdf.set_font('Helvetica', '', 8)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 5, f'  (dont {p.credit_used:.3f} DT de credit reporte)', ln=True)

    pdf.ln(10)
    pdf.set_draw_color(200, 200, 200)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)
    pdf.set_font('Helvetica', 'I', 7)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 4, _s(f'Document genere le {datetime.now().strftime("%d/%m/%Y")} - SyndicPro, {org.name}'), ln=True, align='C')
    pdf.cell(0, 4, 'Ce recu est emis par le syndic de copropriete et vaut justificatif de paiement.', ln=True, align='C')

    buf = io.BytesIO(pdf.output())
    buf.seek(0)
    filename = f"Recu_{apt.block.name}{apt.number}_{p.month_paid}.pdf"
    return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=filename)


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
