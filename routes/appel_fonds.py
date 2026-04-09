import base64, io
from flask import render_template, request, redirect, url_for, flash, send_file, abort
from core import app, db
from models import AppelFonds, AppelFondsQuota, AppelFondsPaiement, AppelFondsDepense, Apartment
from utils import current_user, current_organization, login_required, admin_required, subscription_required
from datetime import datetime, date

MAX_FILE_BYTES = 10 * 1024 * 1024
ALLOWED_MIMES  = {'image/jpeg', 'image/png', 'image/webp', 'application/pdf'}


def _read_file(fs):
    if not fs or fs.filename == '':
        return None, None, None
    if fs.mimetype not in ALLOWED_MIMES:
        raise ValueError('Format non accepté (JPG, PNG, PDF uniquement).')
    raw = fs.read()
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError('Fichier trop lourd (max 10 Mo).')
    return base64.b64encode(raw).decode(), fs.mimetype, fs.filename


def _appel_stats(appel):
    """Calcule collecté, dépensé, solde pour un appel de fonds."""
    quota_map = {q.apartment_id: q.montant_attendu for q in appel.quotas}
    total_attendu = sum(quota_map.values())
    total_collecte = sum(p.amount for p in appel.paiements)
    total_depense  = sum(d.amount for d in appel.depenses)
    return {
        'total_attendu':  total_attendu,
        'total_collecte': total_collecte,
        'total_depense':  total_depense,
        'solde_fonds':    total_collecte - total_depense,
        'reste_a_collecter': max(0, total_attendu - total_collecte),
        'pct': int(total_collecte / total_attendu * 100) if total_attendu > 0 else 0,
    }


# ─── Liste des appels de fonds ────────────────────────────────────────────────

@app.route('/appels-fonds')
@login_required
@admin_required
@subscription_required
def appels_fonds():
    org = current_organization()
    appels = AppelFonds.query.filter_by(organization_id=org.id)\
        .order_by(AppelFonds.created_at.desc()).all()
    stats = {a.id: _appel_stats(a) for a in appels}
    return render_template('appels_fonds.html',
                           appels=appels, stats=stats, user=current_user())


# ─── Créer un appel de fonds ─────────────────────────────────────────────────

@app.route('/appels-fonds/nouveau', methods=['POST'])
@login_required
@admin_required
@subscription_required
def appel_fonds_nouveau():
    org = current_organization()
    titre = request.form.get('titre', '').strip()[:200]
    if not titre:
        flash('Le titre est obligatoire.', 'danger')
        return redirect(url_for('appels_fonds'))
    try:
        budget = float(request.form.get('budget_total', 0) or 0)
    except ValueError:
        budget = 0.0
    d_lanc = request.form.get('date_lancement', '')
    d_ech  = request.form.get('date_echeance', '')
    af = AppelFonds(
        organization_id=org.id,
        titre=titre,
        description=request.form.get('description', '').strip() or None,
        budget_total=budget,
        date_lancement=datetime.strptime(d_lanc, '%Y-%m-%d').date() if d_lanc else None,
        date_echeance=datetime.strptime(d_ech,  '%Y-%m-%d').date() if d_ech  else None,
    )
    db.session.add(af)
    db.session.flush()  # obtenir af.id

    # Générer les quotas égaux pour tous les appartements
    apartments = Apartment.query.filter_by(organization_id=org.id).all()
    nb = len(apartments)
    quota_unitaire = round(budget / nb, 3) if nb > 0 and budget > 0 else 0.0
    for apt in apartments:
        db.session.add(AppelFondsQuota(
            appel_id=af.id,
            apartment_id=apt.id,
            montant_attendu=quota_unitaire,
        ))
    db.session.commit()
    flash(f'Appel de fonds « {titre} » créé. Quotas générés ({quota_unitaire:.3f} DT / appartement).', 'success')
    return redirect(url_for('appel_fonds_detail', af_id=af.id))


# ─── Détail / gestion d'un appel de fonds ────────────────────────────────────

@app.route('/appels-fonds/<int:af_id>', methods=['GET', 'POST'])
@login_required
@admin_required
@subscription_required
def appel_fonds_detail(af_id):
    org = current_organization()
    af  = AppelFonds.query.filter_by(id=af_id, organization_id=org.id).first_or_404()
    apartments = Apartment.query.filter_by(organization_id=org.id)\
        .order_by(Apartment.block_id, Apartment.number).all()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'edit_info':
            af.titre       = request.form.get('titre', af.titre).strip()[:200]
            af.description = request.form.get('description', '').strip() or None
            try:
                af.budget_total = float(request.form.get('budget_total', af.budget_total) or 0)
            except ValueError:
                pass
            d_lanc = request.form.get('date_lancement', '')
            d_ech  = request.form.get('date_echeance', '')
            af.date_lancement = datetime.strptime(d_lanc, '%Y-%m-%d').date() if d_lanc else None
            af.date_echeance  = datetime.strptime(d_ech,  '%Y-%m-%d').date() if d_ech  else None
            db.session.commit()
            flash('Informations mises à jour.', 'success')

        elif action == 'change_status':
            new_s = request.form.get('status')
            if new_s in ('ouvert', 'clos'):
                af.status = new_s
                db.session.commit()
                flash('Statut mis à jour.', 'success')

        elif action == 'upload_devis':
            try:
                d, m, n = _read_file(request.files.get('devis_file'))
                if d:
                    af.devis_data, af.devis_mime, af.devis_nom = d, m, n
                    db.session.commit()
                    flash('Devis enregistré.', 'success')
            except ValueError as e:
                flash(str(e), 'warning')

        elif action == 'save_quotas':
            for apt in apartments:
                val = request.form.get(f'quota_{apt.id}', '')
                try:
                    montant = float(val)
                except ValueError:
                    continue
                q = next((q for q in af.quotas if q.apartment_id == apt.id), None)
                if q:
                    q.montant_attendu = montant
                else:
                    db.session.add(AppelFondsQuota(
                        appel_id=af.id, apartment_id=apt.id, montant_attendu=montant))
            db.session.commit()
            flash('Quotas mis à jour.', 'success')

        elif action == 'add_paiement':
            try:
                apt_id = int(request.form['apartment_id'])
                amount = float(request.form['amount'])
                pdate  = datetime.strptime(request.form['payment_date'], '%Y-%m-%d').date()
                notes  = request.form.get('notes', '').strip()[:300] or None
                db.session.add(AppelFondsPaiement(
                    appel_id=af_id, organization_id=org.id,
                    apartment_id=apt_id, amount=amount,
                    payment_date=pdate, notes=notes,
                ))
                db.session.commit()
                flash('Paiement enregistré.', 'success')
            except Exception as e:
                flash(f'Erreur : {e}', 'danger')

        elif action == 'delete_paiement':
            pid = int(request.form.get('paiement_id', 0))
            p = AppelFondsPaiement.query.filter_by(id=pid, appel_id=af_id).first()
            if p:
                db.session.delete(p)
                db.session.commit()
                flash('Paiement supprimé.', 'success')

        elif action == 'add_depense':
            try:
                amount  = float(request.form['amount'])
                ddate   = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
                libelle = request.form.get('libelle', '').strip()[:200]
                notes   = request.form.get('notes', '').strip() or None
                dep = AppelFondsDepense(
                    appel_id=af_id, organization_id=org.id,
                    amount=amount, date=ddate, libelle=libelle, notes=notes,
                )
                # Fichier joint (facture)
                try:
                    d, m, n = _read_file(request.files.get('facture_file'))
                    if d:
                        dep.facture_data, dep.facture_mime, dep.facture_nom = d, m, n
                except ValueError as e:
                    flash(str(e), 'warning')
                db.session.add(dep)
                db.session.commit()
                flash('Dépense enregistrée.', 'success')
            except Exception as e:
                flash(f'Erreur : {e}', 'danger')

        elif action == 'delete_depense':
            did = int(request.form.get('depense_id', 0))
            d = AppelFondsDepense.query.filter_by(id=did, appel_id=af_id).first()
            if d:
                db.session.delete(d)
                db.session.commit()
                flash('Dépense supprimée.', 'success')

        return redirect(url_for('appel_fonds_detail', af_id=af_id))

    # Construire quota_map et paiements_par_apt
    quota_map = {q.apartment_id: q.montant_attendu for q in af.quotas}
    paie_par_apt = {}
    for p in af.paiements:
        paie_par_apt.setdefault(p.apartment_id, []).append(p)

    stats = _appel_stats(af)

    return render_template('appel_fonds_detail.html',
                           af=af, apartments=apartments,
                           quota_map=quota_map, paie_par_apt=paie_par_apt,
                           stats=stats, user=current_user())


# ─── Téléchargement devis ─────────────────────────────────────────────────────

@app.route('/appels-fonds/<int:af_id>/devis')
@login_required
@subscription_required
def appel_fonds_devis(af_id):
    org = current_organization()
    af  = AppelFonds.query.filter_by(id=af_id, organization_id=org.id).first_or_404()
    if not af.devis_data:
        abort(404)
    buf = io.BytesIO(base64.b64decode(af.devis_data))
    buf.seek(0)
    return send_file(buf, mimetype=af.devis_mime,
                     as_attachment=request.args.get('dl') == '1',
                     download_name=af.devis_nom or f'devis_{af_id}')


# ─── Téléchargement facture dépense ──────────────────────────────────────────

@app.route('/appels-fonds/<int:af_id>/depense/<int:dep_id>/facture')
@login_required
@subscription_required
def appel_fonds_facture(af_id, dep_id):
    org = current_organization()
    af  = AppelFonds.query.filter_by(id=af_id, organization_id=org.id).first_or_404()
    dep = AppelFondsDepense.query.filter_by(id=dep_id, appel_id=af_id).first_or_404()
    if not dep.facture_data:
        abort(404)
    buf = io.BytesIO(base64.b64decode(dep.facture_data))
    buf.seek(0)
    return send_file(buf, mimetype=dep.facture_mime,
                     as_attachment=request.args.get('dl') == '1',
                     download_name=dep.facture_nom or f'facture_{dep_id}')


# ─── Reçu PDF d'un paiement appel de fonds ───────────────────────────────────

@app.route('/appels-fonds/<int:af_id>/paiement/<int:p_id>/recu.pdf')
@login_required
@subscription_required
def appel_fonds_recu(af_id, p_id):
    import traceback
    try:
        from fpdf import FPDF
    except ImportError as e:
        print(f"[appel_fonds_recu] ImportError fpdf: {e}")
        flash('Module PDF non disponible.', 'danger')
        return redirect(url_for('appel_fonds_detail', af_id=af_id))

    try:
        org  = current_organization()
        user = current_user()

        if not org:
            flash('Organisation introuvable.', 'danger')
            return redirect(url_for('appels_fonds'))

        af = AppelFonds.query.filter_by(id=af_id, organization_id=org.id).first_or_404()
        p  = AppelFondsPaiement.query.filter_by(id=p_id, appel_id=af_id).first_or_404()

        # Résident : seulement son propre reçu
        if user.role == 'resident' and p.apartment_id != user.apartment_id:
            abort(403)

        apt = p.apartment
        if not apt:
            flash('Appartement introuvable pour ce paiement.', 'danger')
            return redirect(url_for('appel_fonds_detail', af_id=af_id))

        block_name = apt.block.name if apt.block else 'N/A'
        resident   = apt.residents[0] if apt.residents else None

        def _s(t):
            if not t: return ''
            return (str(t)
                .replace('\u2014', '-').replace('\u2013', '-')
                .replace('\u2019', "'").replace('\u2018', "'")
                .encode('latin-1', errors='replace').decode('latin-1'))

        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

        # Bandeau header
        pdf.set_fill_color(0, 120, 200)
        pdf.rect(0, 0, 210, 32, 'F')
        pdf.set_xy(0, 5)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font('Helvetica', 'B', 22)
        pdf.cell(0, 11, 'SyndicPro', ln=True, align='C')
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(0, 6, _s(org.name), ln=True, align='C')
        pdf.ln(6)

        # Titre
        pdf.set_fill_color(235, 245, 255)
        pdf.set_draw_color(0, 120, 200)
        pdf.set_line_width(0.5)
        pdf.set_text_color(0, 80, 160)
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 10, _s(f'  RECU PAIEMENT - APPEL DE FONDS  N{chr(176)} {p.id:05d}'),
                 ln=True, fill=True, border=1)
        pdf.ln(5)

        def info_line(label, value):
            pdf.set_font('Helvetica', 'B', 9)
            pdf.set_text_color(120, 120, 120)
            pdf.cell(65, 7, _s(label))
            pdf.set_font('Helvetica', '', 9)
            pdf.set_text_color(40, 40, 40)
            pdf.cell(0, 7, _s(str(value)), ln=True)

        info_line('Projet :', af.titre)
        info_line('Appartement :', f"{block_name}-{apt.number}")
        info_line('Resident :', resident.name if resident else '-')
        info_line('Date de paiement :', p.payment_date.strftime('%d/%m/%Y'))
        if p.notes:
            info_line('Notes :', p.notes)
        pdf.ln(4)
        pdf.set_draw_color(200, 200, 200)
        pdf.set_line_width(0.3)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(4)

        # Montant
        pdf.set_fill_color(0, 120, 200)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font('Helvetica', 'B', 14)
        pdf.cell(0, 13, _s(f'  MONTANT VERSE : {p.amount:.3f} DT'), ln=True, fill=True)

        # Quota de l'appartement
        quotas_list = list(af.quotas)
        paiements_list = list(af.paiements)
        quota = next((q.montant_attendu for q in quotas_list if q.apartment_id == p.apartment_id), None)
        if quota:
            total_verse = sum(pp.amount for pp in paiements_list if pp.apartment_id == p.apartment_id)
            reste = max(0, quota - total_verse)
            pdf.set_font('Helvetica', '', 8)
            pdf.set_text_color(80, 80, 80)
            pdf.cell(0, 5, _s(
                f'  Quote-part : {quota:.3f} DT  |  Verse total : {total_verse:.3f} DT  |  Reste : {reste:.3f} DT'
            ), ln=True)

        pdf.ln(8)
        pdf.set_draw_color(200, 200, 200)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(4)
        pdf.set_font('Helvetica', 'I', 7)
        pdf.set_text_color(150, 150, 150)
        pdf.cell(0, 4, _s(
            f'Document genere le {datetime.now().strftime("%d/%m/%Y")} - SyndicPro, {org.name}'
        ), ln=True, align='C')
        pdf.cell(0, 4,
                 'Ce recu concerne exclusivement les fonds de travaux - distinct de la gestion courante.',
                 ln=True, align='C')

        output = pdf.output()
        buf = io.BytesIO(bytes(output) if not isinstance(output, bytes) else output)
        buf.seek(0)
        safe_block = _s(block_name).replace('/', '-').replace(' ', '_')
        safe_apt   = _s(str(apt.number)).replace('/', '-').replace(' ', '_')
        filename = f"Recu_AppelFonds_{safe_block}{safe_apt}_{af_id}_{p_id}.pdf"
        return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=filename)

    except Exception as exc:
        print(f"[appel_fonds_recu] ERREUR: {exc}")
        print(traceback.format_exc())
        flash(f'Erreur lors de la génération du reçu : {exc}', 'danger')
        return redirect(url_for('appel_fonds_detail', af_id=af_id))


# ─── Supprimer un appel de fonds ─────────────────────────────────────────────

@app.route('/appels-fonds/<int:af_id>/supprimer', methods=['POST'])
@login_required
@admin_required
@subscription_required
def appel_fonds_supprimer(af_id):
    org = current_organization()
    af  = AppelFonds.query.filter_by(id=af_id, organization_id=org.id).first_or_404()
    db.session.delete(af)
    db.session.commit()
    flash('Appel de fonds supprimé.', 'success')
    return redirect(url_for('appels_fonds'))


# ─── Vue résident : mes appels de fonds ──────────────────────────────────────

@app.route('/appels-fonds/resident')
@login_required
@subscription_required
def appels_fonds_resident():
    user = current_user()
    if user.role == 'admin':
        return redirect(url_for('appels_fonds'))
    if not user.apartment_id:
        abort(403)
    from utils import current_organization
    org = current_organization()
    appels = AppelFonds.query.filter_by(organization_id=org.id, status='ouvert')\
        .order_by(AppelFonds.created_at.desc()).all()

    resident_data = []
    for af in appels:
        quota = next((q.montant_attendu for q in af.quotas if q.apartment_id == user.apartment_id), 0.0)
        paiements = [p for p in af.paiements if p.apartment_id == user.apartment_id]
        total_verse = sum(p.amount for p in paiements)
        resident_data.append({
            'af': af,
            'quota': quota,
            'total_verse': total_verse,
            'reste': max(0, quota - total_verse),
            'pct': int(total_verse / quota * 100) if quota > 0 else 0,
            'paiements': sorted(paiements, key=lambda x: x.payment_date, reverse=True),
        })

    return render_template('appels_fonds_resident.html',
                           resident_data=resident_data, user=user)
