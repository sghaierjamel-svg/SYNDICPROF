from flask import render_template, request, redirect, url_for, flash, jsonify
from core import app, db
from models import Apartment, Payment, KonnectPayment, Organization
from utils import (current_user, current_organization, login_required,
                   admin_required, subscription_required, get_next_unpaid_month)
from datetime import datetime
import requests as http
import os

BASE_URL = os.environ.get('BASE_URL', 'https://www.syndicpro.tn')


def _call_konnect_init(org, apartment, month_target, amount_dt, created_by='resident'):
    """Crée un KonnectPayment en DB et appelle l'API Konnect.
    Retourne (konnect_payment, None) ou (None, message_erreur).
    """
    kp = KonnectPayment(
        organization_id=org.id,
        apartment_id=apartment.id,
        month_target=month_target,
        amount=amount_dt,
        created_by=created_by,
        status='pending'
    )
    db.session.add(kp)
    db.session.flush()   # obtenir kp.id avant le commit

    try:
        resp = http.post(
            'https://api.konnect.network/api/v2/payments/init-payment',
            headers={
                'x-api-key': org.konnect_api_key,
                'Content-Type': 'application/json'
            },
            json={
                'receiverWalletId': org.konnect_wallet_id,
                'token': 'TND',
                'amount': int(round(amount_dt * 1000)),   # en millimes
                'type': 'immediate',
                'description': (
                    f"Redevance {month_target} — "
                    f"{apartment.block.name}-{apartment.number}"
                ),
                'acceptedPaymentMethods': ['wallet', 'bank_card', 'e-DINAR'],
                'successRedirectUrl': f"{BASE_URL}/konnect/success",
                'failRedirectUrl': f"{BASE_URL}/konnect/fail",
                'orderId': f"kp-{kp.id}",
            },
            timeout=15
        )

        if resp.status_code in (200, 201):
            data = resp.json()
            kp.konnect_payment_ref = (
                data.get('paymentRef')
                or data.get('payment', {}).get('_id')
            )
            kp.pay_url = data.get('payUrl') or data.get('pay_url')
            db.session.commit()
            return kp, None
        else:
            db.session.rollback()
            return None, f"Erreur Konnect ({resp.status_code})"

    except Exception as e:
        db.session.rollback()
        return None, f"Connexion Konnect impossible : {str(e)}"


# ─── RÉSIDENT : initier un paiement ──────────────────────────────────────────

@app.route('/konnect/pay', methods=['POST'])
@login_required
@subscription_required
def konnect_pay():
    """Le résident clique sur 'Payer en ligne' — on crée le lien et on redirige."""
    user = current_user()
    if not user.apartment_id:
        flash("Vous n'êtes pas affecté à un appartement.", "danger")
        return redirect(url_for('residents_menu'))

    org = current_organization()
    if not org.konnect_api_key or not org.konnect_wallet_id:
        flash("Le paiement en ligne n'est pas encore configuré pour votre syndic.", "warning")
        return redirect(url_for('residents_menu'))

    apt = Apartment.query.get(user.apartment_id)
    next_month = get_next_unpaid_month(user.apartment_id)

    # Réutiliser un lien pending existant pour ce mois
    existing = KonnectPayment.query.filter_by(
        apartment_id=apt.id,
        month_target=next_month,
        status='pending'
    ).first()
    if existing and existing.pay_url:
        return redirect(existing.pay_url)

    kp, err = _call_konnect_init(org, apt, next_month, apt.monthly_fee, created_by='resident')
    if err:
        flash(f"Erreur paiement en ligne : {err}", "danger")
        return redirect(url_for('residents_menu'))

    return redirect(kp.pay_url)


# ─── CALLBACKS KONNECT ───────────────────────────────────────────────────────

@app.route('/konnect/success')
def konnect_success():
    """Konnect redirige ici après un paiement réussi (?payment_ref=xxx)."""
    payment_ref = request.args.get('payment_ref') or request.args.get('paymentRef')
    user = current_user()

    if not payment_ref:
        flash("Référence de paiement manquante.", "danger")
        dest = url_for('residents_menu') if user else url_for('login')
        return redirect(dest)

    kp = KonnectPayment.query.filter_by(konnect_payment_ref=payment_ref).first()
    if not kp:
        flash("Paiement introuvable.", "danger")
        dest = url_for('residents_menu') if user else url_for('login')
        return redirect(dest)

    if kp.status == 'completed':
        return render_template('konnect_success.html', kp=kp, already_done=True, user=user)

    # Vérification auprès de l'API Konnect
    org = Organization.query.get(kp.organization_id)
    verified = False
    try:
        resp = http.get(
            f'https://api.konnect.network/api/v2/payments/{payment_ref}',
            headers={'x-api-key': org.konnect_api_key},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            pay_data = data.get('payment', data)
            if pay_data.get('status') == 'completed':
                verified = True
    except Exception:
        pass

    if verified:
        # Enregistrer le paiement si pas déjà fait
        existing = Payment.query.filter_by(
            apartment_id=kp.apartment_id,
            month_paid=kp.month_target
        ).first()
        if not existing:
            p = Payment(
                organization_id=kp.organization_id,
                apartment_id=kp.apartment_id,
                amount=kp.amount,
                payment_date=datetime.utcnow().date(),
                month_paid=kp.month_target,
                description=f"Paiement en ligne Konnect — {kp.month_target}",
                credit_used=0.0
            )
            db.session.add(p)
        kp.status = 'completed'
        kp.paid_at = datetime.utcnow()
        db.session.commit()

    return render_template('konnect_success.html', kp=kp, verified=verified, already_done=False, user=user)


@app.route('/konnect/fail')
def konnect_fail():
    """Konnect redirige ici après un paiement échoué ou annulé."""
    payment_ref = request.args.get('payment_ref') or request.args.get('paymentRef')
    user = current_user()
    kp = None
    if payment_ref:
        kp = KonnectPayment.query.filter_by(konnect_payment_ref=payment_ref).first()
        if kp and kp.status == 'pending':
            kp.status = 'failed'
            db.session.commit()
    return render_template('konnect_fail.html', kp=kp, user=user)


# ─── ADMIN : générer un lien partager ────────────────────────────────────────

@app.route('/konnect/admin/generate-link', methods=['POST'])
@login_required
@admin_required
@subscription_required
def konnect_generate_link():
    """Admin génère un lien Konnect pour un appartement (via AJAX)."""
    org = current_organization()
    if not org.konnect_api_key or not org.konnect_wallet_id:
        return jsonify({'ok': False, 'message': 'Konnect non configuré. Allez dans Paramètres.'})

    apartment_id = request.form.get('apartment_id', type=int)
    month_target = request.form.get('month_target', '').strip()
    amount = request.form.get('amount', type=float)

    if not apartment_id or not month_target or not amount:
        return jsonify({'ok': False, 'message': 'Données manquantes.'})

    apt = Apartment.query.filter_by(id=apartment_id, organization_id=org.id).first()
    if not apt:
        return jsonify({'ok': False, 'message': 'Appartement introuvable.'})

    # Réutiliser un lien pending existant
    existing = KonnectPayment.query.filter_by(
        apartment_id=apt.id,
        month_target=month_target,
        status='pending'
    ).first()
    if existing and existing.pay_url:
        return jsonify({'ok': True, 'pay_url': existing.pay_url, 'reused': True})

    kp, err = _call_konnect_init(org, apt, month_target, amount, created_by='admin')
    if err:
        return jsonify({'ok': False, 'message': err})

    return jsonify({'ok': True, 'pay_url': kp.pay_url, 'reused': False})


# ─── ADMIN : liste des liens ──────────────────────────────────────────────────

@app.route('/konnect/links')
@login_required
@admin_required
@subscription_required
def konnect_links():
    """Admin — historique de tous les liens Konnect générés."""
    org = current_organization()
    links = (KonnectPayment.query
             .filter_by(organization_id=org.id)
             .order_by(KonnectPayment.created_at.desc())
             .all())
    return render_template('konnect_links.html', links=links, user=current_user(), org=org)
