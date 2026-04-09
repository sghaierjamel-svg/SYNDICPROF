from flask import request, jsonify
from core import app, db
from models import PushSubscription
from utils import current_user, login_required
from utils_push import VAPID_PUBLIC_KEY


@app.route('/api/push/vapid-key')
def push_vapid_key():
    return jsonify({'key': VAPID_PUBLIC_KEY})


@app.route('/api/push/subscribe', methods=['POST'])
@login_required
def push_subscribe():
    user = current_user()
    data = request.get_json(silent=True) or {}
    endpoint = data.get('endpoint', '').strip()
    p256dh   = (data.get('keys') or {}).get('p256dh', '').strip()
    auth     = (data.get('keys') or {}).get('auth', '').strip()
    if not endpoint or not p256dh or not auth:
        return jsonify({'ok': False, 'error': 'Données manquantes'}), 400
    # Éviter les doublons sur (user_id, endpoint)
    sub = PushSubscription.query.filter_by(user_id=user.id, endpoint=endpoint).first()
    if sub:
        sub.p256dh = p256dh
        sub.auth   = auth
    else:
        sub = PushSubscription(
            user_id=user.id,
            organization_id=user.organization_id,
            endpoint=endpoint,
            p256dh=p256dh,
            auth=auth,
        )
        db.session.add(sub)
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/push/unsubscribe', methods=['POST'])
@login_required
def push_unsubscribe():
    user = current_user()
    data = request.get_json(silent=True) or {}
    endpoint = data.get('endpoint', '')
    if endpoint:
        PushSubscription.query.filter_by(user_id=user.id, endpoint=endpoint).delete()
        db.session.commit()
    return jsonify({'ok': True})
