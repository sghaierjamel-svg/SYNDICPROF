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

# Configuration pour Render
_secret_key = os.environ.get('SECRET_KEY')
if not _secret_key:
    raise RuntimeError("ERREUR CRITIQUE : SECRET_KEY non définie dans les variables d'environnement !")
app.config['SECRET_KEY'] = _secret_key
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Configuration de la base de données
database_url = os.environ.get('DATABASE_URL')

# Si pas de DATABASE_URL (en local), utiliser SQLite
if not database_url:
    database_dir = os.path.join(BASE_DIR, 'database')
    if not os.path.exists(database_dir):
        os.makedirs(database_dir)
    database_url = 'sqlite:///' + os.path.join(database_dir, 'syndicpro.db')

# Si on utilise PostgreSQL sur Render, corriger l'URL
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://"
)

csrf = CSRFProtect(app)
