from flask import render_template, request, redirect, url_for, flash, jsonify
from core import app, db
from models import Lift, LiftIncident, Block, Intervenant, User
from utils import current_user, current_organization, login_required, admin_required, subscription_required
from datetime import datetime
import secrets


# ─── Pages principales ────────────────────────────────────────────────────────

@app.route('/lifts')
@login_required
@subscription_required
def lifts():
    user = current_user()
    org  = current_organization()
    lifts_list = Lift.query.filter_by(organization_id=org.id).order_by(Lift.name).all()
    blocks      = Block.query.filter_by(organization_id=org.id).order_by(Block.name).all()
    intervenants = Intervenant.query.filter_by(organization_id=org.id).filter(
        Intervenant.categorie.ilike('%ascenseur%')).order_by(Intervenant.nom).all()
    # Incidents ouverts par ascenseur
    open_incidents = {
        i.lift_id for i in LiftIncident.query.filter_by(organization_id=org.id).filter(
            LiftIncident.status.in_(['ouvert', 'en_cours'])).all()
    }
    return render_template('lifts.html',
                           user=user, org=org,
                           lifts=lifts_list,
                           blocks=blocks,
                           intervenants=intervenants,
                           open_incidents=open_incidents)


@app.route('/lift/<int:lift_id>', methods=['GET', 'POST'])
@login_required
@subscription_required
def lift_detail(lift_id):
    user = current_user()
    org  = current_organization()
    lift = Lift.query.filter_by(id=lift_id, organization_id=org.id).first_or_404()
    intervenants = Intervenant.query.filter_by(organization_id=org.id).filter(
        Intervenant.categorie.ilike('%ascenseur%')).order_by(Intervenant.nom).all()

    if request.method == 'POST' and user.role == 'admin':
        action = request.form.get('action')

        if action == 'update_status':
            new_status = request.form.get('status', lift.status)
            if new_status in ('ok', 'warning', 'down'):
                old_status = lift.status
                lift.status = new_status
                db.session.commit()
                flash(f'Statut mis à jour : {new_status.upper()}', 'success')
                if old_status != new_status:
                    _notify_lift_status(org, lift, new_status, source='admin')

        elif action == 'update_info':
            lift.name     = request.form.get('name', lift.name).strip()[:100]
            lift.location = request.form.get('location', '').strip()[:200] or None
            lift.notes    = request.form.get('notes', '').strip() or None
            raw_date = request.form.get('last_maintenance', '').strip()
            if raw_date:
                try:
                    from datetime import date
                    lift.last_maintenance = datetime.strptime(raw_date, '%Y-%m-%d').date()
                except ValueError:
                    pass
            db.session.commit()
            flash('Ascenseur mis à jour.', 'success')

        elif action == 'assign_intervenant':
            inc_id = request.form.get('incident_id')
            int_id = request.form.get('intervenant_id')
            inc = LiftIncident.query.filter_by(id=inc_id, organization_id=org.id).first()
            if inc:
                inc.intervenant_id = int_id or None
                inc.status = 'en_cours'
                db.session.commit()
                flash('Réparateur assigné.', 'success')
                if int_id:
                    interv = Intervenant.query.get(int_id)
                    if interv:
                        _notify_intervenant(org, lift, inc, interv)

        elif action == 'close_incident':
            inc_id = request.form.get('incident_id')
            inc = LiftIncident.query.filter_by(id=inc_id, organization_id=org.id).first()
            if inc:
                inc.status = 'resolu'
                inc.resolved_at = datetime.utcnow()
                inc.admin_notes = request.form.get('admin_notes', '').strip() or None
                db.session.commit()
                # Remettre le lift en OK si plus d'incidents ouverts
                still_open = LiftIncident.query.filter_by(
                    lift_id=lift.id).filter(LiftIncident.status.in_(['ouvert','en_cours'])).count()
                if still_open == 0:
                    lift.status = 'ok'
                    db.session.commit()
                flash('Incident résolu — ascenseur remis en service.', 'success')

        return redirect(url_for('lift_detail', lift_id=lift_id))

    incidents = LiftIncident.query.filter_by(lift_id=lift_id).order_by(
        LiftIncident.created_at.desc()).all()
    return render_template('lift_detail.html',
                           user=user, org=org,
                           lift=lift,
                           incidents=incidents,
                           intervenants=intervenants)


# ─── CRUD ascenseurs (admin) ──────────────────────────────────────────────────

@app.route('/lifts/ajouter', methods=['POST'])
@login_required
@admin_required
@subscription_required
def lift_ajouter():
    org  = current_organization()
    name = request.form.get('name', '').strip()[:100]
    if not name:
        flash('Le nom est obligatoire.', 'danger')
        return redirect(url_for('lifts'))
    lift = Lift(
        organization_id=org.id,
        block_id=request.form.get('block_id') or None,
        name=name,
        location=request.form.get('location', '').strip()[:200] or None,
        notes=request.form.get('notes', '').strip() or None,
        iot_api_key=secrets.token_hex(32),   # clé IoT générée automatiquement
    )
    db.session.add(lift)
    db.session.commit()
    flash(f'Ascenseur « {name} » ajouté.', 'success')
    return redirect(url_for('lifts'))


@app.route('/lifts/<int:lift_id>/supprimer', methods=['POST'])
@login_required
@admin_required
@subscription_required
def lift_supprimer(lift_id):
    org  = current_organization()
    lift = Lift.query.filter_by(id=lift_id, organization_id=org.id).first_or_404()
    nom  = lift.name
    db.session.delete(lift)
    db.session.commit()
    flash(f'Ascenseur « {nom} » supprimé.', 'success')
    return redirect(url_for('lifts'))


# ─── Signalement d'incident (résident + admin) ───────────────────────────────

@app.route('/lift/<int:lift_id>/incident', methods=['POST'])
@login_required
@subscription_required
def lift_report_incident(lift_id):
    user = current_user()
    org  = current_organization()
    lift = Lift.query.filter_by(id=lift_id, organization_id=org.id).first_or_404()

    description = request.form.get('description', '').strip()[:1000]
    if not description:
        flash('La description est obligatoire.', 'danger')
        return redirect(url_for('lift_detail', lift_id=lift_id))

    # Idempotence : 1 seul incident ouvert par ascenseur
    existing = LiftIncident.query.filter_by(lift_id=lift_id).filter(
        LiftIncident.status.in_(['ouvert', 'en_cours'])).first()
    if existing:
        flash('Un incident est déjà ouvert sur cet ascenseur.', 'warning')
        return redirect(url_for('lift_detail', lift_id=lift_id))

    inc = LiftIncident(
        organization_id=org.id,
        lift_id=lift_id,
        reported_by_id=user.id,
        source='manuel',
        description=description,
    )
    lift.status = 'warning'
    db.session.add(inc)
    db.session.commit()
    flash('Incident signalé. L\'administration a été notifiée.', 'success')
    _notify_lift_status(org, lift, 'warning', source='manuel', incident=inc, reporter=user)
    return redirect(url_for('lift_detail', lift_id=lift_id))


# ─── Endpoint IoT (capteur physique) ─────────────────────────────────────────

@app.route('/api/v1/iot/telemetry', methods=['POST'])
def iot_telemetry():
    """Reçoit les données du capteur IoT. Authentification par iot_api_key."""
    api_key = request.headers.get('X-API-Key') or (request.get_json(silent=True) or {}).get('api_key')
    if not api_key:
        return jsonify({'error': 'X-API-Key manquant'}), 401

    lift = Lift.query.filter_by(iot_api_key=api_key).first()
    if not lift:
        return jsonify({'error': 'Clé invalide'}), 401

    data   = request.get_json(silent=True) or {}
    status = data.get('status', '').lower()
    if status not in ('ok', 'warning', 'down'):
        return jsonify({'error': 'status doit être ok / warning / down'}), 400

    old_status = lift.status
    lift.status = status

    incident_id = None
    if status in ('warning', 'down') and old_status == 'ok':
        # Créer un incident automatique si pas déjà ouvert
        existing = LiftIncident.query.filter_by(lift_id=lift.id).filter(
            LiftIncident.status.in_(['ouvert', 'en_cours'])).first()
        if not existing:
            desc = data.get('description') or f'Anomalie détectée par capteur IoT — statut : {status.upper()}'
            inc = LiftIncident(
                organization_id=lift.organization_id,
                lift_id=lift.id,
                source='iot',
                description=desc,
                status='ouvert',
            )
            db.session.add(inc)
            db.session.flush()
            incident_id = inc.id
            from core import db as _db
            _db.session.commit()
            _notify_lift_status(lift.organization, lift, status, source='iot', incident=inc)
        else:
            db.session.commit()
    elif status == 'ok' and old_status != 'ok':
        db.session.commit()
        _notify_lift_status(lift.organization, lift, 'ok', source='iot')
    else:
        db.session.commit()

    return jsonify({'ok': True, 'lift_id': lift.id, 'status': status, 'incident_id': incident_id})


# ─── Helpers notifications ────────────────────────────────────────────────────

def _notify_lift_status(org, lift, status, source='manuel', incident=None, reporter=None):
    """Notifie admin + TOUS les résidents via Push + WhatsApp admin."""
    status_labels = {
        'ok':      '✅ Remis en service',
        'warning': '⚠️ Anomalie signalée',
        'down':    '🔴 HORS SERVICE',
    }
    label = status_labels.get(status, status.upper())

    lift_label = lift.name + (f" ({lift.location})" if lift.location else "")

    # ── Message admin ──────────────────────────────────────────────────────
    title_admin = f"🛗 Ascenseur — {label}"
    body_admin  = lift_label
    if incident:
        body_admin += f"\n{incident.description[:120]}"
    if reporter:
        body_admin += f"\nSignalé par : {reporter.name or reporter.email}"
    if source == 'iot':
        body_admin += "\n📡 Détecté par capteur IoT"

    # ── Message résidents ──────────────────────────────────────────────────
    if status == 'down':
        title_res = "🔴 Ascenseur hors service"
        body_res  = f"{lift_label} est hors service.\nUne intervention est en cours."
    elif status == 'warning':
        title_res = "⚠️ Anomalie sur l'ascenseur"
        body_res  = f"{lift_label} présente une anomalie.\nNous vous tiendrons informés."
    else:
        title_res = "✅ Ascenseur remis en service"
        body_res  = f"{lift_label} est de nouveau opérationnel."

    url = f"/lift/{lift.id}"
    tag = f"lift-{lift.id}"

    # Push → admin
    try:
        from utils_push import push_to_admins
        push_to_admins(org.id, title=title_admin, body=body_admin, url=url, tag=tag)
    except Exception:
        pass

    # WhatsApp → admin
    try:
        from utils_whatsapp import send_whatsapp
        if org.whatsapp_admin_phone:
            send_whatsapp(org, org.whatsapp_admin_phone, f"{title_admin}\n{body_admin}")
    except Exception:
        pass

    # Push → TOUS les résidents (warning + down + ok)
    try:
        from utils_push import push_to_user
        residents = User.query.filter_by(organization_id=org.id, role='resident').all()
        for r in residents:
            push_to_user(r.id, title=title_res, body=body_res, url=url, tag=f"lift-res-{lift.id}")
    except Exception:
        pass


def _notify_intervenant(org, lift, incident, interv):
    """Notifie le réparateur assigné via WhatsApp."""
    try:
        from utils_whatsapp import send_whatsapp
        if interv.telephone:
            msg = (
                f"🔧 *SyndicPro — Intervention ascenseur*\n"
                f"Résidence : {org.name}\n"
                f"Ascenseur : {lift.name}"
                + (f" ({lift.location})" if lift.location else '') +
                f"\nProblème : {incident.description[:200]}\n"
                f"Merci de confirmer votre intervention."
            )
            send_whatsapp(org, interv.telephone, msg)
    except Exception:
        pass
