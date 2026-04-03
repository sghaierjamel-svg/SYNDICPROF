"""
États financiers SyndicPro
Conformes au Système Comptable des Entreprises (SCE) — Loi tunisienne 96-112 du 30/12/1996
Normes Comptables Tunisiennes (NCT 01 et suivantes)
"""
from flask import render_template, request, send_file
from core import app
from models import Apartment, Payment, Expense, Organization
from utils import current_user, current_organization, login_required, admin_required, subscription_required
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import io


# Mapping categories depenses -> comptes SCE tunisiens
CATEGORY_TO_SCE = {
    'Eau':             ('612', 'Eau et fournitures - parties communes'),
    'Electricite':     ('612', 'Energie - parties communes'),
    'Electricité':     ('612', 'Energie - parties communes'),
    'Entretien':       ('614', 'Entretien et reparations'),
    'Réparations':     ('614', 'Entretien et reparations'),
    'Reparations':     ('614', 'Entretien et reparations'),
    'Gardiennage':     ('641', 'Remunerations du personnel / gardiennage'),
    'Assurances':      ('616', "Primes d'assurance immeuble"),
    'Taxes':           ('635', 'Impots et taxes'),
    'Salaire':         ('641', 'Salaires et remunerations du personnel'),
    'Immobilisation':  ('22x', 'Immobilisations corporelles (valeur achat)'),
    'Autre':           ('65x', "Autres charges d'exploitation"),
}


def _s(text):
    """Sanitise un texte pour fpdf2 Helvetica.
    Remplace uniquement les caractères hors Latin-1 (U+0100+).
    Les accents français (é, è, à, ç...) sont dans Latin-1 et restent intacts.
    """
    if not text:
        return ''
    return (str(text)
        .replace('\u2014', '-').replace('\u2013', '-')  # tirets longs -> -
        .replace('\u2019', "'").replace('\u2018', "'")  # apostrophes courbes -> '
        .replace('\u201c', '"').replace('\u201d', '"')  # guillemets courbes -> "
        .replace('\u2192', '>').replace('\u2190', '<')  # fleches -> > <
        .replace('\u2500', '-').replace('\u2502', '|')  # box drawing -> - |
        .encode('latin-1', errors='replace').decode('latin-1')
    )


def _compute_financial_data(org, year):
    """Calcule toutes les données financières pour une organisation et une année."""

    apartments = Apartment.query.filter_by(organization_id=org.id).all()
    all_payments = Payment.query.filter_by(organization_id=org.id).all()
    all_expenses = Expense.query.filter_by(organization_id=org.id).all()

    year_payments = [p for p in all_payments if p.payment_date.year == year]
    year_expenses = [e for e in all_expenses if e.expense_date.year == year]

    # Séparer immobilisations (22x) des charges courantes (6xx)
    all_immos   = [e for e in all_expenses  if e.category == 'Immobilisation']
    year_immos  = [e for e in year_expenses if e.category == 'Immobilisation']
    all_charges = [e for e in all_expenses  if e.category != 'Immobilisation']
    year_charges= [e for e in year_expenses if e.category != 'Immobilisation']

    # ── BILAN — ACTIF ─────────────────────────────────────────────────────────

    # 511/530 — Liquidités : trésorerie nette cumulée (tous décaissements inclus)
    total_encaisse_cumul = sum(p.amount for p in all_payments)
    total_depenses_cumul = sum(e.amount for e in all_expenses)  # immos incluses car argent sorti
    tresorerie_nette = total_encaisse_cumul - total_depenses_cumul
    liquidites = max(0.0, tresorerie_nette)

    # 411 — Créances copropriétaires : charges impayées (valeur des mois en souffrance)
    today = date.today()
    creances_detail = []
    total_creances = 0.0
    for apt in apartments:
        apt_paid_months = {p.month_paid for p in all_payments if p.apartment_id == apt.id}
        # Compter les mois depuis la création de l'appartement jusqu'à aujourd'hui
        start = apt.created_at.date().replace(day=1)
        cursor = start
        montant_du = 0.0
        while cursor <= today.replace(day=1):
            mk = cursor.strftime('%Y-%m')
            if mk not in apt_paid_months:
                montant_du += apt.monthly_fee
            cursor += relativedelta(months=1)
        # Déduire le crédit disponible
        montant_du = max(0.0, montant_du - apt.credit_balance)
        if montant_du > 0:
            resident = apt.residents[0] if apt.residents else None
            creances_detail.append({
                'apt': f"{apt.block.name}-{apt.number}",
                'resident': resident.name if resident else '-',
                'montant': montant_du,
            })
            total_creances += montant_du

    total_actif_courant = liquidites + total_creances

    # 22x — Immobilisations corporelles (valeur brute cumulée tous exercices)
    total_immobilisations = sum(e.amount for e in all_immos)
    immos_detail = []
    for e in sorted(all_immos, key=lambda x: x.expense_date, reverse=True):
        immos_detail.append({
            'date': e.expense_date,
            'description': e.description or e.category,
            'montant': e.amount,
        })
    total_actif_non_courant = total_immobilisations
    total_actif = total_actif_courant + total_actif_non_courant

    # ── BILAN — PASSIF & CAPITAUX PROPRES ────────────────────────────────────

    # 419 — Trop-perçus copropriétaires (credit_balance > 0)
    trop_percus_detail = []
    total_trop_percus = 0.0
    for apt in apartments:
        if apt.credit_balance > 0:
            resident = apt.residents[0] if apt.residents else None
            trop_percus_detail.append({
                'apt': f"{apt.block.name}-{apt.number}",
                'resident': resident.name if resident else '-',
                'montant': apt.credit_balance,
            })
            total_trop_percus += apt.credit_balance

    # Découvert bancaire (si trésorerie négative → passif courant)
    decouvert = max(0.0, -tresorerie_nette)

    total_passif_courant = total_trop_percus + decouvert
    total_passif_non_courant = 0.0

    # 106 — Fonds de roulement / Capitaux propres = Actif - Passif externe
    fonds_roulement = total_actif - total_passif_courant - total_passif_non_courant

    # Résultat de l'exercice sélectionné (hors immobilisations — ce sont des actifs, pas des charges)
    produits_exercice = sum(p.amount for p in year_payments)
    charges_exercice = sum(e.amount for e in year_charges)
    resultat_exercice = produits_exercice - charges_exercice

    # Résultats reportés = résultat cumulé hors exercice en cours (hors immobilisations)
    produits_anterieurs = sum(p.amount for p in all_payments if p.payment_date.year != year)
    charges_anterieures = sum(e.amount for e in all_charges if e.expense_date.year != year)
    resultats_reportes = produits_anterieurs - charges_anterieures

    # Recalcul capitaux propres pour équilibre bilanciel
    # CP = Fonds de roulement courant (106) + Résultats reportés (11x) + Résultat exercice (12x)
    # Pour un syndic: fonds_roulement courant = CP - résultat exercice - résultats reportés
    fonds_roulement_courant = fonds_roulement - resultat_exercice - resultats_reportes

    total_capitaux_propres = fonds_roulement_courant + resultats_reportes + resultat_exercice
    total_passif = total_capitaux_propres + total_passif_non_courant + total_passif_courant

    # ── ÉTAT DE RÉSULTAT ─────────────────────────────────────────────────────

    # Produits
    cotisations_encaissees = produits_exercice
    # Cotisations appelées théoriques (ce qui aurait dû être encaissé)
    cotisations_appelees = sum(apt.monthly_fee * 12 for apt in apartments)

    # Charges par catégorie SCE (immobilisations exclues — elles sont au bilan, pas en charges)
    charges_par_compte = {}
    for e in year_charges:
        cat = e.category or 'Autre'
        compte, libelle = CATEGORY_TO_SCE.get(cat, ('65x', "Autres charges d'exploitation"))
        key = (compte, libelle)
        charges_par_compte[key] = charges_par_compte.get(key, 0.0) + e.amount

    charges_sce = sorted([
        {'compte': k[0], 'libelle': k[1], 'montant': v}
        for k, v in charges_par_compte.items()
    ], key=lambda x: x['compte'])

    total_charges = sum(c['montant'] for c in charges_sce)
    total_produits = cotisations_encaissees
    resultat_net = total_produits - total_charges

    # ── FLUX DE TRÉSORERIE (mensuel pour l'exercice) ─────────────────────────
    flux_mensuel = []
    for m in range(1, 13):
        encaisse = sum(p.amount for p in year_payments if p.payment_date.month == m)
        depense = sum(e.amount for e in year_expenses if e.expense_date.month == m)
        flux_mensuel.append({
            'mois': m,
            'mois_label': ['', 'Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun',
                           'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc'][m],
            'encaissements': encaisse,
            'decaissements': depense,
            'flux_net': encaisse - depense,
        })

    # Solde cumulatif
    cumul = 0.0
    for f in flux_mensuel:
        cumul += f['flux_net']
        f['cumul'] = cumul

    # Taux de recouvrement de l'exercice
    taux_recouvrement = (cotisations_encaissees / cotisations_appelees * 100) if cotisations_appelees > 0 else 0

    return {
        # Méta
        'org': org,
        'year': year,
        'generated_at': datetime.now(),
        'nb_apartments': len(apartments),

        # Bilan — Actif
        'liquidites': liquidites,
        'total_creances': total_creances,
        'creances_detail': creances_detail,
        'total_immobilisations': total_immobilisations,
        'immos_detail': immos_detail,
        'total_actif_courant': total_actif_courant,
        'total_actif_non_courant': total_actif_non_courant,
        'total_actif': total_actif,

        # Bilan — Passif
        'fonds_roulement_courant': fonds_roulement_courant,
        'resultats_reportes': resultats_reportes,
        'resultat_exercice': resultat_exercice,
        'total_capitaux_propres': total_capitaux_propres,
        'total_trop_percus': total_trop_percus,
        'trop_percus_detail': trop_percus_detail,
        'decouvert': decouvert,
        'total_passif_courant': total_passif_courant,
        'total_passif_non_courant': total_passif_non_courant,
        'total_passif': total_passif,

        # État de résultat
        'cotisations_encaissees': cotisations_encaissees,
        'cotisations_appelees': cotisations_appelees,
        'taux_recouvrement': taux_recouvrement,
        'charges_sce': charges_sce,
        'total_charges': total_charges,
        'total_produits': total_produits,
        'resultat_net': resultat_net,

        # Flux de trésorerie
        'flux_mensuel': flux_mensuel,
        'tresorerie_nette': tresorerie_nette,
    }


@app.route('/etats-financiers')
@login_required
@admin_required
@subscription_required
def etats_financiers():
    org = current_organization()
    year = request.args.get('year', date.today().year, type=int)

    # Années disponibles (depuis la première dépense ou le premier paiement)
    all_payments = Payment.query.filter_by(organization_id=org.id).all()
    all_expenses = Expense.query.filter_by(organization_id=org.id).all()
    years_set = {p.payment_date.year for p in all_payments} | {e.expense_date.year for e in all_expenses}
    years_set.add(date.today().year)
    available_years = sorted(years_set, reverse=True)

    data = _compute_financial_data(org, year)

    return render_template(
        'financial_statements.html',
        user=current_user(),
        available_years=available_years,
        selected_year=year,
        **data
    )


@app.route('/etats-financiers/pdf')
@login_required
@admin_required
@subscription_required
def etats_financiers_pdf():
    """Génère le PDF des états financiers selon les normes SCE tunisiennes."""
    org = current_organization()
    year = request.args.get('year', date.today().year, type=int)
    data = _compute_financial_data(org, year)

    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    # ── Couleurs ───────────────────────────────────────────────────────────────
    BG_R, BG_G, BG_B         = 10, 14, 26      # Fond sombre
    HEADER_R, HEADER_G, HEADER_B = 17, 24, 39  # En-tête sections
    GREEN_R, GREEN_G, GREEN_B = 0, 200, 150     # Vert SyndicPro
    WHITE_R, WHITE_G, WHITE_B = 249, 250, 251
    MUTED_R, MUTED_G, MUTED_B = 156, 163, 175
    RED_R,   RED_G,   RED_B   = 239, 68,  68

    def page_header(title):
        pdf.set_fill_color(BG_R, BG_G, BG_B)
        pdf.rect(0, 0, 210, 297, 'F')
        pdf.set_fill_color(HEADER_R, HEADER_G, HEADER_B)
        pdf.rect(0, 0, 210, 28, 'F')
        pdf.set_xy(0, 5)
        pdf.set_text_color(GREEN_R, GREEN_G, GREEN_B)
        pdf.set_font('Helvetica', 'B', 16)
        pdf.cell(0, 8, 'SyndicPro', ln=False, align='C')
        pdf.set_xy(0, 13)
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(MUTED_R, MUTED_G, MUTED_B)
        pdf.cell(0, 5, _s(f"{org.name}  -  {title}  -  Exercice {year}"), ln=True, align='C')
        pdf.set_xy(0, 20)
        pdf.set_font('Helvetica', '', 7)
        pdf.cell(0, 4,
                 _s("Conforme au Systeme Comptable des Entreprises (SCE) - Loi n 96-112 du 30/12/1996"),
                 ln=True, align='C')
        pdf.ln(4)

    def section_title(text):
        pdf.set_fill_color(HEADER_R, HEADER_G, HEADER_B)
        pdf.set_text_color(GREEN_R, GREEN_G, GREEN_B)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(0, 8, _s(f"  {text}"), ln=True, fill=True)
        pdf.ln(1)

    def sub_title(text):
        pdf.set_text_color(GREEN_R, GREEN_G, GREEN_B)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(0, 6, _s(f"    {text}"), ln=True)

    def row(label, compte, montant, bold=False, indent=0, color=None):
        pdf.set_text_color(WHITE_R, WHITE_G, WHITE_B)
        if bold:
            pdf.set_font('Helvetica', 'B', 9)
        else:
            pdf.set_font('Helvetica', '', 8)
        spaces = '    ' * indent
        pdf.cell(20, 6, _s(f"  {compte}"), ln=False)
        pdf.cell(120, 6, _s(f"  {spaces}{label}"), ln=False)
        if color:
            pdf.set_text_color(*color)
        if montant >= 0:
            pdf.cell(40, 6, f"{montant:,.3f} DT", ln=True, align='R')
        else:
            pdf.set_text_color(RED_R, RED_G, RED_B)
            pdf.cell(40, 6, f"({abs(montant):,.3f}) DT", ln=True, align='R')
        pdf.set_text_color(WHITE_R, WHITE_G, WHITE_B)

    def separator():
        pdf.set_draw_color(55, 65, 81)
        pdf.set_line_width(0.3)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(1)

    def total_row(label, montant, bg=True):
        if bg:
            pdf.set_fill_color(31, 41, 55)
        pdf.set_text_color(GREEN_R, GREEN_G, GREEN_B)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(140, 7, _s(f"  {label}"), ln=False, fill=bg)
        color = (RED_R, RED_G, RED_B) if montant < 0 else (GREEN_R, GREEN_G, GREEN_B)
        pdf.set_text_color(*color)
        pdf.cell(40, 7, f"{montant:,.3f} DT", ln=True, align='R', fill=bg)
        pdf.ln(1)

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE 1 — BILAN
    # ══════════════════════════════════════════════════════════════════════════
    pdf.add_page()
    page_header("BILAN")

    col_w = 90  # largeur colonne (on va faire 2 colonnes)

    # On fait le bilan en séquentiel (plus lisible en PDF)
    section_title("ACTIF")

    sub_title("A — ACTIFS NON COURANTS")
    row("Immobilisations incorporelles (nettes)", "21x", 0.0, indent=1)
    if data['immos_detail']:
        for immo in data['immos_detail']:
            libelle = immo['description'].split('|')[0].replace('Bien:', '').strip()
            row(_s(libelle[:45]), "22x", immo['montant'], indent=2)
    else:
        row("Immobilisations corporelles (nettes)", "22x", 0.0, indent=1)
    row("Immobilisations financieres", "27x", 0.0, indent=1)
    separator()
    total_row("TOTAL ACTIFS NON COURANTS", data['total_actif_non_courant'])

    pdf.ln(2)
    sub_title("B — ACTIFS COURANTS")
    row("Créances copropriétaires (charges impayées)", "411", data['total_creances'], indent=1)
    row("Liquidités et équivalents (Banque/Caisse)", "511", data['liquidites'], indent=1)
    separator()
    total_row("TOTAL ACTIFS COURANTS", data['total_actif_courant'])

    pdf.ln(3)
    pdf.set_fill_color(GREEN_R, GREEN_G, GREEN_B)
    pdf.set_text_color(BG_R, BG_G, BG_B)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(0, 9, f"  TOTAL ACTIF  {data['total_actif']:,.3f} DT", ln=True, fill=True)
    pdf.ln(4)

    # ── PASSIF ────────────────────────────────────────────────────────────────
    section_title("PASSIF ET CAPITAUX PROPRES")

    sub_title("C — CAPITAUX PROPRES")
    row("Fonds de roulement courant", "106", data['fonds_roulement_courant'], indent=1)
    row("Résultats reportés (exercices antérieurs)", "11x", data['resultats_reportes'], indent=1)
    res_color = (GREEN_R, GREEN_G, GREEN_B) if data['resultat_exercice'] >= 0 else (RED_R, RED_G, RED_B)
    row("Résultat de l'exercice", "12x", data['resultat_exercice'], indent=1, bold=True, color=res_color)
    separator()
    total_row("TOTAL CAPITAUX PROPRES", data['total_capitaux_propres'])

    pdf.ln(2)
    sub_title("D — PASSIFS NON COURANTS")
    row("Emprunts et dettes financières long terme", "16x", 0.0, indent=1)
    separator()
    total_row("TOTAL PASSIFS NON COURANTS", data['total_passif_non_courant'])

    pdf.ln(2)
    sub_title("E — PASSIFS COURANTS")
    row("Fournisseurs et comptes rattachés", "401", 0.0, indent=1)
    row("Trop-perçus copropriétaires (avances)", "419", data['total_trop_percus'], indent=1)
    if data['decouvert'] > 0:
        row("Concours bancaires / Découvert", "56x", data['decouvert'], indent=1)
    separator()
    total_row("TOTAL PASSIFS COURANTS", data['total_passif_courant'])

    pdf.ln(3)
    pdf.set_fill_color(GREEN_R, GREEN_G, GREEN_B)
    pdf.set_text_color(BG_R, BG_G, BG_B)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(0, 9, f"  TOTAL PASSIF  {data['total_passif']:,.3f} DT", ln=True, fill=True)

    # Note de bas de page
    pdf.ln(6)
    pdf.set_text_color(MUTED_R, MUTED_G, MUTED_B)
    pdf.set_font('Helvetica', 'I', 7)
    pdf.cell(0, 4, "Note : Les montants en parentheses ( ) sont negatifs (deficit).", ln=True, align='C')
    pdf.cell(0, 4, _s(f"Arrete au {data['generated_at'].strftime('%d/%m/%Y')}  -  SyndicPro, {org.name}"), ln=True, align='C')

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE 2 — ÉTAT DE RÉSULTAT
    # ══════════════════════════════════════════════════════════════════════════
    pdf.add_page()
    page_header("ÉTAT DE RÉSULTAT")

    section_title(f"PRODUITS D'EXPLOITATION — Exercice {year}")
    row("Cotisations / charges communes encaissées", "706", data['cotisations_encaissees'], bold=True, indent=1)
    row("Autres produits d'exploitation", "74x", 0.0, indent=1)
    separator()
    total_row("TOTAL PRODUITS D'EXPLOITATION", data['total_produits'])

    pdf.ln(3)
    section_title(f"CHARGES D'EXPLOITATION — Exercice {year}")
    for c in data['charges_sce']:
        row(c['libelle'], c['compte'], c['montant'], indent=1)
    if not data['charges_sce']:
        row("Aucune charge enregistrée pour cet exercice", "—", 0.0, indent=1)
    separator()
    total_row("TOTAL CHARGES D'EXPLOITATION", data['total_charges'])

    pdf.ln(3)
    pdf.set_fill_color(*((17, 74, 57) if data['resultat_net'] >= 0 else (74, 17, 17)))
    pdf.set_text_color(GREEN_R if data['resultat_net'] >= 0 else RED_R,
                       GREEN_G if data['resultat_net'] >= 0 else RED_G,
                       GREEN_B if data['resultat_net'] >= 0 else RED_B)
    pdf.set_font('Helvetica', 'B', 11)
    label_res = "EXCÉDENT DE GESTION" if data['resultat_net'] >= 0 else "DÉFICIT DE GESTION"
    pdf.cell(0, 10,
             f"  {label_res} DE L'EXERCICE {year}  :  {data['resultat_net']:+,.3f} DT",
             ln=True, fill=True)

    # Indicateurs complémentaires
    pdf.ln(6)
    section_title("INDICATEURS COMPLÉMENTAIRES")
    pdf.set_font('Helvetica', '', 8)
    pdf.set_text_color(WHITE_R, WHITE_G, WHITE_B)
    indicators = [
        ("Nombre d'appartements", f"{data['nb_apartments']}"),
        ("Cotisations théoriques appelées (12 mois × redevance)", f"{data['cotisations_appelees']:,.3f} DT"),
        ("Taux de recouvrement", f"{data['taux_recouvrement']:.1f} %"),
        ("Trésorerie nette cumulée (tous exercices)", f"{data['tresorerie_nette']:,.3f} DT"),
        ("Créances copropriétaires (impayés)", f"{data['total_creances']:,.3f} DT"),
        ("Trop-perçus copropriétaires (avances)", f"{data['total_trop_percus']:,.3f} DT"),
    ]
    for label, value in indicators:
        pdf.set_fill_color(HEADER_R, HEADER_G, HEADER_B)
        pdf.cell(130, 6, f"  {label}", ln=False, fill=True)
        pdf.set_text_color(GREEN_R, GREEN_G, GREEN_B)
        pdf.cell(50, 6, value, ln=True, fill=True, align='R')
        pdf.set_text_color(WHITE_R, WHITE_G, WHITE_B)
        pdf.ln(0.5)

    # Note SCE
    pdf.ln(6)
    pdf.set_text_color(MUTED_R, MUTED_G, MUTED_B)
    pdf.set_font('Helvetica', 'I', 7)
    pdf.multi_cell(0, 4,
        "Référentiel : Système Comptable des Entreprises (SCE), Loi tunisienne n° 96-112 du 30/12/1996 "
        "et Décret n° 96-2459 portant approbation du cadre conceptuel de la comptabilité. "
        "Plan comptable : classes 1 à 7 conformes aux NCT. "
        "Principe de la partie double respecté (Total Actif = Total Passif).",
        align='J')
    pdf.ln(2)
    pdf.cell(0, 4, _s(f"Arrete au {data['generated_at'].strftime('%d/%m/%Y')}  -  SyndicPro, {org.name}"), ln=True, align='C')

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE 3 — TABLEAU DE FLUX DE TRÉSORERIE
    # ══════════════════════════════════════════════════════════════════════════
    pdf.add_page()
    page_header("TABLEAU DE FLUX DE TRÉSORERIE")

    section_title(f"FLUX MENSUELS — Exercice {year}")

    # En-tête tableau
    pdf.set_fill_color(HEADER_R, HEADER_G, HEADER_B)
    pdf.set_text_color(GREEN_R, GREEN_G, GREEN_B)
    pdf.set_font('Helvetica', 'B', 8)
    pdf.cell(25, 7, "  Mois", fill=True)
    pdf.cell(40, 7, "Encaissements", fill=True, align='R')
    pdf.cell(40, 7, "Décaissements", fill=True, align='R')
    pdf.cell(40, 7, "Flux net", fill=True, align='R')
    pdf.cell(40, 7, "Cumul", fill=True, align='R')
    pdf.ln()

    total_enc = total_dec = 0.0
    for i, f in enumerate(data['flux_mensuel']):
        fill = (i % 2 == 0)
        if fill:
            pdf.set_fill_color(17, 24, 39)
        else:
            pdf.set_fill_color(11, 18, 31)
        pdf.set_text_color(WHITE_R, WHITE_G, WHITE_B)
        pdf.set_font('Helvetica', '', 8)
        pdf.cell(25, 6, f"  {f['mois_label']} {year}", fill=True)
        pdf.cell(40, 6, f"{f['encaissements']:,.3f}", fill=True, align='R')
        pdf.cell(40, 6, f"{f['decaissements']:,.3f}", fill=True, align='R')
        net = f['flux_net']
        pdf.set_text_color(*((GREEN_R, GREEN_G, GREEN_B) if net >= 0 else (RED_R, RED_G, RED_B)))
        pdf.cell(40, 6, f"{net:+,.3f}", fill=True, align='R')
        cumul = f['cumul']
        pdf.set_text_color(*((GREEN_R, GREEN_G, GREEN_B) if cumul >= 0 else (RED_R, RED_G, RED_B)))
        pdf.cell(40, 6, f"{cumul:,.3f}", fill=True, align='R')
        pdf.ln()
        total_enc += f['encaissements']
        total_dec += f['decaissements']

    separator()
    pdf.set_fill_color(GREEN_R, GREEN_G, GREEN_B)
    pdf.set_text_color(BG_R, BG_G, BG_B)
    pdf.set_font('Helvetica', 'B', 9)
    pdf.cell(25, 7, "  TOTAL", fill=True)
    pdf.cell(40, 7, f"{total_enc:,.3f}", fill=True, align='R')
    pdf.cell(40, 7, f"{total_dec:,.3f}", fill=True, align='R')
    flux_total = total_enc - total_dec
    pdf.cell(40, 7, f"{flux_total:+,.3f}", fill=True, align='R')
    pdf.cell(40, 7, f"{flux_total:,.3f}", fill=True, align='R')
    pdf.ln(8)

    # Résumé trésorerie
    section_title("SYNTHÈSE DE TRÉSORERIE (tous exercices)")
    pdf.set_font('Helvetica', '', 8)
    pdf.set_text_color(WHITE_R, WHITE_G, WHITE_B)
    items = [
        ("Total encaissements cumulés (511)", f"{sum(p.amount for p in Payment.query.filter_by(organization_id=org.id).all()):,.3f} DT"),
        ("Total dépenses cumulées (401/511)", f"{sum(e.amount for e in Expense.query.filter_by(organization_id=org.id).all()):,.3f} DT"),
        ("Solde trésorerie nette", f"{data['tresorerie_nette']:,.3f} DT"),
    ]
    for label, value in items:
        pdf.set_fill_color(HEADER_R, HEADER_G, HEADER_B)
        pdf.cell(130, 6, f"  {label}", ln=False, fill=True)
        pdf.set_text_color(GREEN_R if data['tresorerie_nette'] >= 0 else RED_R,
                           GREEN_G if data['tresorerie_nette'] >= 0 else RED_G,
                           GREEN_B if data['tresorerie_nette'] >= 0 else RED_B)
        pdf.cell(50, 6, value, ln=True, fill=True, align='R')
        pdf.set_text_color(WHITE_R, WHITE_G, WHITE_B)
        pdf.ln(0.5)

    pdf.ln(6)
    pdf.set_text_color(MUTED_R, MUTED_G, MUTED_B)
    pdf.set_font('Helvetica', 'I', 7)
    pdf.cell(0, 4, _s(f"Document genere le {data['generated_at'].strftime('%d/%m/%Y')}  -  SyndicPro, {org.name}"), ln=True, align='C')
    pdf.cell(0, 4, "Ce document est produit a titre informatif et de gestion interne. Il ne remplace pas un bilan certifie par un expert-comptable agree.", ln=True, align='C')

    # ── Export PDF ────────────────────────────────────────────────────────────
    pdf_bytes = pdf.output()
    output = io.BytesIO(pdf_bytes)
    output.seek(0)
    filename = f"SyndicPro_{org.name}_EtatsFinanciers_{year}_{datetime.now().strftime('%Y%m%d')}.pdf"
    return send_file(
        output,
        download_name=filename,
        as_attachment=True,
        mimetype='application/pdf'
    )
