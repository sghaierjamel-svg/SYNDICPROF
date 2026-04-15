"""
Option B — Virement bancaire
- Résident soumet une demande (mois, montant déclaré, photo décharge, référence)
- Admin reçoit push + WhatsApp avec lien de confirmation sécurisé
- Admin confirme en 1 clic : saisit montant reçu + frais bancaires
- Payment enregistré + Expense "Charges bancaires" créée automatiquement
- Résident reçoit push de confirmation
"""
from flask import render_template, request, redirect, url_for, flash, abort
from core import app, db
from models import PaymentRequest, Apartment, Payment, Expense, User
from utils import current_user, current_organization, login_required, subscription_required
from datetime import datetime, date
import secrets
import base64


# ─── Résident — soumettre un virement ────────────────────────────────────────

@app.route('/residents/virement', methods=['POST'])
@login_required
@subscription_required
def virement_soumettre():
    user = current_user()
    org  = current_organization()

    if user.role != 'resident':
        abort(403)

    apt = Apartment.query.filter_by(id=user.apartment_id, organization_id=org.id).first_or_404()

    month_target    = request.form.get('month_target', '').strip()
    amount_declared = request.form.get('amount_declared', '').strip()
    bank_reference  = request.form.get('bank_reference', '').strip()[:200]

    if not month_target or not amount_declared:
        flash('Le mois et le montant sont obligatoires.', 'danger')
        return redirect(url_for('residents'))

    try:
        amount_declared = float(amount_declared)
        if amount_declared <= 0:
            raise ValueError
    except ValueError:
        flash('Montant invalide.', 'danger')
        return redirect(url_for('residents'))

    # Photo de la décharge (optionnelle mais recommandée)
    photo_data = photo_mime = None
    photo = request.files.get('photo_decharge')
    if photo and photo.filename:
        data = photo.read()
        if len(data) > 5 * 1024 * 1024:
            flash('Photo trop lourde (max 5 Mo).', 'warning')
            return redirect(url_for('residents'))
        if photo.mimetype not in ('image/jpeg', 'image/png', 'image/webp', 'image/gif', 'application/pdf'):
            flash('Format non supporté. Utilisez JPEG, PNG, WEBP ou PDF.', 'warning')
            return redirect(url_for('residents'))
        photo_data = base64.b64encode(data).decode('utf-8')
        photo_mime = photo.mimetype

    # Idempotence : pas 2 demandes en attente pour le même mois
    existing = PaymentRequest.query.filter_by(
        organization_id=org.id,
        apartment_id=apt.id,
        month_target=month_target,
        status='en_attente',
    ).first()
    if existing:
        flash('Une demande est déjà en attente pour ce mois.', 'warning')
        return redirect(url_for('residents'))

    pr = PaymentRequest(
        organization_id=org.id,
        apartment_id=apt.id,
        user_id=user.id,
        month_target=month_target,
        amount_declared=amount_declared,
        bank_reference=bank_reference or None,
        photo_data=photo_data,
        photo_mime=photo_mime,
        confirm_token=secrets.token_hex(32),
    )
    db.session.add(pr)
    db.session.commit()

    flash('Votre demande de virement a été transmise. L\'administration va la valider sous peu.', 'success')

    _notify_admin_virement(org, apt, user, pr)
    return redirect(url_for('residents'))


# ─── Admin — page de confirmation ────────────────────────────────────────────

@app.route('/payments/confirm-virement/<token>', methods=['GET', 'POST'])
@login_required
def confirm_virement(token):
    user = current_user()
    org  = current_organization()

    if user.role != 'admin':
        abort(403)

    pr = PaymentRequest.query.filter_by(
        confirm_token=token,
        organization_id=org.id,
    ).first_or_404()

    apt = pr.apartment
    resident = pr.user

    if request.method == 'POST':
        action = request.form.get('action', 'confirmer')

        if action == 'rejeter':
            pr.status = 'rejete'
            pr.admin_notes = request.form.get('admin_notes', '').strip() or None
            db.session.commit()
            flash('Demande de virement rejetée.', 'warning')
            _notify_resident_virement(org, pr, confirme=False)
            return redirect(url_for('payments'))

        # Récupérer montant confirmé + frais
        try:
            amount_confirmed = float(request.form.get('amount_confirmed', pr.amount_declared))
            bank_fees        = float(request.form.get('bank_fees', 0) or 0)
        except ValueError:
            flash('Montant invalide.', 'danger')
            return redirect(url_for('confirm_virement', token=token))

        admin_notes = request.form.get('admin_notes', '').strip() or None
        apt_label   = f"{apt.block.name}-{apt.number}" if apt.block else apt.number
        monthly_fee = apt.monthly_fee or 0

        # ── Calcul automatique du nombre de mois couverts ──────────────────
        def _gen_months(start_ym, n):
            """Génère n mois consécutifs à partir de start_ym (format YYYY-MM)."""
            try:
                y, m = int(start_ym[:4]), int(start_ym[5:7])
            except (ValueError, IndexError):
                return [start_ym]
            result = []
            for _ in range(n):
                result.append(f"{y:04d}-{m:02d}")
                m += 1
                if m > 12:
                    m, y = 1, y + 1
            return result

        if monthly_fee > 0:
            nb_months = max(1, int(amount_confirmed / monthly_fee))
        else:
            nb_months = 1

        months_to_credit = _gen_months(pr.month_target, nb_months)
        amount_per_month = round(amount_confirmed / nb_months, 3)

        desc_base = f"Virement bancaire{(' — Réf: ' + pr.bank_reference) if pr.bank_reference else ''}"

        # 1. Créer un Payment par mois (skip les déjà payés)
        created_months = []
        for mth in months_to_credit:
            already = Payment.query.filter_by(
                apartment_id=apt.id, month_paid=mth
            ).first()
            if not already:
                db.session.add(Payment(
                    organization_id=org.id,
                    apartment_id=apt.id,
                    amount=amount_per_month,
                    payment_date=date.today(),
                    month_paid=mth,
                    description=f"{desc_base} — {mth}",
                ))
                created_months.append(mth)

        # 2. Frais bancaires comme dépense (si > 0)
        if bank_fees > 0:
            db.session.add(Expense(
                organization_id=org.id,
                amount=bank_fees,
                expense_date=date.today(),
                category='Charges bancaires',
                description=f"Frais virement Apt {apt_label} — mois {pr.month_target}",
            ))

        # 3. Mettre à jour la demande
        pr.status           = 'confirme'
        pr.amount_confirmed = amount_confirmed
        pr.bank_fees        = bank_fees
        pr.admin_notes      = admin_notes
        pr.confirmed_at     = datetime.utcnow()
        db.session.commit()

        months_label = ', '.join(created_months) if created_months else pr.month_target
        flash(
            f'Virement de {amount_confirmed:.2f} DT confirmé pour {apt_label} — '
            f'{len(created_months)} mois crédité(s) : {months_label}.',
            'success'
        )
        _notify_resident_virement(org, pr, confirme=True)

        # Push admin (confirmation propre)
        try:
            from utils_push import push_to_admins
            push_to_admins(
                org.id,
                title=f"✅ Virement confirmé — Apt {apt_label}",
                body=f"Mois : {pr.month_target} | Montant : {amount_confirmed:.2f} DT",
                url="/payments",
                tag=f"virement-admin-{pr.id}",
            )
        except Exception:
            pass

        return redirect(url_for('payments'))

    return render_template(
        'payment_request_confirm.html',
        user=user, org=org,
        pr=pr, apt=apt, resident=resident,
    )


# ─── Admin — liste des demandes en attente ───────────────────────────────────

@app.route('/payments/virements')
@login_required
def virements_liste():
    user = current_user()
    org  = current_organization()
    if user.role != 'admin':
        abort(403)
    pending = PaymentRequest.query.filter_by(
        organization_id=org.id, status='en_attente'
    ).order_by(PaymentRequest.created_at.desc()).all()
    all_requests = PaymentRequest.query.filter_by(
        organization_id=org.id
    ).order_by(PaymentRequest.created_at.desc()).limit(50).all()
    return render_template(
        'virements_liste.html',
        user=user, org=org,
        pending=pending,
        all_requests=all_requests,
    )


# ─── Vue photo décharge ───────────────────────────────────────────────────────

@app.route('/payments/virement/<int:pr_id>/photo')
@login_required
def virement_photo(pr_id):
    from flask import Response
    user = current_user()
    org  = current_organization()
    pr = PaymentRequest.query.filter_by(id=pr_id, organization_id=org.id).first_or_404()
    if not pr.photo_data:
        abort(404)
    raw = base64.b64decode(pr.photo_data)
    return Response(raw, mimetype=pr.photo_mime or 'image/jpeg')


# ─── Notifications ───────────────────────────────────────────────────────────

def _notify_admin_virement(org, apt, resident, pr):
    """Notifie l'admin d'une nouvelle demande de virement (push + WhatsApp)."""
    apt_label   = f"{apt.block.name}-{apt.number}" if apt.block else apt.number
    confirm_url = url_for('confirm_virement', token=pr.confirm_token, _external=True)

    title = f"💸 Virement reçu — Apt {apt_label}"
    body  = (
        f"Résident : {resident.name or resident.email}\n"
        f"Mois : {pr.month_target} | Montant déclaré : {pr.amount_declared:.2f} DT"
    )

    # Push
    try:
        from utils_push import push_to_admins
        push_to_admins(org.id, title=title, body=body,
                       url=f"/payments/confirm-virement/{pr.confirm_token}",
                       tag=f"virement-{pr.id}")
    except Exception:
        pass

    # WhatsApp
    try:
        from utils_whatsapp import send_whatsapp
        if org.whatsapp_admin_phone:
            msg = (
                f"💸 *SyndicPro — Virement bancaire reçu*\n"
                f"Résidence : {org.name}\n"
                f"Appartement : {apt_label}\n"
                f"Résident : {resident.name or resident.email}\n"
                f"Mois : {pr.month_target}\n"
                f"Montant déclaré : {pr.amount_declared:.2f} DT\n"
                + (f"Réf. virement : {pr.bank_reference}\n" if pr.bank_reference else '') +
                f"\n✅ Confirmer en 1 clic :\n{confirm_url}"
            )
            send_whatsapp(org, org.whatsapp_admin_phone, msg)
    except Exception:
        pass


def _notify_resident_virement(org, pr, confirme=True):
    """Notifie le résident de la confirmation ou du rejet de sa demande."""
    try:
        from utils_push import push_to_user
        if confirme:
            title = "✅ Virement confirmé"
            body  = (
                f"Votre virement de {pr.amount_confirmed:.2f} DT a été validé.\n"
                f"Mois : {pr.month_target}"
            )
        else:
            title = "❌ Virement non retenu"
            body  = (
                f"Votre demande de virement pour {pr.month_target} n'a pas été validée.\n"
                + (f"Motif : {pr.admin_notes}" if pr.admin_notes else "Contactez l'administration.")
            )
        push_to_user(pr.user_id, title=title, body=body, url='/residents',
                     tag=f"virement-res-{pr.id}")
    except Exception:
        pass
