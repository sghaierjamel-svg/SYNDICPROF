from flask import render_template, request, redirect, url_for, flash
from core import app, db
from models import Announcement, AnnouncementRead, User, Apartment
from utils import current_user, current_organization, login_required, admin_required, subscription_required
from utils_whatsapp import notify_announcement, notify_announcement_read


@app.route('/annonces', methods=['GET', 'POST'])
@login_required
@admin_required
@subscription_required
def announcements():
    org = current_organization()

    if request.method == 'POST':
        title  = request.form.get('title', '').strip()
        body   = request.form.get('body', '').strip()
        pinned = request.form.get('pinned') == 'on'
        if not title or not body:
            flash('Titre et contenu obligatoires.', 'danger')
            return redirect(url_for('announcements'))
        a = Announcement(
            organization_id=org.id,
            title=title,
            body=body,
            pinned=pinned,
            created_by_id=current_user().id
        )
        db.session.add(a)
        db.session.commit()

        # WhatsApp à tous les résidents ayant un numéro
        residents = User.query.filter_by(organization_id=org.id, role='resident').all()
        sent = notify_announcement(org, a, residents)
        if sent > 0:
            flash(f'Annonce publiée et envoyée sur WhatsApp à {sent} résident(s).', 'success')
        else:
            flash('Annonce publiée.', 'success')
        return redirect(url_for('announcements'))

    items = Announcement.query.filter_by(organization_id=org.id)\
        .order_by(Announcement.pinned.desc(), Announcement.created_at.desc()).all()

    # Compteurs de lectures par annonce
    ann_ids = [a.id for a in items]
    read_counts = {}
    recent_reads = []
    if ann_ids:
        from sqlalchemy import func
        rows = db.session.query(
            AnnouncementRead.announcement_id,
            func.count(AnnouncementRead.id)
        ).filter(AnnouncementRead.announcement_id.in_(ann_ids))\
         .group_by(AnnouncementRead.announcement_id).all()
        read_counts = {ann_id: cnt for ann_id, cnt in rows}

        # 10 dernières lectures (notifications in-app)
        recent_reads = db.session.query(AnnouncementRead)\
            .filter(AnnouncementRead.announcement_id.in_(ann_ids))\
            .order_by(AnnouncementRead.read_at.desc()).limit(10).all()

    return render_template('announcements.html',
                           announcements=items,
                           read_counts=read_counts,
                           recent_reads=recent_reads,
                           user=current_user())


@app.route('/annonce/<int:ann_id>/lire')
@login_required
@subscription_required
def read_announcement(ann_id):
    """Le résident ouvre l'annonce → marquer comme lu + notifier l'admin."""
    user = current_user()
    org  = current_organization()
    a    = Announcement.query.filter_by(id=ann_id, organization_id=org.id).first_or_404()

    if user.role == 'resident' and user.apartment_id:
        # Enregistrer la lecture (ignore le doublon si déjà lu)
        existing = AnnouncementRead.query.filter_by(
            announcement_id=ann_id, user_id=user.id
        ).first()
        if not existing:
            read = AnnouncementRead(
                announcement_id=ann_id,
                apartment_id=user.apartment_id,
                user_id=user.id
            )
            db.session.add(read)
            db.session.commit()
            # Notifier l'admin via WhatsApp (optionnel — silencieux si non configuré)
            apt = Apartment.query.get(user.apartment_id)
            if apt:
                notify_announcement_read(org, a, apt, user)

    return render_template('announcement_detail.html', announcement=a, user=user, org=org)


@app.route('/annonce/delete/<int:ann_id>', methods=['POST'])
@login_required
@admin_required
@subscription_required
def delete_announcement(ann_id):
    org = current_organization()
    a = Announcement.query.filter_by(id=ann_id, organization_id=org.id).first_or_404()
    db.session.delete(a)
    db.session.commit()
    flash('Annonce supprimée.', 'success')
    return redirect(url_for('announcements'))


@app.route('/annonce/pin/<int:ann_id>', methods=['POST'])
@login_required
@admin_required
@subscription_required
def toggle_pin(ann_id):
    org = current_organization()
    a = Announcement.query.filter_by(id=ann_id, organization_id=org.id).first_or_404()
    a.pinned = not a.pinned
    db.session.commit()
    return redirect(url_for('announcements'))
