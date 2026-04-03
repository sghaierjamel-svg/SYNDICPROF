"""
Service WhatsApp via fonnte.com
API doc : https://fonnte.com/docs/

Pour configurer :
1. Créer un compte sur fonnte.com
2. Connecter votre numéro WhatsApp
3. Copier le token dans Paramètres > WhatsApp
"""
import requests as http


def _normalize_phone(phone: str) -> str:
    """Normalise un numéro tunisien au format international sans le +."""
    p = phone.strip().replace(' ', '').replace('-', '').replace('.', '')
    if p.startswith('+'):
        p = p[1:]
    if p.startswith('00'):
        p = p[2:]
    if len(p) == 8:           # numéro local sans indicatif
        p = '216' + p
    return p


def send_whatsapp(org, phone: str, message: str) -> bool:
    """
    Envoie un message WhatsApp à `phone` via le compte fonnte de l'organisation.
    Retourne True si l'envoi a réussi, False sinon (silencieux — ne bloque pas l'app).
    """
    if not org.whatsapp_enabled or not org.whatsapp_token or not phone:
        return False

    target = _normalize_phone(phone)
    if not target:
        return False

    try:
        resp = http.post(
            'https://api.fonnte.com/send',
            headers={'Authorization': org.whatsapp_token},
            data={
                'target': target,
                'message': message,
                'countryCode': '216',
            },
            timeout=10
        )
        # Fonnte retourne toujours HTTP 200, même en cas d'erreur.
        # Le vrai résultat est dans le JSON : {"status": true/false}
        try:
            body = resp.json()
            return bool(body.get('status', False))
        except Exception:
            return resp.status_code == 200
    except Exception:
        return False


def send_whatsapp_debug(org, phone: str, message: str) -> dict:
    """
    Identique à send_whatsapp() mais retourne le détail complet pour diagnostic.
    Utilisé uniquement par la route /settings/test-whatsapp.
    """
    if not org.whatsapp_token:
        return {'ok': False, 'reason': 'Token Fonnte manquant dans les paramètres.'}
    if not org.whatsapp_enabled:
        return {'ok': False, 'reason': 'WhatsApp désactivé — cochez "Activer WhatsApp" et sauvegardez.'}
    if not phone:
        return {'ok': False, 'reason': 'Numéro de téléphone admin manquant.'}

    target = _normalize_phone(phone)
    try:
        resp = http.post(
            'https://api.fonnte.com/send',
            headers={'Authorization': org.whatsapp_token},
            data={
                'target': target,
                'message': message,
                'countryCode': '216',
            },
            timeout=10
        )
        try:
            body = resp.json()
        except Exception:
            body = {'raw': resp.text}

        ok = bool(body.get('status', False))
        reason = body.get('message') or body.get('reason') or body.get('detail') or str(body)
        return {'ok': ok, 'reason': reason, 'target': target, 'http_status': resp.status_code, 'body': body}
    except http.exceptions.ConnectionError:
        return {'ok': False, 'reason': 'Impossible de joindre api.fonnte.com — vérifiez la connexion internet du serveur.'}
    except http.exceptions.Timeout:
        return {'ok': False, 'reason': 'Timeout — api.fonnte.com ne répond pas (> 10s).'}
    except Exception as e:
        return {'ok': False, 'reason': str(e)}


def notify_payment(org, apt, month_paid: str, amount: float, resident=None):
    """Notification paiement → admin + résident (si phone disponible)."""
    apt_label = f"{apt.block.name}-{apt.number}"
    msg_admin = (
        f"✅ *SyndicPro — Paiement reçu*\n"
        f"Appartement : {apt_label}\n"
        f"Mois : {month_paid}\n"
        f"Montant : {amount:.2f} DT"
    )
    if resident:
        msg_admin += f"\nRésident : {resident.name or resident.email}"

    if org.whatsapp_admin_phone:
        send_whatsapp(org, org.whatsapp_admin_phone, msg_admin)

    if resident and resident.phone:
        msg_resident = (
            f"✅ *SyndicPro — Paiement confirmé*\n"
            f"Votre paiement de *{amount:.2f} DT* pour le mois *{month_paid}* "
            f"a bien été enregistré.\nMerci !"
        )
        send_whatsapp(org, resident.phone, msg_resident)


def notify_ticket_created(org, ticket, resident=None):
    """Notification nouveau ticket → admin."""
    apt_label = ""
    if ticket.apartment:
        apt_label = f"{ticket.apartment.block.name}-{ticket.apartment.number}"
    msg = (
        f"🎫 *SyndicPro — Nouveau ticket*\n"
        f"Appartement : {apt_label}\n"
        f"Sujet : {ticket.subject}\n"
        f"Priorité : {ticket.priority}"
    )
    if resident:
        msg += f"\nRésident : {resident.name or resident.email}"
    if org.whatsapp_admin_phone:
        send_whatsapp(org, org.whatsapp_admin_phone, msg)


def notify_ticket_response(org, ticket, resident=None):
    """Notification réponse admin → résident."""
    if not resident or not resident.phone:
        return
    msg = (
        f"📋 *SyndicPro — Réponse à votre ticket*\n"
        f"Sujet : {ticket.subject}\n"
        f"Statut : {ticket.status}\n\n"
        f"{ticket.admin_response or ''}"
    )
    send_whatsapp(org, resident.phone, msg)
