from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from datetime import timedelta
from dotenv import load_dotenv
import os

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)

# ── Secrets obligatoires ─────────────────────────────────────────────────────
_secret_key = os.environ.get('SECRET_KEY')
if not _secret_key:
    raise RuntimeError("ERREUR CRITIQUE : SECRET_KEY non définie dans les variables d'environnement !")
app.config['SECRET_KEY'] = _secret_key

# ── Session / Cookies ────────────────────────────────────────────────────────
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
app.config['SESSION_COOKIE_SECURE']   = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Strict'   # MED-014 : Strict au lieu de Lax

# ── Sécurité requêtes ────────────────────────────────────────────────────────
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # HIGH-009 : 5 MB max

# ── Base de données ──────────────────────────────────────────────────────────
database_url = os.environ.get('DATABASE_URL')
if not database_url:
    database_dir = os.path.join(BASE_DIR, 'database')
    if not os.path.exists(database_dir):
        os.makedirs(database_dir)
    database_url = 'sqlite:///' + os.path.join(database_dir, 'syndicpro.db')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI']      = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://"
)

csrf = CSRFProtect(app)

# Filtre Jinja : maintenant (pour calculs de durée dans les templates)
from datetime import datetime as _dt
app.jinja_env.globals['now'] = _dt.utcnow


# ── En-têtes de sécurité HTTP (MED-016) ─────────────────────────────────────
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options']        = 'SAMEORIGIN'
    response.headers['X-XSS-Protection']       = '1; mode=block'
    response.headers['Referrer-Policy']        = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy']     = 'geolocation=(), microphone=(), camera=()'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' cdn.jsdelivr.net fonts.googleapis.com; "
        "font-src 'self' fonts.gstatic.com cdn.jsdelivr.net; "
        "img-src 'self' data: blob:; "
        "connect-src 'self'; "
        "frame-ancestors 'none';"
    )
    return response
