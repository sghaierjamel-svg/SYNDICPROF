"""
Service d'envoi d'emails via Zoho Mail (SMTP).

Variables d'environnement requises sur Render :
  ZOHO_SMTP_PASSWORD  — mot de passe (ou App Password) de contact@syndicpro.tn

Usage :
  from utils_email import send_welcome_admin, send_resident_credentials
"""

import smtplib, ssl, os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SMTP_HOST   = 'smtp.zoho.com'
SMTP_PORT   = 587
SMTP_USER   = 'contact@syndicpro.tn'
SMTP_PASS   = os.environ.get('ZOHO_SMTP_PASSWORD', '')
SITE_URL    = 'https://www.syndicpro.tn'


# ─── Envoi générique ─────────────────────────────────────────────────────────

def send_email(to: str, subject: str, html: str) -> bool:
    """
    Envoie un email HTML via Zoho SMTP.
    Retourne True si succès, False si échec (log dans la console).
    Ne lève jamais d'exception pour ne pas bloquer le flux principal.
    """
    if not SMTP_PASS:
        print("[Email] ZOHO_SMTP_PASSWORD non défini — email non envoyé.")
        return False
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From']    = f'SyndicPro <{SMTP_USER}>'
        msg['To']      = to
        msg['Reply-To'] = SMTP_USER
        msg.attach(MIMEText(html, 'html', 'utf-8'))

        ctx = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls(context=ctx)
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, to, msg.as_string())
        print(f"[Email] Envoyé à {to} — {subject}")
        return True
    except Exception as e:
        print(f"[Email] ERREUR envoi à {to} : {e}")
        return False


# ─── Templates HTML ───────────────────────────────────────────────────────────

def _base_html(content: str, footer_note: str = '') -> str:
    """Enveloppe HTML commune pour tous les emails."""
    return f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SyndicPro</title></head>
<body style="margin:0;padding:0;background:#F3F4F6;font-family:'Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F3F4F6;padding:30px 0;">
  <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0"
           style="background:#ffffff;border-radius:16px;overflow:hidden;
                  box-shadow:0 4px 24px rgba(0,0,0,.08);max-width:600px;width:100%;">

      <!-- Header -->
      <tr>
        <td style="background:linear-gradient(135deg,#1E3A8A,#1E40AF);padding:32px 40px;text-align:center;">
          <div style="font-size:26px;font-weight:800;color:#ffffff;letter-spacing:-0.5px;">SyndicPro</div>
          <div style="font-size:12px;color:rgba(255,255,255,.65);margin-top:4px;">Gestion de syndic intelligente</div>
        </td>
      </tr>

      <!-- Corps -->
      <tr>
        <td style="padding:36px 40px;">
          {content}
        </td>
      </tr>

      <!-- Footer -->
      <tr>
        <td style="background:#F9FAFB;padding:20px 40px;border-top:1px solid #E5E7EB;text-align:center;">
          <p style="margin:0;font-size:11px;color:#9CA3AF;">
            SyndicPro — <a href="{SITE_URL}" style="color:#1D4ED8;text-decoration:none;">{SITE_URL}</a><br>
            <a href="mailto:contact@syndicpro.tn" style="color:#9CA3AF;">contact@syndicpro.tn</a>
          </p>
          {f'<p style="margin:8px 0 0;font-size:10px;color:#D1D5DB;">{footer_note}</p>' if footer_note else ''}
        </td>
      </tr>

    </table>
  </td></tr>
</table>
</body></html>"""


def _btn(url: str, label: str, color: str = '#1D4ED8') -> str:
    return f"""
<div style="text-align:center;margin:28px 0;">
  <a href="{url}" style="background:{color};color:#ffffff;text-decoration:none;
     padding:13px 32px;border-radius:8px;font-size:15px;font-weight:600;
     display:inline-block;letter-spacing:.3px;">{label}</a>
</div>"""


def _info_box(rows: list) -> str:
    """Tableau info-box gris pour afficher des données (label: valeur)."""
    items = ''.join(
        f'<tr><td style="padding:8px 12px;color:#6B7280;font-size:13px;width:40%;'
        f'border-bottom:1px solid #F3F4F6;">{label}</td>'
        f'<td style="padding:8px 12px;font-size:13px;font-weight:600;color:#111827;'
        f'border-bottom:1px solid #F3F4F6;">{value}</td></tr>'
        for label, value in rows
    )
    return f"""
<table width="100%" cellpadding="0" cellspacing="0"
       style="background:#F9FAFB;border:1px solid #E5E7EB;border-radius:10px;
              overflow:hidden;margin:20px 0;">
  {items}
</table>"""


# ─── Email 1 : Bienvenue admin (nouvelle inscription) ────────────────────────

def send_welcome_admin(org_name: str, email: str, days_trial: int = 30) -> bool:
    subject = f"Bienvenue sur SyndicPro — votre essai de {days_trial} jours commence !"
    content = f"""
<h2 style="margin:0 0 8px;font-size:22px;color:#111827;">Bienvenue, {org_name} !</h2>
<p style="margin:0 0 20px;font-size:15px;color:#374151;line-height:1.6;">
  Votre compte SyndicPro est prêt. Vous disposez d'un essai gratuit de
  <strong>{days_trial} jours</strong> pour configurer et tester toutes les fonctionnalités.
</p>

{_info_box([
    ('Email de connexion', email),
    ('Durée de l\'essai', f'{days_trial} jours gratuits'),
    ('Lien de connexion', f'<a href="{SITE_URL}/login" style="color:#1D4ED8;">{SITE_URL}/login</a>'),
])}

<p style="font-size:14px;color:#374151;line-height:1.7;margin:16px 0 8px;">
  <strong>Pour démarrer rapidement :</strong>
</p>
<ol style="margin:0;padding-left:20px;font-size:14px;color:#374151;line-height:2;">
  <li>Connectez-vous et suivez le <strong>guide de démarrage</strong> sur le tableau de bord</li>
  <li>Importez vos appartements et résidents via <strong>Excel</strong> (sidebar → Import Excel)</li>
  <li>Configurez vos paramètres de paiement (Konnect ou Flouci)</li>
</ol>

{_btn(f'{SITE_URL}/login', 'Accéder à mon tableau de bord')}

<p style="font-size:13px;color:#6B7280;margin:16px 0 0;line-height:1.6;">
  Une question ? Répondez à cet email ou écrivez à
  <a href="mailto:contact@syndicpro.tn" style="color:#1D4ED8;">contact@syndicpro.tn</a>.
  Nous répondons en moins de 24h.
</p>"""

    return send_email(
        to=email,
        subject=subject,
        html=_base_html(content,
                        footer_note='Vous recevez cet email car vous venez de créer un compte SyndicPro.')
    )


# ─── Email 2 : Identifiants résident ─────────────────────────────────────────

def send_resident_credentials(org_name: str, resident_name: str, email: str,
                               password_temp: str, apt_label: str = '') -> bool:
    subject = f"Votre accès SyndicPro — {org_name}"
    apt_line = f"<tr><td style='padding:8px 12px;color:#6B7280;font-size:13px;width:40%;border-bottom:1px solid #F3F4F6;'>Appartement</td><td style='padding:8px 12px;font-size:13px;font-weight:600;color:#111827;border-bottom:1px solid #F3F4F6;'>{apt_label}</td></tr>" if apt_label else ''

    content = f"""
<h2 style="margin:0 0 8px;font-size:22px;color:#111827;">Bonjour {resident_name} !</h2>
<p style="margin:0 0 20px;font-size:15px;color:#374151;line-height:1.6;">
  La résidence <strong>{org_name}</strong> utilise SyndicPro pour la gestion des charges et des services.
  Voici vos identifiants pour accéder à votre espace résident.
</p>

<table width="100%" cellpadding="0" cellspacing="0"
       style="background:#F9FAFB;border:1px solid #E5E7EB;border-radius:10px;overflow:hidden;margin:20px 0;">
  {''.join([
    f'<tr><td style="padding:8px 12px;color:#6B7280;font-size:13px;width:40%;border-bottom:1px solid #F3F4F6;">Résidence</td><td style="padding:8px 12px;font-size:13px;font-weight:600;color:#111827;border-bottom:1px solid #F3F4F6;">{org_name}</td></tr>',
    apt_line,
    f'<tr><td style="padding:8px 12px;color:#6B7280;font-size:13px;width:40%;border-bottom:1px solid #F3F4F6;">Email</td><td style="padding:8px 12px;font-size:13px;font-weight:600;color:#111827;border-bottom:1px solid #F3F4F6;">{email}</td></tr>',
    f'<tr><td style="padding:8px 12px;color:#6B7280;font-size:13px;width:40%;">Mot de passe temporaire</td><td style="padding:8px 12px;font-size:13px;font-weight:700;color:#1D4ED8;font-family:monospace;letter-spacing:1px;">{password_temp}</td></tr>',
  ])}
</table>

<div style="background:#FEF3C7;border:1px solid #FDE68A;border-radius:8px;padding:12px 16px;margin:16px 0;">
  <p style="margin:0;font-size:13px;color:#92400E;">
    <strong>Important :</strong> Changez votre mot de passe dès la premiere connexion
    (Mon compte &rsaquo; Changer mon mot de passe).
  </p>
</div>

<p style="font-size:14px;color:#374151;line-height:1.7;margin:16px 0 8px;">
  <strong>Depuis votre espace, vous pouvez :</strong>
</p>
<ul style="margin:0;padding-left:20px;font-size:14px;color:#374151;line-height:2;">
  <li>Consulter vos charges et l'historique des paiements</li>
  <li>Payer en ligne vos charges (si disponible)</li>
  <li>Ouvrir un ticket de maintenance</li>
  <li>Consulter les annonces de votre syndic</li>
</ul>

{_btn(f'{SITE_URL}/login', 'Accéder à mon espace résident', '#059669')}

<p style="font-size:13px;color:#6B7280;margin:16px 0 0;line-height:1.6;">
  Pour toute question, contactez votre syndic ou écrivez à
  <a href="mailto:contact@syndicpro.tn" style="color:#1D4ED8;">contact@syndicpro.tn</a>.
</p>"""

    return send_email(
        to=email,
        subject=subject,
        html=_base_html(content,
                        footer_note=f'Vous recevez cet email car un compte a été créé pour vous sur SyndicPro par {org_name}.')
    )


# ─── Email 3 : Rappel abonnement (bientôt expiré) ────────────────────────────

def send_subscription_reminder(org_name: str, email: str, days_left: int) -> bool:
    urgency = 'danger' if days_left <= 3 else 'warning'
    color   = '#DC2626' if urgency == 'danger' else '#D97706'
    subject = f"{'⚠️ URGENT — ' if urgency == 'danger' else ''}Votre abonnement SyndicPro expire dans {days_left} jour{'s' if days_left > 1 else ''}"

    content = f"""
<h2 style="margin:0 0 8px;font-size:22px;color:{color};">
  {'Votre abonnement expire demain !' if days_left <= 1 else f'Plus que {days_left} jours'}
</h2>
<p style="margin:0 0 20px;font-size:15px;color:#374151;line-height:1.6;">
  L'abonnement SyndicPro de <strong>{org_name}</strong> expire dans
  <strong>{days_left} jour{'s' if days_left > 1 else ''}</strong>.
  Renouvelez maintenant pour éviter toute interruption de service.
</p>

<div style="background:#FEF2F2;border:1px solid #FECACA;border-radius:8px;padding:14px 18px;margin:16px 0;">
  <p style="margin:0;font-size:14px;color:#991B1B;line-height:1.6;">
    <strong>Sans renouvellement :</strong> vos résidents ne pourront plus accéder à leur espace
    et les paiements en ligne seront suspendus.
  </p>
</div>

{_btn(f'{SITE_URL}/subscription', 'Renouveler mon abonnement', color)}

<p style="font-size:13px;color:#6B7280;margin:16px 0 0;">
  Pour renouveler ou pour toute question, contactez-nous à
  <a href="mailto:contact@syndicpro.tn" style="color:#1D4ED8;">contact@syndicpro.tn</a>.
</p>"""

    return send_email(to=email, subject=subject, html=_base_html(content))
