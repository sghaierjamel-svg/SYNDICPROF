from flask import render_template, request, jsonify
from core import app
from models import Apartment, Payment, Expense, Ticket, User
from utils import (current_user, current_organization, login_required,
                   admin_required, subscription_required, get_unpaid_months_count)
from datetime import date
import os


def _build_context(org):
    """Construit le contexte syndic pour le prompt Claude."""
    apartments = Apartment.query.filter_by(organization_id=org.id).all()
    payments   = Payment.query.filter_by(organization_id=org.id).all()
    expenses   = Expense.query.filter_by(organization_id=org.id).all()
    tickets    = Ticket.query.filter_by(organization_id=org.id).all()

    current_month = date.today().strftime('%Y-%m')
    paid_ids = {p.apartment_id for p in payments if p.month_paid == current_month}
    unpaid_apts = [a for a in apartments if a.id not in paid_ids]

    total_encaisse = sum(p.amount for p in payments)
    total_depenses = sum(e.amount for e in expenses)

    unpaid_lines = []
    for a in unpaid_apts[:30]:
        cnt = get_unpaid_months_count(a.id)
        r = User.query.filter_by(apartment_id=a.id).first()
        name = r.name if r else '—'
        unpaid_lines.append(
            f"  - {a.block.name}-{a.number} : {cnt} mois impayé(s), "
            f"résident : {name}, dette : {cnt * a.monthly_fee:.0f} DT"
        )

    open_tickets = [t for t in tickets if t.status in ('ouvert', 'en_cours')]

    return f"""Tu es l'assistant intelligent de SyndicPro pour la résidence **{org.name}**.
Tu as accès à toutes les données en temps réel. Réponds en français, de façon claire et concise.

## Données actuelles — {org.name}

**Résumé général**
- Appartements : {len(apartments)} au total
- Mois en cours : {current_month}
- Payés ce mois : {len(paid_ids)}/{len(apartments)}
- Impayés ce mois : {len(unpaid_apts)}

**Finances (cumulées)**
- Total encaissé : {total_encaisse:.2f} DT
- Total dépenses : {total_depenses:.2f} DT
- Solde trésorerie : {total_encaisse - total_depenses:.2f} DT

**Tickets**
- Ouverts / en cours : {len(open_tickets)}
- Total : {len(tickets)}

**Appartements impayés ce mois**
{chr(10).join(unpaid_lines) if unpaid_lines else "  ✅ Tous les appartements ont payé ce mois !"}

Tu peux répondre à toute question sur les paiements, la trésorerie, les tickets, les résidents, etc.
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
    data = request.get_json(silent=True) or {}
    user_msg = data.get('message', '').strip()
    history  = data.get('history', [])   # liste de {role, content}

    if not user_msg:
        return jsonify({'error': 'Message vide.'})

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        return jsonify({'error': (
            "Clé API Claude manquante. Ajoutez la variable "
            "ANTHROPIC_API_KEY dans les paramètres Render."
        )})

    org = current_organization()
    system_prompt = _build_context(org)

    # Construire les messages (historique + nouveau)
    messages = []
    for h in history[-10:]:   # garder les 10 derniers échanges max
        if h.get('role') in ('user', 'assistant') and h.get('content'):
            messages.append({'role': h['role'], 'content': h['content']})
    messages.append({'role': 'user', 'content': user_msg})

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=1024,
            system=system_prompt,
            messages=messages
        )
        reply = resp.content[0].text
        return jsonify({'reply': reply})
    except Exception as e:
        return jsonify({'error': f"Erreur Claude : {str(e)}"})
