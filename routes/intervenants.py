from flask import render_template, request, redirect, url_for, flash
from core import app, db
from models import Intervenant
from utils import current_user, current_organization, login_required, admin_required, subscription_required

CATEGORIES = [
    'Plombier',
    'Électricien',
    'Ascenseur / Maintenance',
    'Jardinier / Espaces verts',
    'Nettoyage',
    'Gardiennage / Sécurité',
    'Peinture / Maçonnerie',
    'Huissier de justice',
    'Notaire',
    'Avocat',
    'Autre',
]


@app.route('/intervenants', methods=['GET', 'POST'])
@login_required
@admin_required
@subscription_required
def intervenants():
    org = current_organization()

    if request.method == 'POST':
        categorie  = request.form.get('categorie', '').strip()[:60]
        nom_societe = request.form.get('nom_societe', '').strip()[:200]
        prenom     = request.form.get('prenom', '').strip()[:100]
        nom        = request.form.get('nom', '').strip()[:100]
        telephone  = request.form.get('telephone', '').strip()[:25]
        email      = request.form.get('email', '').strip()[:120]
        notes      = request.form.get('notes', '').strip()

        if not categorie:
            flash('La catégorie est obligatoire.', 'danger')
            return redirect(url_for('intervenants'))

        iv = Intervenant(
            organization_id=org.id,
            categorie=categorie,
            nom_societe=nom_societe or None,
            prenom=prenom or None,
            nom=nom or None,
            telephone=telephone or None,
            email=email or None,
            notes=notes or None,
        )
        db.session.add(iv)
        db.session.commit()
        flash('Intervenant ajouté.', 'success')
        return redirect(url_for('intervenants'))

    liste = Intervenant.query.filter_by(organization_id=org.id)\
        .order_by(Intervenant.categorie, Intervenant.nom_societe).all()

    # Regrouper par catégorie (trié)
    from collections import defaultdict
    grouped_raw = defaultdict(list)
    for iv in liste:
        grouped_raw[iv.categorie].append(iv)
    grouped = dict(sorted(grouped_raw.items()))
    total = len(liste)

    return render_template('intervenants.html',
                           grouped=grouped,
                           total=total,
                           categories=CATEGORIES,
                           user=current_user())


@app.route('/intervenants/edit/<int:iv_id>', methods=['GET', 'POST'])
@login_required
@admin_required
@subscription_required
def edit_intervenant(iv_id):
    org = current_organization()
    iv  = Intervenant.query.filter_by(id=iv_id, organization_id=org.id).first_or_404()

    if request.method == 'POST':
        iv.categorie   = request.form.get('categorie', '').strip()[:60]
        iv.nom_societe = request.form.get('nom_societe', '').strip()[:200] or None
        iv.prenom      = request.form.get('prenom', '').strip()[:100] or None
        iv.nom         = request.form.get('nom', '').strip()[:100] or None
        iv.telephone   = request.form.get('telephone', '').strip()[:25] or None
        iv.email       = request.form.get('email', '').strip()[:120] or None
        iv.notes       = request.form.get('notes', '').strip() or None
        db.session.commit()
        flash('Intervenant modifié.', 'success')
        return redirect(url_for('intervenants'))

    return render_template('edit_intervenant.html',
                           iv=iv,
                           categories=CATEGORIES,
                           user=current_user())


@app.route('/intervenants/delete/<int:iv_id>', methods=['POST'])
@login_required
@admin_required
@subscription_required
def delete_intervenant(iv_id):
    org = current_organization()
    iv  = Intervenant.query.filter_by(id=iv_id, organization_id=org.id).first_or_404()
    db.session.delete(iv)
    db.session.commit()
    flash('Intervenant supprimé.', 'success')
    return redirect(url_for('intervenants'))
