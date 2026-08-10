# 📊 Projet de Stage : CUMAREX CostTrack v3
> **Suivi, Consolidation et Analyse des Coûts de Production**

Ce document présente l'objectif global du projet, le produit final attendu, ainsi que la structure des fichiers de départ pour le stagiaire chargé de sa réalisation.

---

## 🎯 1. Objectif du Projet

L'objectif de ce projet est de concevoir et de finaliser une application intégrée d'aide à la décision pour le suivi des performances industrielles et des coûts de production au sein de **CUMAREX S.A.** (conserverie de poisson).

Le stagiaire devra développer une solution qui permet de :
*   **Suivre les rendements matière** : mesurer l'efficacité de la transformation (poisson entier vs filets utilisables).
*   **Surveiller la Main-d'œuvre Directe (MOD)** : auditer les temps de travail passés par kilogramme de produit fini par site de production.
*   **Analyser les écarts de coûts** : comparer en temps réel les coûts réels constatés par rapport aux fiches techniques standards (fiches RR-125A) afin de détecter les anomalies et les pertes financières.

---

## 📦 2. Produit Final Attendu

Le produit final livré par le stagiaire doit être une application web locale complète et sécurisée, composée des éléments suivants :
1.  **Un Tableau de Bord Interactif (Frontend)** : Permettant de visualiser sous forme de graphiques (tendances de rendements, évolution de la MOD, dérive des coûts) les indicateurs consolidés. Il doit intégrer un module d'analyse conversationnelle (Assistant IA) permettant d'interroger la base de données en langage naturel.
2.  **Un Serveur Local de Données et Sécurité (Backend)** : Un serveur Python hébergeant l'application, gérant les enregistrements dans la base de données et servant de relais sécurisé pour les requêtes d'intelligence artificielle sans exposer de clés API côté navigateur.
3.  **Un Module d'Extraction Automatique** : Capable de lire en tâche de fond les rapports journaliers bruts (fichiers PDF et feuilles Excel) déposés par l'utilisateur, d'extraire les données utiles et de mettre à jour automatiquement le tableau de bord.



---

## 📁 3. Structure du Projet (Starter Kit)

Le projet mis à la disposition du stagiaire contient uniquement les composants de démarrage indispensables :

```text
Proposed project/
├── README.md                  # Ce guide de cadrage (cahier des charges)
├── CUMAREX_CostTrack.html     # L'interface utilisateur (Dashboard) à enrichir
├── Lancer_CostTrack.bat       # Script de démarrage rapide sous Windows
├── server.py                  # Code du serveur Python (API et Proxy) à compléter
├── database.json              # Base de données locale (Fichier JSON de départ)
└── Production/                # Dossier contenant les rapports réels de test (PDF)
```
