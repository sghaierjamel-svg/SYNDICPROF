from flask import render_template, request, redirect, url_for, flash, send_file
import io
from core import app, db
from models import AssemblyGeneral, AGItem, AGVote, Apartment, User, AutreLitige
from utils import (current_user, current_organization, login_required,
                   admin_required, subscription_required)
from datetime import datetime
from storage_helper import upload_file as _storage_upload

STATUS_LABELS_AUTRES = {
    'ouvert':   ('Ouvert',   'danger'),
    'en_cours': ('En cours', 'warning'),
    'resolu':   ('Résolu',   'success'),
}

ALLOWED_PV_SCAN_MIMES = {'image/jpeg', 'image/png', 'image/webp', 'application/pdf'}


# ─── helpers ────────────────────────────────────────────────────────────────

def _build_votes(ag):
    item_ids = [it.id for it in ag.items]
    if not item_ids:
        return {}
    all_votes = AGVote.query.filter(AGVote.item_id.in_(item_ids)).all()
    user_ids = {v.user_id for v in all_votes}
    users_map = {u.id: u for u in User.query.filter(User.id.in_(user_ids)).all()} if user_ids else {}
    apt_ids = {v.apartment_id for v in all_votes if v.apartment_id}
    apts_map = {a.id: a for a in Apartment.query.filter(Apartment.id.in_(apt_ids)).all()} if apt_ids else {}

    result = {}
    for item in ag.items:
        iv = [v for v in all_votes if v.item_id == item.id]
        pour       = [(users_map.get(v.user_id), apts_map.get(v.apartment_id)) for v in iv if v.vote == 'pour']
        contre     = [(users_map.get(v.user_id), apts_map.get(v.apartment_id)) for v in iv if v.vote == 'contre']
        abstention = [(users_map.get(v.user_id), apts_map.get(v.apartment_id)) for v in iv if v.vote == 'abstention']
        pc, cc = len(pour), len(contre)
        res = 'ADOPTÉ' if pc > cc else ('REJETÉ' if cc > pc else 'ÉGALITÉ')
        result[item.id] = {
            'pour': pour, 'contre': contre, 'abstention': abstention,
            'pour_count': pc, 'contre_count': cc,
            'abstention_count': len(abstention),
            'total': len(iv),
            'result': res,
        }
    return result


def _user_votes(ag, user):
    item_ids = [it.id for it in ag.items]
    if not item_ids:
        return {}
    my = AGVote.query.filter(
        AGVote.item_id.in_(item_ids),
        AGVote.user_id == user.id
    ).all()
    return {v.item_id: v.vote for v in my}


# ─── Liste des assemblées ────────────────────────────────────────────────────

@app.route('/assemblees')
@login_required
@subscription_required
def assembly_list():
    org  = current_organization()
    user = current_user()
    assemblies = AssemblyGeneral.query.filter_by(organization_id=org.id)\
        .order_by(AssemblyGeneral.meeting_date.desc()).all()

    stats = {}
    for ag in assemblies:
        item_ids = [it.id for it in ag.items]
        voter_count = 0
        if item_ids:
            voter_count = db.session.query(
                db.func.count(db.func.distinct(AGVote.user_id))
            ).filter(AGVote.item_id.in_(item_ids)).scalar() or 0
        stats[ag.id] = {'nb_items': len(ag.items), 'nb_voters': voter_count}

    autres = (AutreLitige.query
              .filter_by(organization_id=org.id)
              .order_by(AutreLitige.created_at.desc())
              .all())

    return render_template('assembly_list.html',
                           assemblies=assemblies, stats=stats, user=user,
                           autres=autres, status_labels=STATUS_LABELS_AUTRES)


# ─── Nouvelle assemblée ──────────────────────────────────────────────────────

@app.route('/assemblees/nouvelle', methods=['GET', 'POST'])
@login_required
@admin_required
@subscription_required
def assembly_new():
    org  = current_organization()
    user = current_user()
    if request.method == 'POST':
        title    = request.form.get('title', '').strip()[:200]
        desc     = request.form.get('description', '').strip()
        date_str = request.form.get('meeting_date', '')
        location = request.form.get('location', '').strip()[:200]
        if not title or not date_str:
            flash('Titre et date sont obligatoires.', 'danger')
            return redirect(url_for('assembly_new'))
        try:
            meeting_date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            try:
                meeting_date = datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                flash('Format de date invalide.', 'danger')
                return redirect(url_for('assembly_new'))

        ag = AssemblyGeneral(
            organization_id=org.id,
            title=title,
            description=desc,
            meeting_date=meeting_date,
            location=location,
            status='planifiee',
            created_by_id=user.id
        )
        db.session.add(ag)
        db.session.commit()
        flash(f'Assemblée « {title} » créée.', 'success')
        return redirect(url_for('assembly_detail', ag_id=ag.id))
    return render_template('assembly_new.html', user=user)


# ─── Détail + vote ───────────────────────────────────────────────────────────

@app.route('/assemblees/<int:ag_id>')
@login_required
@subscription_required
def assembly_detail(ag_id):
    org  = current_organization()
    user = current_user()
    ag   = AssemblyGeneral.query.filter_by(id=ag_id, organization_id=org.id).first_or_404()

    votes_by_item = _build_votes(ag)
    user_voted    = _user_votes(ag, user)

    item_ids = [it.id for it in ag.items]
    voters = []
    if item_ids:
        voter_ids = {v.user_id for v in AGVote.query.filter(AGVote.item_id.in_(item_ids)).all()}
        voters = User.query.filter(User.id.in_(voter_ids)).all() if voter_ids else []

    has_voted_all = bool(user_voted) and len(user_voted) == len(ag.items)
    total_residents = User.query.filter_by(organization_id=org.id, role='resident').count()

    return render_template('assembly_detail.html',
                           ag=ag, user=user,
                           votes_by_item=votes_by_item,
                           user_voted=user_voted,
                           voters=voters,
                           has_voted_all=has_voted_all,
                           total_residents=total_residents)


# ─── Ajouter un point ────────────────────────────────────────────────────────

@app.route('/assemblees/<int:ag_id>/item/ajouter', methods=['POST'])
@login_required
@admin_required
@subscription_required
def assembly_add_item(ag_id):
    org = current_organization()
    ag  = AssemblyGeneral.query.filter_by(id=ag_id, organization_id=org.id).first_or_404()
    if ag.status == 'cloturee':
        flash("Impossible de modifier une assemblée clôturée.", 'warning')
        return redirect(url_for('assembly_detail', ag_id=ag_id))
    question = request.form.get('question', '').strip()[:500]
    if not question:
        flash('La question est obligatoire.', 'danger')
        return redirect(url_for('assembly_detail', ag_id=ag_id))
    item = AGItem(assembly_id=ag.id, question=question, order_num=len(ag.items) + 1)
    db.session.add(item)
    db.session.commit()
    flash('Point ajouté à l\'ordre du jour.', 'success')
    return redirect(url_for('assembly_detail', ag_id=ag_id))


# ─── Supprimer un point ──────────────────────────────────────────────────────

@app.route('/assemblees/<int:ag_id>/item/<int:item_id>/supprimer', methods=['POST'])
@login_required
@admin_required
@subscription_required
def assembly_delete_item(ag_id, item_id):
    org  = current_organization()
    ag   = AssemblyGeneral.query.filter_by(id=ag_id, organization_id=org.id).first_or_404()
    if ag.status == 'cloturee':
        flash("Impossible de modifier une assemblée clôturée.", 'warning')
        return redirect(url_for('assembly_detail', ag_id=ag_id))
    item = AGItem.query.filter_by(id=item_id, assembly_id=ag.id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    flash('Point supprimé.', 'success')
    return redirect(url_for('assembly_detail', ag_id=ag_id))


# ─── Ouvrir le vote ──────────────────────────────────────────────────────────

@app.route('/assemblees/<int:ag_id>/ouvrir-vote', methods=['POST'])
@login_required
@admin_required
@subscription_required
def assembly_open_vote(ag_id):
    org = current_organization()
    ag  = AssemblyGeneral.query.filter_by(id=ag_id, organization_id=org.id).first_or_404()
    if not ag.items:
        flash("Ajoutez au moins un point avant d'ouvrir le vote.", 'warning')
        return redirect(url_for('assembly_detail', ag_id=ag_id))
    ag.status = 'ouverte'
    db.session.commit()
    flash('Vote ouvert — les résidents peuvent maintenant voter en ligne.', 'success')
    return redirect(url_for('assembly_detail', ag_id=ag_id))


# ─── Clôturer l'assemblée ───────────────────────────────────────────────────

@app.route('/assemblees/<int:ag_id>/cloturer', methods=['POST'])
@login_required
@admin_required
@subscription_required
def assembly_close(ag_id):
    org = current_organization()
    ag  = AssemblyGeneral.query.filter_by(id=ag_id, organization_id=org.id).first_or_404()
    ag.status = 'cloturee'
    db.session.commit()
    flash('Assemblée clôturée — le PV est maintenant disponible.', 'success')
    return redirect(url_for('assembly_pv', ag_id=ag_id))


# ─── Rouvrir le vote ─────────────────────────────────────────────────────────

@app.route('/assemblees/<int:ag_id>/rouvrir', methods=['POST'])
@login_required
@admin_required
@subscription_required
def assembly_reopen(ag_id):
    org = current_organization()
    ag  = AssemblyGeneral.query.filter_by(id=ag_id, organization_id=org.id).first_or_404()
    ag.status = 'ouverte'
    db.session.commit()
    flash('Assemblée réouverte au vote.', 'info')
    return redirect(url_for('assembly_detail', ag_id=ag_id))


# ─── Voter ───────────────────────────────────────────────────────────────────

@app.route('/assemblees/<int:ag_id>/voter', methods=['POST'])
@login_required
@subscription_required
def assembly_vote(ag_id):
    org  = current_organization()
    user = current_user()
    ag   = AssemblyGeneral.query.filter_by(id=ag_id, organization_id=org.id).first_or_404()

    if ag.status != 'ouverte':
        flash("Le vote n'est pas ouvert pour cette assemblée.", 'danger')
        return redirect(url_for('assembly_detail', ag_id=ag_id))
    if not user.apartment_id:
        flash("Vous devez être affecté à un appartement pour voter.", 'danger')
        return redirect(url_for('assembly_detail', ag_id=ag_id))

    recorded = 0
    for item in ag.items:
        val = request.form.get(f'vote_{item.id}')
        if val not in ('pour', 'contre', 'abstention'):
            continue
        existing = AGVote.query.filter_by(item_id=item.id, user_id=user.id).first()
        if existing:
            existing.vote = val
            existing.voted_at = datetime.utcnow()
        else:
            db.session.add(AGVote(
                item_id=item.id,
                user_id=user.id,
                apartment_id=user.apartment_id,
                vote=val
            ))
        recorded += 1

    db.session.commit()
    if recorded > 0:
        flash(f'Votre vote a été enregistré ({recorded} point{"s" if recorded > 1 else ""}).', 'success')
    else:
        flash("Aucun vote envoyé — veuillez sélectionner une option par point.", 'warning')
    return redirect(url_for('assembly_detail', ag_id=ag_id))


# ─── Mettre à jour les infos PV (président, secrétaire, heures, quorum) ──────

@app.route('/assemblees/<int:ag_id>/update-infos', methods=['POST'])
@login_required
@admin_required
@subscription_required
def assembly_update_infos(ag_id):
    org = current_organization()
    ag  = AssemblyGeneral.query.filter_by(id=ag_id, organization_id=org.id).first_or_404()
    ag.president_seance  = request.form.get('president_seance', '').strip()[:150] or None
    ag.secretaire_seance = request.form.get('secretaire_seance', '').strip()[:150] or None
    ag.heure_ouverture   = request.form.get('heure_ouverture', '').strip()[:10] or None
    ag.heure_cloture     = request.form.get('heure_cloture', '').strip()[:10] or None
    try:
        ag.nb_presents     = int(request.form.get('nb_presents', '')) if request.form.get('nb_presents') else None
        ag.nb_procurations = int(request.form.get('nb_procurations', '')) if request.form.get('nb_procurations') else None
    except (ValueError, TypeError):
        pass
    db.session.commit()
    flash('Informations du PV enregistrées.', 'success')
    return redirect(url_for('assembly_pv', ag_id=ag_id))


# ─── Upload PV scanné ────────────────────────────────────────────────────────

@app.route('/assemblees/<int:ag_id>/upload-pv', methods=['POST'])
@login_required
@admin_required
@subscription_required
def assembly_upload_pv_scan(ag_id):
    org = current_organization()
    ag  = AssemblyGeneral.query.filter_by(id=ag_id, organization_id=org.id).first_or_404()
    f = request.files.get('pv_scan')
    if not f or not f.filename:
        flash('Aucun fichier sélectionné.', 'warning')
        return redirect(url_for('assembly_pv', ag_id=ag_id))
    mime = f.mimetype
    if mime not in ALLOWED_PV_SCAN_MIMES:
        flash('Format non accepté (JPG, PNG, PDF uniquement).', 'danger')
        return redirect(url_for('assembly_pv', ag_id=ag_id))
    raw = f.read()
    if len(raw) > 10 * 1024 * 1024:
        flash('Fichier trop lourd (max 10 Mo).', 'danger')
        return redirect(url_for('assembly_pv', ag_id=ag_id))
    url = _storage_upload(raw, mime, folder='pv_scans')
    if url:
        ag.pv_scan_url  = url
        ag.pv_scan_mime = mime
        db.session.commit()
        flash('PV scanné enregistré dans le dossier de l\'assemblée.', 'success')
    else:
        flash('Stockage non configuré — scan non sauvegardé.', 'warning')
    return redirect(url_for('assembly_pv', ag_id=ag_id))


# ─── PV HTML ─────────────────────────────────────────────────────────────────

@app.route('/assemblees/<int:ag_id>/pv')
@login_required
@subscription_required
def assembly_pv(ag_id):
    org  = current_organization()
    user = current_user()
    ag   = AssemblyGeneral.query.filter_by(id=ag_id, organization_id=org.id).first_or_404()

    # Résidents : PV uniquement après clôture
    if user.role == 'resident' and ag.status != 'cloturee':
        flash("Le PV est disponible après clôture de l'assemblée.", 'warning')
        return redirect(url_for('assembly_detail', ag_id=ag_id))

    votes_by_item = _build_votes(ag)

    item_ids  = [it.id for it in ag.items]
    voter_ids = set()
    if item_ids:
        voter_ids = {v.user_id for v in AGVote.query.filter(AGVote.item_id.in_(item_ids)).all()}
    voters = User.query.filter(User.id.in_(voter_ids)).all() if voter_ids else []

    total_residents = User.query.filter_by(
        organization_id=org.id, role='resident'
    ).count()

    return render_template('assembly_pv.html',
                           ag=ag, user=user, org=org,
                           votes_by_item=votes_by_item,
                           voters=voters,
                           total_residents=total_residents)


# ─── PV PDF (format légal tunisien CDR) ─────────────────────────────────────

@app.route('/assemblees/<int:ag_id>/pv.pdf')
@login_required
@subscription_required
def assembly_pv_pdf(ag_id):
    from fpdf import FPDF
    org  = current_organization()
    user = current_user()
    ag   = AssemblyGeneral.query.filter_by(id=ag_id, organization_id=org.id).first_or_404()

    if user.role == 'resident' and ag.status != 'cloturee':
        flash("Le PV PDF est disponible après clôture de l'assemblée.", 'warning')
        return redirect(url_for('assembly_detail', ag_id=ag_id))

    votes_data = _build_votes(ag)

    item_ids  = [it.id for it in ag.items]
    voter_ids = set()
    if item_ids:
        voter_ids = {v.user_id for v in AGVote.query.filter(AGVote.item_id.in_(item_ids)).all()}
    voters = User.query.filter(User.id.in_(voter_ids)).all() if voter_ids else []
    total_residents = User.query.filter_by(organization_id=org.id, role='resident').count()

    is_draft = ag.status != 'cloturee'

    def s(t):
        if not t:
            return ''
        return (str(t)
                .replace('é', 'e').replace('è', 'e').replace('ê', 'e')
                .replace('à', 'a').replace('â', 'a').replace('ô', 'o')
                .replace('û', 'u').replace('ü', 'u').replace('î', 'i')
                .replace('ï', 'i').replace('ç', 'c').replace('ù', 'u')
                .replace('—', '-').replace('–', '-')
                .replace('’', "'").replace('‘', "'")
                .replace('É', 'E').replace('À', 'A').replace('Ç', 'C')
                .replace('æ', 'ae').replace('œ', 'oe')
                .encode('latin-1', errors='replace').decode('latin-1'))

    pdf = FPDF()
    pdf.set_margins(20, 15, 20)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # ── Filigrane BROUILLON (largeur fixe 170 = A4 - marges, puis reset curseur) ──
    if is_draft:
        pdf.set_font('Helvetica', 'B', 60)
        pdf.set_text_color(220, 220, 220)
        pdf.set_xy(20, 110)
        pdf.cell(170, 20, 'BROUILLON', align='C')
        pdf.set_text_color(0, 0, 0)
        pdf.set_xy(20, 15)  # reset au coin supérieur gauche

    # ── En-tête sobre (pas de bandeau coloré) ───────────────────────────────
    pdf.set_font('Helvetica', 'B', 11)
    pdf.set_text_color(40, 40, 40)
    pdf.cell(0, 6, s('REPUBLIQUE TUNISIENNE'), ln=True, align='C')
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(0, 5, s('Code des Droits Reels — Articles 90 et suivants'), ln=True, align='C')
    pdf.ln(3)
    pdf.set_draw_color(80, 80, 80)
    pdf.set_line_width(0.8)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(5)

    # Résidence
    pdf.set_font('Helvetica', 'B', 13)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 7, s(org.name), ln=True, align='C')
    if org.address:
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(0, 5, s(org.address), ln=True, align='C')
    pdf.ln(4)

    # Titre PV
    pdf.set_font('Helvetica', 'B', 12)
    pdf.set_text_color(0, 0, 0)
    titre = "PROCES-VERBAL D'ASSEMBLEE GENERALE" + (" — BROUILLON" if is_draft else "")
    pdf.cell(0, 8, titre, ln=True, align='C')
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(0, 6, s(ag.title), ln=True, align='C')
    pdf.ln(3)
    pdf.set_line_width(0.4)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(6)

    def section_title(txt):
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_fill_color(230, 230, 230)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 7, '  ' + s(txt), ln=True, fill=True)
        pdf.ln(2)

    def info_row(label, value, bold_val=False):
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(55, 6, s(label))
        if bold_val:
            pdf.set_font('Helvetica', 'B', 9)
        else:
            pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 6, s(str(value)), ln=True)

    # ── Section 1 : Informations de séance ──────────────────────────────────
    section_title('1. INFORMATIONS DE SEANCE')
    info_row('Date :', ag.meeting_date.strftime('%d/%m/%Y'))
    info_row('Heure d\'ouverture :', ag.heure_ouverture or '___:___')
    if ag.location:
        info_row('Lieu :', ag.location)
    info_row('Convocation :', 'Conformement aux articles 90 et suivants du CDR')
    pdf.ln(3)

    # ── Section 2 : Vérification du quorum ──────────────────────────────────
    section_title('2. VERIFICATION DU QUORUM')
    nb_presents     = ag.nb_presents     if ag.nb_presents     is not None else '___'
    nb_procurations = ag.nb_procurations if ag.nb_procurations is not None else '___'
    total_coprops   = total_residents or '___'
    info_row('Coproprietaires presents :', f'{nb_presents} / {total_coprops}')
    info_row('Procurations recues :',      str(nb_procurations))
    info_row('Total represente :',
             f'{(ag.nb_presents or 0) + (ag.nb_procurations or 0)} / {total_coprops}'
             if (ag.nb_presents is not None or ag.nb_procurations is not None) else '___')

    # Quorum atteint ou non
    if ag.nb_presents is not None and total_residents > 0:
        total_rep = (ag.nb_presents or 0) + (ag.nb_procurations or 0)
        quorum_ok = total_rep >= (total_residents / 2)
        pdf.set_font('Helvetica', 'B', 9)
        if quorum_ok:
            pdf.set_text_color(0, 120, 80)
            pdf.cell(0, 6, '  -> QUORUM ATTEINT — L\'assemblee peut valablement deliberer.', ln=True)
        else:
            pdf.set_text_color(180, 60, 60)
            pdf.cell(0, 6, '  -> QUORUM NON ATTEINT — Deliberation sous reserve (2eme convocation).', ln=True)
        pdf.set_text_color(0, 0, 0)
    pdf.ln(3)

    # ── Section 3 : Bureau de séance ────────────────────────────────────────
    section_title('3. CONSTITUTION DU BUREAU DE SEANCE')
    info_row('President de seance :',
             ag.president_seance or '_________________________________ (elu par l\'assemblee)')
    info_row('Secretaire de seance :',
             ag.secretaire_seance or '_________________________________ (designe par le president)')
    pdf.ln(3)

    # ── Section 4 : Ordre du jour ────────────────────────────────────────────
    section_title('4. ORDRE DU JOUR')
    if ag.items:
        for idx, item in enumerate(ag.items, 1):
            pdf.set_font('Helvetica', 'B', 9)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(10, 6, f'{idx}.')
            pdf.set_font('Helvetica', '', 9)
            pdf.multi_cell(0, 6, s(item.question))
            pdf.ln(1)
    else:
        pdf.set_font('Helvetica', 'I', 9)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(0, 6, "L'ordre du jour sera communique lors de la seance.", ln=True)
    pdf.ln(3)

    # ── Section 5 : Délibérations ────────────────────────────────────────────
    section_title('5. DELIBERATIONS')

    if ag.items and any(votes_data.get(it.id, {}).get('total', 0) > 0 for it in ag.items):
        for idx, item in enumerate(ag.items, 1):
            data = votes_data.get(item.id, {})
            total = data.get('total', 0)
            pc    = data.get('pour_count', 0)
            cc    = data.get('contre_count', 0)
            ac    = data.get('abstention_count', 0)
            res   = data.get('result', '-')

            pdf.set_font('Helvetica', 'B', 9)
            pdf.set_text_color(0, 0, 0)
            pdf.multi_cell(0, 6, s(f'Point {idx} : {item.question}'))

            pdf.set_font('Helvetica', '', 9)
            pdf.set_text_color(60, 60, 60)
            pdf.cell(0, 5, s('Apres deliberation, l\'assemblee procede au vote :'), ln=True)

            # Résultat du vote
            pdf.set_font('Helvetica', 'B', 9)
            vote_line = f'  Pour : {pc}   |   Contre : {cc}   |   Abstention : {ac}   |   Total : {total} votants'
            pdf.cell(0, 6, s(vote_line), ln=True)

            # Décision formulée
            if res == 'ADOPTÉ':
                pdf.set_text_color(0, 120, 80)
                decision = f'  RESOLUTION ADOPTEE a la majorite ({pc} voix pour / {cc} contre).'
            elif res == 'REJETÉ':
                pdf.set_text_color(180, 60, 60)
                decision = f'  RESOLUTION REJETEE ({cc} voix contre / {pc} pour).'
            else:
                pdf.set_text_color(100, 100, 180)
                decision = f'  EGALITE DES VOIX ({pc} pour / {cc} contre) — A soumettre a nouvelle deliberation.'
            pdf.set_font('Helvetica', 'B', 9)
            pdf.cell(0, 6, s(decision), ln=True)
            pdf.set_text_color(0, 0, 0)

            pdf.set_draw_color(180, 180, 180)
            pdf.set_line_width(0.2)
            pdf.line(20, pdf.get_y() + 2, 190, pdf.get_y() + 2)
            pdf.ln(5)
    else:
        pdf.set_font('Helvetica', 'I', 9)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(0, 6, 'Les deliberations seront reportees ici apres la seance.', ln=True)
        pdf.ln(3)

    # ── Section 6 : Clôture ──────────────────────────────────────────────────
    section_title('6. CLOTURE DE SEANCE')
    pdf.set_font('Helvetica', '', 9)
    pdf.set_text_color(0, 0, 0)
    if ag.heure_cloture:
        pdf.cell(0, 6, s(f"L'ordre du jour etant epuise, la seance est levee a {ag.heure_cloture}."), ln=True)
    else:
        pdf.cell(0, 6, "L'ordre du jour etant epuise, la seance est levee a ___:___.", ln=True)
    pdf.ln(4)

    # ── Section 7 : Signatures ───────────────────────────────────────────────
    pdf.set_draw_color(80, 80, 80)
    pdf.set_line_width(0.5)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(5)
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 5, 'SIGNATURES', ln=True, align='C')
    pdf.ln(4)

    col_w = 56
    gap   = 3
    labels = [
        ('Le President de seance', ag.president_seance or ''),
        ('Le Secretaire de seance', ag.secretaire_seance or ''),
        ('Le Syndic', org.name),
    ]
    for lbl, name in labels:
        pdf.set_font('Helvetica', 'B', 8)
        pdf.set_text_color(60, 60, 60)
        pdf.cell(col_w, 5, s(lbl), align='C')
        pdf.cell(gap, 5, '')
    pdf.ln()

    for lbl, name in labels:
        pdf.set_font('Helvetica', '', 8)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(col_w, 5, s(name), align='C')
        pdf.cell(gap, 5, '')
    pdf.ln(12)

    for _, __ in labels:
        pdf.set_draw_color(120, 120, 120)
        x = pdf.get_x()
        pdf.line(x + 5, pdf.get_y(), x + col_w - 5, pdf.get_y())
        pdf.cell(col_w, 0, '')
        pdf.cell(gap, 0, '')
    pdf.ln(6)

    # ── Pied de page légal ───────────────────────────────────────────────────
    pdf.ln(4)
    pdf.set_draw_color(180, 180, 180)
    pdf.set_line_width(0.3)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(3)
    pdf.set_font('Helvetica', 'I', 7)
    pdf.set_text_color(150, 150, 150)
    statut_label = 'BROUILLON — non officiel' if is_draft else 'Document officiel'
    pdf.cell(0, 4,
             s(f'{statut_label} — Etabli le {datetime.now().strftime("%d/%m/%Y")} — SyndicPro — {org.name}'),
             ln=True, align='C')
    if not is_draft:
        pdf.cell(0, 4,
                 "Ce PV constitue le document officiel de l'assemblee generale — CDR Tunisie.",
                 ln=True, align='C')

    buf = io.BytesIO(pdf.output())
    buf.seek(0)
    prefix = 'BROUILLON_PV' if is_draft else 'PV_AG'
    filename = f"{prefix}_{ag.id}_{ag.meeting_date.strftime('%Y%m%d')}.pdf"
    return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=filename)


# ─── Convocation PDF ─────────────────────────────────────────────────────────

@app.route('/assemblees/<int:ag_id>/convocation.pdf')
@login_required
@admin_required
@subscription_required
def assembly_convocation_pdf(ag_id):
    from fpdf import FPDF
    org  = current_organization()
    ag   = AssemblyGeneral.query.filter_by(id=ag_id, organization_id=org.id).first_or_404()

    residents = User.query.filter_by(organization_id=org.id, role='resident').all()

    def s(t):
        if not t:
            return ''
        return (str(t)
                .replace('é', 'e').replace('è', 'e').replace('ê', 'e')
                .replace('à', 'a').replace('â', 'a')
                .replace('ô', 'o').replace('û', 'u').replace('ü', 'u')
                .replace('î', 'i').replace('ï', 'i').replace('ç', 'c')
                .replace('ù', 'u').replace('—', '-').replace('–', '-')
                .replace('’', "'").replace('‘', "'")
                .replace('É', 'E').replace('À', 'A').replace('Ç', 'C')
                .encode('latin-1', errors='replace').decode('latin-1'))

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)

    for resident in (residents if residents else [None]):
        pdf.add_page()

        apt = None
        apt_label = ''
        if resident and resident.apartment_id:
            apt = Apartment.query.get(resident.apartment_id)
            if apt and apt.block:
                apt_label = apt.block.name + '-' + str(apt.number)
            elif apt:
                apt_label = str(apt.number)

        pdf.set_fill_color(0, 180, 130)
        pdf.rect(0, 0, 210, 38, 'F')
        pdf.set_xy(0, 6)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font('Helvetica', 'B', 18)
        pdf.cell(0, 10, s(org.name), ln=True, align='C')
        pdf.set_font('Helvetica', '', 9)
        pdf.cell(0, 5, 'SyndicPro - Gestion de copropriete', ln=True, align='C')
        pdf.ln(2)

        pdf.set_text_color(40, 40, 40)
        pdf.set_font('Helvetica', '', 10)
        pdf.set_xy(120, 48)
        if resident:
            pdf.cell(80, 6, s(resident.name or resident.email), ln=True, align='L')
            pdf.set_x(120)
            if apt_label:
                pdf.cell(80, 6, s('Appartement ' + apt_label), ln=True, align='L')
                pdf.set_x(120)
            pdf.cell(80, 6, s(org.name), ln=True, align='L')
        else:
            pdf.cell(80, 6, '[Nom du destinataire]', ln=True, align='L')
            pdf.set_x(120)
            pdf.cell(80, 6, '[Appartement]', ln=True, align='L')

        pdf.set_xy(10, 48)
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(100, 6, 'Le ' + datetime.now().strftime('%d/%m/%Y'), ln=False)
        pdf.ln(16)

        pdf.set_x(10)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(40, 40, 40)
        pdf.cell(40, 6, 'Objet :')
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(0, 6, s('Convocation a l\'Assemblee Generale - ' + ag.title), ln=True)
        pdf.ln(1)
        pdf.set_x(10)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_text_color(180, 60, 60)
        pdf.cell(0, 5,
                 'Lettre recommandee avec accuse de reception - Art. 7 Loi 77-35 du 25 mai 1977',
                 ln=True)
        pdf.ln(5)

        pdf.set_draw_color(0, 200, 150)
        pdf.set_line_width(0.4)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)

        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(40, 40, 40)
        if resident and resident.name:
            salut = s('Madame, Monsieur ' + resident.name + ',')
        else:
            salut = 'Madame, Monsieur,'
        pdf.cell(0, 7, salut, ln=True)
        pdf.ln(2)

        intro = s('Nous avons l\'honneur de vous convoquer a l\'Assemblee Generale de la '
                  'copropriete ' + org.name + ', qui se tiendra le :')
        pdf.multi_cell(0, 6, intro)
        pdf.ln(3)

        pdf.set_fill_color(240, 250, 247)
        pdf.set_x(10)
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(0, 140, 100)
        date_str = s(ag.meeting_date.strftime('%d/%m/%Y a %H:%M'))
        pdf.cell(0, 8, date_str, ln=True, align='C', fill=True)
        if ag.location:
            pdf.set_x(10)
            pdf.set_font('Helvetica', '', 10)
            pdf.set_text_color(60, 60, 60)
            pdf.cell(0, 6, s('Lieu : ' + ag.location), ln=True, align='C')
        pdf.ln(5)

        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(0, 140, 100)
        pdf.cell(0, 8, 'ORDRE DU JOUR', ln=True)
        pdf.set_draw_color(0, 200, 150)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(3)

        if ag.items:
            for idx, item in enumerate(ag.items, 1):
                pdf.set_font('Helvetica', 'B', 9)
                pdf.set_text_color(0, 140, 100)
                pdf.set_x(10)
                pdf.cell(10, 7, str(idx) + '.')
                pdf.set_font('Helvetica', '', 10)
                pdf.set_text_color(40, 40, 40)
                pdf.multi_cell(0, 6, s(item.question))
                pdf.ln(1)
        else:
            pdf.set_font('Helvetica', 'I', 9)
            pdf.set_text_color(120, 120, 120)
            pdf.cell(0, 6, "L'ordre du jour sera communique ulterieurement.", ln=True)

        pdf.ln(3)
        pdf.set_draw_color(200, 200, 200)
        pdf.set_line_width(0.2)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(4)

        pdf.set_font('Helvetica', 'I', 8)
        pdf.set_text_color(120, 120, 120)
        pdf.multi_cell(0, 5,
            'Conformement aux dispositions du Code Civil tunisien et a la loi n 77-35 du 25 mai 1977 '
            'relative a la copropriete des immeubles, tout coproprietaire a le droit de participer '
            'a cette assemblee. En cas d\'empechement, vous pouvez vous faire representer par un '
            'autre coproprietaire muni d\'une procuration ecrite.')
        pdf.ln(4)

        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(40, 40, 40)
        pdf.cell(0, 6, 'Nous vous prions d\'agreer, Madame, Monsieur, nos salutations distinguees.', ln=True)
        pdf.ln(8)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(0, 6, s('Le Syndic de la copropriete - ' + org.name), ln=True)
        pdf.ln(2)
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(60, 6, 'Signature et cachet :', ln=False)
        pdf.ln(16)
        pdf.set_draw_color(150, 150, 150)
        pdf.set_line_width(0.3)
        pdf.line(10, pdf.get_y(), 80, pdf.get_y())
        pdf.ln(8)

        pdf.set_draw_color(0, 200, 150)
        pdf.set_line_width(0.5)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(3)
        pdf.set_font('Helvetica', 'B', 8)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(0, 5, 'ACCUSE DE RECEPTION - A retourner signe au syndic', ln=True, align='C')
        pdf.ln(2)
        pdf.set_font('Helvetica', '', 8)
        ag_date = ag.meeting_date.strftime('%d/%m/%Y')
        if resident:
            apt_part = (' - Appartement ' + apt_label) if apt_label else ''
            ligne = s('Je soussigne(e) _______________________________' + apt_part
                      + ', accuse reception de la convocation a l\'AG du '
                      + ag_date + ' - ' + ag.title + '.')
        else:
            ligne = s('Je soussigne(e) _______________________________, accuse reception de '
                      'la convocation a l\'AG du ' + ag_date + ' - ' + ag.title + '.')
        pdf.multi_cell(0, 5, ligne, align='C')
        pdf.ln(3)
        pdf.cell(90, 5, 'Date : _____________________', ln=False)
        pdf.cell(0, 5, 'Signature : _______________________', ln=True)

        pdf.ln(3)
        pdf.set_font('Helvetica', 'I', 7)
        pdf.set_text_color(180, 180, 180)
        pdf.cell(0, 4,
                 s('Document genere le ' + datetime.now().strftime('%d/%m/%Y')
                   + ' par SyndicPro - ' + org.name),
                 ln=True, align='C')

    buf = io.BytesIO(pdf.output())
    buf.seek(0)
    filename = 'Convocation_AG_' + str(ag.id) + '_' + ag.meeting_date.strftime('%Y%m%d') + '.pdf'
    return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=filename)


# ─── Supprimer une AG ────────────────────────────────────────────────────────

@app.route('/assemblees/<int:ag_id>/supprimer', methods=['POST'])
@login_required
@admin_required
@subscription_required
def assembly_delete(ag_id):
    org = current_organization()
    ag  = AssemblyGeneral.query.filter_by(id=ag_id, organization_id=org.id).first_or_404()
    db.session.delete(ag)
    db.session.commit()
    flash('Assemblée supprimée.', 'success')
    return redirect(url_for('assembly_list'))
