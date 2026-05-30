from flask import render_template, request, jsonify
from core import app, db
from models import Apartment, Payment, Expense, Ticket
from utils import (current_user, current_organization, login_required,
                   admin_required, subscription_required, get_unpaid_map)
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from datetime import date
import os


def _build_context(org):
    """Construit le contexte syndic pour le prompt Claude.
    HIGH-008 : noms et identités des résidents supprimés — agrégats uniquement.
    """
    apartments = (Apartment.query.options(joinedload(Apartment.block))
                  .filter_by(organization_id=org.id).all())
    current_month = date.today().strftime('%Y-%m')

    # Requêtes scopées + agrégats SQL (pas de chargement de l'historique en RAM)
    paid_ids = {row[0] for row in
                db.session.query(Payment.apartment_id)
                .filter(Payment.organization_id == org.id,
                        Payment.month_paid == current_month).all()}
    unpaid_apts = [a for a in apartments if a.id not in paid_ids]

    total_encaisse = db.session.query(func.coalesce(func.sum(Payment.amount), 0))\
        .filter_by(organization_id=org.id).scalar()
    total_depenses = db.session.query(func.coalesce(func.sum(Expense.amount), 0))\
        .filter_by(organization_id=org.id).scalar()
    total_tickets = db.session.query(func.count(Ticket.id))\
        .filter_by(organization_id=org.id).scalar()
    open_tickets_count = db.session.query(func.count(Ticket.id))\
        .filter(Ticket.organization_id == org.id,
                Ticket.status.in_(('ouvert', 'en_cours'))).scalar()

    # Agrégats impayés (1 requête batch) sans données personnelles identifiables
    unpaid_map = get_unpaid_map(org.id, unpaid_apts)
    unpaid_lines = []
    for a in unpaid_apts[:30]:
        cnt = unpaid_map.get(a.id, 0)
        unpaid_lines.append(
            f"  - {a.block.name}-{a.number} : {cnt} mois en retard, "
            f"dette estimee : {cnt * a.monthly_fee:.0f} DT"
        )

    return f"""Tu es l'assistant intelligent de SyndicPro pour la residence {org.name}.
Tu as acces aux donnees agregees en temps reel. Reponds en francais, de facon claire et concise.
Tu ne dois JAMAIS reveler de donnees personnelles (noms, emails, telephones) des residents.

## Donnees actuelles

Appartements : {len(apartments)} | Payes ce mois : {len(paid_ids)}/{len(apartments)} | Impayes : {len(unpaid_apts)}
Total encaisse : {total_encaisse:.3f} DT | Total depenses : {total_depenses:.3f} DT | Solde : {total_encaisse - total_depenses:.3f} DT
Tickets ouverts : {open_tickets_count} / {total_tickets}

Appartements impayes ce mois :
{chr(10).join(unpaid_lines) if unpaid_lines else "  Tous les appartements ont paye ce mois."}

Reponds uniquement sur la gestion de la residence. Ne fournis jamais de donnees personnelles.
"""


@app.route('/ai')
@login_required
@admin_required
@subscription_required
def ai_chat():
    return render_template('ai_chat.html', user=current_user())


@app.route('/ai/chat', methods=['POST'])
@login_required
@admin_required
@subscription_required
def ai_chat_api():
    # HIGH-004 : vérification CSRF manuelle pour les requêtes JSON
    from flask_wtf.csrf import validate_csrf
    token = request.headers.get('X-CSRFToken') or (request.get_json(silent=True) or {}).get('csrf_token')
    try:
        validate_csrf(token)
    except Exception:
        return jsonify({'error': 'Token de securite invalide. Rechargez la page.'}), 403

    data     = request.get_json(silent=True) or {}
    user_msg = data.get('message', '').strip()[:2000]   # HIGH-009 : limite 2000 chars
    history  = data.get('history', [])

    if not user_msg:
        return jsonify({'error': 'Message vide.'})

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        return jsonify({'error': (
            "Cle API Claude manquante. Ajoutez ANTHROPIC_API_KEY dans les variables Render."
        )})

    org = current_organization()
    system_prompt = _build_context(org)

    messages = []
    for h in history[-10:]:
        if h.get('role') in ('user', 'assistant') and h.get('content'):
            messages.append({'role': h['role'], 'content': str(h['content'])[:2000]})
    messages.append({'role': 'user', 'content': user_msg})

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=512,   # HIGH-008 : limite tokens
            system=system_prompt,
            messages=messages
        )
        reply = resp.content[0].text
        return jsonify({'reply': reply})
    except Exception as e:
        app.logger.error(f"AI chat error: {e}")
        return jsonify({'error': "Erreur de communication avec Claude. Reessayez."})
