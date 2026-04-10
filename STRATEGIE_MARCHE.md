# SyndicPro — Stratégie Marché & Positionnement
**Rédigé le 10 avril 2026 — Confidentiel**

---

## 1. TAILLE DU MARCHÉ TUNISIEN

### Estimation du parc immobilier en copropriété

| Indicateur | Estimation | Raisonnement |
|---|---|---|
| Logements urbains en Tunisie | ~2 400 000 | INS 2024 |
| Part en immeuble collectif | ~35% | Densité urbaine Tunis / Sfax / Sousse |
| Appartements en copropriété | ~840 000 | |
| Taille moyenne d'un immeuble | 25 à 40 appartements | Réalité terrain |
| **Nombre d'immeubles (TAM brut)** | **~25 000 immeubles** | |
| Gérés de façon numérique (2026) | < 2% | Marché naissant |
| **Opportunité non captée** | **~24 500 immeubles** | |

### Revenus potentiels selon le scénario

| Scénario | Immeubles clients | ARPU moyen | Chiffre d'affaires annuel |
|---|---|---|---|
| Court terme (2 ans) | 300 | 60 DT/mois | **216 000 DT/an** |
| Moyen terme (4 ans) | 1 000 | 75 DT/mois | **900 000 DT/an** |
| Long terme (6 ans) | 3 000 | 85 DT/mois | **3 060 000 DT/an** |

> Le marché est large, quasi vierge, et aucun acteur n'a encore pris une position dominante.

---

## 2. ANALYSE CONCURRENTIELLE

### Les acteurs en présence

#### Syndiki (syndiki.tn)
- **Prix :** 1 DT/appartement/mois (ex. 30 DT pour 30 appartements)
- **Forces :** Prix très bas, startup labelisée ministère, AG + votes en ligne, reçus automatiques
- **Faiblesses :** Pas de paiement en ligne, pas de WhatsApp automatisé, pas d'états financiers SCE, zéro fonctionnalités avancées (ascenseurs, litiges, caméras, virements...)
- **Cible :** Petites résidences sensibles au prix

#### E-Syndic (e-syndic.tn)
- **Prix :** Non publié — estimé 150 à 400 DT/mois (3 paliers)
- **Forces :** App mobile iOS + Android, IA EVA (OCR factures par WhatsApp), GED, WhatsApp Business officiel, AG numérique
- **Faiblesses :** Prix élevé et non transparent, complexe à onboarder, inaccessible aux petites résidences
- **Cible :** Gestionnaires professionnels, grands immeubles, entreprises de facility management

#### Gestion manuelle (WhatsApp + Excel + virements)
- **Prix :** Gratuit
- **Forces :** Zéro coût, connu de tous
- **Faiblesses :** Aucune traçabilité, litiges fréquents, impayés non suivis, trésorerie opaque
- **Cible :** 98% du marché actuel — c'est notre principal adversaire

#### Solutions françaises (Matera, ImmoFacile...)
- Non adaptées à la réglementation tunisienne (loi 96-112, SCE, Dinar, banques locales)
- Inutilisables en pratique pour le marché tunisien

---

### Matrice fonctionnelle comparée

| Fonctionnalité | SyndicPro | Syndiki | E-Syndic | Manuel |
|---|---|---|---|---|
| Paiement en ligne résidents | ✅ Flouci / Konnect | ❌ | ✅ | ❌ |
| Virement bancaire avec décharge photo | ✅ | ❌ | ❌ | ❌ |
| Push notifications PWA | ✅ | ❌ | ✅ App | ❌ |
| WhatsApp automatisé (relances, alertes) | ✅ Fonnte | ❌ | ✅ | ❌ |
| États financiers SCE (loi 96-112) | ✅ | ❌ | ✅ partiel | ❌ |
| Gestion ascenseurs + IoT | ✅ | ❌ | ❌ | ❌ |
| Registre accès numérique | ✅ | ❌ | ❌ | ❌ |
| Gestion litiges + huissier | ✅ | ❌ | ❌ | ❌ |
| Appels de fonds | ✅ | ❌ | ✅ | ❌ |
| Assemblées générales + votes | ✅ | ✅ | ✅ | ❌ |
| Traçabilité lectures annonces | ✅ | ❌ | ❌ | ❌ |
| Système de crédit automatique | ✅ | ❌ | ❌ | ❌ |
| Caméras de surveillance | ✅ | ❌ | ❌ | ❌ |
| Multi-résidences (1 compte) | ✅ | ❌ | ✅ | ❌ |
| Assistant IA intégré | ✅ Claude | ❌ | ✅ EVA | ❌ |
| OCR factures (photo → dépense) | 🔜 à venir | ❌ | ✅ | ❌ |
| GED documents | 🔜 à venir | ❌ | ✅ | ❌ |
| Compteurs eau / électricité | 🔜 à venir | ❌ | ❌ | ❌ |
| App mobile native iOS / Android | ❌ PWA | ✅ | ✅ | ❌ |

---

### Carte de positionnement

```
                     PRIX ÉLEVÉ
                          │
              E-Syndic    │   ← Enterprise / Pro
              ~300 DT/m   │     features complètes
                          │
    PEU DE   ─────────────┼─────────────────── BEAUCOUP DE
    FEATURES              │     ★ SyndicPro     FEATURES
                          │      79 DT/m
              Syndiki      │     Meilleur rapport
              20-50 DT/m  │     qualité / prix
                          │
                     PRIX BAS
```

**Conclusion :** SyndicPro doit occuper le quadrant haut-droite (beaucoup de features, prix raisonnable). C'est le sweet spot : plus riche que Syndiki, plus abordable que E-Syndic.

---

## 3. AVANTAGES EXCLUSIFS SYNDICPRO (MOAT)

Ces fonctionnalités n'existent chez aucun concurrent direct en Tunisie :

1. **Virement bancaire avec confirmation photo** — résident soumet sa décharge, admin valide en 1 clic avec calcul automatique des frais bancaires
2. **Gestion ascenseurs + capteur IoT** — monitoring temps réel, incident automatique, notification résidents
3. **Registre d'accès numérique** — entrées/sorties visiteurs horodatées
4. **Traçabilité lectures annonces** — admin sait exactement qui a lu quoi
5. **Système de crédit automatique** — trop-perçu crédité au prochain mois
6. **États financiers SCE** — bilan, état de résultat, flux de trésorerie PDF conformes loi tunisienne 96-112
7. **Charges bancaires comptabilisées** — compte 627 séparé dans l'état de résultat

---

## 4. GRILLE TARIFAIRE PROPOSÉE

### Problèmes de la grille actuelle

| Ancienne grille | Problème |
|---|---|
| 30 DT < 20 appts | Sous-valorisé par rapport aux features délivrées |
| 50 DT 20-75 appts | Correct mais sans palier enterprise |
| 75 DT > 75 appts | Plafond trop bas pour les grands ensembles |
| Pas de plan gestionnaire | Manque le segment le plus rentable |

---

### Nouvelle grille tarifaire

#### STARTER — 49 DT / mois
*Petites résidences jusqu'à 25 appartements*

Inclus :
- Gestion appartements, résidents, paiements
- Virements bancaires avec photo décharge
- Tickets de réclamation + photos
- Annonces + traçabilité lectures
- Push notifications (PWA)
- WhatsApp automatisé (relances impayés)
- États financiers SCE complets (PDF)
- Assemblées générales + votes
- Litiges + gestion huissier
- Historique complet + reçus PDF
- **Essai gratuit 30 jours — Sans carte bancaire**

---

#### STANDARD — 79 DT / mois ⭐ *Recommandé*
*Résidences de 26 à 80 appartements*

Tout Starter, plus :
- Gestion ascenseurs + endpoint IoT
- Surveillance caméras (annuaire + snapshots)
- Appels de fonds (grands travaux)
- Encaissements divers (badges, clés, pénalités)
- Registre d'accès numérique
- Compteurs individuels eau / électricité *(disponible Q3 2026)*
- Assistant IA Claude intégré
- Rapport mensuel automatique PDF

---

#### PREMIUM — 129 DT / mois
*Grandes résidences de plus de 80 appartements*

Tout Standard, plus :
- GED documents illimitée (règlement copro, contrats, PV AG...)
- OCR factures par photo (IA → dépense créée automatiquement)
- Import / export Excel résidents & données comptables
- Tableaux de bord analytiques avancés
- Support prioritaire (réponse < 4h)

---

#### PRO — 249 DT / mois
*Gestionnaires professionnels multi-résidences*

Tout Premium, sur jusqu'à **10 résidences** depuis un seul compte :
- Tableau de bord consolidé toutes résidences
- Facturation et comptabilité séparées par résidence
- Marque blanche (logo du gestionnaire)
- Onboarding & formation dédiés
- Account manager dédié

> **1 client PRO = 10 clients Standard en chiffre d'affaires.**
> C'est le segment à cibler en priorité pour la croissance rapide.

---

### Options complémentaires

| Option | Prix | Détail |
|---|---|---|
| Abonnement annuel | **2 mois offerts** | Équivalent à -17% sur le mensuel |
| Module compteurs eau/élec | +15 DT/mois | Add-on disponible sur Starter |
| SMS (en plus du WhatsApp) | +10 DT/mois | Pour résidents sans WhatsApp |

---

### Comparaison prix / valeur vs Syndiki

| Critère | Syndiki | SyndicPro Standard |
|---|---|---|
| Prix (40 appartements) | 40 DT/mois | 79 DT/mois |
| Écart | — | +39 DT (+98%) |
| Paiement en ligne | ❌ | ✅ |
| WhatsApp automatisé | ❌ | ✅ |
| Virements avec décharge | ❌ | ✅ |
| États financiers SCE PDF | ❌ | ✅ |
| Ascenseurs + IoT | ❌ | ✅ |
| **ROI concret** | Zéro automatisation | Récupère 1 mois impayé = rembourse 2 ans d'abonnement |

---

## 5. STRATÉGIE D'ACQUISITION CLIENT

### Canaux prioritaires (classés par ROI)

#### Canal 1 — Gestionnaires professionnels (B2B)
- Cibler les ~100 sociétés de gestion immobilière en Tunisie
- Un seul contrat PRO = 10 résidences = 249 DT/mois
- Approche : démonstration personnalisée, 30 jours offerts
- Territoire : Tunis, Sousse, Sfax, Nabeul, Bizerte

#### Canal 2 — Bouche à oreille résidentiel
- Un immeuble satisfait = 3 à 5 recommandations dans le quartier
- Programme parrainage : 1 mois offert pour chaque syndic recommandé
- Les assemblées générales sont des moments de prescription naturels

#### Canal 3 — Notaires et promoteurs immobiliers
- Ils livrent des immeubles neufs qui ont besoin d'un syndic dès le premier jour
- Partenariat de référencement : commission sur 6 premiers mois
- Argument : "Votre immeuble livré avec un outil de gestion professionnel inclus"

#### Canal 4 — Réseaux sociaux tunisiens
- Groupes Facebook copropriétaires (très actifs en Tunisie)
- LinkedIn pour les gestionnaires professionnels
- Contenu : problèmes courants (impayés, pannes ascenseur, transparence comptable) → SyndicPro comme solution
- Vidéos courtes de démonstration (fonctionnalité par fonctionnalité)

#### Canal 5 — Associations professionnelles
- UTICA (Union Tunisienne de l'Industrie, du Commerce et de l'Artisanat)
- Chambres de commerce régionales
- Ordre des architectes et ingénieurs (prescripteurs)

---

## 6. ROADMAP PRODUIT ALIGNÉE SUR LE MARCHÉ

### Q2 2026 — Consolidation (déjà livré ✅)
- [x] Virements bancaires avec photo décharge + confirmation 1 clic
- [x] Charges bancaires dans les états financiers (compte 627 SCE)
- [x] Gestion ascenseurs + IoT + notifications résidents
- [x] Push notifications PWA (admin + résidents)
- [x] États financiers SCE complets (Bilan, Résultat, Flux PDF)

### Q3 2026 — Différenciation
- [ ] **Compteurs individuels eau / électricité** — débloque segment marché unique
- [ ] **GED documents** — stockage règlement, contrats, PV AG
- [ ] **OCR factures** — photo → dépense automatique (Claude Vision API)
- [ ] **Export Excel** — données comptables pour experts-comptables

### Q4 2026 — Croissance
- [ ] **Plan PRO multi-résidences** — tableau de bord consolidé
- [ ] **Page commerciale tarifaire** — avec comparatif Syndiki clair
- [ ] **Programme parrainage** — mois offert au parrain et au filleul
- [ ] **Signature électronique PV AG** — différenciateur légal

### 2027 — Scale
- [ ] **Application mobile native** (React Native) — combler le gap vs E-Syndic
- [ ] **SMS fallback** — résidents sans WhatsApp
- [ ] **Intégration comptable** — export format OHADA/SCE pour logiciels comptables
- [ ] **Internationalisation** — Maroc (même cadre juridique maghrébin)

---

## 7. POSITIONNEMENT ET SLOGAN

### Positionnement
> SyndicPro est la solution de gestion de copropriété la plus complète en Tunisie, conçue pour les syndics qui veulent professionnaliser leur gestion sans complexité ni coût excessif.

### Arguments clés (par cible)

**Pour le résident :**
> "Payez vos charges en ligne, suivez vos paiements, signalez une panne — tout depuis votre téléphone."

**Pour l'admin du syndic :**
> "Fini les relances manuelles par WhatsApp. SyndicPro envoie les rappels, encaisse les virements et tient votre comptabilité automatiquement."

**Pour le gestionnaire professionnel :**
> "Gérez 10 résidences comme si vous en aviez une seule. États financiers conformes SCE en un clic, pour tous vos clients."

### Slogan proposé
> **"SyndicPro — La copropriété, enfin professionnelle."**

---

## 8. RÉSUMÉ EXÉCUTIF

| Dimension | Situation actuelle | Objectif 2027 |
|---|---|---|
| Clients actifs | En démarrage | 500 immeubles |
| ARPU mensuel | 30-75 DT | 79 DT (moyenne) |
| CA annuel cible | — | 474 000 DT |
| Part de marché | < 1% | 2% (500/25 000) |
| Segment prioritaire | Toutes tailles | Gestionnaires PRO + Standard |
| Différenciateur n°1 | Paiement en ligne | Automatisation complète + IoT |

---

### Actions immédiates recommandées

1. **Remonter les prix** vers la nouvelle grille — la valeur délivrée le justifie largement
2. **Lancer le plan PRO** pour gestionnaires multi-résidences — levier de croissance x10
3. **Développer les compteurs eau/électricité** — fonctionnalité unique sur le marché
4. **Créer une page commerciale claire** avec les 4 plans et le comparatif Syndiki
5. **Démarcher 10 gestionnaires professionnels** en démonstration directe

---

*Document interne SyndicPro — syndicpro.tn — Mis à jour le 10 avril 2026*
