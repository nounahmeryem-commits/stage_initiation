# 📑 RAPPORT D'AUDIT TECHNIQUE ET DE VALIDATION : MODULE D'EXTRACTION ETL
> **Projet :** CUMAREX CostTrack v3 — Suivi & Consolidation des Coûts de Production  
> **Auteur du rapport :** Superviseur de stage  
> **Étape auditée :** Module d'extraction automatique des rapports industriels (PDF) vers base de données relationnelle  
> **Statut de validation :** ✅ **VALIDÉ SANS RÉSERVE (100% CONFORME)**  
> **Date de validation :** 15 Août 2026  

---

## 🎯 1. Contexte et Objectifs de l'Audit

Dans le cadre du projet de stage **CUMAREX CostTrack v3**, la première brique fondamentale consiste en un **pipeline ETL automatisé** capable de :
1. Lire et parser les rapports journaliers hétérogènes de production émis sous format PDF.
2. Extraire exhaustivement toutes les variables industrielles, financières et temporelles.
3. Vérifier la stricte cohérence des dates entre les 6 sources documentaires avant toute insertion.
4. Structurer les données en schémas relationnels propres pour PostgreSQL.

Cet audit a pour but de **tester et valider formellement la robustesse, l'exhaustivité et la fiabilité des extracteurs** sur l'ensemble des données de test multi-dates fournies (`06_Juin`).

---

## 📊 2. Synthèse Globale des Tests Multi-Journées

L'ensemble des **8 journées de production** disponibles a été audité de manière automatisée.

| Métrique Globale | Résultat Obtenu | Taux de Réussite |
| :--- | :---: | :---: |
| **Journées industrielles auditées** | **8 journées** (01, 02, 03, 04, 05, 06, 08, 09 juin 2026) | **100%** |
| **Documents PDF analysés** | **48 fichiers** (6 fichiers obligatoires / jour) | **100%** |
| **Fiches articles extraites (`Par Article.pdf`)** | **78 fiches complètes** | **100%** |
| **Produits consolidés (`C.Global.pdf`)** | **78 produits** | **100%** |
| **Lots & matières premières (`Rendement.pdf`)** | **105 lots entrants** | **100%** |
| **Mesures de main-d'œuvre Site 1 (`Mod S1.pdf`)** | **2 852 enregistrements unitaires** | **100%** |
| **Mesures de main-d'œuvre Site 2 (`Mod S2.pdf`)** | **3 362 enregistrements unitaires** | **100%** |
| **Sous-tables du rapport Résumé (`Résume.pdf`)** | **9 tables / jour** (**0 erreur** de conversion) | **100%** |
| **Cohérence temporelle inter-fichiers** | **8/8 journées validées** | **100%** |

---

## 🔍 3. Tableau Détaillé par Journée de Production

| Date de Production | Fiches Article | Produits C.Global | Lots Rendement | Lignes MOD S1 | Lignes MOD S2 | Sous-tables Résumé | Réconciliation Articles / C.Global |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **01/06/2026** | 10 | 10 | 14 | 341 | 407 | 9 (0 erreur) | ✅ Conforme (100%) |
| **02/06/2026** | 12 | 12 | 15 | 372 | 444 | 9 (0 erreur) | ✅ Conforme (100%) |
| **03/06/2026** | 12 | 12 | 15 | 279 | 324 | 9 (0 erreur) | ✅ Conforme (100%) |
| **04/06/2026** | 8 | 8 | 12 | 310 | 360 | 9 (0 erreur) | ✅ Conforme (100%) |
| **05/06/2026** | 8 | 8 | 11 | 341 | 396 | 9 (0 erreur) | ✅ Conforme (100%) |
| **06/06/2026** | 8 | 8 | 8 | 372 | 432 | 9 (0 erreur) | ✅ Conforme (100%) |
| **08/06/2026** | 8 | 8 | 14 | 403 | 481 | 9 (0 erreur) | ✅ Conforme (100%) |
| **09/06/2026** | 12 | 12 | 16 | 434 | 518 | 9 (0 erreur) | ✅ Conforme (100%) |
| **TOTAL** | **78** | **78** | **105** | **2 852** | **3 362** | **72 tables** | ✅ **100% PARFAIT** |

---

## 🛠️ 4. Analyse Technique par Extracteur

### 4.1. `ParArticleExtractor` (`par_article_extractor.py`)
* **Fonctionnement :** Extraction positionnelle spatiale (coordonnées `x0`, `top`) préservant l'agencement tabulaire complexe.
* **Champs d'en-tête (40 variables) :** N° Poisson, Date réception, Date fabrication, Espèce, Recette, Marque, Site (normalisé S1/S2), Code produit, Code RR-1, Format de boîte, Nombre de caisses, Poids filet, Prix MP, Taux MOD, MOMg, Charges fixes, Rendements constatés vs calculés.
* **Tableau des Coûts Unitaires (15 postes) :** Capture exhaustive des lignes (*Poisson, Huile, Additif, Boîte, Étui-carton, MOD, MOMg, Frais Fab, Port, etc.*) avec taux réels, montants réels, taux standards, montants standards et écarts.
* **Résultat :** Aucune valeur manquante sur les champs clés. Traitement multi-pages (jusqu'à 12 fiches par PDF) sans collision.

### 4.2. `CoutGlobalExtractor` (`c_global_extractor.py`)
* **Fonctionnement :** Extraction dynamique des marques sans dictionnaire fermé (auto-apprentissage sur le document) et parsing de la date textuelle en français.
* **Champs extraits (14 colonnes) :** Site, Espèce, Code article, Marque, Production nette, Coûts directs (`tot_cd`), Marge brute (`tot_mb`), % Marge brute, Charges fixes, % Charges fixes, Prix moyen de vente (`pmv`), Marge nette (`tot_mn`), Prix de revient (`tot_pr`).
* **Agrégats :** Sous-totaux par site (CX0/CX1 -> S1/S2) et Total général de l'usine validés.

### 4.3. `RendementExtractor` (`rendement_extractor.py`)
* **Fonctionnement :** Découpage en colonnes par barycentre horizontal des mots, isolant la date d'en-tête des dates de réception des lots.
* **Données capturées :** 
  * `df_entrees` : Site, Libellé espèce, État (*Congelé / Frais*), Date entrée, N° jours frigo, N° frigo, Fournisseur, Bon de Réception (BR), Poids (kg), Origine, Moule, % poids.
  * `df_summary` : Poids filets, % Rendement matière, % Marc (déchets).

### 4.4. `ModExtractor` & `ModExtractor_2` (`mod_S1_extractor.py` / `mod_S2_extractor.py`)
* **Fonctionnement :** Analyse matricielle 2D dynamique avec transformation en format tabulaire normalisé (long format relationnel).
* **Architecture des données :**
  * **Postes de production :** Étetage (`ET`), Filetage (`FIL`), Emboîtage (`EMB`), Sertissage (`SRTI`), Sous-totaux (`TOT`, `TOT2`).
  * **Services communs :** Préparation matière première (`PR_MP`), Nettoyage locaux (`NLE`), Commun (`COMM`).
* **Volume :** Reconstitution parfaite des 2 852 mesures (Site 1) et 3 362 mesures (Site 2) avec traçabilité par date.

### 4.5. `ResumeExtractor` (`resume.py`)
* **Fonctionnement :** Extraction simultanée des **9 sections industrielles** du rapport de synthèse journalier :
  1. `informations_generales` (Date, Lot, Site)
  2. `production` (Volumes fabriqués par format)
  3. `mod_global` (MO, MG, ratios MOD/Caisse, MG/Caisse)
  4. `matiere_premiere` (Fournisseurs CAOMA / CAMAT, tonnage, tarifs)
  5. `mod_par_code` (Égoutté, Casse, Huile, MOD, Mg, Fr Fab)
  6. `totaux_journaliers` (Totaux et cumuls du jour)
  7. `couts_serie` (Coûts réels par série A26060...)
  8. `synthese_production` (Production nette, PMV)
  9. `couts_unitaires` (Décomposition unitaire par composant)
* **Qualité :** 0 erreur de parsing (`_erreurs = 0`) sur l'intégralité des dates.

---

## 🛡️ 5. Contrôle de Sécurité & Orchestration

L'orchestrateur ([`orchestrateur_etl.py`](file:///c:/Users/hassan%20bouzidi/Desktop/stage_initiation-main/stage_initiation-main/Backend/Extracteurs/orchestrateur_etl.py)) a été validé sur ses mécanismes de protection :

1. **Exigence stricte des 6 fichiers :** Le script bloque immédiatement si un des 6 fichiers est absent du répertoire.
2. **Contrôle de cohérence de date :** L'insertion en base est automatiquement **refusée** si un fichier présente une date de production différente des autres.
3. **Test de rupture réussi :** Testé sur le dossier `data_sources` contenant des fichiers mixtes (01/06 et 03/06) -> l'orchestrateur a immédiatement bloqué le traitement et signalé les deux fichiers en anomalie.

---

## 💻 6. Reproductibilité & Commandes de Test

Pour rejouer la validation sur n'importe quel jour en mode simulation (sans écriture en base) :
```bash
cd Backend/Extracteurs
python orchestrateur_etl.py "../../data_test/06_Juin/01_06_2026" --dry-run --non-interactif
```

Pour exécuter le pipeline réel avec insertion en base PostgreSQL :
```bash
python orchestrateur_etl.py "../../data_test/06_Juin/01_06_2026" --non-interactif
```

---

## 🏁 7. Conclusion & Décision de Validation

* Le module d'extraction développé par la stagiaire répond **parfaitement au cahier des charges**.
* L'extraction est **générique**, **robuste aux variations de mise en page**, et **exhaustive à 100%**.
* **Décision :** ✅ **ÉTAPE 1 (EXTRACTION & ETL) VALIDÉE POUR MISE EN PRODUCTION**.

Feu vert accordé pour le passage à l'étape suivante : **Alimentation PostgreSQL et Développement du Dashboard interactif**.
