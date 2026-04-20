from flask import render_template, request
from core import app, db
from models import SiteVisit, Organization
from utils import login_required, superadmin_required
from datetime import datetime, timedelta, date
from sqlalchemy import func, cast, Date


@app.route('/superadmin/analytics')
@login_required
@superadmin_required
def superadmin_analytics():
    # Période sélectionnée
    period = request.args.get('period', '30')
    try:
        days = int(period)
        if days not in (7, 30, 90, 365):
            days = 30
    except ValueError:
        days = 30

    since = datetime.utcnow() - timedelta(days=days)

    base_q = SiteVisit.query.filter(SiteVisit.ts >= since)

    # ── Chiffres globaux ────────────────────────────────────────────────────
    total_pages_vues = base_q.count()

    visiteurs_uniques = (
        db.session.query(func.count(func.distinct(SiteVisit.session_key)))
        .filter(SiteVisit.ts >= since, SiteVisit.session_key != '')
        .scalar() or 0
    )

    # Nouvelles sessions = session_keys dont la PREMIÈRE visite est dans la période
    subq_first = (
        db.session.query(
            SiteVisit.session_key,
            func.min(SiteVisit.ts).label('first_ts')
        )
        .filter(SiteVisit.session_key != '')
        .group_by(SiteVisit.session_key)
        .subquery()
    )
    nouvelles_sessions = (
        db.session.query(func.count())
        .filter(subq_first.c.first_ts >= since)
        .scalar() or 0
    )

    # ── Visites par jour (30 derniers jours max pour le graphique) ──────────
    chart_days = min(days, 90)
    chart_since = datetime.utcnow() - timedelta(days=chart_days)

    if 'postgresql' in str(db.engine.url):
        day_expr = func.date_trunc('day', SiteVisit.ts)
    else:
        day_expr = func.date(SiteVisit.ts)

    visits_by_day_rows = (
        db.session.query(day_expr.label('day'), func.count().label('cnt'))
        .filter(SiteVisit.ts >= chart_since)
        .group_by('day')
        .order_by('day')
        .all()
    )

    # Remplir les jours manquants avec 0
    day_map = {}
    for row in visits_by_day_rows:
        d = row.day
        if hasattr(d, 'date'):
            d = d.date()
        day_map[str(d)] = row.cnt

    chart_labels = []
    chart_data = []
    for i in range(chart_days):
        d = (datetime.utcnow() - timedelta(days=chart_days - 1 - i)).date()
        chart_labels.append(d.strftime('%d/%m'))
        chart_data.append(day_map.get(str(d), 0))

    # ── Pages les plus visitées ──────────────────────────────────────────────
    top_pages = (
        db.session.query(SiteVisit.path, func.count().label('cnt'))
        .filter(SiteVisit.ts >= since)
        .group_by(SiteVisit.path)
        .order_by(func.count().desc())
        .limit(15)
        .all()
    )

    # ── Sources de trafic ────────────────────────────────────────────────────
    top_referrers = (
        db.session.query(SiteVisit.referrer_domain, func.count().label('cnt'))
        .filter(SiteVisit.ts >= since, SiteVisit.referrer_domain.isnot(None))
        .group_by(SiteVisit.referrer_domain)
        .order_by(func.count().desc())
        .limit(10)
        .all()
    )

    # Trafic direct (pas de référent)
    direct_count = (
        db.session.query(func.count())
        .filter(SiteVisit.ts >= since,
                SiteVisit.referrer_domain.is_(None),
                SiteVisit.referrer == '')
        .scalar() or 0
    )

    # ── Appareils ────────────────────────────────────────────────────────────
    devices = (
        db.session.query(SiteVisit.device_type, func.count().label('cnt'))
        .filter(SiteVisit.ts >= since)
        .group_by(SiteVisit.device_type)
        .all()
    )
    device_labels = [r.device_type or 'inconnu' for r in devices]
    device_data   = [r.cnt for r in devices]

    # ── Navigateurs ──────────────────────────────────────────────────────────
    browsers = (
        db.session.query(SiteVisit.browser, func.count().label('cnt'))
        .filter(SiteVisit.ts >= since)
        .group_by(SiteVisit.browser)
        .order_by(func.count().desc())
        .all()
    )
    browser_labels = [r.browser or 'Autre' for r in browsers]
    browser_data   = [r.cnt for r in browsers]

    # ── Systèmes d'exploitation ───────────────────────────────────────────────
    os_rows = (
        db.session.query(SiteVisit.os_name, func.count().label('cnt'))
        .filter(SiteVisit.ts >= since)
        .group_by(SiteVisit.os_name)
        .order_by(func.count().desc())
        .all()
    )
    os_labels = [r.os_name or 'Autre' for r in os_rows]
    os_data   = [r.cnt for r in os_rows]

    # ── Entonnoir de conversion ───────────────────────────────────────────────
    # Visiteurs uniques sur la page d'accueil
    visitors_index = (
        db.session.query(func.count(func.distinct(SiteVisit.session_key)))
        .filter(SiteVisit.ts >= since, SiteVisit.path == '/', SiteVisit.session_key != '')
        .scalar() or 0
    )
    # Visiteurs uniques sur /register
    visitors_register = (
        db.session.query(func.count(func.distinct(SiteVisit.session_key)))
        .filter(SiteVisit.ts >= since, SiteVisit.path == '/register', SiteVisit.session_key != '')
        .scalar() or 0
    )
    # Inscriptions réelles dans la période
    new_orgs = Organization.query.filter(Organization.created_at >= since).count()

    funnel = [
        ('Visiteurs uniques', visiteurs_uniques),
        ('Ont vu /register', visitors_register),
        ('Inscriptions réelles', new_orgs),
    ]

    conv_rate = round(new_orgs / visitors_register * 100, 1) if visitors_register else 0

    # ── Campagnes UTM ────────────────────────────────────────────────────────
    utm_rows = (
        db.session.query(
            SiteVisit.utm_source,
            SiteVisit.utm_medium,
            SiteVisit.utm_campaign,
            func.count().label('cnt')
        )
        .filter(SiteVisit.ts >= since, SiteVisit.utm_source.isnot(None))
        .group_by(SiteVisit.utm_source, SiteVisit.utm_medium, SiteVisit.utm_campaign)
        .order_by(func.count().desc())
        .limit(10)
        .all()
    )

    # ── Heures de pointe (0-23h) ─────────────────────────────────────────────
    if 'postgresql' in str(db.engine.url):
        hour_expr = func.extract('hour', SiteVisit.ts)
    else:
        hour_expr = func.strftime('%H', SiteVisit.ts)

    hours_rows = (
        db.session.query(hour_expr.label('h'), func.count().label('cnt'))
        .filter(SiteVisit.ts >= since)
        .group_by('h')
        .order_by('h')
        .all()
    )
    hour_map = {int(float(str(r.h))): r.cnt for r in hours_rows}
    hour_labels = [f"{h:02d}h" for h in range(24)]
    hour_data   = [hour_map.get(h, 0) for h in range(24)]

    return render_template(
        'superadmin/analytics.html',
        period=days,
        total_pages_vues=total_pages_vues,
        visiteurs_uniques=visiteurs_uniques,
        nouvelles_sessions=nouvelles_sessions,
        chart_labels=chart_labels,
        chart_data=chart_data,
        top_pages=top_pages,
        top_referrers=top_referrers,
        direct_count=direct_count,
        device_labels=device_labels,
        device_data=device_data,
        browser_labels=browser_labels,
        browser_data=browser_data,
        os_labels=os_labels,
        os_data=os_data,
        funnel=funnel,
        conv_rate=conv_rate,
        utm_rows=utm_rows,
        hour_labels=hour_labels,
        hour_data=hour_data,
    )
