from functools import wraps
from flask import session, flash, redirect, url_for
from core import app, db
from models import User, Organization, Apartment, Payment, UnpaidAlert
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta


@app.before_request
def check_session_timeout():
    if session.get('user_id'):
        last_activity = session.get('last_activity')
        if last_activity:
            elapsed = datetime.utcnow() - datetime.fromisoformat(last_activity)
            if elapsed > timedelta(minutes=30):
                session.clear()
                flash("Session expirée, veuillez vous reconnecter.", "warning")
                return redirect(url_for('login'))
        session['last_activity'] = datetime.utcnow().isoformat()


@app.before_request
def warn_subscription_expiry():
    """BUG-F006 : Alerte flash 7 jours avant expiration de l'abonnement."""
    from flask import request as req
    # Éviter les boucles infinies sur les routes statiques et de session
    if req.endpoint in (None, 'static', 'login', 'logout', 'register',
                        'subscription_status', 'index'):
        return
    uid = session.get('user_id')
    if not uid:
        return
    user = User.query.get(uid)
    if not user or user.role in ('superadmin',):
        return
    org = Organization.query.get(user.organization_id) if user.organization_id else None
    if not org or not org.subscription or not org.subscription.end_date:
        return
    days = org.subscription.days_remaining()
    if 0 < days <= 7 and not session.get('expiry_warned'):
        flash(
            f"⚠️ Votre abonnement expire dans {days} jour(s). "
            "Pensez à le renouveler pour éviter une interruption de service.",
            "warning"
        )
        session['expiry_warned'] = True
    elif days > 7:
        session.pop('expiry_warned', None)


def current_user():
    uid = session.get('user_id')
    if not uid:
        return None
    return User.query.get(uid)


def current_organization():
    user = current_user()
    if not user:
        return None
    if user.role == 'superadmin':
        return None
    return Organization.query.get(user.organization_id)


def check_subscription():
    org = current_organization()
    if not org:
        return True
    if not org.subscription:
        return False
    return not org.subscription.is_expired() and org.subscription.status == 'active'


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user():
            flash("Veuillez vous connecter.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper


def subscription_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = current_user()
        if user and user.role == 'superadmin':
            return f(*args, **kwargs)
        if not check_subscription():
            flash("Votre abonnement a expiré. Veuillez le renouveler.", "danger")
            return redirect(url_for('subscription_status'))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user or user.role not in ['admin', 'superadmin']:
            flash("Accès administrateur requis.", "danger")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return wrapper


def superadmin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user or user.role != 'superadmin':
            flash("Accès super administrateur requis.", "danger")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return wrapper


def get_unpaid_months_count(apartment_id):
    """Compte le nombre de mois impayés DEPUIS LA CRÉATION de l'appartement"""
    apt = Apartment.query.get(apartment_id)
    if not apt:
        return 0

    payments = Payment.query.filter_by(apartment_id=apartment_id).all()
    paid_months = set(p.month_paid for p in payments)

    if apt.created_at:
        start_date = apt.created_at.date().replace(day=1)
    else:
        start_date = date.today().replace(day=1)

    current = start_date
    end_date = date.today().replace(day=1)

    unpaid_count = 0
    while current <= end_date:
        month_str = current.strftime('%Y-%m')
        if month_str not in paid_months:
            unpaid_count += 1
        current += relativedelta(months=1)

    return unpaid_count


def get_next_unpaid_month(apartment_id):
    """
    Retourne le premier mois (YYYY-MM) non couvert par un paiement
    depuis la création de l'appartement, en regardant jusqu'à 3 mois dans le futur.
    """
    apt = Apartment.query.get(apartment_id)
    if not apt:
        return date.today().strftime('%Y-%m')

    payments = Payment.query.filter_by(apartment_id=apartment_id).all()
    paid_months = set(p.month_paid for p in payments)

    if apt.created_at:
        start_date = apt.created_at.date().replace(day=1)
    else:
        start_date = date.today().replace(day=1)

    current = start_date
    end_check_date = date.today().replace(day=1) + relativedelta(months=3)

    while current <= end_check_date:
        month_str = current.strftime('%Y-%m')
        if month_str not in paid_months:
            return month_str
        current += relativedelta(months=1)

    return (end_check_date + relativedelta(months=1)).strftime('%Y-%m')


def check_unpaid_alerts():
    org = current_organization()
    if not org:
        return []
    apartments = Apartment.query.filter_by(organization_id=org.id).all()
    alerts_created = []
    for apt in apartments:
        unpaid_count = get_unpaid_months_count(apt.id)
        if unpaid_count >= 3:
            recent_alert = UnpaidAlert.query.filter_by(
                apartment_id=apt.id
            ).filter(
                UnpaidAlert.alert_date > datetime.utcnow() - timedelta(days=30)
            ).first()
            if not recent_alert:
                alert = UnpaidAlert(
                    organization_id=org.id,
                    apartment_id=apt.id,
                    months_unpaid=unpaid_count
                )
                db.session.add(alert)
                alerts_created.append(apt)
    if alerts_created:
        db.session.commit()
    return alerts_created


def last_n_months(n=12):
    today = date.today()
    months = []
    for i in range(n-1, -1, -1):
        month_date = today - relativedelta(months=i)
        months.append((month_date.year, month_date.month))
    return months


def get_month_name(month_num):
    months_fr = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin',
                 'Juil', 'Août', 'Sep', 'Oct', 'Nov', 'Déc']
    return months_fr[month_num - 1]
