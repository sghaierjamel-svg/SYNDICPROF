import base64, io
from flask import render_template, request, redirect, url_for, flash, send_file, abort
from core import app, db
from models import Litige, AutreLitige, LitigeDocument, Apartment, Intervenant
from utils import (current_user, current_organization, login_required,
                   admin_required, subscription_required, get_unpaid_months_count)
from datetime import datetime, date

SEUIL_ALERTE = 3   # mois impayés avant de proposer un litige
MAX_DOC_BYTES = 10 * 1024 * 1024   # 10 Mo
ALLOWED_MIMES = {'image/jpeg', 'image/png', 'image/webp', 'application/pdf'}

STATUS_LABELS = {
    'ouvert':    ('Ouvert',    'danger'),
    'en_cours':  ('En cours',  'warning'),
    'resolu':    ('Résolu',    'success'),
}


def _read_file(file_storage):
    """Lit un fichier uploadé, retourne (b64, mime, nom) ou lève ValueError."""
    if not file_storage or file_storage.filename == '':
        return None, None, None
    mime = file_storage.mimetype
    if mime not in ALLOWED_MIMES:
        raise ValueError('Format non accepté (JPG, PNG, PDF uniquement).')
    raw = file_storage.read()
    if len(raw) > MAX_DOC_BYTES:
        raise ValueError('Fichier trop lourd (max 10 Mo).')
    return base64.b64encode(raw).decode(), mime, file_storage.filename


def _default_letter(org, apt, unpaid_count, amount_due):
    today_str = date.today().strftime('%d/%m/%Y')
    return f"""{org.name}, le {today_str}

MISE EN DEMEURE
Envoyée en Recommandé avec Accusé de Réception

Appartement : {apt.block.name}-{apt.number}

Madame, Monsieur,

Nous avons l'honneur de vous adresser la présente lettre recommandée avec accusé de réception afin de vous informer que votre compte de charges de copropriété présente un arriéré de {unpaid_count} mois, soit un montant total de {amount_due:.3f} DT.

Malgré nos rappels amiables (courriers, SMS, WhatsApp), cette situation n'a pas été régularisée à ce jour.

En conséquence, nous vous mettons en demeure de procéder au règlement intégral de la somme de {amount_due:.3f} DT dans un délai de QUINZE (15) jours à compter de la réception de la présente.

À défaut de règlement dans ce délai, nous nous verrons contraints d'engager les voies légales pour le recouvrement forcé de cette créance, aux frais et risques du débiteur défaillant, conformément aux dispositions du Code des Obligations et des Contrats tunisien.

Veuillez agréer, Madame, Monsieur, l'expression de nos salutations distinguées.

Le Syndic de Copropriété
{org.name}
"""


# ─── Page principale ──────────────────────────────────────────────────────────

@app.route('/litiges')
@login_required
@admin_required
@subscription_required
def litiges():
    org = current_organization()

    # Appartements avec 3+ mois impayés sans litige actif
    apartments = Apartment.query.filter_by(organization_id=org.id).all()
    litiges_actifs_ids = {
        l.apartment_id for l in
        Litige.query.filter(
            Litige.organization_id == org.id,
            Litige.status != 'resolu'
        ).all()
    }
    alertes = []
    for apt in apartments:
        cnt = get_unpaid_months_count(apt.id)
        if cnt >= SEUIL_ALERTE and apt.id not in litiges_actifs_ids:
            alertes.append({'apt': apt, 'unpaid': cnt, 'due': cnt * apt.monthly_fee})

    alertes.sort(key=lambda x: x['unpaid'], reverse=True)

    # Litiges impayés
    litiges_list = (Litige.query
                    .filter_by(organization_id=org.id)
                    .order_by(Litige.opened_at.desc())
                    .all())

    # Huissiers disponibles
    huissiers = Intervenant.query.filter(
        Intervenant.organization_id == org.id,
        Intervenant.categorie == 'Huissier de justice'
    ).all()

    # Autres litiges
    autres = (AutreLitige.query
              .filter_by(organization_id=org.id)
              .order_by(AutreLitige.created_at.desc())
              .all())

    return render_template('litiges.html',
                           alertes=alertes, litiges_list=litiges_list,
                           huissiers=huissiers, autres=autres,
                           status_labels=STATUS_LABELS,
                           user=current_user())


# ─── Ouvrir un litige impayé ─────────────────────────────────────────────────

@app.route('/litiges/ouvrir', methods=['POST'])
@login_required
@admin_required
@subscription_required
def litige_ouvrir():
    org = current_organization()
    apt_id = int(request.form['apartment_id'])
    apt = Apartment.query.filter_by(id=apt_id, organization_id=org.id).first_or_404()
    # Pas de doublons
    existing = Litige.query.filter(
        Litige.apartment_id == apt_id,
        Litige.status != 'resolu'
    ).first()
    if existing:
        flash('Un litige actif existe déjà pour cet appartement.', 'warning')
        return redirect(url_for('litiges'))
    cnt = get_unpaid_months_count(apt_id)
    due = cnt * apt.monthly_fee
    letter = _default_letter(org, apt, cnt, due)
    l = Litige(
        organization_id=org.id,
        apartment_id=apt_id,
        unpaid_count=cnt,
        amount_due=due,
        letter_content=letter,
    )
    db.session.add(l)
    db.session.commit()
    flash(f'Litige ouvert pour l\'appartement {apt.block.name}-{apt.number}.', 'success')
    return redirect(url_for('litige_detail', litige_id=l.id))


# ─── Détail / édition lettre ─────────────────────────────────────────────────

@app.route('/litiges/<int:litige_id>', methods=['GET', 'POST'])
@login_required
@admin_required
@subscription_required
def litige_detail(litige_id):
    org = current_organization()
    l   = Litige.query.filter_by(id=litige_id, organization_id=org.id).first_or_404()
    huissiers = Intervenant.query.filter(
        Intervenant.organization_id == org.id,
        Intervenant.categorie == 'Huissier de justice'
    ).all()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'save_letter':
            l.letter_content = request.form.get('letter_content', '')
            if request.form.get('mark_sent'):
                l.letter_sent_at = datetime.utcnow()
            db.session.commit()
            flash('Lettre enregistrée.', 'success')

        elif action == 'assign_huissier':
            h_id = request.form.get('huissier_id')
            l.huissier_id = int(h_id) if h_id else None
            db.session.commit()
            flash('Huissier assigné.' if h_id else 'Huissier retiré.', 'success')

        elif action == 'save_notes':
            l.notes = request.form.get('notes', '')
            db.session.commit()
            flash('Notes sauvegardées.', 'success')

        elif action == 'upload_accuse':
            try:
                d, m, n = _read_file(request.files.get('accuse_file'))
                if d:
                    l.accuse_data, l.accuse_mime, l.accuse_nom = d, m, n
                    db.session.commit()
                    flash('Accusé de réception enregistré.', 'success')
            except ValueError as e:
                flash(str(e), 'warning')

        elif action == 'upload_decharge':
            try:
                d, m, n = _read_file(request.files.get('decharge_file'))
                if d:
                    l.decharge_data, l.decharge_mime, l.decharge_nom = d, m, n
                    db.session.commit()
                    flash('Décharge enregistrée.', 'success')
            except ValueError as e:
                flash(str(e), 'warning')

        elif action == 'change_status':
            new_status = request.form.get('status')
            if new_status in STATUS_LABELS:
                l.status = new_status
                db.session.commit()
                flash(f'Statut mis à jour : {STATUS_LABELS[new_status][0]}.', 'success')

        return redirect(url_for('litige_detail', litige_id=litige_id))

    current_unpaid = get_unpaid_months_count(l.apartment_id)
    return render_template('litige_detail.html',
                           l=l, huissiers=huissiers,
                           status_labels=STATUS_LABELS,
                           current_unpaid=current_unpaid,
                           user=current_user())


# ─── Téléchargement accusé / décharge ────────────────────────────────────────

@app.route('/litiges/<int:litige_id>/accuse')
@login_required
@admin_required
@subscription_required
def litige_accuse(litige_id):
    org = current_organization()
    l = Litige.query.filter_by(id=litige_id, organization_id=org.id).first_or_404()
    if not l.accuse_data:
        abort(404)
    buf = io.BytesIO(base64.b64decode(l.accuse_data))
    buf.seek(0)
    return send_file(buf, mimetype=l.accuse_mime,
                     as_attachment=request.args.get('dl') == '1',
                     download_name=l.accuse_nom or f'accuse_{litige_id}')


@app.route('/litiges/<int:litige_id>/decharge')
@login_required
@admin_required
@subscription_required
def litige_decharge(litige_id):
    org = current_organization()
    l = Litige.query.filter_by(id=litige_id, organization_id=org.id).first_or_404()
    if not l.decharge_data:
        abort(404)
    buf = io.BytesIO(base64.b64decode(l.decharge_data))
    buf.seek(0)
    return send_file(buf, mimetype=l.decharge_mime,
                     as_attachment=request.args.get('dl') == '1',
                     download_name=l.decharge_nom or f'decharge_{litige_id}')


# ─── Supprimer litige ─────────────────────────────────────────────────────────

@app.route('/litiges/<int:litige_id>/supprimer', methods=['POST'])
@login_required
@admin_required
@subscription_required
def litige_supprimer(litige_id):
    org = current_organization()
    l = Litige.query.filter_by(id=litige_id, organization_id=org.id).first_or_404()
    db.session.delete(l)
    db.session.commit()
    flash('Dossier de litige supprimé.', 'success')
    return redirect(url_for('litiges'))


# ─── Autres litiges ───────────────────────────────────────────────────────────

@app.route('/litiges/autres/nouveau', methods=['POST'])
@login_required
@admin_required
@subscription_required
def autre_litige_nouveau():
    org = current_organization()
    titre = request.form.get('titre', '').strip()[:200]
    description = request.form.get('description', '').strip()
    if not titre:
        flash('Le titre est obligatoire.', 'danger')
        return redirect(url_for('litiges') + '#autres')
    al = AutreLitige(
        organization_id=org.id,
        titre=titre,
        description=description or None,
    )
    db.session.add(al)
    db.session.commit()
    flash(f'Dossier « {titre} » créé.', 'success')
    return redirect(url_for('autre_litige_dossier', al_id=al.id))


@app.route('/litiges/autres/<int:al_id>', methods=['GET', 'POST'])
@login_required
@admin_required
@subscription_required
def autre_litige_dossier(al_id):
    org = current_organization()
    al  = AutreLitige.query.filter_by(id=al_id, organization_id=org.id).first_or_404()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'upload':
            try:
                d, m, n = _read_file(request.files.get('document'))
                nom_custom = request.form.get('doc_nom', '').strip() or n
                if d:
                    doc = LitigeDocument(litige_id=al.id, nom=nom_custom[:200], data=d, mime=m)
                    db.session.add(doc)
                    db.session.commit()
                    flash(f'Document « {nom_custom} » ajouté.', 'success')
                else:
                    flash('Aucun fichier sélectionné.', 'warning')
            except ValueError as e:
                flash(str(e), 'warning')

        elif action == 'change_status':
            new_status = request.form.get('status')
            if new_status in STATUS_LABELS:
                al.status = new_status
                db.session.commit()
                flash('Statut mis à jour.', 'success')

        elif action == 'edit_info':
            al.titre = request.form.get('titre', al.titre).strip()[:200]
            al.description = request.form.get('description', '').strip() or None
            db.session.commit()
            flash('Dossier mis à jour.', 'success')

        return redirect(url_for('autre_litige_dossier', al_id=al_id))

    return render_template('autre_litige_dossier.html',
                           al=al, status_labels=STATUS_LABELS,
                           user=current_user())


@app.route('/litiges/autres/<int:al_id>/doc/<int:doc_id>')
@login_required
@admin_required
@subscription_required
def autre_litige_doc(al_id, doc_id):
    org = current_organization()
    al  = AutreLitige.query.filter_by(id=al_id, organization_id=org.id).first_or_404()
    doc = LitigeDocument.query.filter_by(id=doc_id, litige_id=al.id).first_or_404()
    buf = io.BytesIO(base64.b64decode(doc.data))
    buf.seek(0)
    return send_file(buf, mimetype=doc.mime,
                     as_attachment=request.args.get('dl') == '1',
                     download_name=doc.nom)


@app.route('/litiges/autres/<int:al_id>/doc/<int:doc_id>/supprimer', methods=['POST'])
@login_required
@admin_required
@subscription_required
def autre_litige_doc_supprimer(al_id, doc_id):
    org = current_organization()
    al  = AutreLitige.query.filter_by(id=al_id, organization_id=org.id).first_or_404()
    doc = LitigeDocument.query.filter_by(id=doc_id, litige_id=al.id).first_or_404()
    db.session.delete(doc)
    db.session.commit()
    flash('Document supprimé.', 'success')
    return redirect(url_for('autre_litige_dossier', al_id=al_id))


@app.route('/litiges/autres/<int:al_id>/supprimer', methods=['POST'])
@login_required
@admin_required
@subscription_required
def autre_litige_supprimer(al_id):
    org = current_organization()
    al  = AutreLitige.query.filter_by(id=al_id, organization_id=org.id).first_or_404()
    db.session.delete(al)
    db.session.commit()
    flash('Dossier supprimé.', 'success')
    return redirect(url_for('litiges') + '#autres')
