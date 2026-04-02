"""
Tests de base SyndicPro — Phase 7
Lancer : venv/bin/pytest tests/ -v
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


@pytest.fixture
def client():
    os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')
    os.environ.setdefault('SECRET_KEY', 'test-secret-key')

    # Importer app charge toutes les routes
    import app as _app_module   # noqa: F401
    from core import app as flask_app, db as _db

    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False

    with flask_app.app_context():
        _db.create_all()
        yield flask_app.test_client()
        _db.session.remove()
        _db.drop_all()


# ── Pages publiques ────────────────────────────────────────────────────────

def test_login_page(client):
    """La page de login s'affiche."""
    r = client.get('/login')
    assert r.status_code == 200
    assert b'SyndicPro' in r.data or b'login' in r.data.lower()


def test_register_page(client):
    """La page d'inscription s'affiche."""
    r = client.get('/register')
    assert r.status_code == 200


def test_index_redirects(client):
    """La racine redirige (vers login ou dashboard)."""
    r = client.get('/')
    assert r.status_code in (200, 301, 302)


# ── Accès protégé sans login ────────────────────────────────────────────────

@pytest.mark.parametrize("url", [
    '/dashboard', '/payments', '/expenses', '/apartments',
    '/users', '/tickets', '/settings', '/ai', '/automation', '/access',
])
def test_protected_redirects_to_login(client, url):
    """Les routes protégées redirigent vers /login si non connecté."""
    r = client.get(url, follow_redirects=False)
    assert r.status_code in (302, 401), f"{url} devrait rediriger"


# ── Modèles ────────────────────────────────────────────────────────────────

def test_user_password_hash(client):
    """Le mot de passe est bien hashé."""
    from models import User
    u = User(email='test@test.com', name='Test', role='resident')
    u.set_password('motdepasse123')
    assert u.password_hash != 'motdepasse123'
    assert u.check_password('motdepasse123')
    assert not u.check_password('mauvais')


def test_subscription_days_remaining(client):
    """days_remaining() retourne 0 si pas de date de fin."""
    from models import Subscription
    s = Subscription()
    assert s.days_remaining() == 0
    assert not s.is_expired()


def test_organization_model(client):
    """L'organisation se crée correctement."""
    from models import Organization
    from core import db
    with client.application.app_context():
        org = Organization(name='Test Org', slug='test-org', email='test@org.tn')
        db.session.add(org)
        db.session.commit()
        found = Organization.query.filter_by(slug='test-org').first()
        assert found is not None
        assert found.name == 'Test Org'


# ── WhatsApp utils ─────────────────────────────────────────────────────────

def test_whatsapp_disabled(client):
    """Pas d'envoi si WhatsApp désactivé."""
    from utils_whatsapp import send_whatsapp
    from models import Organization
    org = Organization(name='Test', slug='t', email='t@t.tn',
                       whatsapp_enabled=False, whatsapp_token='tok')
    result = send_whatsapp(org, '+21620000000', 'test')
    assert result is False


def test_phone_normalization(client):
    """Normalisation des numéros tunisiens."""
    from utils_whatsapp import _normalize_phone
    assert _normalize_phone('+21620123456') == '21620123456'
    assert _normalize_phone('20123456') == '21620123456'
    assert _normalize_phone('0021620123456') == '21620123456'
