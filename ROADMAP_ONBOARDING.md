# Roadmap Onboarding SyndicPro

## Objectif
Réduire le temps de mise en route d'un nouveau syndic de "plusieurs jours" à "moins d'1 heure".

---

## Phase A — Import Excel ✅ EN COURS
**Priorité : HAUTE — le plus grand bloquant à l'adoption**

Permettre à un admin d'importer tous ses appartements et résidents en une seule fois via un fichier Excel.

### Fonctionnalités :
- Téléchargement d'un modèle Excel pré-formaté (avec instructions)
- Upload du fichier rempli → import en base
- Création automatique des bâtiments, appartements, résidents
- Génération de mots de passe temporaires pour les résidents
- Rapport d'import : ce qui a été créé / ignoré / en erreur
- Lien "Import" dans la sidebar admin

### Route : `/onboarding/import` + `/onboarding/template`
### Fichiers : `routes/onboarding.py`, `templates/onboarding_import.html`
### Dépendance : `openpyxl`

---

## Phase B — Setup Wizard (stepper 4 étapes)
**Priorité : MOYENNE**

Un assistant guidé qui s'affiche automatiquement pour les nouveaux comptes jusqu'à completion.

### Étapes :
1. Résidence (nom, adresse, téléphone)
2. Bâtiments + Appartements (ou rediriger vers import Excel)
3. Résidents (ou importer)
4. Paramètres optionnels (Konnect, WhatsApp)

### Mécanisme :
- Champ `setup_completed` (Boolean) sur `Organization`
- Wizard affiché si `setup_completed = False`
- Bouton "Passer" pour fermer sans compléter
- Checklist de progression sur dashboard

### Fichiers : `routes/onboarding.py` (ajout), `templates/setup_wizard.html`

---

## Phase C — Checklist de progression sur Dashboard
**Priorité : BASSE**

Visible tant que le setup n'est pas 100% complet.

```
✅ Compte créé
✅ Résidence configurée
⬜ Appartements ajoutés (0 appartements)
⬜ Résidents invités (0 résidents)
⬜ Premier encaissement enregistré
```

### Mécanisme :
- Calculé à chaque chargement du dashboard admin
- Disparaît quand toutes les étapes sont vertes
- Lien direct vers chaque section pour compléter

---

## Phase D — Email de bienvenue automatique
**Priorité : BASSE (nécessite SMTP ou SendGrid)**

- Email envoyé au nouvel admin avec lien de connexion + guide démarrage
- Email envoyé à chaque résident créé avec ses identifiants temporaires

---

## État d'avancement

| Phase | Description | Statut |
|-------|-------------|--------|
| A | Import Excel | 🔄 En cours |
| B | Setup Wizard | ⏳ À faire |
| C | Checklist Dashboard | ⏳ À faire |
| D | Email bienvenue | ⏳ À faire |
