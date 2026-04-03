from flask import render_template, request, redirect, url_for, flash
from core import app, db
from models import Ticket, User
from utils import (current_user, current_organization, login_required,
                   admin_required, subscription_required)
from datetime import datetime
from utils_whatsapp import notify_ticket_created, notify_ticket_response


@app.route('/tickets', methods=['GET', 'POST'])
@login_required
@subscription_required
def tickets():
    user = current_user()
    org = current_organization()
    if request.method == 'POST':
        if not user.apartment_id:
            flash('Vous devez être affecté à un appartement', 'danger')
            return redirect(url_for('tickets'))
        # HIGH-009 : limiter la taille des champs texte
        subject  = request.form.get('subject', '').strip()[:200]
        message  = request.form.get('message', '').strip()[:5000]
        priority = request.form.get('priority', 'normale')
        if not subject or not message:
            flash('Sujet et message obligatoires.', 'danger')
            return redirect(url_for('tickets'))
        ticket = Ticket(
            organization_id=org.id,
            apartment_id=user.apartment_id,
            user_id=user.id,
            subject=subject,
            message=message,
            priority=priority
        )
        db.session.add(ticket)
        db.session.commit()
        flash('Ticket créé avec succès', 'success')
        # Notification WhatsApp → admin
        try:
            notify_ticket_created(org, ticket, resident=user)
        except Exception:
            pass
        return redirect(url_for('tickets'))
    if user.role == 'admin':
        tickets_list = Ticket.query.filter_by(organization_id=org.id).order_by(Ticket.created_at.desc()).all()
    else:
        tickets_list = Ticket.query.filter_by(apartment_id=user.apartment_id).order_by(Ticket.created_at.desc()).all()
    return render_template('tickets.html', tickets=tickets_list, user=user)


@app.route('/ticket/<int:ticket_id>', methods=['GET', 'POST'])
@login_required
@subscription_required
def ticket_detail(ticket_id):
    org = current_organization()
    ticket = Ticket.query.filter_by(id=ticket_id, organization_id=org.id).first_or_404()
    user = current_user()
    if user.role != 'admin' and ticket.apartment_id != user.apartment_id:
        flash('Accès non autorisé', 'danger')
        return redirect(url_for('tickets'))
    if request.method == 'POST' and user.role == 'admin':
        ticket.status = request.form.get('status', ticket.status)
        ticket.admin_response = request.form.get('admin_response', ticket.admin_response)
        ticket.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Ticket mis à jour', 'success')
        # Notification WhatsApp → résident si réponse fournie
        try:
            if ticket.admin_response:
                resident = User.query.get(ticket.user_id)
                notify_ticket_response(org, ticket, resident)
        except Exception:
            pass
        return redirect(url_for('ticket_detail', ticket_id=ticket_id))
    return render_template('ticket_detail.html', ticket=ticket, user=user)


@app.route('/ticket/delete/<int:ticket_id>', methods=['POST'])
@login_required
@admin_required
@subscription_required
def delete_ticket(ticket_id):
    org = current_organization()
    ticket = Ticket.query.filter_by(id=ticket_id, organization_id=org.id).first_or_404()
    db.session.delete(ticket)
    db.session.commit()
    flash('Ticket supprimé', 'success')
    return redirect(url_for('tickets'))
