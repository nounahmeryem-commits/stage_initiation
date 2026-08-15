# 📋 CAHIER DES CHARGES DÉTAILLÉ : INTERFACE UTILISATEUR & DASHBOARD ANALYTIQUE
> **Projet :** CUMAREX CostTrack v3 — Suivi, Consolidation et Analyse des Coûts de Production  
> **Document :** Spécifications Détaillées des Écrans, KPIs, Graphiques, Analyses Métiers & Comparateur Inter-Journées  
> **Destinataire :** Stagiaire Développeur  
> **Émetteur :** Superviseur de Stage  
> **Version :** 3.1 — Guide de Réalisation Exhaustif (8 Écrans Analytiques)  

---

## 🎯 1. Vision et Objectifs de l'Application

L'interface **CUMAREX CostTrack v3** est l'outil central d'aide à la décision pour la conserverie de poisson CUMAREX S.A. Elle transforme les 6 rapports PDF journaliers bruts en un **tableau de bord visuel, interactif et dynamique**.

### 🎯 Objectifs fondamentaux :
1. **Visibilité 360° :** Traduire les données brutes des PDF en métriques opérationnelles et financières claires.
2. **Contrôle & Détection des Dérives :** Repérer instantanément les pertes de rendement, les retards de main-d'œuvre et les surcoûts par rapport aux fiches techniques standards (fiches RR-125A).
3. **Analyses Comparatives Multi-Niveaux :**
   * **Réel vs Standard** (écarts fiches techniques)
   * **Site 1 (S1 / CX0) vs Site 2 (S2 / CX1)** (compétitivité des usines)
   * **Fournisseur vs Fournisseur** (qualité des lots)
   * **Jour J vs Jour J-X (Comparateur de deux dossiers/dates)** (progression et variations temporelles)
4. **Ergonomie & Fluidité :** Filtrage instantané par Date, Site, Espèce, Client et Marque sans rechargement de page.

---

## 🎛️ 2. Ergonomie Générale & Filtres Persistants (Header)

L'application est organisée en **Single Page Application (SPA)** avec un menu latéral (Sidebar) et une barre de filtres globale en haut de page.

```text
┌──────────────────────────────────────────────────────────────────────────────────────────────────────┐
│  📊 CUMAREX CostTrack v3      [📅 Date: 01/06/2026]  [🏭 Site: Tous]  [🐟 Poisson: Tous]  [🏷️ Marque] │
├────────────────────┬─────────────────────────────────────────────────────────────────────────────────┤
│  MENU LATÉRAL      │  ZONE D'AFFICHAGE DU MODULE SÉLECTIONNÉ                                         │
│                    │                                                                                 │
│  🏠 1. Vue Générale│  [ 4 Cartes KPI Principales avec indicateurs d'écarts colorés ]                 │
│  🐟 2. Rendements  │                                                                                 │
│  ⏱️ 3. Main d'Œuvre │  [ Zone Graphiques : Barres, Courbes, Cascades Waterfall, Donut ]               │
│  📦 4. Fiches Coûts│                                                                                 │
│  💰 5. Coût Global │  [ Tableaux Interactifs : Tris multicritères, Recherches, Exports ]             │
│  📋 6. Bilan Jour  │                                                                                 │
│  🔄 7. Analyses X  │                                                                                 │
│  ⚖️ 8. Comparateur │                                                                                 │
└────────────────────┴─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📊 3. Spécifications Détaillées des 8 Écrans de l'Interface

---

### 🏠 ÉCRAN 1 : VUE D'ENSEMBLE & SYNTHÈSE USINE (Executive Dashboard)

#### 🎯 Sens Métier :
Donner en 5 secondes à la Direction Générale et aux Directeurs d'Usines la santé globale de la production du jour : *Combien a-t-on produit ? Sommes-nous rentables ? Le rendement est-il au niveau ? Où sont les dérives urgentes ?*

#### 📁 Sources de données :
Consolidation de `C.Global.pdf`, `Rendement.pdf`, `Mod S1/S2.pdf`, `Par Article.pdf`.

#### 📌 Cartes KPIs (Bandeau supérieur) :
| KPI | Définition & Formule de Calcul | Unité | Code Couleur / Seuil |
| :--- | :--- | :---: | :---: |
| **Volume Total Produit** | $\sum(\text{Production})$ depuis `C.Global.pdf` | Boîtes / Caisses | Bleu neutre |
| **Rendement Matière Global** | $\frac{\text{Total Filets (kg)}}{\text{Total Poisson Brut (kg)}} \times 100$ | % | 🟢 Si $\ge 38\%$, 🔴 Si $< 38\%$ |
| **Productivité MOD Moyenne** | Moyenne pondérée des Min/Kg toutes espèces confondues | Min / Kg | 🟢 Si $\le 4.2$, 🔴 Si $> 4.2$ |
| **Chiffre d'Affaires PMV** | $\sum(\text{PMV})$ valeur marchande des boîtes produites | DH | Bleu neutre |
| **Taux de Marge Nette** | $\frac{\sum \text{Marge Nette}}{\sum \text{PMV}} \times 100$ | % | 🟢 Si $\ge 30\%$, 🟠 Si $[20-30\%]$, 🔴 Si $< 20\%$ |

#### 📈 Graphiques & Visualisations :
1. **Graphique 1 — Chiffre d'Affaires vs Coûts du Jour (Stacked Bar Chart) :**
   * *Axe X :* Sites (Site 1, Site 2, Total Usine).
   * *Barres empilées :* Coûts Directs + Frais Fabrication + Charges Fixes + Marge Nette.
   * *Ligne superposée :* PMV (Prix de vente total en DH).
2. **Graphique 2 — Jauges de Rendement par Site (Radial / Gauge Charts) :**
   * Deux jauges côte à côte : Rendement Site 1 vs Rendement Site 2 avec repère cible standard (38%).
3. **Graphique 3 — Répartition de la Production par Marque (Donut Chart) :**
   * Parts de volume en % pour Mercadona/Hacendado, Conad, Alia, etc.
4. **Tableau des Alertes et Anomalies Critiques (Top Dérives) :**
   * Liste des dérives majeures du jour avec badges d'urgence.

---

### 🐟 ÉCRAN 2 : ANALYSE DES RENDEMENTS MATIÈRE & FOURNISSEURS

#### 🎯 Sens Métier :
Le poisson entier représente plus de **50% du coût de fabrication**. Cet écran permet de traquer les pertes de matière première, d'évaluer la qualité livrée par les fournisseurs et de mesurer l'efficacité de découpe des deux sites.

#### 📁 Source de données :
`Rendement.pdf` (`df_entrees` et `df_summary`) + `Résume.pdf` (`matiere_premiere`).

#### 📌 Cartes KPIs :
| KPI | Définition & Source | Unité | Alerte |
| :--- | :--- | :---: | :---: |
| **Poisson Brut Réceptionné** | $\sum(\text{Poids BR})$ des lots du jour | kg | Neutre |
| **Filets Utilisables Obtenus** | $\sum(\text{Filets})$ obtenus après transformation | kg | Neutre |
| **Rendement Moyen Usine** | $\frac{\text{Filets}}{\text{Poids Brut}} \times 100$ | % | 🔴 Si $< 38\%$ |
| **Taux de Marc / Déchets** | $\frac{\text{Marc}}{\text{Poids Brut}} \times 100$ | % | 🔴 Si $> 8\%$ |
| **Écart de Matière vs Standard** | $(\text{Rendement Réel} - 38\%) \times \text{Poids Brut}$ | kg (+/-) | 🟢 Gain / 🔴 Perte nette en kg |

#### 📈 Graphiques & Visualisations :
1. **Graphique 1 — Rendement Réel vs Rendement Standard par Espèce (Grouped Bar Chart) :**
   * Barres réelles vs Ligne cible standard (38%) avec infobulle sur le tonnage et l'écart en kg.
2. **Graphique 2 — Comparatif d'Efficacité Site 1 vs Site 2 par Espèce (Bar Chart côte à côte) :**
   * Efficacité comparée pour le même poisson sur S1 vs S2.
3. **Graphique 3 — Benchmarking des Fournisseurs & Origines (Scatter Plot / Barres Horizontales) :**
   * Fournisseurs (*Omalal, Aveida...*) et Origines (*Larache, Agadir...*) selon le rendement obtenu.
4. **Graphique 4 — Poisson Frais vs Poisson Congelé (Donut & Tableau d'écart) :**
   * Répartition du tonnage et comparaison des rendements Frais (`F`) vs Congelé (`C`).

#### 📋 Tableau des Lots Entrants :
* *Colonnes :* Site | Date Entrée | N° Frigo | Fournisseur | N° BR | Poids BR (kg) | Origine | Calibre Moule | Poids Filets (kg) | % Rendement | % Marc | Statut.

---

### ⏱️ ÉCRAN 3 : AUDIT DE LA MAIN-D'ŒUVRE DIRECTE (MOD & MOMG)

#### 🎯 Sens Métier :
La MOD est mesurée en **minutes passées par kilogramme produit (Min / Kg)**. Cet écran sert à auditer la productivité ouvrière, détecter les goulots d'étranglement poste par poste et suivre les coûts d'encadrement (MOMG).

#### 📁 Sources de données :
`Mod S1.pdf`, `Mod S2.pdf` et `Résume.pdf` (`mod_global`, `mod_par_code`).

#### 📌 Cartes KPIs :
| KPI | Définition & Source | Unité | Alerte |
| :--- | :--- | :---: | :---: |
| **Temps MOD Moyen Usine** | Ratio moyen Min/Kg toutes productions | Min / Kg | 🔴 Si $> 4.2$ |
| **Écart MOD vs Cible** | $\text{Min/Kg Réel} - \text{Min/Kg Standard}$ | Min / Kg | 🟢 Négatif (Rapide) / 🔴 Positif (Retard) |
| **Coût Total MOD Jour** | Total Dirhams versés en main-d'œuvre directe | DH | Neutre |
| **Poids des Services Communs** | $\frac{\text{Heures Communs}}{\text{Total Heures Usine}} \times 100$ | % | 🔴 Si $> 15\%$ |

#### 📈 Graphiques & Visualisations :
1. **Graphique 1 — Décomposition des 4 Postes de Production par Espèce : S1 vs S2 (Stacked Bar Chart) :**
   * Étetage (`ET`), Filetage (`FIL`), Emboîtage (`EMB`), Sertissage (`SRTI`).
   * Double barre par espèce : **Barre Gauche = Site 1 / Barre Droite = Site 2**.
2. **Graphique 2 — Suivi des Services Communs (Donut Chart) :**
   * Préparation Matière Première (`PR_MP`), Nettoyage (`NLE`), Commun (`COMM`).
3. **Graphique 3 — Courbe d'Évolution Temporelle de Productivité (Line Chart Multi-Jours) :**
   * Évolution chronologique du Min/Kg avec ligne de seuil cible.
4. **Matrice Thermique de Productivité (Heatmap Table) :**
   * Grille colorée (Vert = Efficace / Rouge = Retard) croisant *Espèces × Postes*.

---

### 📦 ÉCRAN 4 : COÛTS PAR ARTICLE & ÉCARTS FICHES TECHNIQUES (RR-125A)

#### 🎯 Sens Métier :
Chaque article fabriqué a une fiche technique standard (fiche RR-125A). Cet écran permet d'auditer chaque article au centime près et d'isoler l'origine exacte des surcoûts (matière, boîte, huile, main-d'œuvre, etc.).

#### 📁 Sources de données :
`Par Article.pdf` (`table_couts`) et `Résume.pdf` (`couts_serie`, `couts_unitaires`).

#### 📌 Cartes KPIs :
| KPI | Définition & Source | Unité | Alerte |
| :--- | :--- | :---: | :---: |
| **Nombre d'Articles Produits** | Nombre de fiches de fabrication du jour | Articles | Neutre |
| **Articles en Surcoût** | Nombre d'articles dont Coût Réel > Coût Standard | Articles | 🔴 Si $> 0$ |
| **Dérive Financière Totale** | $\sum(\text{Écart Unitaire} \times \text{Volume Boîtes})$ | DH | 🟢 Économie / 🔴 Surcoût global |
| **Article le Plus Déviant** | Code de l'article ayant généré le plus gros surcoût | Code | Badge rouge |

#### 📈 Visualisations & Graphiques :
1. **Graphique 1 — Graphique en Cascade (Waterfall Chart) de l'Article Sélectionné :**
   * *Barre départ :* Coût Standard Unitaire.
   * *15 Blocs flottants d'écarts :* Ingrédients (Poisson, Huile, Additif) + Emballages (Boîte, Étui, Divers) + Fabrication (MOD, MOMG, Frais Fab, Port, Charges fixes).
   * *Barre finale :* Coût Réel Constaté.
2. **Graphique 2 — Top 5 Surcoûts vs Top 5 Économies (Diverging Bar Chart) :**
   * Classement des articles par impact financier total en DH.
3. **Graphique 3 — Matrice Priorités : Volume Produit vs Dérive Unitaire (Scatter Plot) :**
   * Repérage immédiat des articles à fort volume en surcoût.

#### 📋 Fiche Technique Numérique Interactive :
* Réplique numérique fidèle avec cartouche d'en-tête et tableau complet des 15 lignes de coûts réels vs standards.

---

### 💰 ÉCRAN 5 : RENTABILITÉ COMMERCIALE & COÛT GLOBAL

#### 🎯 Sens Métier :
Piloter la rentabilité commerciale et financière des produits vendus. Détecter les marges faibles ou négatives et mesurer la contribution de chaque client/marque aux résultats.

#### 📁 Source de données :
`C.Global.pdf` (`produits`, `totaux_sites`, `total_general`).

#### 📌 Cartes KPIs :
| KPI | Définition & Source | Unité | Alerte |
| :--- | :--- | :---: | :---: |
| **Production Totale** | Volume global fabriqué | Boîtes | Neutre |
| **Chiffre d'Affaires PMV** | Prix Moyen de Vente $\times$ Volume | DH | Neutre |
| **Marge Brute Globale** | Total Marge Brute consolidée | DH & % | 🟢 Si $\ge 35\%$ |
| **Marge Nette Globale** | Total Marge Nette après charges fixes | DH & % | 🟢 Si $\ge 30\%$, 🔴 Si $< 20\%$ |
| **Charges Fixes Absorbées** | Total charges fixes imputées | DH | Neutre |

#### 📈 Visualisations & Graphiques :
1. **Graphique 1 — Répartition des Volumes par Marque / Client (Treemap / Donut) :**
   * Volume et % pour Mercadona/Hacendado, Conad, Alia, DE, etc.
2. **Graphique 2 — Classement des Produits par Marge Nette (%) (Horizontal Bar Chart) :**
   * Tri du plus rentable au moins rentable.
3. **Graphique 3 — Analyse de l'Effet Ciseau : Prix de Vente (PMV) vs Prix de Revient (PR) :**
   * Barres PR vs Ligne PMV avec zone rouge si vente à perte.
4. **Tableau de Bord Économique Comparatif Site 1 vs Site 2 :**
   * Vis-à-vis complet : Volumes, Coûts directs, Marge Brute et Marge Nette.

---

### 📋 ÉCRAN 6 : BILAN INDUSTRIEL JOURNALIER

#### 🎯 Sens Métier :
Vision d'ensemble 360° pour le Directeur d'Usine. Suivre les approvisionnements des usines amont (CAOMA/CAMAT), les ratios par caisse et les séries de fabrication.

#### 📁 Source de données :
`Résume.pdf` (les 9 sous-tables).

#### 📌 Cartes KPIs :
| KPI | Définition | Unité |
| :--- | :--- | :---: |
| **Ratio MOD / Caisse** | Coût de main-d'œuvre directe par caisse produite | DH / Caisse |
| **Ratio MOMG / Caisse** | Coût d'encadrement/indirects par caisse produite | DH / Caisse |
| **Ratio Frais Fab / Caisse** | Frais généraux d'usine par caisse | DH / Caisse |
| **Tonnage Réceptionné CAOMA vs CAMAT** | Répartition des volumes amont | kg |

#### 📈 Visualisations & Tableaux :
1. **Approvisionnements Matière Première CAOMA vs CAMAT (Bar Chart Comparatif) :**
   * Tonnages et prix moyen d'achat au kg.
2. **Tableau de Suivi des Séries de Fabrication (Séries A260...) :**
   * Tableau par série : Code Série, Format, Boîtes, Poids Filet, Heures MOD, Coût Total Série.
3. **Jauge de Performance Financière de la Journée :**
   * Marge globale dégagée sur la journée par rapport aux coûts engagés.

---

### 🔄 ÉCRAN 7 : ANALYSES CROISÉES & DÉTECTION DES DÉRIVES (Multi-Fichiers)

#### 🎯 Sens Métier :
Outil d'investigation avancée pour le Contrôleur de Gestion. Croise les données de fichiers différents pour révéler des anomalies masquées ou valider des arbitrages stratégiques.

#### 🔍 Les 3 Cas d'Analyses Croisées :
1. **Cas 1 — Rendement Atelier vs Rendement Comptabilisé :**
   * `Rendement.pdf` vs `Par Article.pdf` ➔ Détecter les écarts entre la pesée physique à l'entrée et l'imputation sur fiche.
2. **Cas 2 — Coût Financier des Retards MOD :**
   * `Mod S1/S2.pdf` vs `Par Article.pdf` ➔ Chiffrer en Dirhams l'impact d'un retard de +0.5 min/kg sur la marge finale.
3. **Cas 3 — Arbitrage Fournisseur Moins Cher vs Rendement Réel :**
   * `Rendement.pdf` vs `C.Global.pdf` ➔ Vérifier si acheter un poisson moins cher reste rentable après déduction des déchets.

---

### ⚖️ ÉCRAN 8 : COMPARATEUR INTER-JOURNÉES (Dossier Jour A vs Dossier Jour B)

#### 🎯 Sens Métier :
Permettre au Directeur de Production et au Contrôleur de Gestion de **mettre face à face deux journées complètes de production (ou deux dossiers de dates différentes)**, par exemple :
* *Aujourd'hui vs Hier (02/06 vs 01/06)*
* *Lundi vs Mardi*
* *Jour J vs Même jour de la semaine précédente*

> **Questions auxquelles cet écran répond :**  
> *« Avons-nous progressé ou régressé par rapport à hier ? Pourquoi le rendement global a-t-il chuté de 2.1% entre ces deux dates ? Quel poste MOD a ralenti la cadence ? Quelle marque a tiré la rentabilité vers le haut ? »*

#### 📁 Sources de données :
Ensemble des 6 rapports de la **Date A (Dossier A)** vs ensemble des 6 rapports de la **Date B (Dossier B)**.

#### 🎛️ Sélecteurs de l'Écran :
* **Sélecteur Date A (Date de Référence / Dossier 1) :** ex: `01/06/2026`.
* **Sélecteur Date B (Date de Comparaison / Dossier 2) :** ex: `02/06/2026`.
* **Boutons de raccourcis rapides :** `[Jour J vs Jour J-1]`, `[Semaine N vs Semaine N-1]`, `[Début de mois vs Fin de mois]`.

#### 📌 Cartes KPIs Différentielles (Bandeau en Vis-à-Vis avec Deltas $\Delta$) :
Chaque carte affiche la valeur du Jour A, la valeur du Jour B, l'écart absolu et l'écart en % avec code couleur dynamique :

| Indicateur Comparé | Valeur Jour A | Valeur Jour B | Écart Constaté ($\Delta$) | Interprétation Visuelle |
| :--- | :---: | :---: | :---: | :---: |
| **Volume Produit** | $162\,400$ boîtes | $184\,250$ boîtes | **$+21\,850$ boîtes (+13.5%)** | 🟢 Hausse de volume |
| **Rendement Matière** | $37.8\%$ | $35.9\%$ | **$-1.9\%$ points** | 🔴 Dégradation matière |
| **Productivité MOD** | $4.10$ Min/Kg | $4.45$ Min/Kg | **$+0.35$ Min/Kg (+8.5%)** | 🔴 Ralentissement ouvrier |
| **Chiffre d'Affaires PMV** | $1\,620\,000$ DH | $1\,845\,200$ DH | **$+225\,200$ DH (+13.9%)** | 🟢 Progression CA |
| **Taux Marge Nette** | $34.2\%$ | $31.8\%$ | **$-2.4\%$ points** | 🔴 Érosion de marge |

#### 📈 Graphiques & Visualisations Comparatives (Jour A vs Jour B) :
1. **Graphique 1 — Comparatif des Rendements par Espèce (Dual Bar Chart Jour A vs Jour B) :**
   * *Axe X :* Espèces de poisson.
   * *Barre Bleue (Jour A) vs Barre Violette (Jour B) vs Ligne Rouge (Standard 38%).*
   * *Utilité :* Isoler immédiatement quelle espèce exacte a vu son rendement chuter entre les deux jours.
2. **Graphique 2 — Comparatif de la MOD par Poste de Travail (Grouped Bar Chart Jour A vs Jour B) :**
   * *Axe X :* Postes de travail (Étetage `ET`, Filetage `FIL`, Emboîtage `EMB`, Sertissage `SRTI`, Services Communs `COMM`).
   * *Barres comparées Jour A vs Jour B :*
   * *Utilité :* Identifier si le ralentissement de productivité provient de l'étetage, du filetage ou d'un pic d'heures de nettoyage/entretien.
3. **Graphique 3 — Évolution du Mix Produit et des Marges par Marque (Horizontal Bar Chart Jour A vs Jour B) :**
   * Compare pour chaque client (*Mercadona, Conad, Alia...*) les volumes fabriqués et les marges nettes dégagées entre Jour A et Jour B.
4. **Graphique 4 — Pont d'Explication de Variation de Marge (Bridge / Waterfall Chart Jour A ➔ Jour B) :**
   * **Visualisation Financière Majeure :** Explique mathématiquement la variation de rentabilité entre les deux journées :
     * Marge Nette Jour A ➔ Impact Variation Volume ➔ Impact Rendement Poisson ➔ Impact Prix Ingrédients (Huile) ➔ Impact Productivité MOD ➔ Marge Nette Jour B.

#### 📋 Tableau Différentiel Détaillé par Article (Jour A vs Jour B) :
* Tableau croisé dynamique affichant les articles produits lors des deux journées :
  * `Code Article | Marque | Volume Jour A | Volume Jour B | Écart Volume | Coût Revient Jour A | Coût Revient Jour B | Écart Coût (DH) | Impact Marge`
  * Mise en surbrillance automatique (Vert/Rouge) des articles dont le coût de revient a augmenté entre les deux dates.

---

## 💻 4. Spécifications Techniques Backend & Endpoints API

Le serveur backend Python (`server.py` via FastAPI) doit fournir les endpoints JSON suivants pour alimenter les 8 écrans :

| Endpoint API | Méthode | Paramètres | Données Renvoyées |
| :--- | :---: | :--- | :--- |
| `/api/kpis/global` | `GET` | `date`, `site` | 4 KPIs globaux de l'Écran 1 (Production, Rendement, MOD, Marge) |
| `/api/rendement` | `GET` | `date`, `site` | Données de l'Écran 2 : Lots entrants, Rendements par espèce et Fournisseurs |
| `/api/mod` | `GET` | `date`, `site` | Données de l'Écran 3 : Postes ET/FIL/EMB/SRTI, Services communs, Historique |
| `/api/articles` | `GET` | `date`, `site` | Données de l'Écran 4 : Liste des articles, Écarts standards vs réels |
| `/api/articles/{code_article}` | `GET` | `date` | Fiche technique détaillée avec les 15 postes de coûts décomposés |
| `/api/cout-global` | `GET` | `date`, `site` | Données de l'Écran 5 : Produits, Marges brutes/nettes, PMV, PR, Totaux sites |
| `/api/resume` | `GET` | `date` | Données de l'Écran 6 : Approvisionnements CAOMA/CAMAT, Séries A260... |
| `/api/analyses-croisees` | `GET` | `date` | Données de l'Écran 7 : Calculs des écarts croisés et matrices de décision |
| `/api/comparateur` | `GET` | `date_a`, `date_b`, `site` | Données de l'Écran 8 : Deltas complets, graphiques comparatifs Jour A vs Jour B |

---

## 📅 5. Plan de Réalisation Recommandé pour la Stagiaire

1. **Étape 1 — Structure & Design System (Jour 1) :**
   * Structure HTML (`index.html`), CSS moderne (`index.css`), navbar latérale et header de filtres.
2. **Étape 2 — Endpoints API FastAPI (Jours 2-3) :**
   * Implémenter les routes REST dans `server.py` connectées à PostgreSQL.
3. **Étape 3 — Développement des Écrans Opérationnels 1, 2, 3 (Jours 4-5) :**
   * Vue Générale, Rendements (Lots & Fournisseurs), MOD (Postes & Historique).
4. **Étape 4 — Développement des Écrans Coûts & Finance 4, 5 (Jours 6-7) :**
   * Waterfall Chart des Fiches Articles (15 postes), Coût Global & Rentabilité.
5. **Étape 5 — Écrans 6, 7 et Écran 8 Comparateur Inter-Journées (Jours 8-10) :**
   * Bilan usine, Analyses croisées, Comparateur Jour A vs Jour B, validation et exports.
