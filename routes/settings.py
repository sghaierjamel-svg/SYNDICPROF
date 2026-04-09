from flask import render_template, request, redirect, url_for, flash, jsonify
from core import app, db
from models import Organization, Camera
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

        if section == 'residence':
            org.name    = request.form.get('name', '').strip() or org.name
            org.address = request.form.get('address', '').strip()
            org.phone   = request.form.get('phone', '').strip()
            db.session.commit()
            flash('Informations de la résidence enregistrées.', 'success')

        elif section == 'konnect':
            org.konnect_api_key = request.form.get('konnect_api_key', '').strip()
            org.konnect_wallet_id = request.form.get('konnect_wallet_id', '').strip()
            db.session.commit()
            flash('Paramètres Konnect enregistrés.', 'success')

        elif section == 'flouci':
            org.flouci_app_token = request.form.get('flouci_app_token', '').strip()
            org.flouci_app_secret = request.form.get('flouci_app_secret', '').strip()
            db.session.commit()
            flash('Paramètres Flouci enregistrés.', 'success')

        elif section == 'whatsapp':
            org.whatsapp_enabled = request.form.get('whatsapp_enabled') == 'on'
            org.whatsapp_admin_phone = request.form.get('whatsapp_admin_phone', '').strip()
            org.whatsapp_token = request.form.get('whatsapp_token', '').strip()
            db.session.commit()
            flash('Paramètres WhatsApp enregistrés.', 'success')

        return redirect(url_for('settings'))

    cameras = Camera.query.filter_by(organization_id=org.id).order_by(Camera.created_at.asc()).all()
    return render_template('settings.html', user=current_user(), org=org, cameras=cameras)


@app.route('/settings/test-whatsapp')
@login_required
@admin_required
def test_whatsapp():
    org = current_organization()
    from utils_whatsapp import send_whatsapp_debug
    result = send_whatsapp_debug(
        org,
        org.whatsapp_admin_phone or '',
        'Test SyndicPro - WhatsApp connecte avec succes !'
    )
    if result['ok']:
        return jsonify({'ok': True, 'message': 'Message de test envoyé ✅'})
    # Retourner l'erreur exacte de Fonnte pour aider au diagnostic
    return jsonify({'ok': False, 'message': f"Échec : {result['reason']}"})


@app.route('/settings/test-flouci')
@login_required
@admin_required
def test_flouci():
    org = current_organization()
    if not org.flouci_app_token or not org.flouci_app_secret:
        return jsonify({'ok': False, 'message': 'App Token ou App Secret manquant.'})
    try:
        # Flouci n'a pas d'endpoint /me — on teste en générant un paiement de 0,001 DT
        # et on vérifie que la réponse est cohérente (pas d'erreur d'authentification)
        resp = http.post(
            'https://api.flouci.com/payment/generate',
            json={
                'app_token': org.flouci_app_token,
                'app_secret': org.flouci_app_secret,
                'amount': 1,
                'accept_card': 'true',
                'session_id': 'test-connexion',
                'success_link': 'https://www.syndicpro.tn',
                'fail_link': 'https://www.syndicpro.tn',
                'developer_tracking_id': 'test',
            },
            timeout=8
        )
        if resp.status_code in (200, 201):
            data = resp.json()
            if data.get('result', {}).get('payment_id') or data.get('result', {}).get('link'):
                return jsonify({'ok': True, 'message': 'Connexion Flouci réussie ✅'})
            return jsonify({'ok': False, 'message': f'Réponse inattendue : {data}'})
        elif resp.status_code == 401:
            return jsonify({'ok': False, 'message': 'Token ou Secret invalide.'})
        else:
            return jsonify({'ok': False, 'message': f'Erreur Flouci ({resp.status_code}).'})
    except Exception:
        return jsonify({'ok': False, 'message': 'Impossible de joindre Flouci. Vérifiez votre connexion.'})


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


# ─── Caméras de surveillance ──────────────────────────────────────────────────

@app.route('/settings/cameras/ajouter', methods=['POST'])
@login_required
@admin_required
@subscription_required
def camera_ajouter():
    org = current_organization()
    nom = request.form.get('nom', '').strip()[:100]
    if not nom:
        flash('Le nom est obligatoire.', 'danger')
        return redirect(url_for('settings') + '#cameras')
    cam = Camera(
        organization_id=org.id,
        nom=nom,
        localisation=request.form.get('localisation', '').strip()[:200] or None,
        marque=request.form.get('marque', '').strip()[:100] or None,
        url_acces=request.form.get('url_acces', '').strip()[:500] or None,
        url_snapshot=request.form.get('url_snapshot', '').strip()[:500] or None,
        identifiant=request.form.get('identifiant', '').strip()[:100] or None,
        mot_de_passe=request.form.get('mot_de_passe', '').strip()[:200] or None,
        notes=request.form.get('notes', '').strip() or None,
        actif=request.form.get('actif') == 'on',
    )
    db.session.add(cam)
    db.session.commit()
    flash(f'Caméra « {nom} » ajoutée.', 'success')
    return redirect(url_for('settings') + '#cameras')


@app.route('/settings/cameras/<int:cam_id>/modifier', methods=['POST'])
@login_required
@admin_required
@subscription_required
def camera_modifier(cam_id):
    org = current_organization()
    cam = Camera.query.filter_by(id=cam_id, organization_id=org.id).first_or_404()
    cam.nom = request.form.get('nom', cam.nom).strip()[:100]
    cam.localisation = request.form.get('localisation', '').strip()[:200] or None
    cam.marque = request.form.get('marque', '').strip()[:100] or None
    cam.url_acces = request.form.get('url_acces', '').strip()[:500] or None
    cam.url_snapshot = request.form.get('url_snapshot', '').strip()[:500] or None
    cam.identifiant = request.form.get('identifiant', '').strip()[:100] or None
    cam.mot_de_passe = request.form.get('mot_de_passe', '').strip()[:200] or None
    cam.notes = request.form.get('notes', '').strip() or None
    cam.actif = request.form.get('actif') == 'on'
    db.session.commit()
    flash(f'Caméra « {cam.nom} » mise à jour.', 'success')
    return redirect(url_for('settings') + '#cameras')


@app.route('/settings/cameras/<int:cam_id>/supprimer', methods=['POST'])
@login_required
@admin_required
@subscription_required
def camera_supprimer(cam_id):
    org = current_organization()
    cam = Camera.query.filter_by(id=cam_id, organization_id=org.id).first_or_404()
    nom = cam.nom
    db.session.delete(cam)
    db.session.commit()
    flash(f'Caméra « {nom} » supprimée.', 'success')
    return redirect(url_for('settings') + '#cameras')
