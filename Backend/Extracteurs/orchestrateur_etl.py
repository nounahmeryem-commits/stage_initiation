"""
orchestrateur_etl.py
=====================

Orchestrateur du pipeline Cumarex.

Ce script :
  1. Lit un DOSSIER contenant les rapports PDF d'une journee de production.
  2. Verifie que les 6 fichiers attendus sont bien presents
     (Par Article, C.Global, Resume, Rendement, Mod S1, Mod S2).
     -> Les 6 fichiers sont OBLIGATOIRES. S'il en manque, la liste des
        fichiers manquants est affichee et le script BLOQUE : l'utilisateur
        doit les ajouter (copier le fichier dans le dossier puis rescanner,
        ou indiquer un chemin explicite) avant que le traitement ne puisse
        continuer. Il n'y a pas d'option pour "ignorer" un fichier manquant.
  3. Extrait chaque fichier avec l'extracteur qui lui correspond.
  4. Verifie la coherence des dates trouvees entre les 6 sources (chaque
     rapport doit normalement parler du meme jour de production). Pour
     Mod S1 / Mod S2, qui peuvent legitimement contenir plusieurs dates
     (tableau cumulatif), seule la date la PLUS RECENTE de chacun est
     comparee aux autres fichiers. En cas d'ecart, l'INSERTION EST
     REFUSEE : il n'existe AUCUNE option pour forcer le passage outre,
     par securite (ne jamais melanger les donnees de deux jours
     differents).
  5. Appelle `execute_etl(...)` (defini dans pipeline_etl.py) pour faire
     l'insertion en base, exactement comme le fait `lancer_etl_complet`,
     mais sans re-extraire les PDF une seconde fois.

Usage :
    python orchestrateur_etl.py "D:\\Cumarex\\...\\01_06_2026"
    python orchestrateur_etl.py "D:\\...\\01_06_2026" --site-resume S1
    python orchestrateur_etl.py "D:\\...\\01_06_2026" --strict-dates
    python orchestrateur_etl.py "D:\\...\\01_06_2026" --non-interactif --mod-s2 "D:\\...\\Mod S2.pdf"

Ce script doit rester dans le MEME dossier que resume.py, c_global_extractor.py,
mod_S1_extractor.py, mod_S2_extractor.py, par_article_extractor.py,
rendement_extractor.py et pipeline_etl.py (imports relatifs, comme dans
pipeline_etl.py lui-meme).
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import date as date_cls
from datetime import datetime
from typing import Optional

import pandas as pd

# On s'assure que le dossier du script est bien dans sys.path, pour que les
# imports "a plat" (comme dans pipeline_etl.py) fonctionnent quel que soit
# le repertoire depuis lequel le script est lance.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from resume import ResumeExtractor
from c_global_extractor import CoutGlobalExtractor
from mod_S1_extractor import ModExtractor
from mod_S2_extractor import ModExtractor_2
from par_article_extractor import ParArticleExtractor
from rendement_extractor import RendementExtractor

from pipeline_etl import (
    execute_etl,
    _parse_date_ddmmyyyy,
    logger as etl_logger,  # reutilise le meme logger que le reste du pipeline
)

# ==========================================================
# LOGGING
# ==========================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    handlers=[
        logging.FileHandler("orchestrateur_etl.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("Orchestrateur")


# ==========================================================
# 1. DEFINITION DES 6 FICHIERS ATTENDUS
# ==========================================================
# Chaque entree : cle interne -> (libelle humain, liste de regex qui
# doivent matcher le nom de fichier NORMALISE (minuscules, sans accents,
# sans espaces/points/underscores)).
FICHIERS_ATTENDUS = {
    "par_article": {
        "label": "Par Article",
        "patterns": [r"pararticle", r"par_article"],
    },
    "c_global": {
        "label": "C.Global",
        "patterns": [r"cglobal", r"coutglobal"],
    },
    "resume": {
        "label": "Resume",
        "patterns": [r"resum", r"resume"],
    },
    "rendement": {
        "label": "Rendement",
        "patterns": [r"rendement"],
    },
    "mod_s1": {
        "label": "Mod S1",
        "patterns": [r"mods1", r"mod1"],
    },
    "mod_s2": {
        "label": "Mod S2",
        "patterns": [r"mods2", r"mod2"],
    },
}

ORDRE_AFFICHAGE = ["par_article", "c_global", "resume", "rendement", "mod_s1", "mod_s2"]


def _normaliser(texte: str) -> str:
    """minuscule + accents retires + separateurs retires, pour un matching
    de nom de fichier tolerant ('C.Global.pdf', 'c_global (1).pdf',
    'Résume.pdf', 'RESUME.PDF', ... doivent tous matcher)."""
    texte = texte.lower()
    texte = unicodedata.normalize("NFKD", texte)
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    texte = re.sub(r"[^a-z0-9]", "", texte)
    return texte


# ==========================================================
# 2. SCAN DU DOSSIER
# ==========================================================
@dataclass
class ResultatScan:
    trouves: dict = field(default_factory=dict)      # cle -> chemin complet
    manquants: list = field(default_factory=list)     # liste de cles
    non_reconnus: list = field(default_factory=list)  # fichiers PDF presents mais non attribues
    ambigus: dict = field(default_factory=dict)        # cle -> liste de chemins candidats


def scanner_dossier(dossier: str) -> ResultatScan:
    if not os.path.isdir(dossier):
        raise FileNotFoundError(f"Le dossier n'existe pas : {dossier}")

    fichiers_pdf = [
        f for f in os.listdir(dossier)
        if f.lower().endswith(".pdf") and os.path.isfile(os.path.join(dossier, f))
    ]

    resultat = ResultatScan()
    attribues = set()

    for cle, spec in FICHIERS_ATTENDUS.items():
        candidats = []
        for f in fichiers_pdf:
            nom_norm = _normaliser(f)
            if any(re.search(p, nom_norm) for p in spec["patterns"]):
                candidats.append(f)

        if not candidats:
            resultat.manquants.append(cle)
        elif len(candidats) == 1:
            chemin = os.path.join(dossier, candidats[0])
            resultat.trouves[cle] = chemin
            attribues.add(candidats[0])
        else:
            # plusieurs fichiers matchent la meme cle -> ambigu, on ne
            # devine pas, on le signale a l'utilisateur.
            resultat.ambigus[cle] = [os.path.join(dossier, c) for c in candidats]
            attribues.update(candidats)

    resultat.non_reconnus = [
        os.path.join(dossier, f) for f in fichiers_pdf if f not in attribues
    ]
    return resultat


def afficher_etat_scan(resultat: ResultatScan) -> None:
    print("\n" + "=" * 70)
    print("ETAT DU DOSSIER")
    print("=" * 70)
    for cle in ORDRE_AFFICHAGE:
        label = FICHIERS_ATTENDUS[cle]["label"]
        if cle in resultat.trouves:
            print(f"  [OK]      {label:<15} -> {resultat.trouves[cle]}")
        elif cle in resultat.ambigus:
            print(f"  [AMBIGU]  {label:<15} -> plusieurs fichiers correspondent :")
            for c in resultat.ambigus[cle]:
                print(f"                {c}")
        else:
            print(f"  [MANQUANT] {label:<15}")

    if resultat.non_reconnus:
        print("\n  Fichiers PDF presents mais non reconnus (ignores) :")
        for f in resultat.non_reconnus:
            print(f"    - {f}")
    print("=" * 70)


# ==========================================================
# 3. COMPLETION INTERACTIVE DES FICHIERS MANQUANTS / AMBIGUS
# ==========================================================
def resoudre_fichiers_manquants(dossier: str, resultat: ResultatScan,
                                 interactif: bool = True) -> ResultatScan:
    """Boucle interactive BLOQUANTE : tant qu'il manque des fichiers (ou
    qu'il reste des ambiguites), le script ne continue PAS. L'utilisateur
    doit obligatoirement fournir chaque fichier manquant (en le copiant
    dans le dossier puis en rescannant, ou en donnant un chemin explicite)
    avant que le pipeline ne poursuive. Aucune option pour "ignorer" un
    fichier et continuer sans lui : les 6 fichiers sont obligatoires."""

    a_traiter = list(resultat.manquants) + list(resultat.ambigus.keys())
    if not a_traiter:
        return resultat

    print("\nIl manque ou il y a une ambiguite sur "
          f"{len(a_traiter)} fichier(s) : "
          + ", ".join(FICHIERS_ATTENDUS[c]["label"] for c in a_traiter))
    print("Ces fichiers sont OBLIGATOIRES : le traitement ne peut pas "
          "continuer tant qu'ils ne sont pas tous fournis.")

    if not interactif:
        manquants_labels = ", ".join(FICHIERS_ATTENDUS[c]["label"] for c in a_traiter)
        raise SystemExit(
            "Mode non-interactif : impossible de continuer, il manque le(s) "
            f"fichier(s) obligatoire(s) suivant(s) : {manquants_labels}. "
            "Ajoutez-les au dossier (ou fournissez leur chemin via les options "
            "--par-article / --c-global / --resume / --rendement / --mod-s1 / "
            "--mod-s2) puis relancez."
        )

    for cle in list(a_traiter):
        label = FICHIERS_ATTENDUS[cle]["label"]

        while True:
            if cle in resultat.trouves:
                break  # resolu entre-temps (rescan)

            candidats_ambigus = resultat.ambigus.get(cle)
            print(f"\n--- Fichier OBLIGATOIRE manquant : '{label}' ---")
            if candidats_ambigus:
                print("Plusieurs fichiers correspondent a ce type :")
                for i, c in enumerate(candidats_ambigus, start=1):
                    print(f"  {i}. {c}")
                print("Options : "
                      "[numero] choisir ce fichier | "
                      "[c] indiquer un autre chemin | "
                      "[a] annuler l'operation")
            else:
                print("Ce fichier n'a pas ete trouve dans le dossier. "
                      "Il est obligatoire, vous devez l'ajouter pour continuer.")
                print("Options : "
                      "[r] j'ai copie/deplace le fichier dans le dossier -> rescanner | "
                      "[c] indiquer directement le chemin complet du fichier | "
                      "[a] annuler l'operation")

            choix = input("Votre choix : ").strip().lower()

            if choix == "a":
                raise SystemExit("Operation annulee par l'utilisateur.")

            if choix == "r" and not candidats_ambigus:
                resultat_nouveau = scanner_dossier(dossier)
                if cle in resultat_nouveau.trouves:
                    resultat.trouves[cle] = resultat_nouveau.trouves[cle]
                    if cle in resultat.manquants:
                        resultat.manquants.remove(cle)
                    print(f"  -> Fichier trouve : {resultat.trouves[cle]}")
                    break
                elif cle in resultat_nouveau.ambigus:
                    resultat.ambigus[cle] = resultat_nouveau.ambigus[cle]
                    candidats_ambigus = resultat.ambigus[cle]
                else:
                    print("  -> Toujours introuvable, reessayez.")
                continue

            if choix == "c":
                chemin = input("Chemin complet du fichier PDF : ").strip().strip('"')
                if os.path.isfile(chemin):
                    resultat.trouves[cle] = chemin
                    if cle in resultat.manquants:
                        resultat.manquants.remove(cle)
                    resultat.ambigus.pop(cle, None)
                    print(f"  -> Fichier accepte : {chemin}")
                    break
                else:
                    print("  -> Chemin invalide, ce fichier n'existe pas.")
                continue

            if candidats_ambigus and choix.isdigit():
                idx = int(choix) - 1
                if 0 <= idx < len(candidats_ambigus):
                    resultat.trouves[cle] = candidats_ambigus[idx]
                    resultat.ambigus.pop(cle, None)
                    print(f"  -> Fichier retenu : {resultat.trouves[cle]}")
                    break
                else:
                    print("  -> Numero invalide.")
                continue

            print("  -> Choix non reconnu, reessayez.")

    return resultat


# ==========================================================
# 4. EXTRACTION DE CHAQUE FICHIER + DATES DETECTEES
# ==========================================================
@dataclass
class DonneesExtraites:
    par_article_list: Optional[list] = None
    df_cout_global_produits: Optional[pd.DataFrame] = None
    date_cout_global: Optional[date_cls] = None
    resume_data: Optional[dict] = None
    df_entrees_rendement: Optional[pd.DataFrame] = None
    df_summary_rendement: Optional[pd.DataFrame] = None
    rendement_context_date: Optional[date_cls] = None
    df_mod_s1: Optional[pd.DataFrame] = None
    df_mod_s2: Optional[pd.DataFrame] = None

    # cle -> liste triee de dates (objets date) trouvees pour ce fichier
    dates_par_fichier: dict = field(default_factory=dict)
    # cle -> message d'erreur si l'extraction a echoue
    erreurs: dict = field(default_factory=dict)


def _dates_uniques(valeurs) -> list:
    dates = set()
    for v in valeurs:
        d = _parse_date_ddmmyyyy(v) if not isinstance(v, date_cls) else v
        if d is not None:
            dates.add(d)
    return sorted(dates)


def extraire_toutes_les_donnees(chemins: dict) -> DonneesExtraites:
    donnees = DonneesExtraites()

    if "par_article" in chemins:
        try:
            logger.info(f"Extraction Par Article : {chemins['par_article']}")
            extractor = ParArticleExtractor(chemins["par_article"])
            donnees.par_article_list = extractor.extract_pdf(chemins["par_article"])
            donnees.dates_par_fichier["par_article"] = _dates_uniques(
                a.get("date_production") for a in donnees.par_article_list
            )
            logger.info(f"--> {len(donnees.par_article_list)} fiche(s) article extraite(s).")
        except Exception as exc:
            logger.error(f"Echec extraction Par Article : {exc}", exc_info=True)
            donnees.erreurs["par_article"] = str(exc)

    if "c_global" in chemins:
        try:
            logger.info(f"Extraction C.Global : {chemins['c_global']}")
            extractor = CoutGlobalExtractor(chemins["c_global"])
            cg_data = extractor.extraire()
            donnees.df_cout_global_produits = cg_data.get("produits")
            donnees.date_cout_global = _parse_date_ddmmyyyy(cg_data.get("date"))
            donnees.dates_par_fichier["c_global"] = (
                [donnees.date_cout_global] if donnees.date_cout_global else []
            )
        except Exception as exc:
            logger.error(f"Echec extraction C.Global : {exc}", exc_info=True)
            donnees.erreurs["c_global"] = str(exc)

    if "resume" in chemins:
        try:
            logger.info(f"Extraction Resume : {chemins['resume']}")
            extractor = ResumeExtractor(chemins["resume"])
            donnees.resume_data = extractor.extract()
            info = donnees.resume_data.get("informations_generales")
            if info is not None and not info.empty and "date" in info.columns:
                donnees.dates_par_fichier["resume"] = _dates_uniques(info["date"].tolist())
            else:
                donnees.dates_par_fichier["resume"] = []
        except Exception as exc:
            logger.error(f"Echec extraction Resume : {exc}", exc_info=True)
            donnees.erreurs["resume"] = str(exc)

    if "rendement" in chemins:
        try:
            logger.info(f"Extraction Rendement : {chemins['rendement']}")
            extractor = RendementExtractor(chemins["rendement"])
            rendement_data = extractor.extract()
            donnees.df_entrees_rendement = rendement_data.get("df_entrees")
            donnees.df_summary_rendement = rendement_data.get("df_summary")
            donnees.rendement_context_date = rendement_data.get("date")
            donnees.dates_par_fichier["rendement"] = (
                [donnees.rendement_context_date] if donnees.rendement_context_date else []
            )
        except Exception as exc:
            logger.error(f"Echec extraction Rendement : {exc}", exc_info=True)
            donnees.erreurs["rendement"] = str(exc)

    if "mod_s1" in chemins:
        try:
            logger.info(f"Extraction Mod S1 : {chemins['mod_s1']}")
            extractor = ModExtractor(chemins["mod_s1"])
            donnees.df_mod_s1 = extractor.extract()
            if donnees.df_mod_s1 is not None and "date" in donnees.df_mod_s1.columns:
                toutes_dates = _dates_uniques(donnees.df_mod_s1["date"].tolist())
                if len(toutes_dates) > 1:
                    logger.info(
                        f"Mod S1 : {len(toutes_dates)} dates presentes dans le fichier "
                        f"({', '.join(d.strftime('%d/%m/%Y') for d in toutes_dates)}) "
                        f"-> seule la plus recente ({toutes_dates[-1].strftime('%d/%m/%Y')}) "
                        "est retenue pour la verification de coherence."
                    )
                donnees.dates_par_fichier["mod_s1"] = toutes_dates[-1:] if toutes_dates else []
        except Exception as exc:
            logger.error(f"Echec extraction Mod S1 : {exc}", exc_info=True)
            donnees.erreurs["mod_s1"] = str(exc)

    if "mod_s2" in chemins:
        try:
            logger.info(f"Extraction Mod S2 : {chemins['mod_s2']}")
            extractor = ModExtractor_2(chemins["mod_s2"])
            donnees.df_mod_s2 = extractor.extract()
            if donnees.df_mod_s2 is not None and "date" in donnees.df_mod_s2.columns:
                toutes_dates = _dates_uniques(donnees.df_mod_s2["date"].tolist())
                if len(toutes_dates) > 1:
                    logger.info(
                        f"Mod S2 : {len(toutes_dates)} dates presentes dans le fichier "
                        f"({', '.join(d.strftime('%d/%m/%Y') for d in toutes_dates)}) "
                        f"-> seule la plus recente ({toutes_dates[-1].strftime('%d/%m/%Y')}) "
                        "est retenue pour la verification de coherence."
                    )
                donnees.dates_par_fichier["mod_s2"] = toutes_dates[-1:] if toutes_dates else []
        except Exception as exc:
            logger.error(f"Echec extraction Mod S2 : {exc}", exc_info=True)
            donnees.erreurs["mod_s2"] = str(exc)

    return donnees


# ==========================================================
# 5. VERIFICATION DE LA COHERENCE DES DATES
# ==========================================================
def verifier_coherence_dates(dates_par_fichier: dict) -> tuple:
    """Retourne (ok, date_reference, rapport_texte).

    'ok' est True si toutes les sources qui ont produit au moins une date
    s'accordent sur une date de reference commune (la date la plus
    frequente). Un fichier sans aucune date detectee n'est pas compte
    comme un desaccord (juste signale)."""

    toutes_dates = []
    for dates in dates_par_fichier.values():
        toutes_dates.extend(dates)

    if not toutes_dates:
        return True, None, "Aucune date n'a pu etre extraite d'aucun fichier."

    compteur = Counter(toutes_dates)
    date_reference, _ = compteur.most_common(1)[0]

    lignes = []
    ok = True
    for cle in ORDRE_AFFICHAGE:
        if cle not in dates_par_fichier:
            continue
        label = FICHIERS_ATTENDUS[cle]["label"]
        dates = dates_par_fichier[cle]
        if not dates:
            lignes.append(f"  - {label:<12} : aucune date detectee")
            continue
        dates_str = ", ".join(d.strftime("%d/%m/%Y") for d in dates)
        if date_reference in dates and len(dates) == 1:
            lignes.append(f"  - {label:<12} : {dates_str}  [OK]")
        else:
            ok = False
            lignes.append(f"  - {label:<12} : {dates_str}  [ECART / date(s) supplementaire(s)]")

    rapport = (
        f"Date de reference (la plus frequente) : {date_reference.strftime('%d/%m/%Y')}\n"
        + "\n".join(lignes)
    )
    return ok, date_reference, rapport


def afficher_rapport_coherence(rapport: str) -> None:
    print("\n" + "=" * 70)
    print("VERIFICATION DE LA COHERENCE DES DATES")
    print("=" * 70)
    print(rapport)
    print("=" * 70)


# ==========================================================
# 6. INSERTION EN BASE (reprend execute_etl du pipeline existant)
# ==========================================================
def resumer_donnees_extraites(donnees: DonneesExtraites) -> str:
    """Petit resume lisible de ce qui a ete extrait, utilise par le mode
    --dry-run pour verifier le pipeline SANS toucher a la base."""
    def _forme(obj, label):
        if obj is None:
            return f"  - {label:<28} : absent"
        if isinstance(obj, pd.DataFrame):
            return f"  - {label:<28} : {len(obj)} ligne(s), colonnes = {list(obj.columns)}"
        if isinstance(obj, list):
            return f"  - {label:<28} : {len(obj)} element(s)"
        if isinstance(obj, dict):
            sous = ", ".join(
                f"{k}={len(v)}" if isinstance(v, pd.DataFrame) else f"{k}=?"
                for k, v in obj.items()
            )
            return f"  - {label:<28} : dict -> {sous}"
        return f"  - {label:<28} : {obj!r}"

    lignes = [
        _forme(donnees.par_article_list, "par_article_list"),
        _forme(donnees.df_cout_global_produits, "df_cout_global_produits"),
        _forme(donnees.date_cout_global, "date_cout_global"),
        _forme(donnees.resume_data, "resume_data"),
        _forme(donnees.df_entrees_rendement, "df_entrees_rendement"),
        _forme(donnees.df_summary_rendement, "df_summary_rendement"),
        _forme(donnees.rendement_context_date, "rendement_context_date"),
        _forme(donnees.df_mod_s1, "df_mod_s1"),
        _forme(donnees.df_mod_s2, "df_mod_s2"),
    ]
    return "\n".join(lignes)


def inserer_en_base(donnees: DonneesExtraites, site_resume: str = "S1",
                     strict_dates: bool = False) -> None:
    logger.info("Lancement de l'insertion en base de donnees...")
    execute_etl(
        par_article_list=donnees.par_article_list,
        df_cout_global_produits=donnees.df_cout_global_produits,
        date_cout_global=donnees.date_cout_global,
        resume_data=donnees.resume_data,
        resume_site_code=site_resume,
        df_entrees_rendement=donnees.df_entrees_rendement,
        df_summary_rendement=donnees.df_summary_rendement,
        rendement_context_date=donnees.rendement_context_date,
        df_mod_s1=donnees.df_mod_s1,
        df_mod_s2=donnees.df_mod_s2,
        strict_dates=strict_dates,
    )
    logger.info("Insertion en base terminee avec succes.")


# ==========================================================
# 7. ORCHESTRATION COMPLETE
# ==========================================================
def lancer(dossier: str, site_resume: str = "S1", strict_dates: bool = False,
           interactif: bool = True,
           dry_run: bool = False, chemins_forces: Optional[dict] = None) -> None:

    logger.info(f"Analyse du dossier : {dossier}")
    resultat = scanner_dossier(dossier)

    # Chemins fournis explicitement en ligne de commande (--par-article,
    # --c-global, ...) : ils priment sur le scan automatique et permettent
    # de completer un fichier manquant sans passer par le prompt
    # interactif (utile pour l'automatisation / --non-interactif).
    for cle, chemin in (chemins_forces or {}).items():
        if chemin is None:
            continue
        if not os.path.isfile(chemin):
            raise SystemExit(f"Chemin invalide pour '{FICHIERS_ATTENDUS[cle]['label']}' : {chemin}")
        resultat.trouves[cle] = chemin
        if cle in resultat.manquants:
            resultat.manquants.remove(cle)
        resultat.ambigus.pop(cle, None)

    afficher_etat_scan(resultat)

    # Les 6 fichiers sont OBLIGATOIRES : tant qu'il en manque un (ou qu'une
    # ambiguite subsiste), on ne passe pas a l'extraction. En interactif,
    # resoudre_fichiers_manquants() bloque jusqu'a resolution complete ou
    # annulation explicite ; en non-interactif, elle leve une erreur claire
    # listant ce qu'il manque.
    if resultat.manquants or resultat.ambigus:
        resultat = resoudre_fichiers_manquants(dossier, resultat, interactif=interactif)
        print("\nEtat final apres completion :")
        afficher_etat_scan(resultat)

    manquants_finaux = [c for c in ORDRE_AFFICHAGE if c not in resultat.trouves]
    if manquants_finaux:
        labels = ", ".join(FICHIERS_ATTENDUS[c]["label"] for c in manquants_finaux)
        raise SystemExit(
            f"Fichier(s) obligatoire(s) toujours manquant(s) : {labels}. "
            "Le traitement ne peut pas continuer sans eux."
        )

    donnees = extraire_toutes_les_donnees(resultat.trouves)

    if donnees.erreurs:
        print("\nCertains fichiers n'ont pas pu etre extraits :")
        for cle, err in donnees.erreurs.items():
            print(f"  - {FICHIERS_ATTENDUS[cle]['label']} : {err}")
        if interactif:
            reponse = input("\nContinuer quand meme avec les fichiers restants ? (o/N) : ").strip().lower()
            if reponse not in ("o", "oui", "y", "yes"):
                raise SystemExit("Operation annulee suite a des erreurs d'extraction.")
        else:
            raise SystemExit("Erreurs d'extraction en mode non-interactif : arret.")

    ok, date_reference, rapport = verifier_coherence_dates(donnees.dates_par_fichier)
    afficher_rapport_coherence(rapport)
    if not ok:
        raise SystemExit(
            "Ecart de date detecte entre les fichiers : l'insertion en base est REFUSEE "
            "par securite (pour ne jamais melanger les donnees de deux jours differents). "
            "Corrigez le dossier (bon fichier / bonne date) puis relancez."
        )

    if dry_run:
        print("\n" + "=" * 70)
        print("MODE --dry-run : pas d'ecriture en base. Resume de ce qui aurait ete insere :")
        print("=" * 70)
        print(resumer_donnees_extraites(donnees))
        print("\nTermine (dry-run) : pipeline valide jusqu'a l'etape d'insertion.")
        return

    inserer_en_base(donnees, site_resume=site_resume, strict_dates=strict_dates)
    print("\nTermine : donnees inserees en base avec succes.")


# ==========================================================
# 8. CLI
# ==========================================================
def _construire_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Orchestrateur ETL Cumarex : scanne un dossier de rapports "
                    "journaliers, verifie la presence et la coherence des 6 "
                    "fichiers attendus, puis insere les donnees en base."
    )
    parser.add_argument("dossier", help="Chemin du dossier contenant les 6 PDF du jour.")
    parser.add_argument("--site-resume", default="S1",
                         help="Site par defaut a utiliser pour resume.py si le site "
                              "ne peut pas etre deduit automatiquement (defaut : S1).")
    parser.add_argument("--strict-dates", action="store_true",
                         help="Rend bloquante (au lieu d'un simple avertissement) toute "
                              "incoherence de date rencontree DANS l'ETL lui-meme "
                              "(ex: Par Article vs C.Global pour un meme article).")
    parser.add_argument("--non-interactif", action="store_true",
                         help="Desactive les prompts. Les 6 fichiers restent obligatoires : "
                              "s'il en manque, utilisez --par-article/--c-global/--resume/"
                              "--rendement/--mod-s1/--mod-s2 pour les fournir, sinon le script "
                              "s'arrete avec une erreur listant ce qui manque. Un ecart de date "
                              "entre les fichiers arrete TOUJOURS le traitement avant toute "
                              "insertion en base (aucune option pour forcer le passage outre).")
    parser.add_argument("--dry-run", action="store_true",
                         help="Fait tout le pipeline (scan, completion, extraction, "
                              "verification des dates) mais N'ECRIT RIEN en base : "
                              "affiche a la place un resume de ce qui aurait ete insere. "
                              "Ideal pour tester le processus sans risque.")

    # Chemins explicites : permettent de fournir/completer un fichier
    # obligatoire sans prompt interactif (utile avec --non-interactif).
    parser.add_argument("--par-article", help="Chemin explicite vers le PDF 'Par Article'.")
    parser.add_argument("--c-global", help="Chemin explicite vers le PDF 'C.Global'.")
    parser.add_argument("--resume", help="Chemin explicite vers le PDF 'Resume'.")
    parser.add_argument("--rendement", help="Chemin explicite vers le PDF 'Rendement'.")
    parser.add_argument("--mod-s1", help="Chemin explicite vers le PDF 'Mod S1'.")
    parser.add_argument("--mod-s2", help="Chemin explicite vers le PDF 'Mod S2'.")
    return parser


def main():
    parser = _construire_parser()
    args = parser.parse_args()

    chemins_forces = {
        "par_article": args.par_article,
        "c_global": args.c_global,
        "resume": args.resume,
        "rendement": args.rendement,
        "mod_s1": args.mod_s1,
        "mod_s2": args.mod_s2,
    }

    lancer(
        dossier=args.dossier,
        site_resume=args.site_resume,
        strict_dates=args.strict_dates,
        interactif=not args.non_interactif,
        dry_run=args.dry_run,
        chemins_forces=chemins_forces,
    )


if __name__ == "__main__":
    main()