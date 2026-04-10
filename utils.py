from functools import wraps
from flask import session, flash, redirect, url_for, request as _req
from core import app, db
from models import User, Organization, Apartment, Payment, UnpaidAlert
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta


@app.context_processor
def inject_notifications():
    """Injecte les notifications dans tous les templates (admin + résident)."""
    if _req.endpoint in (None, 'static', 'login', 'logout', 'register',
                         'index', 'demo', 'subscription_status'):
        return {}
    user = current_user()
    if not user or not user.organization_id:
        return {}

    org_id = user.organization_id
    result = {}

    if user.role == 'admin':
        from models import Ticket, AnnouncementRead, Announcement
        from sqlalchemy.orm import joinedload

        since_list = datetime.utcnow() - timedelta(hours=24)   # fenêtre affichage
        # Seuil "non vu" : depuis la dernière ouverture de la cloche (ou 24h si jamais ouvert)
        seen_at = user.notif_seen_at or (datetime.utcnow() - timedelta(hours=24))
        since_new = min(seen_at, since_list)   # on prend le plus ancien des deux

        notifs = []

        # Paiements récents
        recent_payments = Payment.query.options(
            joinedload(Payment.apartment).joinedload(Apartment.block)
        ).filter(
            Payment.organization_id == org_id,
            Payment.payment_date >= since_list.date()
        ).order_by(Payment.payment_date.desc()).limit(5).all()
        for p in recent_payments:
            apt_label = (f"{p.apartment.block.name}-{p.apartment.number}"
                         if p.apartment and p.apartment.block else "?")
            ts = datetime.combine(p.payment_date, datetime.min.time())
            notifs.append({
                'icon': 'cash-coin', 'color': '#00C896',
                'text': f"Paiement reçu — {apt_label}",
                'sub': f"{p.amount:.0f} DT · {p.month_paid}",
                'ts': ts,
                'new': ts > seen_at,
                'url': url_for('payments')
            })

        # Lectures d'annonces récentes
        recent_reads = (db.session.query(AnnouncementRead)
            .join(Announcement)
            .options(joinedload(AnnouncementRead.apartment).joinedload(Apartment.block))
            .filter(
                Announcement.organization_id == org_id,
                AnnouncementRead.read_at >= since_list
            ).order_by(AnnouncementRead.read_at.desc()).limit(5).all())
        for r in recent_reads:
            apt_label = (f"{r.apartment.block.name}-{r.apartment.number}"
                         if r.apartment and r.apartment.block else "?")
            notifs.append({
                'icon': 'eye', 'color': '#60A5FA',
                'text': f"{apt_label} a lu une annonce",
                'sub': (r.announcement.title[:40] if r.announcement else ""),
                'ts': r.read_at,
                'new': r.read_at > seen_at,
                'url': url_for('announcements')
            })

        # Tickets ouverts récents
        recent_tickets = Ticket.query.options(
            joinedload(Ticket.apartment).joinedload(Apartment.block)
        ).filter(
            Ticket.organization_id == org_id,
            Ticket.status == 'ouvert',
            Ticket.created_at >= since_list
        ).order_by(Ticket.created_at.desc()).limit(5).all()
        for t in recent_tickets:
            apt_label = (f"{t.apartment.block.name}-{t.apartment.number}"
                         if t.apartment and t.apartment.block else "?")
            notifs.append({
                'icon': 'chat-left-dots', 'color': '#F59E0B',
                'text': f"Nouveau ticket — {apt_label}",
                'sub': t.subject[:40],
                'ts': t.created_at,
                'new': t.created_at > seen_at,
                'url': url_for('tickets')
            })

        # Impayés critiques (nouveaux depuis seen_at)
        unpaid_critical = UnpaidAlert.query.filter(
            UnpaidAlert.organization_id == org_id,
            UnpaidAlert.email_sent == False,
            UnpaidAlert.alert_date > seen_at
        ).count()
        unpaid_critical_total = UnpaidAlert.query.filter_by(
            organization_id=org_id, email_sent=False
        ).count()

        notifs.sort(key=lambda x: x['ts'], reverse=True)
        # Badge = seulement les éléments non vus
        unseen_count = sum(1 for n in notifs if n['new']) + (1 if unpaid_critical > 0 else 0)

        # Virements en attente
        from models import PaymentRequest
        pending_virements = PaymentRequest.query.filter_by(
            organization_id=org_id, status='en_attente').count()

        result.update({
            'notif_list': notifs[:8],
            'notif_count': unseen_count,
            'unpaid_critical': unpaid_critical_total,
            'pending_virements_count': pending_virements,
        })

    elif user.role == 'resident' and user.apartment_id:
        from models import Announcement, AnnouncementRead
        anns = Announcement.query.filter_by(organization_id=org_id)\
            .order_by(Announcement.pinned.desc(), Announcement.created_at.desc()).limit(5).all()
        read_ids = {r.announcement_id for r in
                    AnnouncementRead.query.filter_by(user_id=user.id).all()}
        sidebar_anns = [(a, a.id not in read_ids) for a in anns]
        result.update({
            'sidebar_announcements': sidebar_anns,
            'sidebar_unread_count': sum(1 for _, unread in sidebar_anns if unread),
        })

    return result


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
