from flask import render_template, request, redirect, url_for, flash, send_file
import io
from core import app, db
from models import AssemblyGeneral, AGItem, AGVote, Apartment, User
from utils import (current_user, current_organization, login_required,
                   admin_required, subscription_required)
from datetime import datetime


# ─── helpers ────────────────────────────────────────────────────────────────

def _build_votes(ag):
    """Retourne {item.id: {pour, contre, abstention, total, result}} avec objets User."""
    item_ids = [it.id for it in ag.items]
    if not item_ids:
        return {}
    all_votes = AGVote.query.filter(AGVote.item_id.in_(item_ids)).all()

    # Précharger les users d'un coup
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
    """Retourne {item.id: 'pour'|'contre'|'abstention'|None} pour le user connecté."""
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

    # Statistiques rapides par AG
    stats = {}
    for ag in assemblies:
        item_ids = [it.id for it in ag.items]
        voter_count = 0
        if item_ids:
            voter_count = db.session.query(
                db.func.count(db.func.distinct(AGVote.user_id))
            ).filter(AGVote.item_id.in_(item_ids)).scalar() or 0
        stats[ag.id] = {'items': len(ag.items), 'voters': voter_count}

    return render_template('assembly_list.html',
                           assemblies=assemblies, stats=stats, user=user)


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

    # Liste des participants (résidents ayant voté)
    item_ids = [it.id for it in ag.items]
    voters = []
    if item_ids:
        voter_ids = {v.user_id for v in AGVote.query.filter(AGVote.item_id.in_(item_ids)).all()}
        voters = User.query.filter(User.id.in_(voter_ids)).all() if voter_ids else []

    has_voted_all = bool(user_voted) and len(user_voted) == len(ag.items)

    return render_template('assembly_detail.html',
                           ag=ag, user=user,
                           votes_by_item=votes_by_item,
                           user_voted=user_voted,
                           voters=voters,
                           has_voted_all=has_voted_all)


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


# ─── PV HTML ─────────────────────────────────────────────────────────────────

@app.route('/assemblees/<int:ag_id>/pv')
@login_required
@subscription_required
def assembly_pv(ag_id):
    org  = current_organization()
    user = current_user()
    ag   = AssemblyGeneral.query.filter_by(id=ag_id, organization_id=org.id).first_or_404()

    # Résident ne voit le PV que si l'AG est clôturée
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


# ─── PV PDF ──────────────────────────────────────────────────────────────────

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

    # ── Helpers PDF (latin-1 safe) ──
    def s(t):
        if not t:
            return ''
        return (str(t)
                .replace('\u00e9', 'e').replace('\u00e8', 'e').replace('\u00ea', 'e')
                .replace('\u00e0', 'a').replace('\u00e2', 'a')
                .replace('\u00f4', 'o').replace('\u00fb', 'u').replace('\u00fc', 'u')
                .replace('\u00ee', 'i').replace('\u00ef', 'i').replace('\u00e7', 'c')
                .replace('\u00e2', 'a').replace('\u00f9', 'u')
                .replace('\u2014', '-').replace('\u2013', '-')
                .replace('\u2019', "'").replace('\u2018', "'")
                .replace('\u00c9', 'E').replace('\u00c0', 'A').replace('\u00c7', 'C')
                .encode('latin-1', errors='replace').decode('latin-1'))

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    # Fond
    pdf.set_fill_color(10, 14, 26)
    pdf.rect(0, 0, 210, 297, 'F')

    # En-tête
    pdf.set_fill_color(17, 24, 39)
    pdf.rect(0, 0, 210, 44, 'F')
    pdf.set_xy(0, 7)
    pdf.set_text_color(0, 200, 150)
    pdf.set_font('Helvetica', 'B', 22)
    pdf.cell(0, 12, 'SyndicPro', ln=True, align='C')
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(156, 163, 175)
    pdf.cell(0, 5, s(org.name), ln=True, align='C')
    pdf.ln(3)

    # Titre PV
    pdf.set_fill_color(0, 200, 150)
    pdf.set_text_color(10, 14, 26)
    pdf.set_font('Helvetica', 'B', 13)
    pdf.cell(0, 11, "  PROCES-VERBAL D'ASSEMBLEE GENERALE", ln=True, fill=True)
    pdf.ln(6)

    # Infos AG
    def info_line(lbl, val):
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_text_color(156, 163, 175)
        pdf.cell(48, 7, s(lbl))
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(249, 250, 251)
        pdf.cell(0, 7, s(str(val)), ln=True)

    info_line('Titre :', ag.title)
    info_line('Date :', ag.meeting_date.strftime('%d/%m/%Y a %H:%M'))
    if ag.location:
        info_line('Lieu :', ag.location)
    if ag.description:
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_text_color(156, 163, 175)
        pdf.cell(48, 7, 'Objet :')
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(249, 250, 251)
        pdf.multi_cell(0, 6, s(ag.description))
    info_line('Statut :', 'Cloturee' if ag.status == 'cloturee' else ag.status.capitalize())
    info_line('Etabli le :', datetime.now().strftime('%d/%m/%Y a %H:%M'))
    info_line('Participants :', f'{len(voters)} votants sur {total_residents} residents')

    # ── Section : Résumé des résolutions ──
    pdf.ln(5)
    pdf.set_draw_color(0, 200, 150)
    pdf.set_line_width(0.5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)
    pdf.set_font('Helvetica', 'B', 11)
    pdf.set_text_color(0, 200, 150)
    pdf.cell(0, 8, 'RESUME DES RESOLUTIONS', ln=True)
    pdf.ln(2)

    # Tableau résumé
    col_w = [85, 22, 22, 22, 39]
    headers = ['Question', 'Pour', 'Contre', 'Abst.', 'Resultat']
    pdf.set_font('Helvetica', 'B', 8)
    pdf.set_fill_color(30, 40, 55)
    pdf.set_text_color(156, 163, 175)
    for h, w in zip(headers, col_w):
        pdf.cell(w, 7, h, border=0, fill=True, align='C')
    pdf.ln()

    for idx, item in enumerate(ag.items, 1):
        data = votes_data.get(item.id, {})
        res  = data.get('result', '-')
        pdf.set_font('Helvetica', '', 8)
        pdf.set_text_color(249, 250, 251)
        q_text = s(f'{idx}. {item.question}')
        if len(q_text) > 55:
            q_text = q_text[:52] + '...'
        pdf.set_fill_color(17, 27, 40) if idx % 2 == 0 else pdf.set_fill_color(20, 32, 48)
        pdf.cell(col_w[0], 7, q_text, fill=True)
        pdf.set_text_color(0, 200, 150)
        pdf.cell(col_w[1], 7, str(data.get('pour_count', 0)), fill=True, align='C')
        pdf.set_text_color(248, 113, 113)
        pdf.cell(col_w[2], 7, str(data.get('contre_count', 0)), fill=True, align='C')
        pdf.set_text_color(156, 163, 175)
        pdf.cell(col_w[3], 7, str(data.get('abstention_count', 0)), fill=True, align='C')
        if res == 'ADOPTÉ':
            pdf.set_text_color(0, 200, 150)
        elif res == 'REJETÉ':
            pdf.set_text_color(248, 113, 113)
        else:
            pdf.set_text_color(200, 200, 255)
        pdf.cell(col_w[4], 7, s(res), fill=True, align='C')
        pdf.ln()

    # ── Section : Détail des votes ──
    pdf.ln(6)
    pdf.set_draw_color(0, 200, 150)
    pdf.set_line_width(0.5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)
    pdf.set_font('Helvetica', 'B', 11)
    pdf.set_text_color(0, 200, 150)
    pdf.cell(0, 8, "DETAIL DES VOTES PAR POINT", ln=True)

    for idx, item in enumerate(ag.items, 1):
        data = votes_data.get(item.id, {})
        res  = data.get('result', '-')
        pdf.ln(3)

        # Question
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(249, 250, 251)
        pdf.multi_cell(0, 7, s(f'Point {idx} : {item.question}'))

        # Badge résultat
        if res == 'ADOPTÉ':
            pdf.set_fill_color(0, 80, 50)
            pdf.set_text_color(0, 200, 150)
        elif res == 'REJETÉ':
            pdf.set_fill_color(90, 20, 20)
            pdf.set_text_color(248, 113, 113)
        else:
            pdf.set_fill_color(40, 40, 80)
            pdf.set_text_color(200, 200, 255)
        pdf.set_font('Helvetica', 'B', 9)
        stat_line = (f"  {s(res)}   |   Pour : {data.get('pour_count', 0)}   "
                     f"Contre : {data.get('contre_count', 0)}   "
                     f"Abstention : {data.get('abstention_count', 0)}   "
                     f"Total : {data.get('total', 0)} votants")
        pdf.cell(0, 7, stat_line, ln=True, fill=True)

        # Listes nominatives
        for lbl, key, rgb in [
            ('POUR', 'pour', (0, 200, 150)),
            ('CONTRE', 'contre', (248, 113, 113)),
            ('ABSTENTION', 'abstention', (156, 163, 175)),
        ]:
            voters_list = data.get(key, [])
            if not voters_list:
                continue
            pdf.set_font('Helvetica', 'B', 8)
            pdf.set_text_color(*rgb)
            names = []
            for u, apt in voters_list:
                n = u.name or u.email if u else '?'
                apt_lbl = f' ({apt.block.name}-{apt.number})' if apt else ''
                names.append(s(n + apt_lbl))
            pdf.multi_cell(0, 5, f'   {lbl} : {", ".join(names)}')

        pdf.set_draw_color(55, 65, 81)
        pdf.set_line_width(0.2)
        pdf.line(10, pdf.get_y() + 2, 200, pdf.get_y() + 2)
        pdf.ln(4)

    # ── Section : Participants ──
    pdf.ln(4)
    pdf.set_draw_color(0, 200, 150)
    pdf.set_line_width(0.5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)
    pdf.set_font('Helvetica', 'B', 11)
    pdf.set_text_color(0, 200, 150)
    pdf.cell(0, 8, f'LISTE DES PARTICIPANTS ({len(voters)} votants)', ln=True)
    pdf.set_font('Helvetica', '', 8)
    pdf.set_text_color(249, 250, 251)

    if voters:
        col_per_row = 2
        col_width   = 95
        pairs = [voters[i:i + col_per_row] for i in range(0, len(voters), col_per_row)]
        for pair in pairs:
            for v_user in pair:
                apt = None
                if v_user.apartment_id:
                    apt = Apartment.query.get(v_user.apartment_id)
                apt_lbl = f' — {apt.block.name}-{apt.number}' if apt else ''
                pdf.cell(col_width, 6, s(f'• {v_user.name or v_user.email}{apt_lbl}'))
            pdf.ln()
    else:
        pdf.set_text_color(156, 163, 175)
        pdf.cell(0, 6, 'Aucun participant enregistre.', ln=True)

    # Pied de page
    pdf.ln(8)
    pdf.set_font('Helvetica', 'I', 7)
    pdf.set_text_color(156, 163, 175)
    pdf.cell(0, 4,
             s(f'Document officiel genere le {datetime.now().strftime("%d/%m/%Y a %H:%M")} — SyndicPro — {org.name}'),
             ln=True, align='C')
    pdf.cell(0, 4,
             "Ce PV constitue le document officiel de l'assemblee generale des coproprietaires.",
             ln=True, align='C')

    buf = io.BytesIO(pdf.output())
    buf.seek(0)
    filename = f"PV_AG_{ag.id}_{ag.meeting_date.strftime('%Y%m%d')}.pdf"
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
