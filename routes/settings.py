from flask import render_template, request, redirect, url_for, flash, jsonify
from core import app, db
from models import Organization
from utils import current_user, current_organization, login_required, admin_required, subscription_required
import requests as http


@app.route('/settings', methods=['GET', 'POST'])
@login_required
@admin_required
@subscription_required
def settings():
    org = current_organization()
    if request.method == 'POST':
        section = request.form.get('section')

        if section == 'konnect':
            org.konnect_api_key = request.form.get('konnect_api_key', '').strip()
            org.konnect_wallet_id = request.form.get('konnect_wallet_id', '').strip()
            db.session.commit()
            flash('Paramètres Konnect enregistrés.', 'success')

        elif section == 'whatsapp':
            org.whatsapp_enabled = request.form.get('whatsapp_enabled') == 'on'
            org.whatsapp_admin_phone = request.form.get('whatsapp_admin_phone', '').strip()
            db.session.commit()
            flash('Paramètres WhatsApp enregistrés.', 'success')

        return redirect(url_for('settings'))

    return render_template('settings.html', user=current_user(), org=org)


@app.route('/settings/test-konnect')
@login_required
@admin_required
def test_konnect():
    org = current_organization()
    if not org.konnect_api_key or not org.konnect_wallet_id:
        return jsonify({'ok': False, 'message': 'Clé API ou Wallet ID manquant.'})
    try:
        resp = http.get(
            'https://api.konnect.network/api/v2/account/me',
            headers={'x-api-key': org.konnect_api_key},
            timeout=8
        )
        if resp.status_code == 200:
            return jsonify({'ok': True, 'message': 'Connexion Konnect réussie ✅'})
        elif resp.status_code == 401:
            return jsonify({'ok': False, 'message': 'Clé API invalide ou expirée.'})
        else:
            return jsonify({'ok': False, 'message': f'Erreur Konnect ({resp.status_code}).'})
    except Exception:
        return jsonify({'ok': False, 'message': 'Impossible de joindre Konnect. Vérifiez votre connexion.'})
