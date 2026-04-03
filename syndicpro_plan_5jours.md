# 🗓️ SyndicPro — Plan 5 Jours
## Sécurisation + Amélioration Visuelle
> **Pour Jamel — Linux Ubuntu — Comme un enfant de 12 ans**
> Mis à jour : 1er avril 2026

---

## 📌 COMMENT UTILISER CE PLAN

- Lis **seulement le jour où tu es**
- Coche chaque case quand c'est fait ✅
- Si tu bloques → dis à Claude : **"Je suis au Jour X, Étape Y, voici l'erreur : [colle l'erreur]"**
- Ne saute pas d'étape

---

## 🗂️ VUE D'ENSEMBLE

| Jour | Travail | Durée |
|------|---------|-------|
| Jour 1 | Sécurité critique | 3h |
| Jour 2 | Sécurité complémentaire | 1h30 |
| Jour 3 | Page d'accueil | 3h |
| Jour 4 | Dashboard admin + bugs visuels | 2h |
| Jour 5 | Dashboard résident + test final | 2h |
| **Total** | | **~11h30** |

---

---

# 🔧 AVANT DE COMMENCER — Vérifications (15 min)

Ouvre le terminal Linux :
- **Raccourci clavier :** `Ctrl + Alt + T`
- **Ou** cherche "Terminal" dans tes applications

Tape ces commandes **une par une** :

```bash
python3 --version
```
✅ Tu dois voir `Python 3.x.x`

```bash
git --version
```
✅ Tu dois voir `git version 2.x.x`

```bash
node --version
```
❌ Si tu vois une erreur, installe Node.js :
```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs
```

```bash
claude --version
```
❌ Si tu vois une erreur, installe Claude Code :
```bash
npm install -g @anthropic-ai/claude-code
```

✅ **Tout fonctionne ? Tu peux commencer le Jour 1.**

---

---

# 🔴 JOUR 1 — Sécurité critique (3h)

> **Objectif :** Protéger ton site avant de le montrer à quelqu'un.
> Le mot de passe superadmin est visible sur GitHub en ce moment !

---

## ✅ Étape 1 — Récupérer ton projet sur ton PC (10 min)

Ouvre le terminal et tape :

```bash
cd ~/Bureau
```

> 💡 Si ton Bureau s'appelle "Desktop" en anglais :
> ```bash
> cd ~/Desktop
> ```

Clone ton projet depuis GitHub :

```bash
git clone https://github.com/sghaierjamel-svg/SYNDICPROF1.git
```

Entre dans le dossier :

```bash
cd SYNDICPROF1
```

Vérifie que tu es au bon endroit :

```bash
ls
```
✅ Tu dois voir `app.py` dans la liste.

---

## ✅ Étape 2 — Créer l'environnement Python (10 min)

```bash
python3 -m venv venv
```

Active l'environnement :

```bash
source venv/bin/activate
```

✅ Tu dois voir `(venv)` au début de ta ligne. Exemple :
```
(venv) jamel@pc:~/Bureau/SYNDICPROF1$
```

Installe les dépendances :

```bash
pip install -r requirements.txt
```

Attends 2-3 minutes.

---

## ✅ Étape 3 — Lancer Claude Code (5 min)

Toujours dans le même terminal :

```bash
claude
```

Claude Code va s'ouvrir et te demander de te connecter avec ton compte Claude.
Suis les instructions à l'écran.

---

## ✅ Étape 4 — Donner le contexte à Claude Code

Quand Claude Code est ouvert, **copie-colle exactement ce texte** et appuie sur Entrée :

```
Je travaille sur SyndicPro, mon application Flask de gestion de syndic tunisien.
Le site est live sur syndicpro.tn et déployé sur Render.
Je suis sur Linux Ubuntu. Je ne sais pas coder.
Explique chaque modification en français simple.
Montre-moi le code AVANT de modifier.
Demande-moi confirmation avant toute modification.
Ne touche à rien tant que je n'ai pas dit OK.
```

Attends la réponse de Claude.

---

## ✅ Étape 5 — Corriger la sécurité critique

**Copie-colle ce prompt** dans Claude Code :

```
Corrige ces 4 problèmes de sécurité dans app.py dans cet ordre.
Montre-moi le code AVANT chaque modification. J'approuve, tu modifies.
Dis-moi "✅ Correction X terminée" après chaque étape.

CORRECTION 1 — Mot de passe superadmin visible sur GitHub :
- Cherche "SuperAdmin2024!" dans app.py
- Remplace par : os.environ.get('SUPERADMIN_PASSWORD', 'changez-moi')
- Crée un fichier .env à la racine du projet avec :
  SUPERADMIN_PASSWORD=SuperAdmin2024!
- Crée un fichier .env.example avec :
  SUPERADMIN_PASSWORD=votre_mot_de_passe_ici
- Ouvre .gitignore et ajoute .env dedans

CORRECTION 2 — Trop de tentatives de connexion possibles :
- Installe Flask-Limiter avec pip
- Ajoute une limite de 5 tentatives par minute sur la route /login
- Message affiché : "Trop de tentatives. Réessayez dans 1 minute."

CORRECTION 3 — Suppression sans protection :
- Les routes /payment/delete et /expense/delete acceptent les requêtes GET
- Transforme-les en POST uniquement
- Ajoute une confirmation JavaScript dans les templates :
  "Êtes-vous sûr de vouloir supprimer ?"

CORRECTION 4 — Erreurs techniques visibles aux utilisateurs :
- Cherche tous les flash(f'Erreur: {str(e)}') dans tout le projet
- Remplace par : flash('Une erreur est survenue. Réessayez.')
- Garde un print(e) juste avant pour voir l'erreur dans les logs Render

Commence par la Correction 1.
```

> 💡 **Comment approuver :** Lis ce que Claude te montre. Tape `OK` pour approuver. Tape `explique moi` si tu ne comprends pas.

---

## ✅ Étape 6 — Mettre à jour les variables sur Render

Ouvre ton navigateur. Va sur **render.com**. Connecte-toi.

1. Clique sur ton service **SyndicPro**
2. Dans le menu gauche → clique **"Environment"**
3. Clique **"Add Environment Variable"**
4. Ajoute :
   - **Key :** `SUPERADMIN_PASSWORD`
   - **Value :** un mot de passe fort (ex: `Syndic@2026!`)
5. Clique **"Save Changes"**
6. Render redéploie automatiquement (2-3 min)

- [ ] Va sur **syndicpro.tn** et vérifie que le site fonctionne encore

---

## ✅ Étape 7 — Sauvegarder sur GitHub

Dans Claude Code, colle :

```
Fais un git add de tous les fichiers modifiés, puis un git commit avec
le message "security: superadmin + rate limit + delete POST + errors",
puis un git push sur GitHub.
```

✅ Va sur **github.com/sghaierjamel-svg/SYNDICPROF1** et vérifie que le dernier commit s'appelle bien `security: superadmin...`

Pour quitter Claude Code :
```
/exit
```

### 🎉 Fin du Jour 1

**Ce que tu as sécurisé :**
- ✅ Mot de passe superadmin protégé
- ✅ Brute-force impossible sur /login
- ✅ Suppressions protégées
- ✅ Erreurs techniques masquées

---

---

# 🔴 JOUR 2 — Sécurité complémentaire (1h30)

> **Objectif :** Finir les protections de sécurité importantes.

---

## ✅ Étape 1 — Ouvrir le projet

```bash
cd ~/Bureau/SYNDICPROF1
source venv/bin/activate
claude
```

---

## ✅ Étape 2 — Corriger la sécurité complémentaire

Colle ce prompt :

```
Bonjour ! Je continue les corrections de sécurité sur SyndicPro.
Montre-moi le code avant chaque modification. J'approuve, tu modifies.

CORRECTION 1 — TIMEOUT DE SESSION :
- Ajoute une déconnexion automatique après 30 minutes d'inactivité
- Si la session expire, affiche : "Session expirée, veuillez vous reconnecter."
- Redirige vers /login automatiquement

CORRECTION 2 — MOT DE PASSE FORT sur /register :
- Vérifie que le mot de passe fait au moins 8 caractères
- Vérifie qu'il contient au moins 1 chiffre
- Vérifie qu'il contient au moins 1 lettre majuscule
- Si une règle n'est pas respectée, affiche un message d'erreur clair en rouge

CORRECTION 3 — PROTECTION CSRF :
- Installe Flask-WTF avec pip
- Initialise la protection CSRF sur toute l'application
- Ajoute le token CSRF dans tous les formulaires POST des templates HTML

Commence par la Correction 1.
```

---

## ✅ Étape 3 — Tester manuellement

Lance l'app en local. Ouvre un **deuxième terminal** (`Ctrl+Alt+T`) :

```bash
cd ~/Bureau/SYNDICPROF1
source venv/bin/activate
python3 app.py
```

Ouvre **http://localhost:5000** dans le navigateur et vérifie :

- [ ] Tu peux te connecter avec ton compte admin
- [ ] Sur /register, essaie le mot de passe `123` → doit être **refusé**
- [ ] Sur /register, essaie `password1` → doit être **refusé** (pas de majuscule)
- [ ] Sur /register, essaie `Password1` → doit être **accepté**

Arrête l'app : dans le deuxième terminal, appuie sur `Ctrl+C`

---

## ✅ Étape 4 — Sauvegarder

Dans Claude Code :

```
Fais git add, git commit "security: session + password + csrf", git push.
```

Puis quitte :
```
/exit
```

### 🎉 Fin du Jour 2

**✅ Sécurité 100% terminée. Tu n'y reviens plus jamais.**

---

---

# 🎨 JOUR 3 — Page d'accueil (3h)

> **Objectif :** La page que voit ton prospect en premier.
> C'est ton vendeur silencieux.

---

## ✅ Étape 1 — Ouvrir le projet

```bash
cd ~/Bureau/SYNDICPROF1
source venv/bin/activate
claude
```

---

## ✅ Étape 2 — Refaire la page d'accueil

Colle ce prompt :

```
Refais complètement la page d'accueil de SyndicPro (la route / et son template).

COULEURS ET POLICES :
- Fond principal : #0A0E1A (bleu très foncé)
- Couleur accent : #00C896 (vert)
- Polices : importe depuis Google Fonts → Syne (titres) + DM Sans (texte)
- Garde Bootstrap 5 existant pour la structure

NAVBAR en haut :
- Gauche : logo "SyndicPro" avec "Pro" en vert #00C896
- Centre : liens Fonctionnalités / Tarifs / Contact (couleur grise)
- Droite : bouton "Se connecter" (contour blanc) + bouton "Essai gratuit 30j" (fond vert)

SECTION 1 — HERO :
- Badge au-dessus du titre : "🇹🇳 Fait en Tunisie — 100% adapté au marché local"
  (fond vert transparent, texte vert, coins arrondis)
- Titre H1 : "Fini les impayés qui traînent. SyndicPro fait tout pour vous."
  (le mot "SyndicPro" en couleur verte #00C896)
- Sous-titre : "Relances automatiques, paiement en ligne, contrôle d'accès badges.
  La seule solution syndic pensée pour la Tunisie."
- 2 boutons côte à côte :
  "Démarrer gratuitement" (fond vert, texte noir)
  "Voir une démo →" (contour blanc, texte blanc)
- 3 statistiques sous les boutons, séparées par une ligne horizontale :
  "94% taux de recouvrement" | "30 jours d'essai gratuit" | "0 intervention humaine"

SECTION 2 — 6 FONCTIONNALITÉS en grille 3 colonnes × 2 lignes :
Chaque carte : fond #111827, bordure #1F2937, coins arrondis, padding 1.5rem

Carte 1 : 🏢 Gestion appartements
"Organisez vos blocs, suivez chaque appartement et son historique."

Carte 2 : 💰 Encaissements & crédit
"Enregistrez les paiements en 10 secondes. Crédit résiduel automatique."

Carte 3 : 📊 Tableau comptable
"Vue 12 mois exportable Excel. Chaque centime tracé."

Carte 4 : 🔑 Contrôle badges accès — CARTE SPÉCIALE :
- Bordure verte #00C896 au lieu de grise
- Fond légèrement vert transparent : rgba(0,200,150,0.04)
- Ajoute un badge "EXCLUSIF EN TUNISIE" en vert au-dessus du titre
- Description : "Badge suspendu automatiquement après 3 mois impayés.
  Réactivé en 10 secondes dès paiement en ligne."

Carte 5 : 🔔 Relances automatiques
"WhatsApp progressif chaque semaine. Poli, ferme, puis urgent."

Carte 6 : 🎫 Tickets maintenance
"Résidents et gestionnaire communiquent directement dans l'app."

SECTION 3 — TARIFICATION (3 cartes côte à côte) :

Carte Starter :
- Titre : STARTER
- Prix : 30 DT / mois
- Description : Moins de 20 appartements
- Liste : ✓ Gestion appartements / ✓ Encaissements / ✓ Tableau comptable / ✓ Tickets / ✓ Export Excel
- Bouton : "Commencer gratuitement" (contour)

Carte Pro (milieu) :
- Badge "⭐ Populaire" en haut (fond vert)
- Titre : PRO
- Prix : 50 DT / mois
- Description : 20 à 75 appartements
- Liste : ✓ Tout du Starter / ✓ Relances WhatsApp auto / ✓ Paiement Konnect / ✓ 🔑 Contrôle badges / ✓ Rapports PDF
- Bordure verte
- Bouton : "Commencer gratuitement" (fond vert, texte noir)

Carte Enterprise :
- Titre : ENTERPRISE
- Prix : 75 DT / mois
- Description : Plus de 75 appartements
- Liste : ✓ Tout du Pro / ✓ Agent IA WhatsApp / ✓ Import relevé bancaire / ✓ Support prioritaire
- Bouton : "Commencer gratuitement" (contour)

FOOTER :
- Gauche : © 2026 SyndicPro — Fait en Tunisie 🇹🇳
- Droite : contact@syndicpro.tn

Quand c'est fait, commit "ux: new landing page" et push.
```

---

## ✅ Étape 3 — Vérifier le résultat en local

Ouvre un **deuxième terminal** (`Ctrl+Alt+T`) :

```bash
cd ~/Bureau/SYNDICPROF1
source venv/bin/activate
python3 app.py
```

Va sur **http://localhost:5000** et vérifie :

- [ ] Page sombre avec fond #0A0E1A
- [ ] Logo "SyndicPro" avec "Pro" en vert
- [ ] Les 3 tarifs s'affichent correctement
- [ ] Carte badges avec bordure verte et badge "EXCLUSIF EN TUNISIE"
- [ ] Les boutons "Se connecter" et "Essai gratuit" fonctionnent

Si quelque chose ne va pas → reviens dans Claude Code et décris le problème.

Arrête l'app : `Ctrl+C`

### 🎉 Fin du Jour 3

---

---

# 🎨 JOUR 4 — Dashboard admin + corrections visuelles (2h)

---

## ✅ Étape 1 — Ouvrir le projet

```bash
cd ~/Bureau/SYNDICPROF1
source venv/bin/activate
claude
```

---

## ✅ Étape 2 — Corrections et améliorations

Colle ce prompt :

```
Corrige ces bugs visuels et améliore le dashboard admin de SyndicPro.
Montre-moi le code avant chaque modification. J'approuve, tu modifies.

CORRECTION 1 — Page /register affiche seulement 75 DT :
- Cherche le template de la page /register
- Affiche les 3 tarifs correctement côte à côte :
  Starter 30 DT — moins de 20 appartements
  Pro 50 DT — 20 à 75 appartements
  Enterprise 75 DT — plus de 75 appartements

CORRECTION 2 — Navbar montre des liens aux visiteurs non connectés :
- Les liens "Tableau de bord", "Tickets", "Export Excel" ne doivent
  apparaître QUE si l'utilisateur est connecté
- Avant connexion : affiche seulement "Connexion" et "S'inscrire"
- Après connexion : affiche tous les liens

CORRECTION 3 — Trop de messages flash lors d'un paiement :
- Maximum 2 messages flash visibles en même temps
- Si plus de 2 messages sont générés, garde seulement les 2 plus importants

AMÉLIORATION 4 — Dashboard admin : 4 KPIs en haut :
Dans le template du dashboard admin, avant le contenu existant, ajoute
4 cartes côte à côte (Bootstrap grid, 4 colonnes) :

Carte 1 — Taux de recouvrement ce mois :
- Calcule depuis la BDD : (appartements payés ce mois / total appartements) × 100
- Affiche en vert si > 80%, orange si 60-80%, rouge si < 60%

Carte 2 — Total encaissé ce mois :
- Somme de tous les paiements du mois en cours depuis la BDD
- Affiche en DT

Carte 3 — Total dépensé ce mois :
- Somme de toutes les dépenses du mois en cours depuis la BDD
- Affiche en DT

Carte 4 — Solde de trésorerie :
- Total encaissé depuis le début - Total dépensé depuis le début
- Affiche en DT, vert si positif, rouge si négatif

Design des 4 cartes : fond #111827, bordure #1F2937, coins arrondis 12px,
chiffre en grand, font-weight 800, label en petit gris au-dessus.

AMÉLIORATION 5 — Colonne Actions dans le tableau des impayés :
- Ajoute une colonne "Actions" dans le tableau des appartements impayés
- Bouton "📨 Relancer" par ligne, grisé (disabled)
- Tooltip au survol : "Bientôt disponible — Relances WhatsApp arrivent en V2"

Commit "ux: register + navbar + dashboard KPIs" et push quand tout est fait.
```

---

## ✅ Étape 3 — Vérifier en local

```bash
python3 app.py
```

Va sur **http://localhost:5000** et vérifie :

- [ ] /register montre 3 tarifs (30 / 50 / 75 DT)
- [ ] Page d'accueil sans connexion → navbar propre (pas de liens dashboard)
- [ ] Connexion admin → 4 cartes KPI visibles en haut du dashboard
- [ ] Tableau impayés → colonne Actions avec bouton grisé

Arrête l'app : `Ctrl+C`

### 🎉 Fin du Jour 4

---

---

# 🎨 JOUR 5 — Dashboard résident + test final (2h)

---

## ✅ Étape 1 — Ouvrir le projet

```bash
cd ~/Bureau/SYNDICPROF1
source venv/bin/activate
claude
```

---

## ✅ Étape 2 — Dashboard résident

Colle ce prompt :

```
Améliore le tableau de bord du résident (utilisateurs avec rôle "resident").

Quand un résident se connecte, sa page doit afficher dans cet ordre :

BLOC 1 — Statut principal (très visible, en haut) :
Si tous les mois sont payés :
  → Grand encadré vert avec ✅ "Vous êtes à jour — Merci !"
Si des mois sont impayés :
  → Grand encadré rouge avec ❌ "X mois impayés — Montant dû : X DT"
  (X = le vrai nombre calculé depuis la BDD pour CE résident)

BLOC 2 — Informations de son appartement (carte) :
- Numéro d'appartement et nom du bloc
- Redevance mensuelle en DT
- Crédit disponible (affiche seulement si > 0 DT)
- Prochain mois à payer

BLOC 3 — Historique des 6 derniers mois (tableau simple) :
Colonnes : Mois | Statut | Montant payé
- Ligne fond vert clair = mois payé avec ✅
- Ligne fond rouge clair = mois impayé avec ❌
Données réelles depuis la BDD pour CE résident uniquement.

BLOC 4 — Actions rapides (2 boutons côte à côte en bas) :
- "🎫 Créer un ticket" → redirige vers /tickets/new
- "📋 Mes tickets" → redirige vers /tickets

Design cohérent : fond sombre #0A0E1A, cartes #111827, vert #00C896.

Commit "ux: resident dashboard" et push.
```

---

## ✅ Étape 3 — Test final complet

Lance l'app :

```bash
python3 app.py
```

Va sur **http://localhost:5000** et coche **tout** :

### Sécurité
- [ ] Sur /login, essaie 6 fois avec un mauvais mot de passe → message rate limit après 5
- [ ] Sur /register, essaie `abc` → refusé
- [ ] Sur /register, essaie `password1` → refusé (pas de majuscule)
- [ ] Sur /register, essaie `Password1` → accepté ✅

### Page d'accueil
- [ ] Page sombre et professionnelle
- [ ] Logo avec "Pro" en vert
- [ ] 3 tarifs visibles : 30 / 50 / 75 DT
- [ ] Carte badges avec bordure verte et badge "EXCLUSIF EN TUNISIE"
- [ ] Navbar sans liens de navigation (juste Connexion et S'inscrire)

### Dashboard admin
- [ ] Connexion admin fonctionne
- [ ] 4 cartes KPI visibles en haut (taux / encaissé / dépensé / solde)
- [ ] Tableau impayés avec bouton "Relancer" grisé
- [ ] Navbar après connexion montre tous les liens

### Dashboard résident
- [ ] Connexion résident fonctionne
- [ ] Grand badge vert ou rouge visible en haut
- [ ] Historique 6 mois affiché avec couleurs
- [ ] 2 boutons d'action en bas

Arrête l'app : `Ctrl+C`

---

## ✅ Étape 4 — Déploiement final sur Render

Dans Claude Code :

```
Fais un git add de tout, git commit "v1.2: security + ux complete", git push.
```

Puis dans ton navigateur, va sur **render.com** :

1. Ouvre ton service SyndicPro
2. Clique **"Manual Deploy"** → **"Deploy latest commit"**
3. Attends 3-4 minutes
4. Va sur **syndicpro.tn** et refais toute la checklist ci-dessus

Quitte Claude Code :
```
/exit
```

### 🎉 Fin du Jour 5 — Le produit est prêt à être montré

---

---

## 🔁 COMMANDES À RETENIR

Tu fais ça **chaque matin** pour démarrer :

```bash
cd ~/Bureau/SYNDICPROF1
source venv/bin/activate
claude
```

Tu fais ça **chaque soir** pour sauvegarder (depuis Claude Code) :

```
Fais git add, git commit "[description de ce que tu as fait]", git push.
```

Pour **tester l'app en local** (dans un deuxième terminal) :

```bash
cd ~/Bureau/SYNDICPROF1
source venv/bin/activate
python3 app.py
```

Puis ouvre **http://localhost:5000** dans ton navigateur.

Pour **arrêter l'app locale** :

```
Ctrl+C
```

---

## 🆘 SI TU BLOQUES

Reviens sur Claude et dis exactement :

```
Je suis au Jour [X], Étape [Y].
Voici ce que j'essaie de faire : [description]
Voici l'erreur exacte : [colle l'erreur]
Mon système : Linux Ubuntu
```

---

## 📁 FICHIERS IMPORTANTS

| Fichier | Contenu | À partager ? |
|---------|---------|-------------|
| `.env` | Tes mots de passe secrets | ❌ JAMAIS |
| `.env.example` | Modèle sans valeurs réelles | ✅ OK |
| `.gitignore` | Liste des fichiers à ne pas pousser sur GitHub | ✅ OK |
| `app.py` | Le cœur de ton application | ✅ OK |
| `requirements.txt` | Liste des dépendances Python | ✅ OK |

---

## 🎯 APRÈS LE JOUR 5

**Le Jour 6, tu n'ouvres plus le terminal.**

Tu prends ton téléphone et tu appelles les 10 premières personnes de ton réseau qui gèrent ou connaissent un syndic.

Le script :

> *"J'ai une plateforme de gestion de syndic, je cherche 3 personnes pour tester gratuitement 2 mois. Tu connais quelqu'un ?"*

**C'est le vrai travail qui commence.**

---

*Généré par Claude — 1er avril 2026*
*Repartage ce fichier à Claude à chaque nouvelle session si tu bloques.*
