"""
Suivi des visites du site SyndicPro.
Enregistre chaque page vue (GET) en base de données pour le tableau de bord superadmin.
"""
import hashlib
import secrets
from urllib.parse import urlparse

# Orgs exclues des analytics (comptes de test — insensible à la casse, recherche partielle)
_EXCLUDED_ORG_KEYWORDS = ('jasmin',)


def _is_excluded_user(user_id):
    """Retourne True si cet utilisateur ne doit pas être comptabilisé dans les analytics."""
    if not user_id:
        return False
    try:
        from models import User, Organization
        user = User.query.get(user_id)
        if not user:
            return False
        if user.role == 'superadmin':
            return True
        if user.organization_id:
            org = Organization.query.get(user.organization_id)
            if org:
                name_lower = (org.name or '').lower()
                slug_lower = (org.slug or '').lower()
                if any(kw in name_lower or kw in slug_lower for kw in _EXCLUDED_ORG_KEYWORDS):
                    return True
    except Exception:
        pass
    return False


# ─── Parsing User-Agent (sans bibliothèque externe) ───────────────────────────

_BOT_KEYWORDS = (
    'bot', 'crawler', 'spider', 'scraper', 'slurp', 'wget', 'curl/',
    'python-requests', 'python/', 'java/', 'go-http', 'postman',
    'okhttp', 'axios', 'libwww', 'facebookexternalhit', 'linkedinbot',
    'twitterbot', 'whatsapp', 'googlebot', 'bingbot', 'yandexbot',
    'duckduckbot', 'baiduspider', 'semrushbot', 'ahrefsbot', 'mj12bot',
)

_SKIP_PREFIXES = ('/static/', '/favicon')
_SKIP_ENDPOINTS = {'static'}


def _is_bot(ua: str) -> bool:
    ua_lo = ua.lower()
    return any(kw in ua_lo for kw in _BOT_KEYWORDS)


def _parse_ua(ua_string: str):
    """Retourne (device_type, browser, os_name)."""
    ua = (ua_string or '').lower()

    # Device
    is_mobile = 'mobile' in ua and 'ipad' not in ua
    is_tablet = 'ipad' in ua or ('android' in ua and 'mobile' not in ua) or 'tablet' in ua
    if is_tablet:
        device = 'tablet'
    elif is_mobile or 'android' in ua and 'mobile' in ua:
        device = 'mobile'
    else:
        device = 'desktop'

    # Browser (ordre important — Edge/Opera avant Chrome)
    if 'edg/' in ua or 'edge/' in ua:
        browser = 'Edge'
    elif 'opr/' in ua or 'opera' in ua:
        browser = 'Opera'
    elif 'chrome/' in ua:
        browser = 'Chrome'
    elif 'firefox/' in ua:
        browser = 'Firefox'
    elif 'safari/' in ua:
        browser = 'Safari'
    else:
        browser = 'Autre'

    # OS
    if 'windows' in ua:
        os_name = 'Windows'
    elif 'android' in ua:
        os_name = 'Android'
    elif 'iphone' in ua or 'ipad' in ua:
        os_name = 'iOS'
    elif 'mac os' in ua or 'macintosh' in ua:
        os_name = 'macOS'
    elif 'linux' in ua:
        os_name = 'Linux'
    else:
        os_name = 'Autre'

    return device, browser, os_name


def _hash_ip(ip: str) -> str:
    """SHA-256 tronqué à 16 caractères — anonymise l'IP."""
    return hashlib.sha256(ip.encode('utf-8')).hexdigest()[:16]


def _referrer_domain(referrer: str) -> str | None:
    if not referrer:
        return None
    try:
        netloc = urlparse(referrer).netloc.lower()
        netloc = netloc.split(':')[0]  # enlever le port
        if netloc.startswith('www.'):
            netloc = netloc[4:]
        return netloc[:150] or None
    except Exception:
        return None


# ─── Enregistrement d'une visite ──────────────────────────────────────────────

def track_visit(response):
    """Hook after_request : enregistre la visite si applicable."""
    from flask import request, session as flask_session
    from models import SiteVisit
    from core import db

    try:
        # Seulement les pages (GET, pas AJAX / POST / API)
        if request.method != 'GET':
            return response

        path = request.path

        # Ignorer fichiers statiques et favicon
        if any(path.startswith(p) for p in _SKIP_PREFIXES):
            return response

        ua_string = request.headers.get('User-Agent', '')

        # Ignorer les bots
        if _is_bot(ua_string):
            return response

        device, browser, os_name = _parse_ua(ua_string)

        # Référent
        referrer = (request.referrer or '')[:500]
        ref_domain = _referrer_domain(referrer)
        # Supprimer auto-référent (même domaine)
        own_host = request.host.lower().replace('www.', '').split(':')[0]
        if ref_domain and (ref_domain == own_host or ref_domain.endswith('.' + own_host)):
            ref_domain = None
            referrer = ''

        # UTM params (landing page uniquement, pas polluant dans les autres pages)
        utm_source = (request.args.get('utm_source') or '')[:80] or None
        utm_medium = (request.args.get('utm_medium') or '')[:80] or None
        utm_campaign = (request.args.get('utm_campaign') or '')[:100] or None

        # IP → hash court
        forwarded = request.headers.get('X-Forwarded-For', '')
        ip_raw = (forwarded.split(',')[0].strip() if forwarded else request.remote_addr) or ''
        ip_hash = _hash_ip(ip_raw) if ip_raw else ''

        # Clé de session anonyme (cookie _sv)
        session_key = request.cookies.get('_sv', '')

        # Utilisateur connecté
        user_id = flask_session.get('user_id')

        # Exclure superadmin et comptes de test
        if _is_excluded_user(user_id):
            return response

        visit = SiteVisit(
            path=path[:500],
            ip_hash=ip_hash,
            session_key=session_key[:32] if session_key else '',
            user_id=user_id,
            referrer=referrer,
            referrer_domain=ref_domain,
            device_type=device,
            browser=browser,
            os_name=os_name,
            utm_source=utm_source,
            utm_medium=utm_medium,
            utm_campaign=utm_campaign,
            status_code=response.status_code,
        )
        db.session.add(visit)
        db.session.commit()

        # Poser le cookie anonyme si absent (365 jours)
        if not session_key:
            new_key = secrets.token_hex(16)
            secure = request.is_secure
            response.set_cookie(
                '_sv', new_key,
                max_age=365 * 24 * 3600,
                httponly=True,
                samesite='Lax',
                secure=secure,
            )
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass

    return response
