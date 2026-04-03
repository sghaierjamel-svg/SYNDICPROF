# 🗓️ PLAN SYNDICPRO — JOUR PAR JOUR (MIS À JOUR)
## De la V1 à la V2 complète avec Agent IA WhatsApp + **Contrôle d'Accès Badges**
> **Pour Jamel — rédigé comme pour un enfant de 12 ans**
> Mis à jour : 31 mars 2026

---

## 📌 COMMENT UTILISER CE PLAN

- Lis **seulement le jour où tu es**
- Chaque action a une **case à cocher** → coche quand c'est fait ✅
- Si tu bloques → reviens sur Claude et dis **"Je suis au Jour X, étape Y, j'ai ce problème"**
- Ne saute pas d'étape — chaque jour prépare le suivant
- Certains jours sont courts (30 min), d'autres plus longs (2-3h)

---

## 🗂️ VUE D'ENSEMBLE

| Phase | Jours | Ce qu'on fait |
|-------|-------|---------------|
| 🔧 PHASE 0 — Installation | Jour 1 | Installer tous les outils |
| 🔴 PHASE 1 — Sécurité V1 | Jours 2-3 | Corriger les failles critiques |
| 🎨 PHASE 2 — UX V1 | Jours 4-7 | Améliorer l'interface existante |
| 🏗️ PHASE 3 — Refactoring V1 | Jours 8-10 | Réorganiser le code |
| 🚀 PHASE 4 — V2 Setup | Jours 11-14 | Créer les fondations V2 |
| 💻 PHASE 5 — V2 Core | Jours 15-25 | Coder les modules principaux |
| 🔑 **PHASE 5B — Badges** | **Jours 26-30** | **Module contrôle d'accès badges** |
| 🤖 PHASE 6 — Agent IA | Jours 31-36 | Intégrer Claude dans l'app |
| 💬 PHASE 7 — WhatsApp | Jours 37-43 | Connecter WhatsApp |
| 💳 PHASE 8 — Konnect | Jours 44-47 | Paiement en ligne |
| ⚙️ PHASE 9 — Automatisation | Jours 48-52 | Relances + suspension auto badges |
| 🧪 PHASE 10 — Tests | Jours 53-58 | Tout tester |
| 🚀 PHASE 11 — Lancement | Jours 59-65 | Mettre en ligne et vendre |

**Durée totale estimée : 65 jours (environ 2 mois et demi)**

---

# 🔧 PHASE 0 — INSTALLATION
## Jour 1 — Installer tous les outils (durée : 1h30)

> **Objectif du jour :** Avoir tout installé et prêt à coder.
> Tu ne codes rien aujourd'hui. Tu installes seulement.

### ✅ Étape 1 — S'abonner à Claude Pro (10 min)

1. Ouvre **claude.ai** dans ton navigateur
2. Clique sur **"Upgrade"** en haut à droite
3. Choisis le plan **Pro — 20$/mois**
4. Paye avec ta carte
5. ✅ Confirme que tu vois "Pro" dans ton compte

> 💡 Pourquoi ? Claude Code est inclus dans le plan Pro. Sans ça, tu ne peux pas aller plus loin.

### ✅ Étape 2 — Installer Node.js (15 min)

1. Va sur **nodejs.org**
2. Clique sur le gros bouton vert **"LTS"**
3. Télécharge et installe
4. Vérifie : `node --version`
✅ Tu dois voir quelque chose comme `v20.11.0`

### ✅ Étape 3 — Installer Claude Code (5 min)

```bash
npm install -g @anthropic-ai/claude-code
claude --version
```

### ✅ Étape 4 — Installer Python (10 min)

1. Va sur **python.org/downloads**
2. Télécharge **Python 3.11**
3. **IMPORTANT** : coche **"Add Python to PATH"**
4. Vérifie : `python --version`

### ✅ Étape 5 — Installer Git (10 min)

```bash
git --version
```

### ✅ Étape 6 — Cloner ton projet V1 (10 min)

```bash
cd Desktop
git clone https://github.com/sghaierjamel-svg/SYNDICPROF1.git
cd SYNDICPROF1
```

### ✅ Étape 7 — Tester Claude Code (10 min)

```bash
claude
```
Tape : `Bonjour ! Dis-moi combien de lignes fait le fichier app.py`
✅ Il doit répondre environ 1415 lignes.

### ✅ Étape 8 — Créer le repo GitHub V2 (10 min)

1. Va sur **github.com**
2. Clique **+** → "New repository"
3. Nom : `SYNDICPROV2` — **Private**
4. Coche "Add a README file"
✅ Note l'URL : `https://github.com/sghaierjamel-svg/SYNDICPROV2`

---

# 🔴 PHASE 1 — SÉCURITÉ V1
## Jour 2 — Corriger la sécurité critique (durée : 1h)

> **Objectif :** Protéger ton site. Le mot de passe superadmin est visible sur GitHub !

### ✅ Étape 1 — Ouvrir Claude Code

```bash
cd Desktop/SYNDICPROF1
claude
```

### ✅ Étape 2 — Contexte du projet

Copie-colle :
```
Je travaille sur SyndicPro, mon application Flask de gestion de syndic tunisien.
Le site est live sur syndicpro.tn et déployé sur Render.
Je ne sais pas coder. Explique chaque modification en français simple.
Demande-moi confirmation avant toute modification importante.
Ne touche à rien tant que je n'ai pas dit OK.
```

### ✅ Étape 3 — Corriger la sécurité

```
Corrige ces problèmes de sécurité dans app.py, dans cet ordre :

PROBLÈME 1 — Mot de passe superadmin visible sur GitHub :
- Cherche "SuperAdmin2024!" dans app.py
- Remplace par os.environ.get('SUPERADMIN_PASSWORD', 'changez-moi')
- Crée un fichier .env avec : SUPERADMIN_PASSWORD=SuperAdmin2024!
- Crée un fichier .env.example avec : SUPERADMIN_PASSWORD=votre_mot_de_passe_ici
- Ajoute .env dans .gitignore

PROBLÈME 2 — Trop de tentatives de connexion :
- Installe Flask-Limiter
- Ajoute une limite de 5 tentatives par minute sur /login

PROBLÈME 3 — Suppression sans protection :
- Les routes /payment/delete et /expense/delete sont en GET
- Transforme-les en POST avec confirmation JavaScript

PROBLÈME 4 — Erreurs techniques visibles :
- Remplace flash(f'Erreur: {str(e)}') par des messages génériques
- Log l'erreur réelle dans la console (print) mais n'affiche pas à l'utilisateur

Montre-moi le code AVANT de modifier.
```

### ✅ Étape 4 — Mettre à jour sur Render

1. Va sur **render.com** → ton service SyndicPro
2. Clique **"Environment"**
3. Ajoute : `SUPERADMIN_PASSWORD` et `SECRET_KEY`
4. Clique **"Save Changes"**

### ✅ Étape 5 — Pusher sur GitHub

```
Git commit "security: fix critical vulnerabilities" et git push
```

---

## Jour 3 — Sécurité complémentaire (durée : 45 min)

### ✅ Prompt :

```
Continue les corrections de sécurité :

1. TIMEOUT DE SESSION :
   - Déconnexion automatique après 30 minutes d'inactivité

2. VALIDATION MOT DE PASSE FORT :
   - Minimum 8 caractères, 1 chiffre, 1 majuscule sur /register

3. PROTECTION CSRF :
   - Installe Flask-WTF
   - Ajoute protection CSRF sur tous les formulaires POST

Commit "security: session timeout + strong password + CSRF"
```

---

# 🎨 PHASE 2 — AMÉLIORATION UX V1
## Jour 4 — Corriger les bugs visuels (durée : 1h)

### ✅ Prompt :

```
Corrige ces problèmes visuels dans SyndicPro :

1. BUG PAGE /register : affiche les 3 tarifs : 30 DT / 50 DT / 75 DT

2. NAVBAR AVANT CONNEXION :
   - Les liens tableau de bord, tickets, export ne doivent apparaître QUE si connecté

3. TROP DE MESSAGES FLASH :
   - Maximum 2 messages lors d'un paiement
```

---

## Jour 5 — Navbar et profil résident (durée : 1h30)

### ✅ Prompt :

```
Améliore la navigation et ajoute le profil résident :

1. NAVBAR : nom de l'utilisateur + menu déroulant avec "Mon Profil" et "Déconnexion"

2. PAGE PROFIL (/profile) :
   - Section changer le mot de passe
   - Section changer l'email

Routes : GET /profile, POST /profile/change-password, POST /profile/change-email
```

---

## Jour 6 — Dashboard résident (durée : 1h)

### ✅ Prompt :

```
Améliore le tableau de bord du résident :

- Badge vert "✅ À jour" ou rouge "❌ X mois impayés"
- Informations de l'appartement (numéro, bloc, redevance, crédit)
- Historique des 6 derniers mois
- Actions rapides (créer ticket, voir tickets)
```

---

## Jour 7 — Page d'accueil (durée : 2h)

### ✅ Prompt :

```
Refais la page d'accueil de SyndicPro pour vendre au marché tunisien.

SECTION HERO :
Titre : "Fini les impayés qui traînent. SyndicPro relance, encaisse et suspend
l'accès automatiquement."
Sous-titre : "La solution complète pour les syndics tunisiens. Essai gratuit 30 jours."
Stats : "120+ syndics actifs" | "94% taux de recouvrement" | "Sans carte bancaire"

SECTION 6 FONCTIONNALITÉS :
- Gestion appartements
- Encaissements
- Alertes automatiques
- 🔑 Contrôle d'accès badges (NOUVEAU — à mettre en avant avec badge "Exclusif")
- Tableau comptable
- Rapports

SECTION TARIFICATION (3 cartes) :
- Starter : 30 DT/mois — Moins de 20 appartements
- Pro : 50 DT/mois — 20 à 75 appartements (badge "Populaire")
- Enterprise : 75 DT/mois — Plus de 75 appartements

SECTION PREUVE SOCIALE :
Ajoute un encadré : "🔑 SyndicPro est la seule plateforme en Tunisie qui coupe 
automatiquement l'accès à l'ascenseur en cas d'impayés — et le réactive dès que 
le résident paie en ligne."

Design Bootstrap 5. Couleurs : bleu foncé (#1e3a5f) et vert (#28a745).
```

---

# 🏗️ PHASE 3 — REFACTORING V1
## Jour 8 — Préparer le refactoring (durée : 30 min)

```bash
git checkout -b backup-v1-before-refactor
git push origin backup-v1-before-refactor
git checkout main
```

---

## Jour 9 — Refactoring Flask Blueprints (durée : 2h)

### ✅ Prompt :

```
Refactorise app.py (1400 lignes) en Flask Blueprints.

Structure :
syndicpro/
├── app.py
├── models.py
├── utils.py
├── routes/
│   ├── auth.py
│   ├── dashboard.py
│   ├── apartments.py
│   ├── payments.py
│   ├── residents.py
│   ├── tickets.py
│   └── superadmin.py
└── templates/

Procède fichier par fichier. Vérifie après chaque fichier que l'app démarre sans erreur.
RÈGLE : aucune fonctionnalité ne doit être perdue.
```

---

## Jour 10 — Vérification post-refactoring (durée : 1h)

### ✅ Prompt :

```
Vérifie que tout fonctionne après le refactoring :
- Lance l'app en local
- Teste les routes principales
- Commit "refactor: Flask Blueprints complete V1.2" et push
```

---

# 🚀 PHASE 4 — FONDATIONS V2
## Jour 11 — Créer le projet V2 (durée : 1h30)

```bash
cd Desktop
mkdir syndicpro-v2
cd syndicpro-v2
claude
```

### ✅ Prompt :

```
Crée le projet SyndicPro V2 from scratch.

STACK TECHNIQUE :
- Backend : FastAPI + SQLAlchemy 2.0 (async) + Alembic
- Base de données : PostgreSQL
- Auth : JWT (access token 1h + refresh token 30j)
- Frontend : HTML5 + Jinja2 + Tailwind CSS + Alpine.js + Chart.js

STRUCTURE :
syndicpro-v2/
├── main.py
├── requirements.txt
├── .env.example
├── .gitignore
├── alembic.ini
├── alembic/versions/
└── app/
    ├── config.py
    ├── database.py
    ├── models/
    ├── routers/
    ├── services/
    └── templates/

Lance "uvicorn main:app --reload" et vérifie que l'app démarre.
```

---

## Jour 12 — Créer tous les modèles (durée : 1h30)

### ✅ Prompt :

```
Crée tous les modèles SQLAlchemy pour SyndicPro V2.

Dans app/models/, crée ces fichiers :

organization.py : id, name, slug, email, phone, address, is_active, created_at,
logo_url, whatsapp_number, admin_whatsapp

subscription.py : id, organization_id, plan, status, start_date, end_date,
monthly_price, max_apartments

user.py : id, organization_id, email, name, password_hash, role, apartment_id,
phone, whatsapp_number, language, created_at, last_login

apartment.py : id, organization_id, block_id, number, floor, monthly_fee,
credit_balance, created_at, notes

block.py : id, organization_id, name, floor_count

payment.py : id, organization_id, apartment_id, amount, payment_date,
month_paid, description, payment_method, receipt_image_url, credit_used,
recorded_by, created_at

expense.py : id, organization_id, amount, expense_date, category, description,
receipt_url, created_at

ticket.py : id, organization_id, apartment_id, user_id, subject, message,
status, priority, admin_response, created_at, updated_at

whatsapp.py :
- whatsapp_conversations : id, organization_id, phone_number, user_id,
  role, last_message_at, context_json, created_at
- whatsapp_messages : id, conversation_id, direction, message_type,
  content, media_url, wa_message_id, status, created_at

konnect_payment.py : id, payment_ref, apartment_id, organization_id,
months_json, amount, status, created_at, paid_at

ai_memory.py : id, organization_id, user_id, channel, messages_json,
summary, last_updated

🔑 badge.py (NOUVEAU) :
- Table badges :
  id, organization_id, apartment_id, resident_id,
  badge_uid (unique), label, statut (actif/suspendu/perdu/révoqué),
  motif_suspension, date_activation, date_suspension,
  suspendu_par (gestionnaire/IA_automatique), created_at

- Table access_logs :
  id, badge_id, organization_id, timestamp,
  point_acces (Ascenseur A / Parking / etc.), resultat (autorisé/refusé),
  motif_refus

🔌 access_controller.py (NOUVEAU) :
- Table access_controllers :
  id, organization_id, marque (zkteco/dahua/hid/hikvision/csv),
  ip_address, port, username, password_encrypted,
  statut_connexion (connecté/erreur/non_configuré),
  derniere_sync, created_at

Après tous les modèles, crée la première migration Alembic :
alembic revision --autogenerate -m "initial_with_badges"
```

---

## Jour 13 — Authentification JWT (durée : 2h)

### ✅ Prompt :

```
Crée le système d'authentification JWT pour SyndicPro V2.

Dans app/routers/auth.py :

POST /auth/register : crée organisation + subscription trial + user admin
POST /auth/login : retourne access_token (1h) + refresh_token (30j)
POST /auth/refresh : nouveau access_token
POST /auth/logout
GET /auth/me

Templates :
- templates/auth/login.html
- templates/auth/register.html avec les 3 plans
```

---

## Jour 14 — Design system de base (durée : 2h)

### ✅ Prompt :

```
Crée le design system de base pour SyndicPro V2.

COULEURS CSS :
--bg: #0F172A
--secondary: #1E293B
--border: #334155
--accent: #00D4AA
--accent2: #6366F1
--danger: #EF4444
--warning: #F59E0B
--success: #10B981
--text: #F8FAFC
--muted: #94A3B8

templates/base.html avec :
- Sidebar 240px avec logo + navigation
- Items de navigation :
  Dashboard, Appartements, Encaissements, Dépenses, Comptable,
  Trésorerie, Tickets, 🔑 Badges & Accès (NOUVEAU), Agent IA, Rapports
- Zone contenu principal
- Toast notifications
- Responsive mobile

Crée aussi : templates/404.html, templates/500.html,
templates/subscription_expired.html
```

---

# 💻 PHASE 5 — MODULES CORE V2
## Jour 15 — Page d'accueil V2 (durée : 1h30)

### ✅ Prompt :

```
Crée la page d'accueil publique V2 (templates/index.html).

Inclus une section dédiée "🔑 Contrôle d'accès automatique" qui explique :
- Badge suspendu automatiquement après 3 mois impayés
- Réactivé instantanément après paiement Konnect
- Compatible ZKTeco, Dahua, HID, et tous autres systèmes

Thème sombre, Tailwind CSS, très professionnel.
```

---

## Jour 16 — Dashboard admin (durée : 2h)

### ✅ Prompt :

```
Crée le tableau de bord admin pour SyndicPro V2.

4 CARTES KPI :
1. Taux de recouvrement du mois (%)
2. Total encaissé ce mois (DT)
3. Total dépensé ce mois (DT)
4. Solde de trésorerie (DT)

2 GRAPHIQUES :
1. Barres : Encaissements vs Dépenses (6 derniers mois)
2. Donut : Statut des appartements (à jour / 1-2 mois / 3 mois+)

1 TABLEAU DES ALERTES :
- Appartements avec 3+ mois impayés
- Colonnes : Appartement | Résident | Mois impayés | Montant dû | Badges | Actions
- Bouton "🔴 Suspendre badge" par ligne
- Bouton "💳 Lien Konnect" par ligne
- Indicateur badges : "2 badges actifs" ou "⚠️ 2 badges suspendus"
```

---

## Jour 17 — Gestion des appartements (durée : 2h)

### ✅ Prompt :

```
Crée le module gestion des appartements pour SyndicPro V2.

Routes :
- GET /apartments
- POST /apartments/block
- POST /apartments
- GET /apartments/{id}/edit
- POST /apartments/{id}/edit
- DELETE /apartments/{id}
- GET /apartments/{id}/history
- GET /apartments/{id}/badges (NOUVEAU — liste les badges de cet appartement)

Template apartments/list.html :
- Vue par blocs (accordéon)
- Badge coloré : vert (à jour) / orange (1-2 mois) / rouge (3+ mois)
- Icône 🔑 sur chaque appartement montrant le nombre de badges actifs
- Si badges suspendus : icône rouge 🔴
```

---

## Jours 18-19 — Encaissements et dépenses (durée : 2×2h)

### ✅ Prompt Jour 18 :

```
Crée le module encaissements pour SyndicPro V2.

Routes :
- GET /payments
- POST /payments
- GET /payments/{id}/edit
- POST /payments/{id}/edit
- DELETE /payments/{id}
- GET /api/apartments/{id}/next-unpaid

Logique crédit résiduel conservée de la V1.
Badge sur chaque paiement : source (manuel / WhatsApp / Konnect).
```

### ✅ Prompt Jour 19 :

```
Crée le module dépenses pour SyndicPro V2.

Catégories : Électricité, Eau, Ascenseur, Nettoyage, Gardiennage, Travaux, Autre
Upload reçu/facture (stocker l'URL).
Vue mensuelle et annuelle.
```

---

## Jours 20-21 — Tableau comptable et trésorerie (durée : 2×1h30)

### ✅ Prompt Jour 20 :

```
Crée le tableau comptable interactif pour SyndicPro V2.

Route GET /comptable

Vue croisée : appartements × mois (12 derniers + 3 futurs)
- Vert = payé / Rouge = impayé / Gris = non applicable
- Clic cellule rouge → modal saisie rapide
- Colonne supplémentaire "Badges" : icône 🟢 (actifs) ou 🔴 (suspendus)
- Filtres par bloc + export Excel
```

### ✅ Prompt Jour 21 :

```
Crée la vue trésorerie pour SyndicPro V2.

- Tableau mensuel : Mois | Encaissements | Dépenses | Solde
- Graphique lignes : évolution sur 12 mois
- Projections 3 prochains mois
- Export Excel
```

---

## Jours 22-23 — Tickets (durée : 2×1h30)

### ✅ Prompt Jour 22 :

```
Crée le module tickets pour SyndicPro V2.

Côté résident : formulaire + liste de ses tickets
Côté admin : liste filtrée + réponse + changement de statut
Routes : GET/POST /tickets, GET /tickets/{id}, POST /tickets/{id}/respond
```

### ✅ Prompt Jour 23 :

```
Améliore les tickets :
1. Notification WhatsApp quand l'admin répond (stocker en BDD pour l'instant)
2. Stats tickets ouverts sur le dashboard admin
3. Filtre "mes tickets" pour les résidents
4. Pagination
```

---

## Jours 24-25 — Superadmin et rapports (durée : 2×1h30)

### ✅ Prompt Jour 24 :

```
Crée l'interface superadmin pour SyndicPro V2.

Pages :
1. /superadmin → liste de toutes les organisations
2. /superadmin/organizations/{id} → détails + stats
3. /superadmin/stats → MRR total, croissance
4. /superadmin/change-password
```

### ✅ Prompt Jour 25 :

```
Crée le générateur de rapports PDF pour SyndicPro V2.

Route GET /reports/monthly?month=2026-03

PDF contenant :
1. En-tête : Logo SyndicPro + Nom syndic + Mois
2. KPIs : encaissements, dépenses, solde, taux recouvrement
3. Tableau appartements impayés + statut badges
4. Détail dépenses par catégorie
5. Signature et date

Route GET /reports/annual?year=2026 → rapport annuel complet
```

---

---

# 🔑 PHASE 5B — MODULE BADGES & CONTRÔLE D'ACCÈS
## ⭐ C'EST LE MODULE QUI TE DIFFÉRENCIE DE TOUS LES CONCURRENTS

> **Objectif :** Permettre à SyndicPro de contrôler automatiquement l'accès aux
> ascenseurs via les badges RFID, sans intervention humaine.

---

## Jour 26 — Modèle connecteur + service générique (durée : 2h)

> **Objectif :** Construire le moteur central qui parle à n'importe quelle marque
> de contrôleur d'accès.

### ✅ Prompt à coller dans Claude Code :

```
Crée le service de contrôle d'accès badges pour SyndicPro V2.

Dans app/services/access_control/, crée cette architecture :

1. app/services/access_control/base.py :
   Classe abstraite BaseAccessController avec ces méthodes :
   - suspendre_badge(badge_uid: str) → bool
   - reactiver_badge(badge_uid: str) → bool
   - tester_connexion() → dict {ok: bool, message: str}
   - exporter_whitelist() → list[dict]

2. app/services/access_control/zkteco.py :
   Classe ZKTecoController(BaseAccessController) :
   - Utilise l'API ZKBioSecurity de ZKTeco
   - URL de base : http://{ip}:{port}/api/
   - Auth : POST /api/auth avec username/password → token
   - Suspendre : PATCH /api/users/{uid} avec {enable: false}
   - Réactiver : PATCH /api/users/{uid} avec {enable: true}
   - Tester : GET /api/info → vérifie la connexion

3. app/services/access_control/dahua.py :
   Classe DahuaController(BaseAccessController) :
   - API Dahua Access Control
   - Auth : digest authentication
   - Suspendre : PUT /cgi-bin/AccessCard.cgi?action=setConfig
   - Réactiver : même route avec enable=true

4. app/services/access_control/csv_export.py :
   Classe CSVController(BaseAccessController) :
   - Pas d'API matériel — génère un fichier CSV
   - suspendre_badge : marque le badge comme SUSPENDU dans le fichier
   - reactiver_badge : remet ACTIF
   - Le fichier est régénéré à chaque appel
   - Chemin : /exports/{organization_id}/badges_autorises.csv
   - Format CSV :
     badge_uid,label,appartement,statut,derniere_modification
     A3F2-9C1B,Badge principal,3B,ACTIF,2026-03-31T10:00:00
     C9D1-4F2A,Badge conjoint,3B,SUSPENDU,2026-03-31T10:00:00

5. app/services/access_control/factory.py :
   Classe ConnecteurFactory :
   def get(marque: str, config: dict) → BaseAccessController :
     - "zkteco" → ZKTecoController(config)
     - "dahua"  → DahuaController(config)
     - "hid"    → HIController(config) (stub vide pour l'instant)
     - "csv"    → CSVController(config)
     - défaut   → CSVController(config)

Ajoute des logs complets sur chaque action (badge_uid, action, résultat, timestamp).
```

---

## Jour 27 — Routes API badges (durée : 2h)

> **Objectif :** Créer toutes les routes pour gérer les badges dans SyndicPro.

### ✅ Prompt à coller dans Claude Code :

```
Crée le module de gestion des badges dans app/routers/badges.py.

ROUTES BADGES :

GET /badges/appartement/{appart_id} :
- Liste tous les badges d'un appartement
- Retourne : badge_uid, label, statut, date_suspension, suspendu_par

POST /badges/ :
- Ajouter un nouveau badge
- Body : {appartement_id, resident_id, badge_uid, label}
- Vérifie que le badge_uid n'existe pas déjà dans cette organisation
- Appelle l'API du contrôleur pour enregistrer le badge (si connecté)

PATCH /badges/{badge_id}/suspendre :
- Suspendre un badge manuellement (par le gestionnaire)
- Body : {motif: "string"}
- Appelle ConnecteurFactory → suspendre_badge()
- Log l'action dans access_logs
- Envoie notification WhatsApp au résident (stocké en BDD pour l'instant)

PATCH /badges/{badge_id}/reactiver :
- Réactiver un badge
- Appelle ConnecteurFactory → reactiver_badge()
- Log l'action

DELETE /badges/{badge_id} :
- Supprimer un badge définitivement

GET /badges/export/{organization_id} :
- Exporte la whitelist complète en CSV
- Utilisé par les contrôleurs qui font du polling

GET /badges/logs/{organization_id} :
- Historique de toutes les actions (suspension/réactivation)
- Filtres : date, appartement, type d'action

ROUTE INTÉGRATION CONTRÔLEUR :

POST /integrations/access-controller/test :
- Teste la connexion avec le contrôleur configuré
- Retourne : {ok: bool, marque, nb_badges_detectes, message}

GET /integrations/access-controller/whitelist/{organization_id} :
- Endpoint public (avec token secret) pour polling du contrôleur
- Retourne la liste JSON des badges actifs
- URL : /integrations/whitelist/{org_token}
```

---

## Jour 28 — Interface gestionnaire badges (durée : 2h)

> **Objectif :** Créer la page de gestion des badges dans le dashboard.

### ✅ Prompt à coller dans Claude Code :

```
Crée l'interface de gestion des badges dans SyndicPro V2.

PAGE 1 — /badges (liste principale)

Template : templates/badges/list.html

En haut : Statut de la connexion au contrôleur :
  ✅ ZKTeco connecté — Dernière sync : il y a 5 min
  ou ❌ Aucun contrôleur configuré — [Configurer maintenant]

Tableau principal :
Appartement | Résident | Badge UID | Label | Statut | Dernière action | Actions

Statut avec badge coloré :
- 🟢 Actif
- 🔴 Suspendu (avec motif au survol)
- ⚫ Perdu/Révoqué

Actions par ligne :
- [+ Ajouter badge] → ouvre un modal
- [🔴 Suspendre] → confirmation + motif
- [🟢 Réactiver] → confirmation
- [🗑️ Supprimer]

Filtres en haut : Tous / Actifs / Suspendus / Par bloc

Bouton en haut à droite : [📥 Exporter CSV] [⚙️ Configuration contrôleur]

PAGE 2 — Modal "Ajouter un badge" :
- Sélecteur appartement
- Sélecteur résident (filtre par appartement sélectionné)
- Champ Badge UID (avec info-bulle : "Numéro gravé derrière le badge physique")
- Champ Label (exemples : "Badge principal", "Badge conjoint", "Voiture")
- Bouton Enregistrer

PAGE 3 — /badges/configuration (paramétrage du contrôleur)

Titre : "Connecter votre système de contrôle d'accès"

Sélecteur de marque avec icônes :
  ◉ ZKTeco      — Intégration API directe (temps réel)
  ○ Dahua       — Intégration API directe (temps réel)
  ○ HID         — Intégration API directe (temps réel)
  ○ Hikvision   — Intégration API directe (temps réel)
  ○ Autre       — Export CSV (votre installateur configure le polling)

Quand ZKTeco/Dahua/HID sélectionné, afficher :
  Adresse IP du serveur : [__________]
  Port : [8080]
  Identifiant : [__________]
  Mot de passe : [__________]
  [🔌 Tester la connexion]

Quand "Autre/CSV" sélectionné, afficher :
  Message explicatif : "SyndicPro va générer automatiquement un fichier CSV
  avec la liste des badges autorisés. Donnez ce lien à votre installateur :
  [URL whitelist]
  Il devra configurer son logiciel pour lire ce fichier toutes les heures."

PAGE 4 — /badges/logs (historique)

Tableau : Date | Appartement | Badge | Action | Déclenché par | Résultat
Filtres : date, appartement, action (suspension/réactivation)
```

---

## Jour 29 — Intégration avec le module paiements (durée : 1h30)

> **Objectif :** Connecter les paiements aux badges — quand on paie, le badge
> se réactive automatiquement.

### ✅ Prompt à coller dans Claude Code :

```
Connecte le module badges au module paiements dans SyndicPro V2.

RÈGLE 1 — Quand un paiement est enregistré pour un appartement :
Dans la route POST /payments, après avoir enregistré le paiement :
1. Vérifie si cet appartement a des badges suspendus avec motif "impayés"
2. Calcule les mois impayés restants après ce paiement
3. Si mois_impayes_restants < 3 :
   → Réactive automatiquement tous les badges suspendus pour impayés
   → Log l'action : "Réactivation automatique suite au paiement"
   → Prépare une notification WhatsApp : "✅ Votre accès a été rétabli"
4. Si mois_impayes_restants >= 3 :
   → Ne fait rien, les badges restent suspendus

RÈGLE 2 — Quand un paiement Konnect est confirmé (webhook) :
Même logique que ci-dessus, mais déclenchée par le webhook Konnect.
C'est la réactivation INSTANTANÉE après paiement en ligne.

RÈGLE 3 — Indicateur sur la page /payments :
Ajoute une colonne "Badges" dans le tableau des appartements impayés :
- Si badges suspendus → "🔴 2 badges suspendus"
- Si badges actifs → "🟢 2 badges actifs"
- Si pas de badges enregistrés → "⚪ Aucun badge"

RÈGLE 4 — Sur le profil résident (/resident/dashboard) :
Ajoute une section "Mes badges" :
- Statut de chaque badge (actif / suspendu)
- Si suspendu : motif + lien "Régulariser mes paiements"
```

---

## Jour 30 — Tests du module badges (durée : 1h30)

> **Objectif :** Tester que tout le module badges fonctionne correctement.

### ✅ Prompt Jour 30 :

```
Teste le module badges complet. Pour chaque test, dis-moi si c'est ✅ OK ou ❌ ERREUR.

TEST 1 — Configuration CSV (sans matériel) :
1. Va dans /badges/configuration
2. Sélectionne "Autre/CSV"
3. Enregistre
4. Va dans /badges
5. Ajoute un badge : appartement 3B, badge UID "A3F2-9C1B", label "Badge principal"
6. Vérifie que le badge apparaît dans la liste avec statut 🟢 Actif
7. Clique [Suspendre] → confirme
8. Vérifie que le statut passe à 🔴 Suspendu
9. Va sur /badges/export/{org_id} → vérifie le CSV généré
10. Clique [Réactiver] → vérifie que le statut repasse à 🟢 Actif

TEST 2 — Lien paiement → réactivation badge :
1. L'appartement 3B a 3 mois impayés
2. Les badges de 3B sont suspendus
3. Enregistre un paiement pour 3B qui ramène à 2 mois impayés
4. Vérifie que les badges sont automatiquement réactivés

TEST 3 — Ajout de plusieurs badges pour un même appartement :
1. Ajoute 3 badges pour l'appartement 3B : "Principal", "Conjoint", "Voiture"
2. Suspends tous → vérifie que les 3 sont suspendus
3. Réactive → vérifie que les 3 sont réactivés

TEST 4 — Export CSV :
1. Appelle GET /integrations/whitelist/{org_token}
2. Vérifie que le JSON retourné contient les bons badges et statuts

Si un test échoue, corrige le bug avant de passer au suivant.
Commit "feat: badge access control module complete" et push.
```

---

# 🤖 PHASE 6 — AGENT IA WEBAPP
## Jour 31 — Setup de l'agent IA (durée : 2h)

### ✅ Étape 1 — Obtenir une clé API Anthropic

1. Va sur **console.anthropic.com**
2. Va dans **"API Keys"** → **"Create Key"**
3. Ajoute dans `.env` : `ANTHROPIC_API_KEY=sk-ant-ta_cle_ici`

### ✅ Prompt à coller dans Claude Code :

```
Crée le service agent IA pour SyndicPro V2.

Dans app/services/ai_agent.py, crée le moteur Claude avec ces outils :

tools = [
  get_unpaid_apartments()
  get_treasury_balance()
  get_apartment_history(apt)
  record_payment(apt, amount, months)
  record_expense(category, amount, date)
  get_dashboard_summary()
  create_ticket(subject, msg)
  get_resident_info(apt)
  
  🔑 get_badge_status(apt)      → NOUVEAU : statut des badges d'un appartement
  🔑 suspend_badge(apt, motif)  → NOUVEAU : suspendre tous les badges d'un appart
  🔑 reactivate_badge(apt)      → NOUVEAU : réactiver tous les badges d'un appart
]

Système prompt de l'agent :
"Tu es l'assistant intelligent de SyndicPro, une application de gestion de syndic
tunisien. Tu aides les administrateurs à gérer leurs immeubles, suivre les paiements,
et contrôler l'accès aux ascenseurs via les badges.
Tu peux suspendre ou réactiver des badges sur demande, mais toujours avec confirmation.
Réponds en français sauf si l'utilisateur écrit en arabe."
```

---

## Jour 32 — Interface chat de l'agent (durée : 1h30)

### ✅ Prompt :

```
Crée l'interface de chat pour l'agent IA.

Route GET /agent → page du chat
Route POST /agent/chat → envoie un message à l'agent

Template agent/chat.html :
- Thème sombre, style iMessage
- Suggestions rapides au démarrage :
  "📊 Résumé du mois"
  "💰 Qui n'a pas payé ?"
  "🔑 Statut des badges"
  "📋 Bilan financier"
  "🔔 Envoyer des relances"

L'agent doit pouvoir répondre à :
- "Quels sont les badges suspendus ?"
- "Suspend les badges de l'appartement 3B"
- "Réactive les badges de 3B, ils ont payé"
```

---

## Jours 33-36 — Tests et affinage de l'agent (durée : 4×1h)

### ✅ Prompt Jour 33 :

```
Teste l'agent IA avec ces commandes :

1. "Bonjour"
2. "Qui n'a pas payé ce mois ?"
3. "Quel est notre solde de trésorerie ?"
4. "Enregistre un paiement de 150 DT pour l'appartement A-12 pour mars 2026"
5. "Quels appartements ont des badges suspendus ?"
6. "Suspend les badges de l'appartement 5F"
7. "Réactive les badges de 5F, ils ont régularisé"
8. "Combien d'appartements ont 3+ mois d'impayés avec des badges encore actifs ?"

Pour chaque problème, corrige le tool concerné.
```

---

# 💬 PHASE 7 — WHATSAPP
## Jour 37 — Créer le compte Meta Business (durée : 2h)

> ⚠️ Pas de code aujourd'hui. Administration.

1. Crée un compte Meta Business sur **business.facebook.com**
2. Crée une app Meta sur **developers.facebook.com** (type : Business)
3. Ajoute "WhatsApp" dans les produits
4. Obtiens : `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID`, `WHATSAPP_VERIFY_TOKEN`
5. Ajoute dans `.env`

---

## Jours 38-39 — Webhook WhatsApp (durée : 2×2h)

### ✅ Prompt Jour 38 :

```
Crée le webhook WhatsApp pour SyndicPro V2.

Dans app/routers/whatsapp.py :

GET /whatsapp/webhook : vérifie le verify_token Meta

POST /whatsapp/webhook :
- Extrait numéro + type de message + contenu
- Identifie l'utilisateur (admin ou résident)
- Route vers le bon flux

app/services/whatsapp_service.py :
- send_text_message(phone, message)
- send_image_message(phone, image_url, caption)
- get_media_url(media_id)
```

### ✅ Prompt Jour 39 :

```
Crée l'agent WhatsApp pour SyndicPro V2.

FLUX RÉSIDENT :
- "mon solde" → mois impayés + montant dû + statut badges
- "mes paiements" → historique 6 derniers
- "ticket [description]" → crée ticket
- Image reçu → analyse Claude Vision → enregistre paiement
- "aide" → menu des commandes

FLUX ADMIN :
- Saisie paiement : "apt A-12 150dt mars 2026"
- Saisie dépense : "nettoyage 200dt"
- Consultation : "impayés", "bilan mars", "badges suspendus"
- 🔑 Actions badges : "suspend 3B", "reactive 3B"
- Actions : "relancer tous", "lien paiement A-12"

Gère la mémoire conversationnelle (contexte en BDD).
```

---

## Jours 40-43 — Tests WhatsApp (durée : 4×1h)

### ✅ Prompt Jour 40 :

```
Déploie le webhook WhatsApp sur Render et configure dans Meta.

URL : https://syndicpro-v2.onrender.com/whatsapp/webhook
Verify Token : syndicpro2026
```

### ✅ Jours 41-43 : Tests manuels depuis le téléphone

- [ ] "mon solde" depuis le numéro résident
- [ ] Photo d'un reçu test
- [ ] "impayés" depuis le numéro admin
- [ ] "apt A-12 150dt mars 2026"
- [ ] 🔑 "suspend 3B" depuis le numéro admin
- [ ] 🔑 "reactive 3B" depuis le numéro admin

---

# 💳 PHASE 8 — KONNECT (PAIEMENT EN LIGNE)
## Jour 44 — Créer un compte Konnect (durée : 1h)

> ⚠️ Pas de code aujourd'hui.

1. Va sur **konnect.network**
2. Crée un compte business
3. Obtiens clé API + Wallet ID
4. Active mode sandbox
5. Ajoute dans `.env` : `KONNECT_API_KEY`, `KONNECT_WALLET_ID`, `KONNECT_MODE=sandbox`

---

## Jours 45-47 — Intégration Konnect (durée : 3×2h)

### ✅ Prompt Jour 45 :

```
Intègre Konnect dans SyndicPro V2.

app/services/konnect_service.py :
generate_payment_link(apartment_id, months, amount) → URL Konnect (valide 24h)

app/routers/konnect.py :
POST /konnect/generate/{apartment_id} → génère lien + envoie WhatsApp au résident

GET /konnect/webhook :
- Confirme paiement Konnect
- Enregistre en BDD
- 🔑 Réactive automatiquement les badges de l'appartement si < 3 mois impayés restants
- Notifie résident ("✅ Accès rétabli") et admin par WhatsApp

GET /payment/success : page de confirmation avec animation
```

### ✅ Prompt Jour 46 :

```
Ajoute les boutons Konnect dans l'interface :

1. /apartments : bouton "💳 Générer lien" pour chaque appart impayé
   → modal avec lien + option "Envoyer par WhatsApp"

2. Dashboard admin : bouton "💳 Lien" dans le tableau des alertes

3. Espace résident : bouton "Payer en ligne" si impayés
   → affiche aussi le statut badge ("🔴 Votre accès est suspendu")

Teste en mode sandbox.
```

### ✅ Prompt Jour 47 :

```
Connecte Konnect avec les badges :

Scénario complet à tester :
1. Appartement 3B a 4 mois impayés → badges suspendus
2. Admin génère un lien Konnect pour 3B
3. Résident clique et paie 2 mois via Konnect
4. Webhook Konnect reçu → 2 mois restants impayés (< 3)
5. SyndicPro réactive automatiquement tous les badges de 3B
6. WhatsApp envoyé au résident : "✅ Votre paiement de 100 DT a été reçu.
   Votre accès aux parties communes est rétabli."
7. WhatsApp envoyé à l'admin : "Paiement 3B reçu (100 DT). Badges réactivés auto."

Vérifie que ce scénario fonctionne de bout en bout.
```

---

# ⚙️ PHASE 9 — AUTOMATISATION COMPLÈTE
## Jour 48 — Scheduler — Relances automatiques (durée : 1h30)

### ✅ Prompt :

```
Crée le système de relances automatiques avec APScheduler.

Dans app/services/scheduler.py :

Tâche 1 — Chaque lundi à 8h :
- Appartements avec 1+ mois impayé → relance WhatsApp personnalisée par Claude
- Ton progressif selon le nombre de mois :
  1 mois : "Rappel amical : votre redevance de [mois] est en attente (X DT)"
  2 mois : "Rappel important : 2 mois en attente (X DT)"
  3 mois : "⚠️ Mise en demeure : 3 mois impayés. Votre accès sera suspendu à minuit."

Tâche 2 — Le 1er de chaque mois à 7h :
- Génère bilan mensuel PDF pour chaque organisation
- Envoie à l'admin par WhatsApp

Lance le scheduler au démarrage de FastAPI.
```

---

## Jour 49 — Scheduler — Suspension automatique badges (durée : 2h)

> **C'EST LE CŒUR DU SYSTÈME — LE ZÉRO INTERVENTION HUMAINE**

### ✅ Prompt à coller dans Claude Code :

```
Crée la tâche automatique de suspension des badges dans app/services/scheduler.py.

🔑 TÂCHE BADGE — Chaque nuit à 00h01 (minuit passé d'une minute) :

async def auto_suspendre_badges_impayes():
  
  ÉTAPE 1 — Identifier les appartements à suspendre :
  Pour chaque organisation active :
    - Calcule la date d'il y a 3 mois
    - Trouve tous les appartements avec 3+ mois impayés CONSÉCUTIFS
    - (mois consécutifs = les 3 derniers mois, pas n'importe quels 3 mois)
  
  ÉTAPE 2 — Suspendre les badges :
  Pour chaque appartement concerné :
    - Cherche tous ses badges avec statut "actif"
    - Pour chaque badge actif :
      → badge.statut = "suspendu"
      → badge.motif_suspension = f"{nb_mois} mois d'impayés consécutifs"
      → badge.date_suspension = datetime.utcnow()
      → badge.suspendu_par = "IA_automatique"
    - Appelle ConnecteurFactory → suspendre_badge(badge_uid) pour chaque badge
    - Log l'action dans access_logs
  
  ÉTAPE 3 — Notifier le résident :
  Pour chaque appartement suspendu :
    - Envoie WhatsApp au résident :
      "🔴 SyndicPro — Résidence [nom]
       Bonjour [prénom],
       Votre accès aux parties communes a été suspendu suite à
       [X] mois d'impayés de redevance syndic.
       Montant dû : [X] DT
       👉 Payer maintenant : [lien Konnect généré automatiquement]
       Dès réception, votre accès sera rétabli automatiquement."
  
  ÉTAPE 4 — Notifier le gestionnaire :
  Un seul message récapitulatif pour chaque organisation :
    "📊 SyndicPro — Rapport automatique de cette nuit :
     [X] badges suspendus automatiquement
     Appartements concernés : [liste]
     [X] relances envoyées"
  
  ÉTAPE 5 — Log complet :
  Enregistre dans la BDD :
    - Nombre d'organisations traitées
    - Nombre d'appartements vérifiés
    - Nombre de badges suspendus
    - Nombre de notifications envoyées
    - Durée de l'exécution
    - Éventuelles erreurs

🔑 TÂCHE BADGE RÉACTIVATION — Vérification après paiement :
(déclenchée en temps réel par le webhook Konnect, pas par cron)
Voir le code déjà créé au Jour 47.

INTERFACE D'ADMINISTRATION DU SCHEDULER :

Page /admin/scheduler :
- Tableau des prochaines exécutions planifiées
- Historique des dernières exécutions (date, nb badges suspendus, nb notifications)
- Bouton "▶️ Lancer maintenant" pour forcer la vérification
- Toggle ON/OFF par organisation (certains syndics peuvent vouloir désactiver)
- Log de la dernière exécution en détail

Lance le scheduler au démarrage et vérifie qu'il ne plante pas.
```

---

## Jour 50 — Import relevé bancaire (durée : 1h30)

### ✅ Prompt :

```
Crée le module d'import de relevé bancaire.

Page /import/releve (admin seulement)

1. Upload PDF ou Excel
2. Parse les transactions (date, montant, description) avec pdfplumber/pandas
3. Envoie à Claude pour réconciliation : quel appartement correspond à ce virement ?
4. Tableau de validation : Transaction | Appartement proposé | Confiance | Confirmer
5. Bouton "Enregistrer les paiements confirmés"
```

---

## Jours 51-52 — Interface scheduler et finitions (durée : 2×1h30)

### ✅ Prompt Jour 51 :

```
Améliore l'interface du scheduler badges :

1. Graphique : badges suspendus vs réactivés sur 30 derniers jours
2. Tableau : liste de TOUS les badges actuellement suspendus pour impayés
   avec bouton "Réactiver manuellement" par ligne
3. Statistiques : taux de recouvrement AVANT et APRÈS activation du module badges
4. Alerte si le contrôleur d'accès n'a pas synchronisé depuis plus de 2h
```

### ✅ Prompt Jour 52 :

```
Ajoute ces fonctionnalités de confort :

1. Email de bienvenue automatique quand un gestionnaire configure son contrôleur
2. Onboarding : guide étape par étape pour configurer les badges (5 étapes)
3. Démo : mode "preview" qui simule le flux sans envoyer de vrais WhatsApp
4. FAQ intégrée : "Pourquoi mes badges ne se synchronisent pas ?"
```

---

# 🧪 PHASE 10 — TESTS COMPLETS
## Jours 53-58 — Tests de tout (durée : 6×1h)

### ✅ Prompt Jour 53 :

```
Crée un script de tests automatisés complet avec Playwright pour SyndicPro V2.

TESTS D'AUTHENTIFICATION :
- Inscription nouveau syndic
- Connexion admin + résident
- Déconnexion
- Connexion mauvais mot de passe

TESTS ADMIN :
- Créer bloc + appartement
- Enregistrer paiement (avec crédit résiduel)
- Enregistrer dépense
- Vérifier tableau comptable
- Générer rapport PDF

TESTS RÉSIDENT :
- Tableau de bord
- Historique paiements
- Créer ticket
- Changer mot de passe + email
- Voir statut badges

🔑 TESTS MODULE BADGES :
- Configurer un contrôleur CSV
- Ajouter 3 badges pour un appartement
- Suspendre un badge manuellement
- Réactiver un badge
- Vérifier export CSV whitelist
- Simuler 3 mois impayés → vérifier suspension auto
- Enregistrer paiement → vérifier réactivation auto
- Tester la page /badges avec filtres
- Tester les logs d'accès

TESTS SÉCURITÉ :
- Résident ne peut pas accéder aux pages admin
- Rate limiting sur /login
- Gestionnaire d'une org ne peut pas voir les badges d'une autre org

Lance les tests et donne-moi un rapport détaillé ✅/❌.
```

### ✅ Jours 54-58 : Corriger les bugs trouvés

```
[Chaque jour] Voici les tests qui ont échoué hier : [liste].
Corrige ces bugs et relance les tests.
```

---

# 🚀 PHASE 11 — LANCEMENT
## Jour 59 — Migration V1 → V2 (durée : 2h)

### ✅ Prompt :

```
Crée un script de migration des données de la V1 vers la V2.

Tables à migrer : organizations, subscriptions, users, blocks,
apartments, payments, expenses, tickets

Crée aussi un script de vérification qui compare les totaux entre V1 et V2.

Note : les badges sont une nouvelle fonctionnalité, aucune donnée à migrer.
```

---

## Jour 60 — Déploiement V2 sur Render (durée : 2h)

1. Va sur **render.com** → nouveau service Web
2. Connecte au repo GitHub `SYNDICPROV2`
3. Build : `pip install -r requirements.txt`
4. Start : `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Ajoute toutes les variables d'environnement
6. Nouvelle base PostgreSQL sur Render
7. Lance + vérifie

---

## Jour 61 — Basculer le domaine (durée : 1h)

1. Render : ajoute `app.syndicpro.tn` au service V2
2. DNS : `app` → CNAME → url-render-v2
3. Garde `www.syndicpro.tn` sur V1 pendant 2 semaines
4. Vérifie que `app.syndicpro.tn` fonctionne

---

## Jour 62 — Communication et lancement (durée : 2h)

### ✅ Email à tous les clients V1 :

```
Objet : SyndicPro se transforme — V2 avec IA WhatsApp + Contrôle d'accès badges

Bonjour [prénom],

SyndicPro V2 est disponible avec des fonctionnalités révolutionnaires :

🤖 Agent IA WhatsApp qui gère les paiements automatiquement
💳 Paiement en ligne via Konnect
🔑 Contrôle d'accès badges automatique (EXCLUSIF EN TUNISIE)
   → Badge suspendu après 3 mois impayés
   → Badge réactivé dès réception du paiement
   → Zéro intervention humaine

Votre accès V2 : app.syndicpro.tn
Vos données ont été migrées automatiquement.

L'équipe SyndicPro
```

### ✅ Argument commercial à utiliser :

```
Pitch en 30 secondes :

"Avec SyndicPro, si un résident ne paie pas 3 mois,
l'ascenseur s'arrête automatiquement la nuit même.
Dès qu'il paie en ligne, l'accès repart en 10 secondes.
Vous ne faites plus rien. Le taux de recouvrement passe à 90%."
```

### ✅ Actions marketing :

- [ ] Post LinkedIn avec le pitch badges
- [ ] Groupes Facebook syndics tunisiens
- [ ] Appeler 5 prospects en proposant essai gratuit + démo badges
- [ ] Contacter 3 installateurs ZKTeco en Tunisie pour partenariat de référence

---

## Jours 63-65 — Stabilisation et croissance

### ✅ Chaque jour pendant cette période :

**Matin (15 min) :**
- Vérifier les logs Render
- Vérifier les nouveaux inscrits
- Vérifier le log de la tâche badges de la nuit (combien de suspensions ?)

**En cas de bug signalé :**
```
Je travaille sur SyndicPro V2.
Je suis au Jour [X], Étape [Y].
Voici le problème : [description]
Voici l'erreur : [colle l'erreur exacte]
```

**Chaque semaine :**
- Demande à Claude d'analyser les logs badges
- Ajoute les nouvelles marques de contrôleurs demandées par les clients

---

# 📊 RÉCAPITULATIF GLOBAL MIS À JOUR

| Phase | Jours | Durée / jour | Total |
|-------|-------|-------------|-------|
| Installation | 1 | 1h30 | 1h30 |
| Sécurité V1 | 2-3 | 1h | 2h |
| UX V1 | 4-7 | 1h30 | 6h |
| Refactoring V1 | 8-10 | 1h30 | 4h30 |
| Fondations V2 | 11-14 | 2h | 8h |
| Modules Core V2 | 15-25 | 2h | 22h |
| **🔑 Module Badges** | **26-30** | **2h** | **10h** |
| Agent IA | 31-36 | 1h30 | 9h |
| WhatsApp | 37-43 | 2h | 14h |
| Konnect | 44-47 | 2h | 8h |
| Automatisation | 48-52 | 1h30 | 7h30 |
| Tests | 53-58 | 1h | 6h |
| Lancement | 59-65 | 2h | 14h |
| **TOTAL** | **65 jours** | | **~112h** |

---

# 🎯 CE QUI REND SYNDICPRO UNIQUE

```
AVANT SYNDICPRO           AVEC SYNDICPRO
─────────────────────     ────────────────────────────────
Gestionnaire appelle   →  Automatique
Résident ignore appel  →  Impossible : ascenseur bloqué
Oublie de relancer     →  Cron job chaque nuit à minuit
Paiement → réactivation manuelle → 10 secondes automatique
Taux recouvrement 60%  →  Taux recouvrement 90%+
```

**Pitch en une phrase :**
> *"SyndicPro est la seule plateforme en Tunisie — et en Afrique du Nord —
> qui coupe l'accès à l'ascenseur automatiquement en cas d'impayés,
> et le réactive instantanément après paiement. Sans intervention humaine."*

---

## 🆘 QUE FAIRE SI TU BLOQUES ?

```
Je travaille sur SyndicPro V2.
Je suis au Jour [X], Étape [Y].
Voici ce que j'essaie de faire : [description]
Voici ce qui se passe / l'erreur : [colle l'erreur exacte]
Mon système : Windows/Mac
```

---

## 📁 FICHIERS IMPORTANTS

| Fichier | Contenu |
|---------|---------|
| `syndicpro_plan_v2_badges.md` | Ce fichier — plan complet mis à jour |
| `syndicpro_session.md` | Mémoire complète du projet |
| `.env` | Tes clés secrètes (NE JAMAIS partager) |
| `.env.example` | Modèle des variables |

---

*Généré par Claude — 31 mars 2026*
*Version mise à jour avec module Contrôle d'Accès Badges*
*Repartage ce fichier à Claude à chaque nouvelle session.*
