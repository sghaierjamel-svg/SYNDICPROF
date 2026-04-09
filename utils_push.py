"""
Service Web Push Notifications via VAPID (pywebpush).

Variables d'environnement requises sur Render :
  VAPID_PUBLIC_KEY   — clé publique VAPID (base64url)
  VAPID_PRIVATE_KEY  — clé privée VAPID (format PEM, \\n pour les sauts de ligne)
"""
import os, json

VAPID_PUBLIC_KEY  = os.environ.get('VAPID_PUBLIC_KEY', '')
_raw_priv         = os.environ.get('VAPID_PRIVATE_KEY', '')
VAPID_PRIVATE_KEY = _raw_priv.replace('\\n', '\n') if _raw_priv else ''
VAPID_CLAIMS      = {'sub': 'mailto:contact@syndicpro.tn'}


def _send_one(sub, title: str, body: str, url: str = '/dashboard', tag: str = 'syndicpro'):
    """Envoie une notification push à un seul abonnement."""
    if not VAPID_PRIVATE_KEY or not VAPID_PUBLIC_KEY:
        print('[Push] VAPID keys manquantes — notifications désactivées')
        return
    try:
        from pywebpush import webpush, WebPushException
        payload = json.dumps({
            'title': title,
            'body':  body,
            'url':   url,
            'icon':  '/static/icons/icon-192.png',
            'badge': '/static/icons/icon-192.png',
            'tag':   tag,
        }, ensure_ascii=False)
        webpush(
            subscription_info={
                'endpoint': sub.endpoint,
                'keys': {'p256dh': sub.p256dh, 'auth': sub.auth},
            },
            data=payload,
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims=VAPID_CLAIMS,
        )
        print(f'[Push] OK → user_id={sub.user_id} | {title}')
    except Exception as e:
        err = str(e)
        print(f'[Push] ERREUR : {err}')
        # Abonnement expiré ou révoqué → supprimer silencieusement
        if '410' in err or '404' in err or '401' in err:
            try:
                from core import db
                from models import PushSubscription
                PushSubscription.query.filter_by(id=sub.id).delete()
                db.session.commit()
            except Exception:
                pass


def push_to_user(user_id: int, title: str, body: str, url: str = '/dashboard', tag: str = 'syndicpro'):
    """Envoie une push notification à tous les appareils d'un utilisateur."""
    try:
        from models import PushSubscription
        subs = PushSubscription.query.filter_by(user_id=user_id).all()
        for sub in subs:
            _send_one(sub, title, body, url, tag)
    except Exception as e:
        print(f'[Push] push_to_user error : {e}')


def push_to_admins(org_id: int, title: str, body: str, url: str = '/dashboard', tag: str = 'syndicpro'):
    """Envoie une push notification à tous les admins d'une organisation."""
    try:
        from models import User
        for admin in User.query.filter_by(organization_id=org_id, role='admin').all():
            push_to_user(admin.id, title, body, url, tag)
    except Exception as e:
        print(f'[Push] push_to_admins error : {e}')
