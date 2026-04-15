from flask import render_template, request, redirect, url_for, flash, jsonify
from core import app, db
from models import Apartment, Payment, FlouciPayment, Organization, User
from utils import (current_user, current_organization, login_required,
                   admin_required, subscription_required, get_next_unpaid_month)
from datetime import datetime
import requests as http
import os
import uuid
from utils_whatsapp import notify_payment

BASE_URL = os.environ.get('BASE_URL', 'https://www.syndicpro.tn')

FLOUCI_GENERATE_URL = 'https://api.flouci.com/payment/generate'
FLOUCI_VERIFY_URL   = 'https://api.flouci.com/payment/verify/{payment_id}'


def _call_flouci_init(org, apartment, month_target, amount_dt, created_by='resident'):
    """Crée un FlouciPayment en DB et appelle l'API Flouci.
    Retourne (flouci_payment, None) ou (None, message_erreur).
    """
    fp = FlouciPayment(
        organization_id=org.id,
        apartment_id=apartment.id,
        month_target=month_target,
        amount=amount_dt,
        created_by=created_by,
        status='pending'
    )
    db.session.add(fp)
    db.session.flush()

    session_id = f"fp-{fp.id}-{uuid.uuid4().hex[:8]}"

    try:
        resp = http.post(
            FLOUCI_GENERATE_URL,
            json={
                'app_token': org.flouci_app_token,
                'app_secret': org.flouci_app_secret,
                'amount': int(round(amount_dt * 1000)),   # en millimes
                'accept_card': 'true',
                'session_id': session_id,
                'success_link': f"{BASE_URL}/flouci/success",
                'fail_link': f"{BASE_URL}/flouci/fail",
                'developer_tracking_id': f"fp-{fp.id}",
            },
            timeout=15
        )

        if resp.status_code in (200, 201):
            data = resp.json()
            result = data.get('result', {})
            fp.flouci_payment_id = result.get('payment_id') or result.get('paymentId')
            fp.pay_url = result.get('link') or result.get('pay_url')
            db.session.commit()
            return fp, None
        else:
            db.session.rollback()
            return None, f"Erreur Flouci ({resp.status_code})"

    except Exception as e:
        db.session.rollback()
        return None, f"Connexion Flouci impossible : {str(e)}"


# ─── RÉSIDENT : initier un paiement ──────────────────────────────────────────

@app.route('/flouci/pay', methods=['POST'])
@login_required
@subscription_required
def flouci_pay():
    user = current_user()
    if not user.apartment_id:
        flash("Vous n'êtes pas affecté à un appartement.", "danger")
        return redirect(url_for('residents_menu'))

    org = current_organization()
    if not org.flouci_app_token or not org.flouci_app_secret:
        flash("Le paiement Flouci n'est pas encore configuré pour votre syndic.", "warning")
        return redirect(url_for('residents_menu'))

    apt = Apartment.query.get(user.apartment_id)
    next_month = get_next_unpaid_month(user.apartment_id)

    already_paid = Payment.query.filter_by(
        apartment_id=apt.id,
        month_paid=next_month
    ).first()
    if already_paid:
        flash(f"Le mois {next_month} est déjà enregistré comme payé.", "info")
        return redirect(url_for('residents_menu'))

    # Réutiliser un lien pending existant
    existing = FlouciPayment.query.filter_by(
        apartment_id=apt.id,
        month_target=next_month,
        status='pending'
    ).first()
    if existing and existing.pay_url:
        return redirect(existing.pay_url)

    fp, err = _call_flouci_init(org, apt, next_month, apt.monthly_fee, created_by='resident')
    if err:
        flash(f"Erreur paiement Flouci : {err}", "danger")
        return redirect(url_for('residents_menu'))

    return redirect(fp.pay_url)


# ─── CALLBACKS FLOUCI ────────────────────────────────────────────────────────

@app.route('/flouci/success')
def flouci_success():
    payment_id = request.args.get('payment_id') or request.args.get('paymentId')
    user = current_user()

    if not payment_id:
        flash("Référence de paiement manquante.", "danger")
        dest = url_for('residents_menu') if user else url_for('login')
        return redirect(dest)

    fp = FlouciPayment.query.filter_by(flouci_payment_id=payment_id).first()
    if not fp:
        flash("Paiement introuvable.", "danger")
        dest = url_for('residents_menu') if user else url_for('login')
        return redirect(dest)

    if user and user.organization_id and user.organization_id != fp.organization_id:
        flash("Accès non autorisé.", "danger")
        return redirect(url_for('login'))

    if fp.status == 'completed':
        return render_template('flouci_success.html', fp=fp, already_done=True, user=user)

    # Vérification auprès de l'API Flouci
    org = Organization.query.get(fp.organization_id)
    verified = False
    try:
        resp = http.get(
            FLOUCI_VERIFY_URL.format(payment_id=payment_id),
            headers={
                'app_token': org.flouci_app_token,
                'app_secret': org.flouci_app_secret,
            },
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            result = data.get('result', {})
            if result.get('status') == 'SUCCESS':
                verified = True
    except Exception:
        pass

    if verified:
        import json as _json
        try:
            months_to_pay = _json.loads(fp.months_json) if fp.months_json else [fp.month_target]
        except Exception:
            months_to_pay = [fp.month_target]

        amount_per_month = round(fp.amount / len(months_to_pay), 3)

        for _month in months_to_pay:
            existing = Payment.query.filter_by(
                apartment_id=fp.apartment_id, month_paid=_month
            ).first()
            if not existing:
                p = Payment(
                    organization_id=fp.organization_id,
                    apartment_id=fp.apartment_id,
                    amount=amount_per_month,
                    payment_date=datetime.utcnow().date(),
                    month_paid=_month,
                    description=f"Paiement en ligne Flouci — {_month}",
                    credit_used=0.0
                )
                db.session.add(p)
        fp.status = 'completed'
        fp.paid_at = datetime.utcnow()
        db.session.commit()
        try:
            apt = Apartment.query.get(fp.apartment_id)
            resident = User.query.filter_by(apartment_id=fp.apartment_id).first()
            notify_payment(org, apt, months_to_pay[0], fp.amount, resident)
        except Exception:
            pass

    return render_template('flouci_success.html', fp=fp, verified=verified, already_done=False, user=user)


@app.route('/flouci/fail')
def flouci_fail():
    payment_id = request.args.get('payment_id') or request.args.get('paymentId')
    user = current_user()
    fp = None
    if payment_id:
        fp = FlouciPayment.query.filter_by(flouci_payment_id=payment_id).first()
        if fp and fp.status == 'pending':
            fp.status = 'failed'
            db.session.commit()
    return render_template('flouci_fail.html', fp=fp, user=user)


# ─── RÉSIDENT : paiement groupé (plusieurs mois) ────────────────────────────

@app.route('/flouci/pay-multi', methods=['POST'])
@login_required
@subscription_required
def flouci_pay_multi():
    import json as _json
    user = current_user()
    if not user.apartment_id:
        flash("Vous n'êtes pas affecté à un appartement.", "danger")
        return redirect(url_for('residents_menu'))

    org = current_organization()
    if not org.flouci_app_token or not org.flouci_app_secret:
        flash("Le paiement Flouci n'est pas encore configuré pour votre syndic.", "warning")
        return redirect(url_for('residents_menu'))

    months_raw = request.form.get('months', '').strip()
    if not months_raw:
        flash("Aucun mois sélectionné.", "warning")
        return redirect(url_for('residents_menu'))

    months = [m.strip() for m in months_raw.split(',') if m.strip()]
    apt = Apartment.query.get(user.apartment_id)

    # Exclure les mois déjà payés
    months = [m for m in months
              if not Payment.query.filter_by(apartment_id=apt.id, month_paid=m).first()]
    if not months:
        flash("Tous les mois sélectionnés sont déjà payés.", "info")
        return redirect(url_for('residents_menu'))

    total = round(apt.monthly_fee * len(months), 3)

    fp = FlouciPayment(
        organization_id=org.id,
        apartment_id=apt.id,
        month_target=months[0],
        amount=total,
        months_json=_json.dumps(months),
        created_by='resident',
        status='pending'
    )
    db.session.add(fp)
    db.session.flush()

    session_id = f"fp-{fp.id}-multi"
    try:
        resp = http.post(
            FLOUCI_GENERATE_URL,
            json={
                'app_token': org.flouci_app_token,
                'app_secret': org.flouci_app_secret,
                'amount': int(round(total * 1000)),
                'accept_card': 'true',
                'session_id': session_id,
                'success_link': f"{BASE_URL}/flouci/success",
                'fail_link': f"{BASE_URL}/flouci/fail",
                'developer_tracking_id': f"fp-{fp.id}",
            },
            timeout=15
        )
        if resp.status_code in (200, 201):
            data = resp.json()
            result = data.get('result', {})
            fp.flouci_payment_id = result.get('payment_id') or result.get('paymentId')
            fp.pay_url = result.get('link') or result.get('pay_url')
            db.session.commit()
            return redirect(fp.pay_url)
        else:
            db.session.rollback()
            flash(f"Erreur Flouci ({resp.status_code})", "danger")
    except Exception as e:
        db.session.rollback()
        flash(f"Connexion Flouci impossible : {e}", "danger")

    return redirect(url_for('residents_menu'))


# ─── ADMIN : générer un lien ─────────────────────────────────────────────────

@app.route('/flouci/admin/generate-link', methods=['POST'])
@login_required
@admin_required
@subscription_required
def flouci_generate_link():
    org = current_organization()
    if not org.flouci_app_token or not org.flouci_app_secret:
        return jsonify({'ok': False, 'message': 'Flouci non configuré. Allez dans Paramètres.'})

    apartment_id = request.form.get('apartment_id', type=int)
    month_target = request.form.get('month_target', '').strip()
    amount = request.form.get('amount', type=float)

    if not apartment_id or not month_target or not amount:
        return jsonify({'ok': False, 'message': 'Données manquantes.'})

    apt = Apartment.query.filter_by(id=apartment_id, organization_id=org.id).first()
    if not apt:
        return jsonify({'ok': False, 'message': 'Appartement introuvable.'})

    existing = FlouciPayment.query.filter_by(
        apartment_id=apt.id,
        month_target=month_target,
        status='pending'
    ).first()
    if existing and existing.pay_url:
        return jsonify({'ok': True, 'pay_url': existing.pay_url, 'reused': True})

    fp, err = _call_flouci_init(org, apt, month_target, amount, created_by='admin')
    if err:
        return jsonify({'ok': False, 'message': err})

    return jsonify({'ok': True, 'pay_url': fp.pay_url, 'reused': False})


# ─── ADMIN : liste des liens ──────────────────────────────────────────────────

@app.route('/flouci/links')
@login_required
@admin_required
@subscription_required
def flouci_links():
    org = current_organization()
    links = (FlouciPayment.query
             .filter_by(organization_id=org.id)
             .order_by(FlouciPayment.created_at.desc())
             .all())
    return render_template('flouci_links.html', links=links, user=current_user(), org=org)
