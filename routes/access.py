from flask import render_template, request, redirect, url_for, flash
from core import app, db
from models import Apartment, AccessLog
from utils import current_user, current_organization, login_required, admin_required, subscription_required
from datetime import datetime


@app.route('/access', methods=['GET', 'POST'])
@login_required
@admin_required
@subscription_required
def access_log():
    org = current_organization()
    apartments = Apartment.query.filter_by(organization_id=org.id).all()

    if request.method == 'POST':
        visitor_name = request.form.get('visitor_name', '').strip()
        apt_id = request.form.get('apartment_id') or None
        direction = request.form.get('direction', 'entree')
        reason = request.form.get('reason', '').strip()

        if not visitor_name:
            flash("Le nom du visiteur est obligatoire.", "danger")
            return redirect(url_for('access_log'))

        try:
            apt_id = int(apt_id) if apt_id else None
        except ValueError:
            apt_id = None

        u = current_user()
        entry = AccessLog(
            organization_id=org.id,
            visitor_name=visitor_name,
            apartment_id=apt_id,
            direction=direction,
            reason=reason or None,
            logged_by=u.name or u.email
        )
        db.session.add(entry)
        db.session.commit()
        direction_label = "Entrée" if direction == 'entree' else "Sortie"
        flash(f"{direction_label} enregistrée pour {visitor_name}.", "success")
        return redirect(url_for('access_log'))

    logs = (AccessLog.query
            .filter_by(organization_id=org.id)
            .order_by(AccessLog.logged_at.desc())
            .limit(100)
            .all())
    return render_template('access_log.html', logs=logs, apartments=apartments, user=current_user())


@app.route('/access/delete/<int:entry_id>', methods=['POST'])
@login_required
@admin_required
@subscription_required
def delete_access(entry_id):
    org = current_organization()
    entry = AccessLog.query.filter_by(id=entry_id, organization_id=org.id).first_or_404()
    db.session.delete(entry)
    db.session.commit()
    flash("Entrée supprimée.", "success")
    return redirect(url_for('access_log'))
