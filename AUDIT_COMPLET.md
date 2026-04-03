# AUDIT COMPLET — SyndicPro V2
**Date :** 3 avril 2026  
**Méthode :** Revue de code exhaustive (sécurité + fonctionnel + métier + UX + performance)  
**Fichiers analysés :** tous les fichiers Python, tous les templates HTML, requirements.txt, .env, config

---

## RÉSUMÉ EXÉCUTIF

| Domaine | Niveau | Nombre | Délai |
|---------|--------|--------|-------|
| Sécurité | CRITIQUE | 3 | Immédiat (P0) |
| Sécurité | ÉLEVÉ | 8 | < 1 semaine (P1) |
| Sécurité | MOYEN | 6 | < 1 mois (P2) |
| Fonctionnel | CRITIQUE | 4 | Avant prod |
| Fonctionnel | HAUTE | 7 | < 1 semaine (P1) |
| Fonctionnel | MOYENNE | 10 | < 1 mois (P2) |
| Fonctionnel | BASSE | 9 | Quand possible |
| **TOTAL** | | **47** | |

---

# PARTIE 1 — AUDIT SÉCURITÉ

## CRITIQUE SÉCURITÉ (P0 — Corriger avant tout push)

### CRIT-001 — Secrets exposés dans .env
- **Fichier :** `.env` lignes 1-2
- **Problème :** `SUPERADMIN_PASSWORD=SuperAdmin2024!` et `SECRET_KEY` en clair — potentiellement versionnés sur GitHub
- **Impact :** Accès total à toutes les organisations, forgerie de session
- **Fix :** Regénérer les deux valeurs, les mettre uniquement dans les variables d'environnement Render. Ne jamais commiter `.env`.

### CRIT-002 — Debug mode activé en production
- **Fichier :** `app.py` ligne 39
- **Problème :** `app.run(debug=True, host='0.0.0.0')` → console Werkzeug interactive publique
- **Impact :** Exécution de code Python arbitraire sur le serveur par n'importe qui
- **Fix :**
```python
app.run(debug=False, host='127.0.0.1', port=int(os.environ.get('PORT', 5000)))
```

### CRIT-003 — Mot de passe superadmin faible
- **Fichier :** `models.py` ligne 253
- **Problème :** Fallback `'changez-moi'` + `SuperAdmin2024!` brute-forçable en quelques secondes
- **Fix :**
```python
password = os.environ.get('SUPERADMIN_PASSWORD')
if not password or len(password) < 16:
    raise RuntimeError("SUPERADMIN_PASSWORD obligatoire et >= 16 caractères")
superadmin.set_password(password)
```

---

## ÉLEVÉ SÉCURITÉ (P1 — < 1 semaine)

### HIGH-004 — Pas de CSRF sur /ai/chat (POST JSON)
- **Fichier :** `routes/ai.py` ligne 53
- **Problème :** Route POST JSON sans vérification CSRF → injection de prompts via lien piégé
- **Fix :** Vérifier le header `X-CSRFToken` ou ajouter `@csrf_protect`

### HIGH-005 — Validation montants insuffisante (paiements)
- **Fichier :** `routes/payments.py` lignes 18-38
- **Problème :** Montants négatifs, nuls, excessifs, dates futures acceptés sans validation
- **Fix :**
```python
if amount <= 0 or amount > 1000000:
    flash('Montant invalide', 'danger')
if payment_date > date.today():
    flash('Date future non autorisée', 'danger')
```

### HIGH-006 — Montants négatifs acceptés (dépenses, appartements)
- **Fichiers :** `routes/expenses.py` ligne 9, `routes/apartments.py` ligne 25
- **Problème :** `monthly_fee` et `amount` peuvent être 0, négatifs ou excessifs
- **Fix :** Créer `validate_amount(min=0.01, max=9999999.99)` dans `utils.py`

### HIGH-007 — Clés API en clair en base de données
- **Fichiers :** `models.py` lignes 22-25, `routes/konnect.py` ligne 37
- **Problème :** `konnect_api_key`, `whatsapp_token` stockés en texte clair
- **Fix :** Chiffrement Fernet avec `ENCRYPTION_KEY` comme variable d'environnement

### HIGH-008 — Prompt injection IA + exposition données personnelles
- **Fichier :** `routes/ai.py` lignes 8-44
- **Problème :** Contexte IA injecte noms et dettes de tous les résidents → jailbreak possible
- **Fix :** Contexte anonymisé (agrégats uniquement), blacklist mots-clés, `max_tokens` à 512

### HIGH-009 — Pas de limite taille requêtes
- **Fichiers :** `core.py`, `routes/tickets.py` ligne 19
- **Problème :** Pas de `MAX_CONTENT_LENGTH` → envoi de 100 MB → DoS possible
- **Fix :**
```python
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024
subject = request.form.get('subject', '')[:200]
message = request.form.get('message', '')[:5000]
```

### HIGH-010 — XSS stockée potentielle dans tickets
- **Fichier :** `templates/ticket_detail.html` lignes 64, 73
- **Problème :** Aucun sanitize à l'écriture — si `|safe` est ajouté un jour, XSS stockée immédiate
- **Fix :** Installer `bleach` et nettoyer à l'insertion

### HIGH-011 — Email non normalisé à la création d'utilisateur
- **Fichier :** `routes/users.py` ligne 16
- **Problème :** Email sans `.lower()` → bypass de la vérification d'unicité
- **Fix :** `email = request.form.get('email', '').strip().lower()`

---

## MOYEN SÉCURITÉ (P2 — < 1 mois)

### MED-012 — Rate limiting insuffisant sur APIs
- **Fichiers :** `routes/ai.py`, `routes/dashboard.py`, `routes/konnect.py`
- **Problème :** `/ai/chat`, `/api/dashboard_data`, `/konnect/generate-link` sans rate limit
- **Fix :** `@limiter.limit("10 per minute")` + Redis pour persistance multi-workers

### MED-013 — Politique mot de passe incohérente
- **Fichiers :** `routes/users.py` ligne 22, `routes/auth.py`
- **Problème :** Admin peut créer un user avec 6 chars (vs 8 au register). Pas de blacklist.
- **Fix :** 12 chars minimum partout + `zxcvbn` pour mots de passe courants

### MED-014 — Gestion de session insuffisante
- **Fichiers :** `utils.py`, `core.py`
- **Problème :** `SameSite='Lax'` (pas Strict), pas de révocation forcée des sessions
- **Fix :** `SameSite='Strict'` + modèle `SessionToken` en DB

### MED-015 — Erreurs techniques dans les logs
- **Fichier :** `routes/payments.py` ligne 81
- **Problème :** `print(f"ERREUR: {str(e)}")` expose des traces techniques
- **Fix :** `app.logger.error(..., exc_info=True)` + logging structuré

### MED-016 — En-têtes HTTP de sécurité manquants
- **Fichier :** `core.py` (à ajouter)
- **Fix :**
```python
@app.after_request
def set_security_headers(response):
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    if not app.debug:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response
```

### MED-017 — Dépendances non verrouillées
- **Fichier :** `requirements.txt`
- **Problème :** `anthropic>=0.88.0`, `fpdf2>=2.8.0` sans borne supérieure
- **Fix :** Fixer versions exactes + ajouter `bleach==6.0.0` et `cryptography==41.0.7`

---

# PARTIE 2 — AUDIT FONCTIONNEL & MÉTIER

## CRITIQUE FONCTIONNEL (P0 — Avant mise en prod avec vraies données)

### SECURITY-F001 — Multi-tenant bypass sur Konnect success
- **Fichier :** `routes/konnect.py` ligne 110
- **Problème :** Recherche `KonnectPayment` par `payment_ref` sans filtrer par `organization_id` → admin d'une org peut accéder aux données financières d'une autre
- **Fix :**
```python
kp = KonnectPayment.query.filter_by(
    konnect_payment_ref=payment_ref,
    organization_id=current_organization().id
).first()
```

### SECURITY-F002 — Pas de webhook sécurisé Konnect
- **Fichier :** `routes/konnect.py` (aucun webhook serveur)
- **Problème :** Callbacks Konnect = redirections navigateur sans signature HMAC → URL rejouable pour valider de faux paiements
- **Fix :** Route `/konnect/webhook` POST avec validation `X-Konnect-Signature: HMAC-SHA256`

### BUG-F001 — Doublons de paiement possibles (pas d'idempotence)
- **Fichiers :** `routes/payments.py` lignes 79-82, `routes/konnect.py`
- **Problème :** Si callback Konnect rejoué → 2e Payment créé pour le même mois
- **Fix :** Vérifier unicité `(apartment_id, month_paid)` AVANT d'initier la transaction

### BUG-F003 — Cascade delete sur Apartment = perte définitive des paiements
- **Fichier :** `models.py` ligne 101
- **Problème :** `cascade='all, delete-orphan'` → supprimer un appartement supprime tout son historique de paiements
- **Impact :** Perte irréversible de données financières, problème légal
- **Fix :** `cascade='save-update, merge'` + colonne `is_archived` pour soft delete

---

## HAUTE FONCTIONNEL (P1 — < 1 semaine)

### BUG-F002 — Credit_balance incohérent après changement de redevance
- **Fichier :** `models.py` ligne 98
- **Problème :** Crédit stocké en DT absolu. Changement de `monthly_fee` rend le crédit incohérent.
- **Fix :** Avertissement à l'admin lors du changement si crédit > 0

### BUG-F004 — Pas de grace period à l'expiration d'abonnement
- **Fichier :** `models.py` lignes 46-49
- **Problème :** Accès coupé pile à `end_date`, même si l'admin renouvelle 5 minutes après
- **Fix :** `return datetime.utcnow() > (self.end_date + timedelta(hours=24))`

### BUG-F007 — Vérification API Konnect silencieuse en cas d'erreur
- **Fichier :** `routes/konnect.py` lignes 130-145
- **Problème :** `except Exception: pass` → paiements bloqués sans alerte
- **Fix :** `app.logger.error(...)` + flash informatif à l'admin

### BUG-F009 — Notification WhatsApp silencieuse si envoi échoue
- **Fichier :** `routes/payments.py` lignes 114-118
- **Problème :** Erreur WhatsApp ignorée → résident croit n'avoir pas payé
- **Fix :** Logger + flash "(notification non envoyée)" si échec

### BUG-F006 — Pas de rappel avant expiration d'essai gratuit
- **Fichier :** `routes/auth.py` ligne 99
- **Problème :** Admin découvre l'expiration en perdant l'accès, sans avertissement préalable
- **Fix :** Alerte flash 7 jours avant expiration dans `before_request`

### LOGIC-F004 — Trésorerie groupée par date, pas par mois couvert
- **Fichier :** `routes/reports.py` lignes 27-30
- **Problème :** 3 mois payés en une fois = tout affiché dans le mois de paiement
- **Fix :** Vue secondaire groupée par `month_paid` (accrual basis)

### PERF-F002 — Requêtes N+1 sur le calcul des impayés
- **Fichier :** `routes/apartments.py` lignes 47-50
- **Problème :** 1 requête SQL par appartement. 100 appartements = 100 requêtes.
- **Fix :** Pré-charger tous les paiements en une requête, calculer en mémoire

---

## MOYENNE FONCTIONNEL (P2 — < 1 mois)

### BUG-F008 — Arrondi millimes Konnect imprécis
- **Fichier :** `routes/konnect.py` ligne 39 — `int(round(amount_dt * 1000))` peut créer 1 millime d'écart

### BUG-F010 — Numéros de téléphone non validés
- **Fichier :** `models.py` ligne 74 — format libre, `_normalize_phone()` peut produire des numéros invalides
- **Fix :** Valider format `+216 XXXXXXXX` ou `0XXXXXXX` à la saisie

### BUG-F011 — Pas de gestion d'erreur lisible si ANTHROPIC_API_KEY absente
- **Fichier :** `routes/ai.py` lignes 83-88 — erreur JSON brute affichée au user
- **Fix :** Message explicatif à l'affichage de `/ai`

### BUG-F012 — Relances WhatsApp sans mention du crédit disponible
- **Fichier :** `routes/automation.py` lignes 46-94
- **Fix :** Inclure `apt.credit_balance` dans le message de relance

### BUG-F013 — Rapport PDF toujours du mois courant
- **Fichier :** `routes/automation.py` ligne 99
- **Fix :** Paramètre GET `?month=2025-01`

### LOGIC-F002 — Relances non idempotentes (double envoi possible)
- **Fichier :** `routes/automation.py` — double-clic = 2 séries de messages
- **Fix :** Vérifier si relance déjà envoyée ce mois

### LOGIC-F003 — Registre d'accès sans validation cohérente
- **Fichier :** `routes/access.py` — sortie possible sans entrée préalable

### PERF-F001 — Sum des paiements en Python au lieu de SQL
- **Fichier :** `routes/dashboard.py` ligne 21
- **Fix :** `db.session.query(db.func.sum(Payment.amount)).filter_by(...).scalar() or 0`

### PERF-F003 — Boucles O(apts × mois × paiements) dans les rapports
- **Fichier :** `routes/reports.py` lignes 22-45
- **Fix :** `GROUP BY (apartment_id, year, month)` en SQL

### BUG-F014 — Colonne "Crédit Utilisé" absente dans feuille Tableau Comptable
- **Fichier :** `routes/reports.py` lignes 112-166

---

## BASSE FONCTIONNEL

### UX-001 — Messages flash limités à 2 (`messages[:2]` dans `base.html:603`)
### UX-002 — Input montant sans `min="0.01"` côté client dans les formulaires
### UX-003 — Pas de page "Détails de mon organisation" pour l'admin
### UX-004 — Page `/subscription` peut crasher si `org.subscription` est None
### LOGIC-F001 — Un résident = un seul appartement (limitation modèle)
### LOGIC-F005 — Politique mot de passe incohérente (6/8/8 chars selon la route)
### BUG-F016 — Suppression user : impossible de savoir qui avait payé (paiements liés à Apartment)
### PERF-F004 — Pas de pagination sur les listes de paiements/dépenses (tout en mémoire)

---

## POINTS POSITIFS

| Module | Ce qui fonctionne bien |
|--------|------------------------|
| Multi-tenant | Filtres `organization_id` appliqués partout (sauf Konnect success) |
| Crédits | Logique crédit automatique bien pensée et bien affichée |
| Dashboard | KPIs clairs (taux de recouvrement, solde, impayés) |
| Konnect | Redirection + vérification API côté serveur |
| WhatsApp | Intégration fonctionnelle avec fallback gracieux |
| Export Excel | 4 feuilles complètes |
| Session | Timeout 30 min + cookies sécurisés (Secure, HttpOnly) |
| Rate limiting | Login et register protégés (5/min, 3/min) |
| UX/UI | Design moderne, responsive, Bootstrap 5 propre |
| Tests | 18 tests pytest — 18/18 verts |
| Architecture | Modulaire, propre, maintenable |

---

# PLAN DE CORRECTION CONSOLIDÉ

## P0 — Avant tout push / avant mise en prod
- [ ] CRIT-001 : Regénérer SECRET_KEY + SUPERADMIN_PASSWORD — vérifier `.gitignore`
- [ ] CRIT-002 : `debug=False` dans `app.py`
- [ ] CRIT-003 : `RuntimeError` si `SUPERADMIN_PASSWORD` absent ou < 16 chars
- [ ] SECURITY-F001 : Filtrer `KonnectPayment` par `organization_id`
- [ ] SECURITY-F002 : Implémenter webhook Konnect avec signature HMAC
- [ ] BUG-F001 : Vérifier unicité `(apartment_id, month_paid)` avant initiation Konnect
- [ ] BUG-F003 : Retirer `cascade delete` sur `Apartment.payments` + soft delete

## P1 — Cette semaine
- [ ] HIGH-004 : CSRF sur `/ai/chat`
- [ ] HIGH-005 : Validation montants paiements (négatif, futur, excessif)
- [ ] HIGH-006 : Validation montants dépenses/appartements
- [ ] HIGH-007 : Chiffrement clés API (Fernet)
- [ ] HIGH-008 : Contexte IA anonymisé
- [ ] HIGH-009 : `MAX_CONTENT_LENGTH` + limites texte tickets
- [ ] HIGH-010 : Sanitize `bleach` sur tickets
- [ ] HIGH-011 : `.lower()` sur emails à la création user
- [ ] BUG-F002 : Avertissement changement redevance si crédit existant
- [ ] BUG-F004 : Grace period 24h expiration abonnement
- [ ] BUG-F007 : Logger erreurs Konnect + alerte admin
- [ ] BUG-F009 : Logger erreurs WhatsApp + flash informatif
- [ ] LOGIC-F004 : Vue trésorerie par `month_paid`
- [ ] PERF-F002 : Corriger N+1 calcul impayés

## P2 — Ce mois
- [ ] MED-012 : Rate limit sur APIs + Redis
- [ ] MED-013 : Politique mot de passe harmonisée
- [ ] MED-014 : `SameSite=Strict` + révocation sessions
- [ ] MED-015 : Logging structuré
- [ ] MED-016 : En-têtes HTTP sécurité
- [ ] MED-017 : Verrouiller versions `requirements.txt`
- [ ] BUG-F006 : Rappel 7 jours avant expiration essai
- [ ] BUG-F010 : Validation format téléphone
- [ ] BUG-F011 : Message d'erreur IA lisible sans clé API
- [ ] BUG-F013 : PDF rapport flexible par mois
- [ ] LOGIC-F002 : Idempotence des relances WhatsApp
- [ ] PERF-F001 : Sum SQL au lieu de Python
- [ ] PERF-F003 : `GROUP BY` SQL dans rapports
- [ ] UX-001 : Messages flash `[:3]` au lieu de `[:2]`
- [ ] UX-002 : `min="0.01"` sur inputs montants

---

# PARTIE 3 — ÉTATS FINANCIERS (à implémenter)

> Fichiers : `routes/financial_statements.py` + `templates/financial_statements.html`  
> Routes : `/etats-financiers?year=YYYY` (consultation) + `/etats-financiers/pdf?year=YYYY` (téléchargement)  
> Référentiel : SCE — Loi n° 96-112 du 30/12/1996, Décret n° 96-2459, Plan comptable NCT classes 1-7

- [x] Bilan comptable (Actif / Passif) selon plan comptable tunisien
- [x] État de résultat (Produits 706 / Charges 612-641)
- [x] Tableau de flux de trésorerie mensuel avec cumul
- [x] Export PDF 3 pages (Bilan, État résultat, Flux trésorerie)
- [x] Consultation en ligne par l'admin avec 4 onglets
- [x] Graphiques (répartition charges, flux mensuels)
- [x] Annexes (détail créances 411, trop-perçus 419)
- [x] Note de conformité SCE + conseil OECT
- [x] Sélection d'exercice (toutes les années disponibles)
