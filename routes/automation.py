from flask import render_template, redirect, url_for, flash, send_file
from core import app, db
from models import Apartment, Payment, Expense, User, Organization
from utils import (current_user, current_organization, login_required,
                   admin_required, subscription_required, get_unpaid_map)
from utils_whatsapp import send_whatsapp
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from datetime import date
import io


# ─── Tableau de bord automatisation ─────────────────────────────────────────

@app.route('/automation')
@login_required
@admin_required
@subscription_required
def automation():
    org = current_organization()
    apartments = (Apartment.query.options(joinedload(Apartment.block))
                  .filter_by(organization_id=org.id).all())
    current_month = date.today().strftime('%Y-%m')
    # Appartements payés ce mois — requête scopée (pas tout l'historique)
    paid_ids = {row[0] for row in
                db.session.query(Payment.apartment_id)
                .filter(Payment.organization_id == org.id,
                        Payment.month_paid == current_month).all()}
    # Impayés + résidents en batch (au lieu de 2 N+1 par appartement)
    unpaid_map = get_unpaid_map(org.id, apartments)
    residents_by_apt = {}
    for u in User.query.filter_by(organization_id=org.id, role='resident').all():
        residents_by_apt.setdefault(u.apartment_id, u)

    unpaid = []
    for a in apartments:
        if a.id not in paid_ids:
            r = residents_by_apt.get(a.id)
            unpaid.append({
                'apt': a,
                'unpaid_count': unpaid_map.get(a.id, 0),
                'resident': r,
                'has_whatsapp': bool(r and r.phone),
            })

    unpaid.sort(key=lambda x: x['unpaid_count'], reverse=True)
    return render_template('automation.html', user=current_user(), org=org,
                           unpaid=unpaid, current_month=current_month)


# ─── Relances WhatsApp groupées ──────────────────────────────────────────────

@app.route('/automation/send-reminders', methods=['POST'])
@login_required
@admin_required
@subscription_required
def send_reminders():
    org = current_organization()
    if not org.whatsapp_enabled or not org.whatsapp_token:
        flash("WhatsApp non configuré. Activez-le dans Paramètres.", "warning")
        return redirect(url_for('automation'))

    current_month = date.today().strftime('%Y-%m')
    apartments = (Apartment.query.options(joinedload(Apartment.block))
                  .filter_by(organization_id=org.id).all())
    paid_ids = {row[0] for row in
                db.session.query(Payment.apartment_id)
                .filter(Payment.organization_id == org.id,
                        Payment.month_paid == current_month).all()}
    unpaid_map = get_unpaid_map(org.id, apartments)
    residents_by_apt = {}
    for u in User.query.filter_by(organization_id=org.id, role='resident').all():
        residents_by_apt.setdefault(u.apartment_id, u)

    sent = 0
    no_phone = 0
    for a in apartments:
        if a.id in paid_ids:
            continue
        r = residents_by_apt.get(a.id)
        if not (r and r.phone):
            no_phone += 1
            continue
        cnt = unpaid_map.get(a.id, 0)
        msg = (
            f"📢 *SyndicPro — Rappel paiement*\n"
            f"Bonjour {r.name or 'résident'},\n"
            f"Appartement : *{a.block.name}-{a.number}*\n"
            f"Mois impayés : *{cnt}*\n"
            f"Montant dû : *{cnt * a.monthly_fee:.0f} DT*\n\n"
            f"Merci de régulariser votre situation.\n"
            f"— {org.name}"
        )
        if send_whatsapp(org, r.phone, msg):
            sent += 1
        else:
            no_phone += 1

    if sent:
        flash(f"✅ {sent} rappel(s) WhatsApp envoyé(s).", "success")
    if no_phone:
        flash(f"⚠️ {no_phone} appartement(s) sans numéro WhatsApp — non contactés.", "warning")
    if not sent and not no_phone:
        flash("Tous les appartements sont à jour ce mois !", "info")
    return redirect(url_for('automation'))


# ─── Rapport PDF mensuel ─────────────────────────────────────────────────────

@app.route('/automation/pdf-report')
@login_required
@admin_required
@subscription_required
def pdf_report():
    org = current_organization()
    from fpdf import FPDF

    current_month = date.today().strftime('%Y-%m')
    year, month_num = current_month.split('-')
    months_fr = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                 'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
    month_label = f"{months_fr[int(month_num)]} {year}"

    apartments = (Apartment.query.options(joinedload(Apartment.block))
                  .filter_by(organization_id=org.id).all())
    # Données du mois — requêtes scopées (pas tout l'historique en RAM)
    month_payments = (Payment.query
                      .options(joinedload(Payment.apartment).joinedload(Apartment.block))
                      .filter(Payment.organization_id == org.id,
                              Payment.month_paid == current_month).all())
    month_expenses = (Expense.query
                      .filter(Expense.organization_id == org.id,
                              func.extract('year',  Expense.expense_date) == int(year),
                              func.extract('month', Expense.expense_date) == int(month_num)).all())
    paid_ids = {p.apartment_id for p in month_payments}
    encaisse_mois = sum(p.amount for p in month_payments)
    depenses_mois = sum(e.amount for e in month_expenses)
    # Totaux cumulés — agrégats SQL (pas de chargement de l'historique)
    total_encaisse = db.session.query(func.coalesce(func.sum(Payment.amount), 0))\
        .filter_by(organization_id=org.id).scalar()
    total_depenses = db.session.query(func.coalesce(func.sum(Expense.amount), 0))\
        .filter_by(organization_id=org.id).scalar()
    unpaid_map = get_unpaid_map(org.id, apartments)

    # ── Création PDF ──────────────────────────────────────────────────────────
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # En-tête — bandeau vert sur fond blanc
    pdf.set_fill_color(0, 180, 130)
    pdf.rect(0, 0, 210, 32, 'F')
    pdf.set_xy(0, 5)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Helvetica', 'B', 20)
    pdf.cell(0, 12, 'SyndicPro', new_x="LMARGIN", new_y="NEXT", align='C')
    pdf.set_font('Helvetica', '', 12)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 6, f"Rapport mensuel — {month_label}", new_x="LMARGIN", new_y="NEXT", align='C')
    pdf.cell(0, 6, org.name, new_x="LMARGIN", new_y="NEXT", align='C')
    pdf.ln(6)

    def section(title):
        pdf.set_fill_color(220, 240, 235)
        pdf.set_text_color(0, 140, 100)
        pdf.set_font('Helvetica', 'B', 11)
        pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT", fill=True)
        pdf.set_text_color(30, 30, 30)
        pdf.ln(2)

    def row(label, value, bold=False):
        pdf.set_font('Helvetica', 'B' if bold else '', 10)
        pdf.set_text_color(50, 50, 50)
        pdf.cell(100, 7, label)
        pdf.set_text_color(0, 150, 100)
        pdf.cell(0, 7, str(value), new_x="LMARGIN", new_y="NEXT")

    # Résumé du mois
    section(f"  Résumé — {month_label}")
    pdf.set_text_color(50, 50, 50)
    pdf.set_font('Helvetica', '', 10)
    row("Appartements total :", len(apartments))
    row("Payés ce mois :", f"{len(paid_ids)} / {len(apartments)}")
    row("Impayés ce mois :", len(apartments) - len(paid_ids))
    row("Encaissements du mois :", f"{encaisse_mois:.3f} DT")
    row("Dépenses du mois :", f"{depenses_mois:.3f} DT")
    row("Solde du mois :", f"{encaisse_mois - depenses_mois:.3f} DT", bold=True)
    pdf.ln(4)

    # Trésorerie cumulée
    section("  Trésorerie cumulée")
    row("Total encaissé (historique) :", f"{total_encaisse:.3f} DT")
    row("Total dépenses (historique) :", f"{total_depenses:.3f} DT")
    row("Solde général :", f"{total_encaisse - total_depenses:.3f} DT", bold=True)
    pdf.ln(4)

    # Encaissements du mois (déjà chargés, scopés au mois)
    if month_payments:
        section(f"  Encaissements — {month_label}")
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(55, 6, "Appartement")
        pdf.cell(35, 6, "Montant")
        pdf.cell(40, 6, "Date paiement")
        pdf.cell(0, 6, "Mois payé", new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(200, 200, 200)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(1)
        for p in month_payments:
            pdf.set_font('Helvetica', '', 9)
            pdf.set_text_color(50, 50, 50)
            apt_label = f"{p.apartment.block.name}-{p.apartment.number}"
            pdf.cell(55, 6, apt_label)
            pdf.cell(35, 6, f"{p.amount:.3f} DT")
            pdf.cell(40, 6, p.payment_date.strftime('%d/%m/%Y'))
            pdf.cell(0, 6, p.month_paid, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

    # Impayés du mois
    unpaid_apts = [a for a in apartments if a.id not in paid_ids]
    if unpaid_apts:
        section(f"  Appartements impayés — {month_label}")
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(55, 6, "Appartement")
        pdf.cell(40, 6, "Mois en retard")
        pdf.cell(0, 6, "Montant dû", new_x="LMARGIN", new_y="NEXT")
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(1)
        for a in unpaid_apts:
            cnt = unpaid_map.get(a.id, 0)
            pdf.set_font('Helvetica', '', 9)
            pdf.set_text_color(180, 50, 50)
            apt_label = f"{a.block.name}-{a.number}"
            pdf.cell(55, 6, apt_label)
            pdf.cell(40, 6, str(cnt))
            pdf.cell(0, 6, f"{cnt * a.monthly_fee:.0f} DT", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

    # Dépenses du mois (déjà chargées, scopées au mois)
    if month_expenses:
        section(f"  Dépenses — {month_label}")
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(55, 6, "Date")
        pdf.cell(35, 6, "Montant")
        pdf.cell(50, 6, "Catégorie")
        pdf.cell(0, 6, "Description", new_x="LMARGIN", new_y="NEXT")
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(1)
        for e in month_expenses:
            pdf.set_font('Helvetica', '', 9)
            pdf.set_text_color(50, 50, 50)
            pdf.cell(55, 6, e.expense_date.strftime('%d/%m/%Y'))
            pdf.cell(35, 6, f"{e.amount:.3f} DT")
            pdf.cell(50, 6, (e.category or '')[:20])
            pdf.cell(0, 6, (e.description or '')[:30], new_x="LMARGIN", new_y="NEXT")

    # Pied de page
    pdf.ln(8)
    pdf.set_font('Helvetica', 'I', 8)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 6, f"Genere par SyndicPro le {date.today().strftime('%d/%m/%Y')} - www.syndicpro.tn", align='C')

    buf = io.BytesIO(pdf.output())
    buf.seek(0)
    filename = f"rapport_{org.slug}_{current_month}.pdf"
    return send_file(buf, mimetype='application/pdf',
                     as_attachment=True, download_name=filename)
