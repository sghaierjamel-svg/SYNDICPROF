"""
Messagerie directe admin ↔ résident (par appartement)
"""
from flask import render_template, request, redirect, url_for, flash, jsonify
from core import app, db
from models import DirectMessage, Apartment, User, Block
from utils import (current_user, current_organization, login_required,
                   admin_required, subscription_required)
from utils_push import push_to_user, push_to_admins
from utils_whatsapp import send_whatsapp
from datetime import datetime


# ─── Vue admin : liste des fils de conversation ──────────────────────────────

@app.route('/messagerie')
@login_required
@subscription_required
def messagerie():
    org  = current_organization()
    user = current_user()

    if user.role == 'admin':
        # Tous les appartements qui ont au moins 1 message, triés par dernier message
        apts = (
            db.session.query(Apartment)
            .join(DirectMessage, DirectMessage.apartment_id == Apartment.id)
            .filter(DirectMessage.organization_id == org.id)
            .distinct()
            .all()
        )
        # Pour chaque appartement : dernier message + nombre non-lus
        fils = []
        for apt in apts:
            last_msg = (DirectMessage.query
                        .filter_by(organization_id=org.id, apartment_id=apt.id)
                        .order_by(DirectMessage.created_at.desc())
                        .first())
            unread = (DirectMessage.query
                      .filter_by(organization_id=org.id, apartment_id=apt.id)
                      .filter(DirectMessage.read_at.is_(None))
                      .filter(DirectMessage.sender_id != user.id)
                      .count())
            resident = apt.residents[0] if apt.residents else None
            fils.append({
                'apt': apt,
                'resident': resident,
                'last_msg': last_msg,
                'unread': unread,
            })
        # Trier par dernier message (plus récent en premier)
        fils.sort(key=lambda x: x['last_msg'].created_at if x['last_msg'] else datetime.min, reverse=True)

        # Appartements sans messages pour démarrer une conversation
        apt_ids_with_msgs = {f['apt'].id for f in fils}
        all_apts = Apartment.query.filter_by(organization_id=org.id).all()
        apts_sans_msg = [a for a in all_apts if a.id not in apt_ids_with_msgs]

        return render_template('messagerie.html', fils=fils, apts_sans_msg=apts_sans_msg, user=user)

    else:
        # Résident → redirige vers son propre fil
        if not user.apartment_id:
            flash('Votre compte n\'est pas associé à un appartement.', 'warning')
            return redirect(url_for('residents_menu'))
        return redirect(url_for('messagerie_fil', apt_id=user.apartment_id))


# ─── Fil de conversation pour un appartement ────────────────────────────────

@app.route('/messagerie/<int:apt_id>', methods=['GET', 'POST'])
@login_required
@subscription_required
def messagerie_fil(apt_id):
    org  = current_organization()
    user = current_user()
    apt  = Apartment.query.filter_by(id=apt_id, organization_id=org.id).first_or_404()

    # Sécurité : résident ne peut voir que son propre fil
    if user.role == 'resident' and apt.id != user.apartment_id:
        flash('Accès non autorisé.', 'danger')
        return redirect(url_for('residents_menu'))

    if request.method == 'POST':
        body = request.form.get('body', '').strip()
        if not body:
            flash('Le message ne peut pas être vide.', 'warning')
            return redirect(url_for('messagerie_fil', apt_id=apt_id))
        if len(body) > 2000:
            flash('Message trop long (max 2000 caractères).', 'warning')
            return redirect(url_for('messagerie_fil', apt_id=apt_id))

        msg = DirectMessage(
            organization_id=org.id,
            apartment_id=apt.id,
            sender_id=user.id,
            body=body,
            created_at=datetime.utcnow(),
        )
        db.session.add(msg)
        db.session.commit()

        # Notifications
        resident = apt.residents[0] if apt.residents else None
        apt_label = f"{apt.block.name}-{apt.number}"

        if user.role == 'admin':
            # Notif push au résident
            if resident:
                push_to_user(
                    resident.id,
                    title=f"💬 Message de votre syndic",
                    body=f"{body[:100]}{'…' if len(body) > 100 else ''}",
                    url=f"/messagerie/{apt.id}",
                    tag=f"msg-{apt.id}",
                )
                # WhatsApp si disponible
                if resident.phone and org.whatsapp_token:
                    wa_msg = (
                        f"📩 *Message de votre syndic — {org.name}*\n\n"
                        f"{body}\n\n"
                        f"Répondre : {request.host_url}messagerie/{apt.id}"
                    )
                    send_whatsapp(org, resident.phone, wa_msg)
        else:
            # Notif push aux admins
            push_to_admins(
                org.id,
                title=f"💬 Message — Apt {apt_label}",
                body=f"{resident.name if resident else 'Résident'} : {body[:100]}{'…' if len(body) > 100 else ''}",
                url=f"/messagerie/{apt.id}",
                tag=f"msg-{apt.id}",
            )
            # WhatsApp admin si disponible
            if org.whatsapp_admin_phone and org.whatsapp_token:
                wa_msg = (
                    f"💬 *Message résident — Apt {apt_label}*\n"
                    f"De : {resident.name if resident else 'Résident'}\n\n"
                    f"{body}\n\n"
                    f"Répondre : {request.host_url}messagerie/{apt.id}"
                )
                send_whatsapp(org, org.whatsapp_admin_phone, wa_msg)

        return redirect(url_for('messagerie_fil', apt_id=apt_id))

    # Marquer les messages de l'autre partie comme lus
    unread = (DirectMessage.query
              .filter_by(organization_id=org.id, apartment_id=apt.id)
              .filter(DirectMessage.read_at.is_(None))
              .filter(DirectMessage.sender_id != user.id)
              .all())
    for m in unread:
        m.read_at = datetime.utcnow()
    if unread:
        db.session.commit()

    messages = (DirectMessage.query
                .filter_by(organization_id=org.id, apartment_id=apt.id)
                .order_by(DirectMessage.created_at.asc())
                .all())

    resident = apt.residents[0] if apt.residents else None
    return render_template('messagerie_fil.html',
                           apt=apt, messages=messages,
                           resident=resident, user=user)


# ─── API : nombre de messages non-lus (pour badge topbar) ───────────────────

@app.route('/api/messagerie/unread-count')
@login_required
def api_messagerie_unread():
    org  = current_organization()
    user = current_user()
    count = (DirectMessage.query
             .filter_by(organization_id=org.id)
             .filter(DirectMessage.read_at.is_(None))
             .filter(DirectMessage.sender_id != user.id)
             .count())
    return jsonify({'count': count})


# ─── Supprimer un message (admin uniquement) ─────────────────────────────────

@app.route('/messagerie/msg/<int:msg_id>/delete', methods=['POST'])
@login_required
@admin_required
@subscription_required
def messagerie_delete_msg(msg_id):
    org  = current_organization()
    msg  = DirectMessage.query.filter_by(id=msg_id, organization_id=org.id).first_or_404()
    apt_id = msg.apartment_id
    db.session.delete(msg)
    db.session.commit()
    return redirect(url_for('messagerie_fil', apt_id=apt_id))
