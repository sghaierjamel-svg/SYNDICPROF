from flask import render_template, request, redirect, url_for, flash
from core import app, db
from models import Announcement
from utils import current_user, current_organization, login_required, admin_required, subscription_required


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
        flash('Annonce publiée.', 'success')
        return redirect(url_for('announcements'))

    items = Announcement.query.filter_by(organization_id=org.id)\
        .order_by(Announcement.pinned.desc(), Announcement.created_at.desc()).all()
    return render_template('announcements.html', announcements=items, user=current_user())


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
