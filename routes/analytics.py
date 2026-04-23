from flask import render_template, request
from core import app, db
from models import SiteVisit, Organization, User
from utils import login_required, superadmin_required
from datetime import datetime, timedelta
from sqlalchemy import func


def _get_excluded_user_ids():
    """Retourne la liste des user_ids à exclure des analytics (superadmin + orgs de test)."""
    excluded = []
    # Superadmins
    for u in User.query.filter_by(role='superadmin').all():
        excluded.append(u.id)
    # Orgs de test (contenant 'jasmin' dans le nom ou le slug)
    test_orgs = Organization.query.filter(
        db.or_(
            func.lower(Organization.name).contains('jasmin'),
            func.lower(Organization.slug).contains('jasmin'),
        )
    ).all()
    for org in test_orgs:
        for u in User.query.filter_by(organization_id=org.id).all():
            excluded.append(u.id)
    return excluded


@app.route('/superadmin/analytics')
@login_required
@superadmin_required
def superadmin_analytics():
    period = request.args.get('period', '30')
    try:
        days = int(period)
        if days not in (7, 30, 90, 365):
            days = 30
    except ValueError:
        days = 30

    since = datetime.utcnow() - timedelta(days=days)

    # ── Exclusion superadmin + comptes de test ───────────────────────────────
    excluded_ids = _get_excluded_user_ids()

    def _exclude(q):
        if excluded_ids:
            return q.filter(
                db.or_(
                    SiteVisit.user_id.is_(None),
                    SiteVisit.user_id.notin_(excluded_ids),
                )
            )
        return q

    base_q = _exclude(SiteVisit.query.filter(SiteVisit.ts >= since))

    # ── Chiffres globaux ─────────────────────────────────────────────────────
    total_pages_vues = base_q.count()

    visiteurs_uniques = (
        db.session.query(func.count(func.distinct(SiteVisit.session_key)))
        .filter(SiteVisit.ts >= since, SiteVisit.session_key != '')
        .filter(db.or_(SiteVisit.user_id.is_(None), SiteVisit.user_id.notin_(excluded_ids)) if excluded_ids else db.true())
        .scalar() or 0
    )

    subq_first = (
        db.session.query(
            SiteVisit.session_key,
            func.min(SiteVisit.ts).label('first_ts')
        )
        .filter(SiteVisit.session_key != '')
        .filter(db.or_(SiteVisit.user_id.is_(None), SiteVisit.user_id.notin_(excluded_ids)) if excluded_ids else db.true())
        .group_by(SiteVisit.session_key)
        .subquery()
    )
    nouvelles_sessions = (
        db.session.query(func.count())
        .filter(subq_first.c.first_ts >= since)
        .scalar() or 0
    )

    # ── Bounce rate (sessions avec 1 seule page vue) ─────────────────────────
    sessions_with_counts = (
        db.session.query(
            SiteVisit.session_key,
            func.count(SiteVisit.id).label('page_count')
        )
        .filter(SiteVisit.ts >= since, SiteVisit.session_key != '')
        .filter(db.or_(SiteVisit.user_id.is_(None), SiteVisit.user_id.notin_(excluded_ids)) if excluded_ids else db.true())
        .group_by(SiteVisit.session_key)
        .subquery()
    )
    total_sessions = db.session.query(func.count()).select_from(sessions_with_counts).scalar() or 0
    bounce_sessions = (
        db.session.query(func.count())
        .select_from(sessions_with_counts)
        .filter(sessions_with_counts.c.page_count == 1)
        .scalar() or 0
    )
    bounce_rate = round(bounce_sessions / total_sessions * 100, 1) if total_sessions else 0

    # ── Durée de session estimée (moy. en secondes entre 1ère et dernière vue) ─
    session_times = (
        db.session.query(
            SiteVisit.session_key,
            func.min(SiteVisit.ts).label('first'),
            func.max(SiteVisit.ts).label('last'),
            func.count(SiteVisit.id).label('cnt')
        )
        .filter(SiteVisit.ts >= since, SiteVisit.session_key != '')
        .filter(db.or_(SiteVisit.user_id.is_(None), SiteVisit.user_id.notin_(excluded_ids)) if excluded_ids else db.true())
        .group_by(SiteVisit.session_key)
        .having(func.count(SiteVisit.id) > 1)
        .all()
    )
    if session_times:
        total_secs = sum((r.last - r.first).total_seconds() for r in session_times)
        avg_duration_secs = int(total_secs / len(session_times))
        avg_duration = f"{avg_duration_secs // 60}m {avg_duration_secs % 60}s"
    else:
        avg_duration = "—"

    # ── Visites par jour ─────────────────────────────────────────────────────
    chart_days = min(days, 90)
    chart_since = datetime.utcnow() - timedelta(days=chart_days)

    if 'postgresql' in str(db.engine.url):
        day_expr = func.date_trunc('day', SiteVisit.ts)
    else:
        day_expr = func.date(SiteVisit.ts)

    visits_by_day_rows = (
        _exclude(
            db.session.query(day_expr.label('day'), func.count().label('cnt'))
            .filter(SiteVisit.ts >= chart_since)
        )
        .group_by('day')
        .order_by('day')
        .all()
    )

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
        _exclude(
            db.session.query(SiteVisit.path, func.count().label('cnt'))
            .filter(SiteVisit.ts >= since)
        )
        .group_by(SiteVisit.path)
        .order_by(func.count().desc())
        .limit(15)
        .all()
    )

    # ── Sources de trafic ────────────────────────────────────────────────────
    top_referrers = (
        _exclude(
            db.session.query(SiteVisit.referrer_domain, func.count().label('cnt'))
            .filter(SiteVisit.ts >= since, SiteVisit.referrer_domain.isnot(None))
        )
        .group_by(SiteVisit.referrer_domain)
        .order_by(func.count().desc())
        .limit(10)
        .all()
    )

    direct_count = (
        _exclude(
            db.session.query(func.count())
            .filter(SiteVisit.ts >= since,
                    SiteVisit.referrer_domain.is_(None),
                    SiteVisit.referrer == '')
        )
        .scalar() or 0
    )

    # ── Appareils ────────────────────────────────────────────────────────────
    devices = (
        _exclude(
            db.session.query(SiteVisit.device_type, func.count().label('cnt'))
            .filter(SiteVisit.ts >= since)
        )
        .group_by(SiteVisit.device_type)
        .all()
    )
    device_labels = [r.device_type or 'inconnu' for r in devices]
    device_data   = [r.cnt for r in devices]

    # ── Navigateurs ──────────────────────────────────────────────────────────
    browsers = (
        _exclude(
            db.session.query(SiteVisit.browser, func.count().label('cnt'))
            .filter(SiteVisit.ts >= since)
        )
        .group_by(SiteVisit.browser)
        .order_by(func.count().desc())
        .all()
    )
    browser_labels = [r.browser or 'Autre' for r in browsers]
    browser_data   = [r.cnt for r in browsers]

    # ── Systèmes d'exploitation ───────────────────────────────────────────────
    os_rows = (
        _exclude(
            db.session.query(SiteVisit.os_name, func.count().label('cnt'))
            .filter(SiteVisit.ts >= since)
        )
        .group_by(SiteVisit.os_name)
        .order_by(func.count().desc())
        .all()
    )
    os_labels = [r.os_name or 'Autre' for r in os_rows]
    os_data   = [r.cnt for r in os_rows]

    # ── Entonnoir de conversion ───────────────────────────────────────────────
    visitors_index = (
        db.session.query(func.count(func.distinct(SiteVisit.session_key)))
        .filter(SiteVisit.ts >= since, SiteVisit.path == '/', SiteVisit.session_key != '')
        .filter(db.or_(SiteVisit.user_id.is_(None), SiteVisit.user_id.notin_(excluded_ids)) if excluded_ids else db.true())
        .scalar() or 0
    )
    visitors_register = (
        db.session.query(func.count(func.distinct(SiteVisit.session_key)))
        .filter(SiteVisit.ts >= since, SiteVisit.path == '/register', SiteVisit.session_key != '')
        .filter(db.or_(SiteVisit.user_id.is_(None), SiteVisit.user_id.notin_(excluded_ids)) if excluded_ids else db.true())
        .scalar() or 0
    )
    # Exclure les orgs de test des inscriptions réelles
    test_org_ids = [o.id for o in Organization.query.filter(
        db.or_(
            func.lower(Organization.name).contains('jasmin'),
            func.lower(Organization.slug).contains('jasmin'),
        )
    ).all()]
    new_orgs_q = Organization.query.filter(Organization.created_at >= since)
    if test_org_ids:
        new_orgs_q = new_orgs_q.filter(Organization.id.notin_(test_org_ids))
    new_orgs = new_orgs_q.count()

    funnel = [
        ('Visiteurs uniques', visiteurs_uniques),
        ('Ont vu /register', visitors_register),
        ('Inscriptions réelles', new_orgs),
    ]
    conv_rate = round(new_orgs / visitors_register * 100, 1) if visitors_register else 0

    # ── Campagnes UTM ────────────────────────────────────────────────────────
    utm_rows = (
        _exclude(
            db.session.query(
                SiteVisit.utm_source,
                SiteVisit.utm_medium,
                SiteVisit.utm_campaign,
                func.count().label('cnt')
            )
            .filter(SiteVisit.ts >= since, SiteVisit.utm_source.isnot(None))
        )
        .group_by(SiteVisit.utm_source, SiteVisit.utm_medium, SiteVisit.utm_campaign)
        .order_by(func.count().desc())
        .limit(10)
        .all()
    )

    # ── Heures de pointe ─────────────────────────────────────────────────────
    if 'postgresql' in str(db.engine.url):
        hour_expr = func.extract('hour', SiteVisit.ts)
    else:
        hour_expr = func.strftime('%H', SiteVisit.ts)

    hours_rows = (
        _exclude(
            db.session.query(hour_expr.label('h'), func.count().label('cnt'))
            .filter(SiteVisit.ts >= since)
        )
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
        bounce_rate=bounce_rate,
        avg_duration=avg_duration,
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
