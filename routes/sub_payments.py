"""
Paiement d'abonnement SyndicPro par virement bancaire.

Flux :
  1. Admin du syndic  → soumet un virement (scan + montant + référence + plan)
  2. Superadmin       → approuve ou rejette
  3. Approbation      → subscription prolongée + facture PDF générée automatiquement
"""
import os
import secrets
import base64
import io
from datetime import datetime, timedelta
from flask import render_template, request, redirect, url_for, flash, send_file, abort, Response
from core import app, db
from models import SubscriptionPaymentRequest, Organization, Subscription, User
from utils import (current_user, current_organization, login_required,
                   admin_required, superadmin_required)
from storage_helper import upload_file as _storage_upload

MAX_SCAN_BYTES = 5 * 1024 * 1024
ALLOWED_MIMES  = {'image/jpeg', 'image/png', 'image/webp', 'application/pdf'}


def _get_emetteur():
    """Informations légales de la société émettrice.
    Configurables via variables d'environnement Render — à remplir dès NEXARA immatriculée.
    Vars Render : COMPANY_NAME, COMPANY_ADDRESS, COMPANY_MF, COMPANY_RIB,
                  COMPANY_PHONE, COMPANY_EMAIL, COMPANY_IBAN
    """
    return {
        'nom':     os.environ.get('COMPANY_NAME',    'NEXARA SARL'),
        'adresse': os.environ.get('COMPANY_ADDRESS', '10 Rue El Hana, Cité El Nozha, 2080 Ariana, Tunis, Tunisie'),
        'mf':      os.environ.get('COMPANY_MF',      ''),   # Matricule Fiscal — à remplir après immatriculation RNE
        'rib':     os.environ.get('COMPANY_RIB',     ''),   # RIB Banque de Tunisie — à remplir après ouverture compte
        'iban':    os.environ.get('COMPANY_IBAN',    ''),
        'phone':   os.environ.get('COMPANY_PHONE',   '+216 24 545 853'),
        'email':   os.environ.get('COMPANY_EMAIL',   'contact@syndicpro.tn'),
        'produit': 'SyndicPro',                              # marque commerciale
    }


# ─── Aide : numéro de facture unique SP-YYYY-NNNN ────────────────────────────

def _next_invoice_number():
    year = datetime.utcnow().year
    prefix = f"SP-{year}-"
    last = (SubscriptionPaymentRequest.query
            .filter(SubscriptionPaymentRequest.invoice_number.like(f"{prefix}%"))
            .order_by(SubscriptionPaymentRequest.invoice_number.desc())
            .first())
    if last and last.invoice_number:
        try:
            n = int(last.invoice_number.split('-')[-1]) + 1
        except ValueError:
            n = 1
    else:
        n = 1
    return f"{prefix}{n:04d}"


# ─── 1. Admin du syndic — soumettre un virement ──────────────────────────────

@app.route('/subscription/payer-virement', methods=['GET', 'POST'])
@login_required
@admin_required
def subscription_payer_virement():
    user = current_user()
    org  = current_organization()

    if request.method == 'POST':
        plan_requested = request.form.get('plan_requested', '').strip()
        if plan_requested not in SubscriptionPaymentRequest.PLAN_DETAILS:
            flash('Plan invalide.', 'danger')
            return redirect(url_for('subscription_payer_virement'))

        try:
            months_count = int(request.form.get('months_count', 1))
            if months_count not in (1, 12):
                months_count = 1
        except ValueError:
            months_count = 1

        plan_price = SubscriptionPaymentRequest.PLAN_DETAILS[plan_requested]['price']
        expected_amount = round(plan_price * months_count, 2)

        try:
            amount_declared = float(request.form.get('amount_declared', 0))
            if amount_declared <= 0:
                raise ValueError
        except ValueError:
            flash('Montant invalide.', 'danger')
            return redirect(url_for('subscription_payer_virement'))

        bank_reference = request.form.get('bank_reference', '').strip()[:200]

        # Upload scan virement (obligatoire)
        scan = request.files.get('scan_virement')
        if not scan or not scan.filename:
            flash('Le scan du virement est obligatoire.', 'danger')
            return redirect(url_for('subscription_payer_virement'))

        if scan.mimetype not in ALLOWED_MIMES:
            flash('Format non accepté (JPG, PNG, WEBP ou PDF).', 'danger')
            return redirect(url_for('subscription_payer_virement'))

        raw = scan.read()
        if len(raw) > MAX_SCAN_BYTES:
            flash('Fichier trop lourd (max 5 Mo).', 'danger')
            return redirect(url_for('subscription_payer_virement'))

        photo_url  = _storage_upload(raw, scan.mimetype, folder='abonnements')
        photo_data = None if photo_url else base64.b64encode(raw).decode('utf-8')

        pr = SubscriptionPaymentRequest(
            organization_id = org.id,
            submitted_by_id = user.id,
            plan_requested  = plan_requested,
            months_count    = months_count,
            amount_declared = amount_declared,
            bank_reference  = bank_reference or None,
            photo_data      = photo_data,
            photo_mime      = scan.mimetype,
            photo_url       = photo_url,
            confirm_token   = secrets.token_hex(32),
        )
        db.session.add(pr)
        db.session.commit()

        _notify_superadmin_new_virement(org, pr)

        flash(
            f'Votre demande de renouvellement ({plan_requested.capitalize()}, '
            f'{months_count} mois) a été transmise. '
            'Le superadmin va la vérifier et activer votre abonnement.', 'success'
        )
        return redirect(url_for('subscription_status'))

    # Demandes déjà soumises par cette org
    pending = (SubscriptionPaymentRequest.query
               .filter_by(organization_id=org.id, status='en_attente')
               .order_by(SubscriptionPaymentRequest.created_at.desc())
               .all())
    history = (SubscriptionPaymentRequest.query
               .filter_by(organization_id=org.id)
               .filter(SubscriptionPaymentRequest.status != 'en_attente')
               .order_by(SubscriptionPaymentRequest.created_at.desc())
               .limit(10).all())

    return render_template(
        'subscription_payer_virement.html',
        user=user, org=org,
        plans=SubscriptionPaymentRequest.PLAN_DETAILS,
        pending=pending,
        history=history,
        emetteur=_get_emetteur(),
    )


# ─── 2. Superadmin — liste des demandes en attente ───────────────────────────

@app.route('/superadmin/abonnements/paiements')
@login_required
@superadmin_required
def superadmin_sub_payments():
    pending = (SubscriptionPaymentRequest.query
               .filter_by(status='en_attente')
               .order_by(SubscriptionPaymentRequest.created_at.asc())
               .all())
    history = (SubscriptionPaymentRequest.query
               .filter(SubscriptionPaymentRequest.status != 'en_attente')
               .order_by(SubscriptionPaymentRequest.confirmed_at.desc())
               .limit(50).all())
    return render_template(
        'superadmin_sub_payments.html',
        user=current_user(),
        pending=pending,
        history=history,
        plans=SubscriptionPaymentRequest.PLAN_DETAILS,
    )


# ─── 3. Superadmin — approuver ───────────────────────────────────────────────

@app.route('/superadmin/abonnements/paiements/<int:pr_id>/approuver', methods=['POST'])
@login_required
@superadmin_required
def superadmin_sub_approve(pr_id):
    pr = SubscriptionPaymentRequest.query.get_or_404(pr_id)
    if pr.status != 'en_attente':
        flash('Cette demande a déjà été traitée.', 'warning')
        return redirect(url_for('superadmin_sub_payments'))

    try:
        amount_confirmed = float(request.form.get('amount_confirmed', pr.amount_declared))
    except ValueError:
        amount_confirmed = pr.amount_declared

    superadmin_notes = request.form.get('superadmin_notes', '').strip() or None

    # ── Prolonger l'abonnement ────────────────────────────────────────────────
    org  = pr.organization
    sub  = org.subscription
    plan = pr.plan_requested
    details = SubscriptionPaymentRequest.PLAN_DETAILS[plan]
    now = datetime.utcnow()

    if sub is None:
        sub = Subscription(organization_id=org.id)
        db.session.add(sub)

    # Partir de la date d'expiration actuelle si abonnement encore valide
    if sub.end_date and sub.end_date > now:
        new_end = sub.end_date + timedelta(days=30 * pr.months_count)
    else:
        new_end = now + timedelta(days=30 * pr.months_count)

    sub.plan           = plan
    sub.monthly_price  = details['price']
    sub.max_apartments = details['max_apartments']
    sub.status         = 'active'
    sub.end_date       = new_end

    # ── Générer numéro de facture ──────────────────────────────────────────────
    invoice_number = _next_invoice_number()

    pr.status           = 'approuve'
    pr.amount_confirmed = amount_confirmed
    pr.superadmin_notes = superadmin_notes
    pr.invoice_number   = invoice_number
    pr.confirmed_at     = now
    db.session.commit()

    _notify_admin_approved(org, pr)

    plan_label = details['label']
    flash(
        f'Abonnement activé : {org.name} — Plan {plan_label}, '
        f'{pr.months_count} mois (expire le {new_end.strftime("%d/%m/%Y")}). '
        f'Facture {invoice_number} générée.', 'success'
    )
    return redirect(url_for('superadmin_sub_payments'))


# ─── 4. Superadmin — rejeter ─────────────────────────────────────────────────

@app.route('/superadmin/abonnements/paiements/<int:pr_id>/rejeter', methods=['POST'])
@login_required
@superadmin_required
def superadmin_sub_reject(pr_id):
    pr = SubscriptionPaymentRequest.query.get_or_404(pr_id)
    if pr.status != 'en_attente':
        flash('Cette demande a déjà été traitée.', 'warning')
        return redirect(url_for('superadmin_sub_payments'))

    pr.status           = 'rejete'
    pr.superadmin_notes = request.form.get('superadmin_notes', '').strip() or None
    pr.confirmed_at     = datetime.utcnow()
    db.session.commit()

    _notify_admin_rejected(pr.organization, pr)
    flash(f'Demande de {pr.organization.name} rejetée.', 'warning')
    return redirect(url_for('superadmin_sub_payments'))


# ─── 5. Scan virement — affichage (superadmin + admin de l'org) ──────────────

@app.route('/subscription/paiement/<int:pr_id>/scan')
@login_required
def sub_payment_scan(pr_id):
    user = current_user()
    pr   = SubscriptionPaymentRequest.query.get_or_404(pr_id)

    # Droits : superadmin ou admin de la même org
    if user.role != 'superadmin' and user.organization_id != pr.organization_id:
        abort(403)

    if pr.photo_url:
        from flask import redirect as _r
        return _r(pr.photo_url)
    if not pr.photo_data:
        abort(404)
    raw = base64.b64decode(pr.photo_data)
    return Response(raw, mimetype=pr.photo_mime or 'image/jpeg')


# ─── 6. Facture PDF — téléchargement (superadmin + admin de l'org) ───────────

@app.route('/subscription/facture/<int:pr_id>.pdf')
@login_required
def sub_payment_invoice(pr_id):
    from fpdf import FPDF
    user = current_user()
    pr   = SubscriptionPaymentRequest.query.get_or_404(pr_id)

    if user.role != 'superadmin' and user.organization_id != pr.organization_id:
        abort(403)
    if pr.status != 'approuve':
        flash('La facture n\'est disponible qu\'après approbation.', 'warning')
        return redirect(url_for('subscription_status'))

    em      = _get_emetteur()
    org     = pr.organization
    details = SubscriptionPaymentRequest.PLAN_DETAILS.get(pr.plan_requested, {})
    amount  = pr.amount_confirmed or pr.amount_declared

    def _s(t):
        if not t:
            return ''
        return (str(t)
                .replace('\u2014', '-').replace('\u2013', '-')
                .replace('\u2019', "'").replace('\u2018', "'")
                .encode('latin-1', errors='replace').decode('latin-1'))

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # ── Bandeau en-tête ──────────────────────────────────────────────────────
    pdf.set_fill_color(30, 58, 138)
    pdf.rect(0, 0, 210, 38, 'F')
    pdf.set_xy(0, 5)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Helvetica', 'B', 20)
    pdf.cell(0, 10, _s(em['produit']), ln=True, align='C')
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(0, 6, _s(em['nom']), ln=True, align='C')
    pdf.set_font('Helvetica', '', 9)
    pdf.cell(0, 5, _s(em['adresse']), ln=True, align='C')
    if em.get('mf'):
        pdf.cell(0, 4, _s(f"MF : {em['mf']}  |  {em['email']}  |  {em['phone']}"), ln=True, align='C')
    else:
        pdf.cell(0, 4, _s(f"{em['email']}  |  {em['phone']}"), ln=True, align='C')
    pdf.ln(8)

    # ── Titre ────────────────────────────────────────────────────────────────
    pdf.set_text_color(30, 58, 138)
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 9, f"FACTURE  {_s(pr.invoice_number)}", ln=True, align='C')
    pdf.set_draw_color(30, 58, 138)
    pdf.set_line_width(0.5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    # ── Deux colonnes : émetteur / destinataire ───────────────────────────────
    col_w  = 90
    y_start = pdf.get_y()

    pdf.set_xy(10, y_start)
    pdf.set_font('Helvetica', 'B', 8)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(col_w, 5, 'EMETTEUR', ln=False)
    pdf.set_xy(110, y_start)
    pdf.cell(col_w, 5, 'FACTURE A', ln=True)

    def _col(left, right, y_off):
        pdf.set_xy(10, y_start + y_off)
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(40, 40, 40)
        pdf.cell(col_w, 5, _s(left), ln=False)
        pdf.set_xy(110, y_start + y_off)
        pdf.cell(col_w, 5, _s(right), ln=True)

    _col(em['nom'],              org.name,         7)
    _col(em['adresse'][:45],     org.address or '', 13)
    if em.get('mf'):
        _col(f"MF : {em['mf']}", org.email,        19)
        _col(em['email'],         org.phone or '',  25)
    else:
        _col(em['email'],         org.email,        19)
        _col(em['phone'],         org.phone or '',  25)
    pdf.ln(34)

    # ── Méta-données de la facture ────────────────────────────────────────────
    pdf.set_draw_color(220, 220, 220)
    pdf.set_line_width(0.3)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)

    def _meta(label, value):
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(58, 6, label)
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(40, 40, 40)
        pdf.cell(0, 6, _s(str(value)), ln=True)

    _meta('N Facture :',       pr.invoice_number)
    _meta('Date emission :',   pr.confirmed_at.strftime('%d/%m/%Y'))
    _meta('Periode :',         f"{pr.months_count} mois a compter du {pr.confirmed_at.strftime('%d/%m/%Y')}")
    _meta('Mode paiement :',   'Virement bancaire')
    if pr.bank_reference:
        _meta('Ref virement :', pr.bank_reference)
    pdf.ln(4)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    # ── Tableau des prestations ────────────────────────────────────────────────
    pdf.set_fill_color(240, 244, 255)
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_text_color(30, 58, 138)
    pdf.cell(100, 8, 'Description',    fill=True, border='B')
    pdf.cell(28,  8, 'Qte',            fill=True, border='B', align='C')
    pdf.cell(30,  8, 'PU (DT)',        fill=True, border='B', align='R')
    pdf.cell(0,   8, 'Total (DT)',     fill=True, border='B', align='R', ln=True)

    plan_label = details.get('label', pr.plan_requested.capitalize())
    unit_price = details.get('price', round(amount / max(pr.months_count, 1), 3))
    pdf.set_font('Helvetica', '', 9)
    pdf.set_text_color(40, 40, 40)
    pdf.cell(100, 7, _s(f"Abonnement {em['produit']} - Plan {plan_label}"))
    pdf.cell(28,  7, f"{pr.months_count} mois", align='C')
    pdf.cell(30,  7, f"{unit_price:.3f}", align='R')
    pdf.cell(0,   7, f"{amount:.3f}", align='R', ln=True)

    pdf.set_draw_color(200, 200, 200)
    pdf.set_line_width(0.3)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)

    # ── Total ─────────────────────────────────────────────────────────────────
    pdf.set_fill_color(30, 58, 138)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Helvetica', 'B', 13)
    pdf.cell(0, 12, f"  TOTAL TTC : {amount:.3f} DT", fill=True, ln=True)
    pdf.ln(6)

    # ── Coordonnées bancaires ─────────────────────────────────────────────────
    has_bank_info = em.get('rib') or em.get('iban')
    if has_bank_info:
        pdf.set_fill_color(248, 250, 255)
        pdf.set_draw_color(30, 58, 138)
        pdf.set_line_width(0.3)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_text_color(30, 58, 138)
        pdf.cell(0, 7, '  Coordonnees bancaires pour virement', fill=True, border=1, ln=True)
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(40, 40, 40)
        if em.get('rib'):
            pdf.cell(0, 6, _s(f"  RIB : {em['rib']}"), ln=True)
        if em.get('iban'):
            pdf.cell(0, 6, _s(f"  IBAN : {em['iban']}"), ln=True)
        pdf.cell(0, 5, _s(f"  Beneficiaire : {em['nom']}"), ln=True)
        pdf.ln(4)

    # ── Pied de page ──────────────────────────────────────────────────────────
    pdf.set_draw_color(200, 200, 200)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(3)
    pdf.set_font('Helvetica', 'I', 7)
    pdf.set_text_color(160, 160, 160)
    pdf.cell(0, 4, _s(f"Genere le {datetime.now().strftime('%d/%m/%Y %H:%M')} - {em['produit']} (www.syndicpro.tn) - {em['nom']}"), ln=True, align='C')
    pdf.cell(0, 4, 'Cette facture est valable comme justificatif de paiement conformement a la legislation tunisienne.', ln=True, align='C')

    buf = io.BytesIO(pdf.output())
    buf.seek(0)
    filename = f"Facture_{pr.invoice_number}_{org.slug}.pdf"
    return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=filename)


# ─── Notifications internes ──────────────────────────────────────────────────

def _notify_superadmin_new_virement(org, pr):
    """Push au superadmin quand une nouvelle demande de paiement abonnement arrive."""
    try:
        from models import User as _User
        from utils_push import push_to_user
        sa = _User.query.filter_by(role='superadmin').first()
        if sa:
            push_to_user(
                sa.id,
                title=f"💳 Virement abonnement — {org.name}",
                body=(f"Plan {pr.plan_requested.capitalize()}, {pr.months_count} mois, "
                      f"{pr.amount_declared:.0f} DT"),
                url='/superadmin/abonnements/paiements',
                tag=f"sub-virement-{pr.id}",
            )
    except Exception:
        pass


def _notify_admin_approved(org, pr):
    """Email + push à l'admin du syndic quand l'abonnement est activé."""
    try:
        from utils_email import send_email
        em = _get_emetteur()
        details = SubscriptionPaymentRequest.PLAN_DETAILS.get(pr.plan_requested, {})
        plan_label = details.get('label', pr.plan_requested.capitalize())
        new_end = org.subscription.end_date
        end_str = new_end.strftime('%d/%m/%Y') if new_end else '—'
        html = f"""
        <h2 style="color:#1E3A8A;">Abonnement activé !</h2>
        <p>Votre virement a été vérifié et votre abonnement SyndicPro est maintenant actif.</p>
        <table style="background:#F9FAFB;border:1px solid #E5E7EB;border-radius:8px;padding:12px;width:100%;">
          <tr><td style="color:#6B7280;padding:6px;font-size:13px;">Plan</td>
              <td style="font-weight:600;padding:6px;font-size:13px;">{plan_label}</td></tr>
          <tr><td style="color:#6B7280;padding:6px;font-size:13px;">Durée</td>
              <td style="font-weight:600;padding:6px;font-size:13px;">{pr.months_count} mois</td></tr>
          <tr><td style="color:#6B7280;padding:6px;font-size:13px;">Expire le</td>
              <td style="font-weight:600;padding:6px;font-size:13px;">{end_str}</td></tr>
          <tr><td style="color:#6B7280;padding:6px;font-size:13px;">Facture</td>
              <td style="font-weight:600;padding:6px;font-size:13px;">{pr.invoice_number}</td></tr>
        </table>
        <p style="margin-top:20px;">
          <a href="https://www.syndicpro.tn/subscription/facture/{pr.id}.pdf"
             style="background:#1D4ED8;color:#fff;padding:11px 28px;border-radius:6px;
                    text-decoration:none;font-weight:600;">
            Télécharger la facture
          </a>
        </p>
        """
        from utils_email import _base_html
        send_email(org.email, f'SyndicPro — Abonnement {plan_label} activé ({pr.invoice_number})', _base_html(html))
    except Exception:
        pass

    try:
        from utils_push import push_to_admins
        push_to_admins(
            org.id,
            title='✅ Abonnement SyndicPro activé',
            body=f"Plan {pr.plan_requested.capitalize()} — {pr.months_count} mois",
            url='/subscription',
            tag=f"sub-approved-{pr.id}",
        )
    except Exception:
        pass


def _notify_admin_rejected(org, pr):
    try:
        from utils_push import push_to_admins
        push_to_admins(
            org.id,
            title='❌ Virement non validé',
            body=pr.superadmin_notes or 'Contactez SyndicPro pour plus d\'informations.',
            url='/subscription/payer-virement',
            tag=f"sub-rejected-{pr.id}",
        )
    except Exception:
        pass
