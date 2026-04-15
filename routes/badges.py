from flask import render_template, request, redirect, url_for, flash, jsonify
from core import app, db
from models import Badge, BadgeAccessLog, User, Apartment
from utils import current_user, current_organization, login_required, admin_required, subscription_required
from datetime import datetime


# ─────────────────────────────────────────────
#  Liste + création de badges
# ─────────────────────────────────────────────

@app.route('/badges', methods=['GET', 'POST'])
@login_required
@admin_required
@subscription_required
def badges():
    org = current_organization()
    residents = (User.query
                 .filter_by(organization_id=org.id, role='resident')
                 .order_by(User.name)
                 .all())

    if request.method == 'POST':
        badge_number = request.form.get('badge_number', '').strip()
        resident_id  = request.form.get('resident_id') or None
        notes        = request.form.get('notes', '').strip()

        if not badge_number:
            flash("Le numéro de badge est obligatoire.", "danger")
            return redirect(url_for('badges'))

        # Unicité du numéro au sein de l'organisation
        existing = Badge.query.filter_by(
            organization_id=org.id, badge_number=badge_number
        ).first()
        if existing:
            flash(f"Le badge {badge_number} existe déjà.", "danger")
            return redirect(url_for('badges'))

        try:
            resident_id = int(resident_id) if resident_id else None
        except ValueError:
            resident_id = None

        badge = Badge(
            organization_id=org.id,
            badge_number=badge_number,
            resident_id=resident_id,
            status='actif',
            notes=notes or None,
        )
        db.session.add(badge)
        db.session.commit()
        flash(f"Badge {badge_number} créé avec succès.", "success")
        return redirect(url_for('badges'))

    badges_list = (Badge.query
                   .filter_by(organization_id=org.id)
                   .order_by(Badge.issued_at.desc())
                   .all())

    # Statistiques rapides
    stats = {
        'total':  len(badges_list),
        'actif':  sum(1 for b in badges_list if b.status == 'actif'),
        'bloque': sum(1 for b in badges_list if b.status == 'bloqué'),
        'perdu':  sum(1 for b in badges_list if b.status == 'perdu'),
    }

    return render_template('badges.html',
                           badges=badges_list,
                           residents=residents,
                           stats=stats,
                           user=current_user())


# ─────────────────────────────────────────────
#  Changer le statut d'un badge (bloquer / activer / perdu / révoquer)
# ─────────────────────────────────────────────

@app.route('/badges/<int:badge_id>/status', methods=['POST'])
@login_required
@admin_required
@subscription_required
def badge_set_status(badge_id):
    org = current_organization()
    badge = Badge.query.filter_by(id=badge_id, organization_id=org.id).first_or_404()
    new_status = request.form.get('status', '').strip()

    allowed = {'actif', 'bloqué', 'perdu', 'révoqué'}
    if new_status not in allowed:
        flash("Statut invalide.", "danger")
        return redirect(url_for('badges'))

    badge.status = new_status
    badge.blocked_at = datetime.utcnow() if new_status != 'actif' else None
    db.session.commit()

    labels = {'actif': 'activé', 'bloqué': 'bloqué', 'perdu': 'marqué perdu', 'révoqué': 'révoqué'}
    flash(f"Badge {badge.badge_number} {labels[new_status]}.", "success")
    return redirect(url_for('badges'))


# ─────────────────────────────────────────────
#  Modifier les notes / le résident d'un badge
# ─────────────────────────────────────────────

@app.route('/badges/<int:badge_id>/edit', methods=['POST'])
@login_required
@admin_required
@subscription_required
def badge_edit(badge_id):
    org = current_organization()
    badge = Badge.query.filter_by(id=badge_id, organization_id=org.id).first_or_404()

    resident_id = request.form.get('resident_id') or None
    notes       = request.form.get('notes', '').strip()

    try:
        badge.resident_id = int(resident_id) if resident_id else None
    except ValueError:
        badge.resident_id = None

    badge.notes = notes or None
    db.session.commit()
    flash(f"Badge {badge.badge_number} mis à jour.", "success")
    return redirect(url_for('badges'))


# ─────────────────────────────────────────────
#  Supprimer un badge
# ─────────────────────────────────────────────

@app.route('/badges/<int:badge_id>/delete', methods=['POST'])
@login_required
@admin_required
@subscription_required
def badge_delete(badge_id):
    org = current_organization()
    badge = Badge.query.filter_by(id=badge_id, organization_id=org.id).first_or_404()
    num = badge.badge_number
    # Supprimer aussi les logs liés
    BadgeAccessLog.query.filter_by(badge_id=badge.id).delete()
    db.session.delete(badge)
    db.session.commit()
    flash(f"Badge {num} supprimé.", "success")
    return redirect(url_for('badges'))


# ─────────────────────────────────────────────
#  Journal des passages (BadgeAccessLog)
# ─────────────────────────────────────────────

@app.route('/badges/journal', methods=['GET', 'POST'])
@login_required
@admin_required
@subscription_required
def badge_journal():
    org = current_organization()
    badges_list = Badge.query.filter_by(organization_id=org.id).all()

    if request.method == 'POST':
        badge_number  = request.form.get('badge_number', '').strip()
        access_point  = request.form.get('access_point', '').strip()
        direction     = request.form.get('direction', 'entree')
        access_granted = request.form.get('access_granted', '1') == '1'

        if not badge_number or not access_point:
            flash("Numéro de badge et point d'accès sont obligatoires.", "danger")
            return redirect(url_for('badge_journal'))

        # Chercher si ce badge existe dans l'org
        badge_obj = Badge.query.filter_by(
            organization_id=org.id, badge_number=badge_number
        ).first()

        log = BadgeAccessLog(
            organization_id=org.id,
            badge_id=badge_obj.id if badge_obj else None,
            badge_number=badge_number,
            access_point=access_point,
            direction=direction,
            access_granted=access_granted,
        )
        db.session.add(log)
        db.session.commit()
        flash("Passage enregistré.", "success")
        return redirect(url_for('badge_journal'))

    # Filtres optionnels
    filter_badge   = request.args.get('badge', '').strip()
    filter_point   = request.args.get('point', '').strip()
    filter_granted = request.args.get('granted', '')

    query = BadgeAccessLog.query.filter_by(organization_id=org.id)
    if filter_badge:
        query = query.filter(BadgeAccessLog.badge_number.ilike(f'%{filter_badge}%'))
    if filter_point:
        query = query.filter(BadgeAccessLog.access_point.ilike(f'%{filter_point}%'))
    if filter_granted == '1':
        query = query.filter_by(access_granted=True)
    elif filter_granted == '0':
        query = query.filter_by(access_granted=False)

    logs = query.order_by(BadgeAccessLog.timestamp.desc()).limit(200).all()

    return render_template('badge_journal.html',
                           logs=logs,
                           badges=badges_list,
                           filter_badge=filter_badge,
                           filter_point=filter_point,
                           filter_granted=filter_granted,
                           user=current_user())
