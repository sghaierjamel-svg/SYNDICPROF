# 🏢 SyndicPro Multi-Tenant v3.0

## 🎯 Version Multi-Tenant SaaS Professionnelle

Application complète de gestion de syndic avec système d'abonnements et gestion multi-organisations.

---

## ✨ NOUVEAUTÉS VERSION 3.0

### 🚀 Architecture Multi-Tenant
- **Chaque syndic = 1 organisation isolée** avec ses propres données
- **Gestion centralisée** par le super administrateur
- **Données complètement séparées** entre organisations
- **Sécurité renforcée** avec isolation totale

### 💰 Système d'Abonnements Automatique
- **Essai gratuit : 30 jours** pour tous les nouveaux clients
- **Tarification progressive** selon le nombre d'appartements :
  - **< 20 appartements** : 30 DT/mois
  - **20-75 appartements** : 50 DT/mois
  - **> 75 appartements** : 75 DT/mois
- **Gestion automatique des expirations** avec alertes
- **Blocage automatique** après expiration

### 👑 Dashboard Super Admin
- **Vue globale** de toutes les organisations
- **Statistiques en temps réel**
- **Activation/Désactivation** des organisations
- **Prolongation d'abonnements**
- **Changement de mot de passe sécurisé**

### 📊 Toutes les fonctionnalités existantes conservées
- Gestion des redevances mensuelles
- Tableaux trésorerie et comptable
- Système de tickets
- Alertes impayés
- Export Excel complet
- Interface moderne et responsive

---

## 📦 INSTALLATION COMPLÈTE

### Option 1 : NOUVELLE INSTALLATION (Pas d'anciennes données)

#### Étape 1 : Télécharger les fichiers
```bash
# Placez tous les fichiers dans un dossier
cd SyndicPro_MultiTenant
```

#### Étape 2 : Créer les dossiers nécessaires
```bash
mkdir database
mkdir templates
mkdir templates/superadmin
```

#### Étape 3 : Placer les fichiers
- `app_multitenant.py` → Racine
- `requirements.txt` → Racine
- `register.html` → templates/
- `subscription_status.html` → templates/
- `dashboard.html` (modifié) → templates/
- `superadmin/dashboard.html` → templates/superadmin/
- `superadmin/org_detail.html` → templates/superadmin/
- `superadmin/change_password.html` → templates/superadmin/

#### Étape 4 : Installation
```bash
# Windows
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app_multitenant.py

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 app_multitenant.py
```

#### Étape 5 : Premier lancement
```
✅ L'application va créer automatiquement :
   - La base de données multi-tenant
   - Le compte Super Admin

🔐 Connexion Super Admin :
   Email: superadmin@syndicpro.tn
   Mot de passe: SuperAdmin2024!
   
⚠️  CHANGEZ CE MOT DE PASSE immédiatement !
```

---

### Option 2 : MIGRATION DEPUIS VERSION ANCIENNE

#### Étape 1 : Sauvegarde
```bash
# Faites une copie complète de votre dossier actuel
cp -r SyndicPro SyndicPro_backup
```

#### Étape 2 : Ajouter les nouveaux fichiers
- Ajoutez `app_multitenant.py` à la racine
- Ajoutez `migrate_to_multitenant.py` à la racine
- Ajoutez les nouveaux templates HTML

#### Étape 3 : Lancer la migration
```bash
python migrate_to_multitenant.py
```

Le script va vous demander :
- Nom de votre organisation
- Email de contact
- Téléphone (optionnel)

#### Étape 4 : Résultat de la migration
```
✅ Toutes vos données sont migrées :
   - Utilisateurs
   - Appartements
   - Paiements
   - Dépenses
   - Tickets
   - Alertes

🎁 BONUS : 1 an d'abonnement gratuit offert !
```

#### Étape 5 : Activer la nouvelle version
```bash
# Renommer les fichiers
mv app.py app_old.py
mv app_multitenant.py app.py

# Lancer
python app.py
```

---

## 🔐 COMPTES D'ACCÈS

### Super Administrateur (VOUS)
```
Email: superadmin@syndicpro.tn
Mot de passe: SuperAdmin2024!
```
**⚠️ IMPORTANT : Changez ce mot de passe dès la première connexion !**

### Organisations Clientes
Chaque syndic s'inscrit via : `http://votre-domaine.com/register`

---

## 📖 GUIDE D'UTILISATION

### Pour VOUS (Propriétaire de l'application)

#### 1. Connexion Super Admin
1. Allez sur `http://localhost:5000/login`
2. Connectez-vous avec `superadmin@syndicpro.tn`
3. **CHANGEZ votre mot de passe** : Menu → Changer mot de passe

#### 2. Dashboard Super Admin
Vous voyez :
- ✅ Nombre total d'organisations
- ✅ Organisations actives/inactives
- ✅ Revenu mensuel total
- ✅ Liste complète des clients

#### 3. Gérer une organisation
- Cliquez sur **"Voir"** sur n'importe quelle organisation
- Vous pouvez :
  - Voir toutes les informations
  - Prolonger l'abonnement
  - Activer/Désactiver l'organisation
  - Voir les statistiques d'utilisation

#### 4. Prolonger un abonnement
```
1. Cliquez sur l'organisation
2. Section "Abonnement" → Sélectionnez la durée
3. Cliquez "Prolonger"
✅ L'abonnement est prolongé automatiquement !
```

#### 5. Désactiver une organisation
```
Si un client ne paie pas :
1. Allez sur sa page
2. Cliquez "Désactiver l'Organisation"
❌ L'organisation ne pourra plus se connecter
```

---

### Pour VOS CLIENTS (Les Syndics)

#### 1. Inscription
1. Vont sur `http://votre-domaine.com/register`
2. Remplissent le formulaire
3. Reçoivent **30 jours gratuits** automatiquement !

#### 2. Utilisation
- Gèrent leurs appartements
- Enregistrent les paiements
- Suivent les impayés
- Créent des tickets
- Exportent en Excel

#### 3. Vérifier leur abonnement
Menu → **Mon Abonnement** :
- Voir les jours restants
- Voir le prix selon leurs appartements
- Contacter pour renouvellement

---

## 💰 SYSTÈME DE TARIFICATION

### Comment ça marche ?

Le **prix est automatiquement calculé** selon le nombre d'appartements :

| Appartements | Prix/mois | Exemple |
|--------------|-----------|---------|
| 1 - 19 | 30 DT | Petite résidence |
| 20 - 75 | 50 DT | Résidence moyenne |
| 76+ | 75 DT | Grande résidence |

### Processus d'abonnement

1. **Inscription** → 30 jours gratuits
2. **Jour 23** → Alert