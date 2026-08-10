"""
Pipeline ETL corrige pour Cum_db, base sur les 6 extracteurs reels :
    - resume.py                (ResumeExtractor)        -> Resume_1.pdf
    - c_global_extractor.py    (CoutGlobalExtractor)    -> C.Global.pdf
    - mod_S1_extractor.py      (ModExtractor)           -> Mod S1.pdf
    - mod_S2_extractor.py      (ModExtractor_2)         -> Mod S2.pdf
    - par_article_extractor.py (ParArticleExtractor)    -> par_article_*.pdf
    - rendement_extractor.py   (RendementExtractor)     -> Rendement.pdf

=====================================================================
CORRECTIONS APPORTEES PAR RAPPORT A L'ANCIEN pipeline_etl.py
=====================================================================
1. `main_oeuvre_detail` et `syntheses_mensuelles` n'existent PAS dans
   db_v7.sql -> supprimes. Les donnees MOD (mod_S1/mod_S2) sont en
   realite au format long (date, categorie, type_poisson, service,
   valeur) et correspondent EXACTEMENT a deux tables qui existent
   deja dans le schema :
       - categorie == "Service Comm"  -> mod_communs_journaliers
         (UNIQUE (date_production, id_site) deja en place)
       - categorie == "Production"    -> mod_durees_espece_poste
         (UNIQUE (date_production, id_site, id_type_poisson, id_poste)
          deja en place)

2. `table_couts` (sortie de ParArticleExtractor) est un DataFrame, pas
   une liste de dicts : l'ancien code faisait "for row in table_couts"
   ce qui iterait sur les NOMS DE COLONNES, pas les lignes. Corrige
   avec `.to_dict(orient="records")`.

3. `cout_global` n'est pas un dict scalaire comme le supposait l'ancien
   pipeline (donnees de test bidon) : CoutGlobalExtractor renvoie un
   DataFrame de TOUS les produits du site. On selectionne la ligne du
   produit courant par son "code" (== code_produit de l'article), qui
   fournit tot_cd / tot_mb / pct_mb / charges_fixes / pct_cf / pmv /
   tot_pr / pct_mn / tot_mn -- des champs que ParArticleExtractor ne
   fournit PAS. C'est cette ligne, et non par_article, qui alimente
   ces colonnes de `productions_journalieres`.

4. `lots_poisson` : le "ON CONFLICT (br, id_site)" necessite une
   contrainte UNIQUE qui n'existe pas dans db_v7.sql -> voir le script
   SQL `migration_v8.sql` fourni a part (a executer AVANT ce pipeline).

5. `resume_journalier` n'a aucune contrainte UNIQUE utilisable non plus
   -> meme migration SQL, + pattern "get_or_create" explicite ici
   plutot qu'un ON CONFLICT (pour ne pas dupliquer le jour si l'ETL
   est relance).

6. Tables `resume_journalier`, `matiere_premiere`, `mod_global`,
   `resume_production_poisson`, `table_codes` (alimentees par
   resume.py) n'etaient JAMAIS ecrites par l'ancien pipeline : ajoute.

7. [v9] `ecarts_couts_postes` reutilisait `postes_production` (via
   get_or_create_poste) pour les lignes du tableau des couts de
   par_article (Poisson, Huile, Additif, Boite, Etui-carton, MOD,
   MOMG, Fr Fab, Port, ...). Ce sont des LIGNES DE COUT, pas des
   postes MOD -> elles polluaient postes_production avec
   categorie=NULL et nom_poste="Poste {CODE}" generique.
   Corrige : nouvelle table `postes_couts_reference` (voir
   migration_v9_separation_postes.sql) + nouvelle methode
   FKResolver.get_or_create_poste_cout(), utilisee uniquement par
   replace_ecarts_couts_postes(). `postes_production` ne recoit plus
   que les 7 postes MOD (ET/EMB/FIL/SRTI/PR_MP/NLE/COMM).

8. [v10] Aucune des 3 sources (C.Global, Rendement, par_article) ne
   fournissait de date fiable et coherente entre elles :
     - CoutGlobalExtractor n'extrayait AUCUNE date (le PDF affiche
       pourtant "mardi 02 juin 2026" en 2e ligne) -> corrige, exposee
       comme cle "date" du dict retourne par extraire().
     - RendementExtractor perdait la date globale du rapport (ex.
       "02/06/2026", en haut du PDF) : elle etait traitee comme un
       group_label transitoire puis ecrasee par le premier vrai
       libelle d'espece rencontre -> corrige, exposee comme cle "date"
       du dict retourne par extract().
     - ParArticleExtractor extrait DEUX dates differentes
       (date_fabrication et date_reception, pas forcement le meme
       jour) ; confirme avec le metier que c'est date_reception qui
       correspond a C.Global/Rendement pour la meme journee -> ajout
       d'un alias explicite "date_production" = date_reception.
   Cote pipeline : upsert_production_journaliere utilise desormais
   par_article["date_production"] (au lieu de "date_fabrication"), et
   l'exemple d'orchestration (section 8) utilise la date propre a
   RendementExtractor pour rendement_context_date (au lieu de la
   deriver de par_article), avec un log d'avertissement si les 3
   dates ne concordent pas.

=====================================================================
POINTS CONFIRMES AVEC LE METIER
=====================================================================
A. resume.py n'extrait aucun code de site depuis Resume_1.pdf (confirme
   par le metier) -> c'est normal, le site est passe explicitement en
   parametre a `run_etl_resume()` (voir `resume_site_code`).
B. Mapping des sites C.Global confirme : "CX0" == "S1", "CX1" == "S2"
   -> voir SITE_MAPPING_CGLOBAL + normalize_cglobal_sites().
   `_find_cout_global_row()` filtre maintenant par (code, site) pour
   eviter toute ambiguite si un meme code produit existe sur les deux
   sites le meme jour.
C. Correspondance confirmee : matiere_premiere, mod_global,
   resume_production_poisson et table_codes (alimentees par resume.py)
   correspondent bien aux blocs matiere_premiere / mod_global /
   production / mod_par_code de ResumeExtractor -- aucun changement
   necessaire sur ce point, deja implemente comme ci-dessous.

=====================================================================
POINTS ENCORE OUVERTS
=====================================================================
D. mod_S1_extractor / mod_S2_extractor n'incluent PAS le site dans
   leurs lignes malgre le parametre `site=` du constructeur : le site
   est donc passe explicitement a `upsert_mod_long_format()` (deja
   fait ici, "S1"/"S2" en dur dans `execute_etl()` -- a verifier que
   c'est toujours le bon site si tu changes de source de fichier).
E. resume.py extrait aussi couts_serie / synthese_production /
   couts_unitaires / totaux_journaliers : AUCUNE table du schema ne
   correspond a ces 4 blocs (ce sont des agregats/derives, pas des
   donnees brutes). Je ne les insere pas en base -- ils restent
   disponibles dans le dict retourne pour affichage/QA. Dis-moi si tu
   veux que je cree des tables dediees pour les stocker tels quels.
F. `fiches_techniques` n'est alimentee par AUCUN des 6 extracteurs
   fournis (ca vient probablement d'un autre PDF, la fiche technique
   produit) -> non traite ici.
"""

import logging
from datetime import datetime
from datetime import date as _date_cls

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# --- Tes extracteurs reels ---
from resume import ResumeExtractor
from c_global_extractor import CoutGlobalExtractor
from mod_S1_extractor import ModExtractor
from mod_S2_extractor import ModExtractor_2
from par_article_extractor import ParArticleExtractor
from rendement_extractor import RendementExtractor

# ==========================================
# 1. CONFIGURATION DU LOGGING & CONNEXION BDD
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    handlers=[
        logging.FileHandler("etl_production.log", encoding="utf-8"),
        logging.StreamHandler()
    ]



)
logger = logging.getLogger("ETL_Pipeline")

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

DATABASE_URL = (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

engine = create_engine(DATABASE_URL)


Session = sessionmaker(bind=engine)

# Confirme par le metier : C.Global.pdf designe les sites "CX0"/"CX1",
# qui correspondent respectivement a "S1"/"S2" utilises partout ailleurs
# (par_article, mod_S1/mod_S2, resume.py).
SITE_MAPPING_CGLOBAL = {
    "CX0": "S1",
    "CX1": "S2",
}


def normalize_cglobal_sites(df):
    """Remplace les codes site 'CX...' de CoutGlobalExtractor par leur
    equivalent S1/S2, dans une COPIE du DataFrame (n'altere pas l'original).
    Si un code CX inconnu apparait (site 3, 4, ...), il est laisse tel
    quel et un warning est loggue -> a ajouter dans SITE_MAPPING_CGLOBAL."""
    if df is None or df.empty or "site" not in df.columns:
        return df
    df = df.copy()
    inconnus = set(df["site"].dropna().unique()) - set(SITE_MAPPING_CGLOBAL.keys())
    for code_inconnu in inconnus:
        logger.warning(
            f"C.Global : code site '{code_inconnu}' absent de SITE_MAPPING_CGLOBAL "
            f"-> laisse inchange, a ajouter au mapping si c'est un site reel."
        )
    df["site"] = df["site"].map(lambda s: SITE_MAPPING_CGLOBAL.get(s, s))
    return df


def normalize_site_code(code_site):
    """[correctif] par_article_extractor.py renvoie le site brut tel
    qu'imprime sur la fiche (ex. "Site CX0"), donc "CX0"/"CX1" -- EXACTEMENT
    le meme codage que C.Global. Ce code brut n'etait auparavant jamais
    passe par SITE_MAPPING_CGLOBAL avant d'etre utilise pour creer/chercher
    un site dans `sites_production`, ce qui faisait apparaitre une ligne
    parasite "CX0" en base (en plus de "S1"/"S2") et cassait le matching
    avec C.Global (site normalise "S1" vs site brut "CX0" -> aucune
    correspondance, repli sur un match par code seul).

    A appliquer sur TOUT code site provenant de par_article_extractor.py
    avant utilisation (creation de site, filtrage C.Global, etc.)."""
    if not code_site or pd.isna(code_site):
        return code_site
    key = str(code_site).strip().upper()
    return SITE_MAPPING_CGLOBAL.get(key, code_site)


# ==========================================
# 1bis. REFERENTIEL DES POSTES MOD (mod_S1 / mod_S2)
# ==========================================
# Les deux PDF MOD (S1/S2) melangent deux familles de codes "service"
# dans la meme colonne source :
#   - categorie == "Production"   -> postes lies a un TYPE DE POISSON
#                                     (ET/EMB/FIL/SRTI...) => table
#                                     mod_durees_espece_poste
#                                     (id_poste + id_type_poisson)
#   - categorie == "Service Comm" -> postes COMMUNS, valables pour
#                                     tout le site, independants du
#                                     poisson (PR_MP/NLE/COMM) => table
#                                     mod_communs_journaliers
#
# Ce dict centralise le nom "propre" et la categorie de
# postes_production.categorie a appliquer pour chaque code source, afin
# que postes_production.categorie contienne bien 'production' ou
# 'commun' (et jamais NULL) pour les postes MOD. Les cles sont testees
# en MAJUSCULES (meme normalisation que FKResolver._cache_postes).
# Codes "service" reellement produits par mod_S1_extractor.py /
# mod_S2_extractor.py pour categorie == "Production", en plus des 4
# vrais postes : "TOT" et "TOT2" sont des SOUS-TOTAUX par espece (colonnes
# du PDF dont l'extracteur n'a pas pu identifier le libelle -- cf.
# docstrings des deux extracteurs), pas des postes. Il ne faut donc PAS
# les inserer dans mod_durees_espece_poste (double comptage avec
# ET+FIL+EMB+SRTI) ni les creer dans postes_production.
POSTES_PRODUCTION_A_IGNORER = {"TOT", "TOT2"}

# ==========================================
# 1ter. REFERENTIEL DES POSTES DE COUT (par_article_extractor.py)
# ==========================================
# ATTENTION : ce dict alimente `postes_couts_reference`, une table
# DISTINCTE de `postes_production` (voir migration_v9_separation_postes.sql).
# `ecarts_couts_postes` (les lignes du tableau des couts de la fiche
# par_article : Poisson, Huile, Additif, Boite, Etui-carton, MOD, MOMG,
# Fr Fab, Port, ...) N'A RIEN A VOIR conceptuellement avec les postes
# MOD (ET/EMB/FIL/SRTI/PR_MP/NLE/COMM) : ce sont des lignes de cout de
# revient, pas des postes de transformation. Elles ne doivent plus
# etre inserees dans postes_production.
#
# Les libelles proviennent directement du texte du PDF (voir
# ParArticleExtractor.extract_table_couts -> `label`), donc ils
# arrivent tels quels ("POISSON", "HUILE", "FR FAB", ...). Ce dict
# permet, si besoin, de leur donner un nom_poste_cout plus propre ;
# sinon on garde le libelle du PDF a l'identique.
POSTE_REFERENTIEL_COUTS = {
    # code_pdf : nom_poste_cout propre (optionnel, sinon libelle brut)
    # "POISSON": "Poisson",
    # "HUILE": "Huile",
    # "ADDITIF": "Additif",
    # "BOITE": "Boite",
    # "ETUI-CART": "Etui carton",
    # "MOD": "Main d'oeuvre directe",
    # "MOMG": "Main d'oeuvre indirecte (MOMg)",
    # "FR FAB": "Frais de fabrication",
    # "PORT": "Port",
    # -- a completer avec le metier si des noms plus lisibles sont voulus --
}


POSTE_REFERENTIEL_MOD = {
    # -- Postes de PRODUCTION (etape de transformation, par espece) --
    "ET":   {"nom_poste": "Etetage",   "categorie": "production"},
    "EMB":  {"nom_poste": "Emboitage", "categorie": "production"},
    "FIL":  {"nom_poste": "Filetage",  "categorie": "production"},
    "SRTI": {"nom_poste": "Sertissage", "categorie": "production"},
    # -- Postes COMMUNS (temps non affecte a une espece particuliere) --
    "PR_MP": {"nom_poste": "Preparation matiere premiere", "categorie": "commun"},
    "NLE":   {"nom_poste": "Nettoyage locaux et equipements", "categorie": "commun"},
    "COMM":  {"nom_poste": "Commun / services generaux", "categorie": "commun"},
}


# ==========================================
# 2. GESTIONNAIRE DE REFERENTIELS (FK RESOLVER)
# ==========================================
class FKResolver:
    """Gere le cache et la creation dynamique des tables de reference."""

    def __init__(self, session):
        self.session = session
        self._cache_clients = {}
        self._cache_sites = {}
        self._cache_poissons = {}
        self._cache_articles = {}
        self._cache_postes = {}
        self._cache_postes_couts = {}
        self._preload_caches()

    def _preload_caches(self):
        for r in self.session.execute(text("SELECT id_client, nom_client FROM clients")).fetchall():
            if r[1]:
                self._cache_clients[str(r[1]).strip().upper()] = r[0]

        for r in self.session.execute(text("SELECT id_site, code_site FROM sites_production")).fetchall():
            if r[1]:
                self._cache_sites[str(r[1]).strip().upper()] = r[0]

        for r in self.session.execute(text("SELECT id_type_poisson, nom_type FROM types_poisson")).fetchall():
            if r[1]:
                self._cache_poissons[str(r[1]).strip().upper()] = r[0]

        for r in self.session.execute(text("SELECT id_article, code_article FROM articles")).fetchall():
            if r[1]:
                self._cache_articles[str(r[1]).strip().upper()] = r[0]

        for r in self.session.execute(text("SELECT id_poste, code_poste FROM postes_production")).fetchall():
            if r[1]:
                self._cache_postes[str(r[1]).strip().upper()] = r[0]

        for r in self.session.execute(
            text("SELECT id_poste_cout, code_poste_cout FROM postes_couts_reference")
        ).fetchall():
            if r[1]:
                self._cache_postes_couts[str(r[1]).strip().upper()] = r[0]

    def seed_postes_referentiel_mod(self):
        """Garantit que les 7 postes MOD (4 'production' + 3 'commun')
        existent dans postes_production des le depart, avec le bon
        nom_poste et la bonne categorie -- meme si un des deux PDF
        (S1 ou S2) n'a pas encore ete ingere. A appeler une fois avant
        (ou au debut de) l'ETL mod_S1/mod_S2."""
        for code in POSTE_REFERENTIEL_MOD:
            self.get_or_create_poste(code)

    def get_or_create_client(self, marque):
        if not marque or pd.isna(marque):
            return None
        key = str(marque).strip().upper()
        if key not in self._cache_clients:
            code_client = f"CLI_{key[:10].replace(' ', '_')}"
            res = self.session.execute(
                text("""
                    INSERT INTO clients (code_client, nom_client) VALUES (:code, :nom)
                    ON CONFLICT (code_client) DO UPDATE SET nom_client = EXCLUDED.nom_client
                    RETURNING id_client;
                """),
                {"code": code_client, "nom": marque}
            ).fetchone()
            self._cache_clients[key] = res[0]
            logger.info(f"Referentiel Client ajoute/mis a jour : {marque}")
        return self._cache_clients[key]

    def get_or_create_site(self, code_site):
        if not code_site or pd.isna(code_site):
            return None
        key = str(code_site).strip().upper()
        if key not in self._cache_sites:
            res = self.session.execute(
                text("""
                    INSERT INTO sites_production (code_site, nom_site, actif) VALUES (:code, :nom, true)
                    ON CONFLICT (code_site) DO UPDATE SET code_site = EXCLUDED.code_site
                    RETURNING id_site;
                """),
                {"code": key, "nom": f"Site {key}"}
            ).fetchone()
            self._cache_sites[key] = res[0]
            logger.info(f"Referentiel Site ajoute : {key}")
        return self._cache_sites[key]

    def get_or_create_poisson(self, nom_type):
        if not nom_type or pd.isna(nom_type):
            return None
        key = str(nom_type).strip().upper()
        if key not in self._cache_poissons:
            code_type = f"P_{key[:10].replace(' ', '_')}"
            res = self.session.execute(
                text("""
                    INSERT INTO types_poisson (code_type, nom_type) VALUES (:code, :nom)
                    ON CONFLICT (code_type) DO UPDATE SET nom_type = EXCLUDED.nom_type
                    RETURNING id_type_poisson;
                """),
                {"code": code_type, "nom": key}
            ).fetchone()
            self._cache_poissons[key] = res[0]
            logger.info(f"Referentiel Poisson ajoute : {key}")
        return self._cache_poissons[key]

    def get_or_create_poste(self, code_poste, nom_poste=None, categorie=None):
        """Cree/maj un poste dans postes_production.

        Si `nom_poste`/`categorie` ne sont pas fournis explicitement,
        on les deduit de POSTE_REFERENTIEL_MOD quand le code est connu
        (ET/EMB/FIL/SRTI -> 'production', PR_MP/NLE/COMM -> 'commun').
        Pour les codes hors MOD (ex. postes de `ecarts_couts_postes`
        issus de par_article), le comportement d'origine est conserve :
        nom_poste="Poste {CODE}", categorie=NULL, sauf si fournis en
        argument.

        TOT/TOT2 (sous-totaux par espece, cf. POSTES_PRODUCTION_A_IGNORER)
        sont explicitement rejetes ici : ce ne sont pas de vrais postes
        et ne doivent JAMAIS apparaitre dans postes_production, quel que
        soit l'appelant.
        """
        if not code_poste or pd.isna(code_poste):
            return None
        key = str(code_poste).strip().upper()
        if key in POSTES_PRODUCTION_A_IGNORER:
            return None
        if key not in self._cache_postes:
            ref = POSTE_REFERENTIEL_MOD.get(key, {})
            nom = nom_poste or ref.get("nom_poste") or f"Poste {key}"
            cat = categorie or ref.get("categorie")
            res = self.session.execute(
                text("""
                    INSERT INTO postes_production (code_poste, nom_poste, categorie)
                    VALUES (:code, :nom, :cat)
                    ON CONFLICT (code_poste) DO UPDATE SET
                        nom_poste = EXCLUDED.nom_poste,
                        categorie = COALESCE(EXCLUDED.categorie, postes_production.categorie)
                    RETURNING id_poste;
                """),
                {"code": key, "nom": nom, "cat": cat}
            ).fetchone()
            self._cache_postes[key] = res[0]
            logger.info(f"Referentiel Poste ajoute/mis a jour : {key} -> nom='{nom}', categorie='{cat}'")
        return self._cache_postes[key]

    def get_or_create_poste_cout(self, code_poste_cout, nom_poste_cout=None):
        """Cree/maj une ligne dans `postes_couts_reference` (postes de
        cout des fiches par_article : Poisson, Huile, Additif, Boite,
        Etui-carton, MOD, MOMG, Fr Fab, Port, ...).

        A NE PAS CONFONDRE avec get_or_create_poste(), qui gere
        `postes_production` (postes MOD de transformation/communs).
        Depuis la migration v9, ecarts_couts_postes.id_poste_cout
        pointe vers cette nouvelle table, distincte de postes_production.
        """
        if not code_poste_cout or pd.isna(code_poste_cout):
            return None
        key = str(code_poste_cout).strip().upper()
        if key not in self._cache_postes_couts:
            nom = nom_poste_cout or POSTE_REFERENTIEL_COUTS.get(key) or key.title()
            res = self.session.execute(
                text("""
                    INSERT INTO postes_couts_reference (code_poste_cout, nom_poste_cout)
                    VALUES (:code, :nom)
                    ON CONFLICT (code_poste_cout) DO UPDATE SET
                        nom_poste_cout = EXCLUDED.nom_poste_cout
                    RETURNING id_poste_cout;
                """),
                {"code": key, "nom": nom}
            ).fetchone()
            self._cache_postes_couts[key] = res[0]
            logger.info(f"Referentiel Poste de cout ajoute/mis a jour : {key} -> nom='{nom}'")
        return self._cache_postes_couts[key]

    def get_article_id(self, code_article):
        """Recherche un article par son code.

        [correctif] resume.py tronque le code produit DIFFEREMMENT selon
        la sous-table du PDF (constate sur les vraies donnees) :
            mod_par_code    -> "125MCDSTP"   (9 caracteres)
            couts_unitaires -> "125MCDSTPM"  (10 caracteres)
            couts_serie     -> "125MCDSTPM"  (10 caracteres)
            vrai code (par_article/C.Global) -> "125MCDSTPME" (11 caracteres)
        Une recherche exacte echoue donc systematiquement pour ces
        lignes ("article inconnu" -> ligne ignoree), meme si l'article
        existe bel et bien en base sous un code plus long. On tente
        donc, en repli, un match par PREFIXE (le code fourni est
        toujours tronque par la DROITE, jamais par la gauche) : si un
        seul article de la base commence par ce prefixe, on le retient.
        En cas d'ambiguite (plusieurs articles partagent le meme
        prefixe), on refuse de choisir au hasard et on logge un
        avertissement -- mieux vaut une ligne ignoree qu'un mauvais
        rattachement.
        """
        if not code_article or pd.isna(code_article):
            return None
        key = str(code_article).strip().upper()

        exact = self._cache_articles.get(key)
        if exact is not None:
            return exact

        candidats = {
            code: id_art
            for code, id_art in self._cache_articles.items()
            if code.startswith(key)
        }
        if len(candidats) == 1:
            (code_trouve, id_art), = candidats.items()
            logger.info(
                f"Article resolu par prefixe : '{key}' -> '{code_trouve}' "
                f"(id_article={id_art})."
            )
            return id_art
        if len(candidats) > 1:
            logger.warning(
                f"Code article '{key}' ambigu : plusieurs articles "
                f"commencent par ce prefixe ({sorted(candidats.keys())}) "
                f"-> impossible de choisir, ligne ignoree."
            )
        return None


# ==========================================
# 3. PAR_ARTICLE_EXTRACTOR -> articles / productions_journalieres / ecarts_couts_postes
# ==========================================

def upsert_article(session, fk_resolver, par_article):
    """Table `articles`."""
    id_client = fk_resolver.get_or_create_client(par_article.get("marque"))
    id_poisson = fk_resolver.get_or_create_poisson(par_article.get("espece"))

    res = session.execute(
        text("""
            INSERT INTO articles (code_article, designation, code_interne, fiche_type, sauce, id_type_poisson, id_client)
            VALUES (:code_article, :designation, :code_interne, :fiche_type, :sauce, :id_type_poisson, :id_client)
            ON CONFLICT (code_article) DO UPDATE SET
                designation = EXCLUDED.designation,
                code_interne = EXCLUDED.code_interne,
                fiche_type = EXCLUDED.fiche_type,
                sauce = EXCLUDED.sauce,
                id_type_poisson = COALESCE(EXCLUDED.id_type_poisson, articles.id_type_poisson),
                id_client = COALESCE(EXCLUDED.id_client, articles.id_client)
            RETURNING id_article;
        """),
        {
            "code_article": par_article.get("code_produit"),
            "designation": f"{par_article.get('recette', '')} {par_article.get('espece', '')}".strip(),
            "code_interne": par_article.get("code_interne"),
            "fiche_type": par_article.get("code_rr_1"),
            "sauce": par_article.get("type_huile"),
            "id_type_poisson": id_poisson,
            "id_client": id_client
        }
    ).fetchone()
    id_article = res[0]
    fk_resolver._cache_articles[str(par_article.get("code_produit")).strip().upper()] = id_article
    return id_article


def _find_cout_global_row(
    df_produits,
    code_produit,
    site_code=None,
    date_par_article=None,
    date_cout_global=None,
    strict_dates=False,
):
    """Isole la ligne de CoutGlobalExtractor correspondant a cet article.

    Le DataFrame doit deja avoir ete normalise via `normalize_cglobal_sites`
    (site "S1"/"S2", pas "CX0"/"CX1"). On filtre par `code` ET par `site`
    quand le site est connu, pour eviter une ambiguite si le meme code
    produit existe sur les deux sites le meme jour ; a defaut de site
    fourni ou de correspondance avec site, on retombe sur un match par
    code seul (avec warning, car potentiellement ambigu).

    [correctif] VERIFICATION DE DATE (meme code + meme site mais date
    differente entre par_article et C.Global.pdf). Le rapport
    C.Global.pdf entier porte une seule date globale (extraite par
    CoutGlobalExtractor.extraire(), cle "date"), qui ne concerne donc
    pas forcement la meme journee que la fiche par_article en cours de
    traitement. Un match par (code, site) sans verification de date
    est dangereux : on risque de coller les couts totaux (tot_cd,
    tot_mb, pct_mb, charges_fixes, ...) d'un AUTRE jour sur la
    production du jour traite, en silence.

    `date_par_article` et `date_cout_global` : objets `date` deja
    parses. Si les deux sont fournis et different :
      - strict_dates=False (defaut) : la ligne C.Global est traitee
        comme "non trouvee" (memes consequences que code introuvable
        -> colonnes NULL + warning), pour ne jamais bloquer tout l'ETL
        a cause d'UN fichier decale.
      - strict_dates=True : leve une exception (utile pour un import
        batch supervise ou tu preferes stopper net).
    """
    if df_produits is None or df_produits.empty or not code_produit:
        return {}

    if (
        date_par_article is not None
        and date_cout_global is not None
        and date_par_article != date_cout_global
    ):
        msg = (
            f"C.Global : code '{code_produit}' / site '{site_code}' trouve, mais "
            f"date C.Global ({date_cout_global}) != date par_article ({date_par_article}) "
            f"-> jointure refusee pour eviter de melanger des donnees de jours differents."
        )
        if strict_dates:
            raise ValueError(msg)
        logger.warning(msg + " Colonnes issues de C.Global mises a NULL pour cette ligne.")
        return {}

    par_code = df_produits[df_produits["code"].astype(str).str.upper() == str(code_produit).upper()]
    if par_code.empty:
        return {}

    if site_code:
        par_code_et_site = par_code[par_code["site"].astype(str).str.upper() == str(site_code).upper()]
        if not par_code_et_site.empty:
            return par_code_et_site.iloc[0].to_dict()
        logger.warning(
            f"C.Global : code '{code_produit}' trouve mais pas sur le site '{site_code}' "
            f"-> repli sur un match par code seul (verifier la coherence des donnees)."
        )

    if len(par_code) > 1:
        logger.warning(
            f"C.Global : code '{code_produit}' present {len(par_code)} fois sans site "
            f"pour departager -> la premiere ligne trouvee est utilisee."
        )
    return par_code.iloc[0].to_dict()


def upsert_production_journaliere(session, fk_resolver, par_article, cout_global_row):
    """Table `productions_journalieres`.

    par_article       : dict renvoye par ParArticleExtractor.extract()
    cout_global_row    : dict = une ligne de CoutGlobalExtractor (deja
                          filtree sur le bon "code" par _find_cout_global_row)
    """
    id_site = fk_resolver.get_or_create_site(par_article.get("site"))
    id_article = fk_resolver.get_article_id(par_article.get("code_produit"))

    # [correctif] "date_production" (= date_reception) est la date qui
    # correspond a C.Global.pdf et Rendement.pdf pour la meme journee ;
    # "date_fabrication" est une date differente (souvent le jour
    # suivant) qui ne doit PAS servir de cle de jointure entre les
    # sources. Voir par_article_extractor.py.
    date_prod = _parse_date_ddmmyyyy(par_article.get("date_production"))

    result = session.execute(
        text("""
            INSERT INTO productions_journalieres (
                date_production, id_site, id_article, no_s_produit, no_poisson, t_boites, caisses,
                t_boites_utilises, poisson_kg, filet_kg, rdt_filet_pct, rdt_calcule_pct, px_mp,
                huile_kg, pu_huile, fr_fab, mod_total, mod_pct, momg, momg_pct, ch_fixes, devise,
                taux_change, tot_cd_dhs, tot_pmv_dhs, tot_pr_dhs, tot_mb_dhs, tot_mn_dhs, pct_mb,
                pct_cf, pct_mn, numero_serie, reference_client, date_reception, ligne_production,
                cout_min_reel, cout_min_stnd
            ) VALUES (
                :date_production, :id_site, :id_article, :no_s_produit, :no_poisson, :t_boites, :caisses,
                :t_boites_utilises, :poisson_kg, :filet_kg, :rdt_filet_pct, :rdt_calcule_pct, :px_mp,
                :huile_kg, :pu_huile, :fr_fab, :mod_total, :mod_pct, :momg, :momg_pct, :ch_fixes, :devise,
                :taux_change, :tot_cd_dhs, :tot_pmv_dhs, :tot_pr_dhs, :tot_mb_dhs, :tot_mn_dhs, :pct_mb,
                :pct_cf, :pct_mn, :numero_serie, :reference_client, :date_reception, :ligne_production,
                :cout_min_reel, :cout_min_stnd
            )
            ON CONFLICT (date_production, id_site, id_article) DO UPDATE SET
                no_s_produit = EXCLUDED.no_s_produit,
                no_poisson = EXCLUDED.no_poisson,
                t_boites = EXCLUDED.t_boites,
                caisses = EXCLUDED.caisses,
                t_boites_utilises = EXCLUDED.t_boites_utilises,
                poisson_kg = EXCLUDED.poisson_kg,
                filet_kg = EXCLUDED.filet_kg,
                rdt_filet_pct = EXCLUDED.rdt_filet_pct,
                rdt_calcule_pct = EXCLUDED.rdt_calcule_pct,
                px_mp = EXCLUDED.px_mp,
                huile_kg = EXCLUDED.huile_kg,
                pu_huile = EXCLUDED.pu_huile,
                fr_fab = EXCLUDED.fr_fab,
                mod_total = EXCLUDED.mod_total,
                mod_pct = EXCLUDED.mod_pct,
                momg = EXCLUDED.momg,
                momg_pct = EXCLUDED.momg_pct,
                ch_fixes = EXCLUDED.ch_fixes,
                devise = EXCLUDED.devise,
                taux_change = EXCLUDED.taux_change,
                tot_cd_dhs = EXCLUDED.tot_cd_dhs,
                tot_pmv_dhs = EXCLUDED.tot_pmv_dhs,
                tot_pr_dhs = EXCLUDED.tot_pr_dhs,
                tot_mb_dhs = EXCLUDED.tot_mb_dhs,
                tot_mn_dhs = EXCLUDED.tot_mn_dhs,
                pct_mb = EXCLUDED.pct_mb,
                pct_cf = EXCLUDED.pct_cf,
                pct_mn = EXCLUDED.pct_mn,
                numero_serie = EXCLUDED.numero_serie,
                reference_client = EXCLUDED.reference_client,
                date_reception = EXCLUDED.date_reception,
                ligne_production = EXCLUDED.ligne_production,
                cout_min_reel = EXCLUDED.cout_min_reel,
                cout_min_stnd = EXCLUDED.cout_min_stnd
            RETURNING id_production;
        """),
        {
            "date_production": date_prod,
            "id_site": id_site,
            "id_article": id_article,
            "no_s_produit": par_article.get("ordre_fabrication"),
            "no_poisson": par_article.get("numero_poisson"),
            "t_boites": par_article.get("t_boites"),
            "caisses": par_article.get("caisses"),
            "t_boites_utilises": par_article.get("t_boites_utilisees"),
            "poisson_kg": par_article.get("poisson"),
            "filet_kg": par_article.get("filet"),
            "rdt_filet_pct": par_article.get("rdt_filet"),
            "rdt_calcule_pct": par_article.get("rdt_calcule"),
            "px_mp": par_article.get("prix_mp"),
            "huile_kg": par_article.get("huile"),
            "pu_huile": par_article.get("pu_huile"),
            "fr_fab": par_article.get("fr_fab"),
            "mod_total": par_article.get("mod"),
            "mod_pct": par_article.get("mod_taux"),
            "momg": par_article.get("momg"),
            "momg_pct": par_article.get("momg_taux"),
            # ch_fixes : priorite au cartouche (par_article), sinon repli sur C.Global
            "ch_fixes": par_article.get("ch_fixes", cout_global_row.get("charges_fixes")),
            "devise": par_article.get("devise") or "MAD",
            "taux_change": par_article.get("change"),
            # -- Ces 8 champs ne sont PAS fournis par ParArticleExtractor :
            #    ils viennent de la ligne C.Global correspondante (point ouvert B/C).
            "tot_cd_dhs": cout_global_row.get("tot_cd"),
            "tot_pmv_dhs": cout_global_row.get("pmv"),
            "tot_pr_dhs": cout_global_row.get("tot_pr"),
            "tot_mb_dhs": cout_global_row.get("tot_mb"),
            "tot_mn_dhs": cout_global_row.get("tot_mn"),
            "pct_mb": cout_global_row.get("pct_mb"),
            "pct_cf": cout_global_row.get("pct_cf"),
            "pct_mn": cout_global_row.get("pct_mn"),
            "numero_serie": par_article.get("numero_serie"),
            "reference_client": par_article.get("reference_client"),
            "date_reception": _parse_date_ddmmyyyy(par_article.get("date_reception")),
            "ligne_production": par_article.get("ligne"),
            "cout_min_reel": (par_article.get("cout_min") or {}).get("reel"),
            "cout_min_stnd": (par_article.get("cout_min") or {}).get("stnd"),
        }
    )
    return result.fetchone()[0]


def replace_ecarts_couts_postes(session, fk_resolver, id_production, df_table_couts):
    """Table `ecarts_couts_postes`, alimentee par
    ParArticleExtractor.extract_table_couts() (poste, cout_reel, cout_stnd).

    CORRECTION : df_table_couts est un DataFrame (pas une liste de
    dicts comme le supposait l'ancien pipeline) -> conversion explicite.
    """
    session.execute(
        text("DELETE FROM ecarts_couts_postes WHERE id_production = :id_prod"),
        {"id_prod": id_production}
    )

    if df_table_couts is None or df_table_couts.empty:
        return

    query = text("""
        INSERT INTO ecarts_couts_postes (id_production, id_poste_cout, reel_unitaire, stnd_unitaire, ecart_unitaire, pct_ecart)
        VALUES (:id_production, :id_poste_cout, :reel, :stnd, :ecart, :pct_ecart);
    """)

    for row in df_table_couts.to_dict(orient="records"):
        # Postes de COUT (Poisson/Huile/Additif/Boite/MOD/MOMg/Fr Fab/Port...)
        # -> postes_couts_reference, PAS postes_production (voir migration_v9).
        id_poste_cout = fk_resolver.get_or_create_poste_cout(row.get("poste"))
        reel = float(row.get("cout_reel") or 0)
        stnd = float(row.get("cout_stnd") or 0)
        ecart = reel - stnd
        pct_ecart = ((ecart / stnd) * 100) if stnd else 0.0

        session.execute(query, {
            "id_production": id_production,
            "id_poste_cout": id_poste_cout,
            "reel": reel,
            "stnd": stnd,
            "ecart": ecart,
            "pct_ecart": pct_ecart
        })


# ==========================================
# 4. RENDEMENT_EXTRACTOR -> lots_poisson
# ==========================================

def upsert_lots_poisson(session, fk_resolver, df_entrees, df_summary, context_date):
    """Table `lots_poisson`.
    NECESSITE la contrainte UNIQUE (br, id_site) -> voir migration_v8.sql.
    """
    if df_entrees is None or df_entrees.empty:
        return

    date_prod = _parse_date_ddmmyyyy(context_date)

    query = text("""
        INSERT INTO lots_poisson (
            date_production, id_site, no_lot, date_entree, nb_jours_frigo, frigo,
            fournisseur, br, poids_kg, origine, moule, poids_filets_kg, rdt_pct,
            pct_mrc, id_type_poisson, pct_repartition, etat
        ) VALUES (
            :date_prod, :id_site, :no_lot, :date_entree, :nb_jrs, :frigo,
            :fournisseur, :br, :poids, :origine, :moule, :filets, :rdt,
            :mrc_pct, :id_poisson, :poids_pct, :etat
        )
        ON CONFLICT (br, id_site) DO UPDATE SET
            date_production = EXCLUDED.date_production,
            no_lot = EXCLUDED.no_lot,
            date_entree = EXCLUDED.date_entree,
            nb_jours_frigo = EXCLUDED.nb_jours_frigo,
            frigo = EXCLUDED.frigo,
            fournisseur = EXCLUDED.fournisseur,
            poids_kg = EXCLUDED.poids_kg,
            origine = EXCLUDED.origine,
            moule = EXCLUDED.moule,
            poids_filets_kg = EXCLUDED.poids_filets_kg,
            rdt_pct = EXCLUDED.rdt_pct,
            pct_mrc = EXCLUDED.pct_mrc,
            id_type_poisson = EXCLUDED.id_type_poisson,
            pct_repartition = EXCLUDED.pct_repartition,
            etat = EXCLUDED.etat;
    """)

    for _, row in df_entrees.iterrows():
        id_site = fk_resolver.get_or_create_site(row.get("site"))
        id_poisson = fk_resolver.get_or_create_poisson(row.get("libelle"))

        summary_row = {}
        if df_summary is not None and not df_summary.empty:
            m = df_summary[df_summary["libelle"] == row.get("libelle")]
            if not m.empty:
                summary_row = m.iloc[0].to_dict()

        session.execute(query, {
            "date_prod": date_prod,
            "id_site": id_site,
            "no_lot": row.get("br"),
            "date_entree": _parse_date_ddmmyyyy(row.get("date_entree")),
            "nb_jrs": row.get("nb_jrs"),
            "frigo": row.get("frigo"),
            "fournisseur": row.get("fournisseur"),
            "br": row.get("br"),
            "poids": row.get("poids"),
            "origine": row.get("origine"),
            "moule": row.get("moule"),
            "filets": summary_row.get("filets"),
            "rdt": summary_row.get("rdt_pct"),
            "mrc_pct": summary_row.get("mrc_pct"),
            "id_poisson": id_poisson,
            "poids_pct": row.get("poids_pct"),
            "etat": row.get("etat")
        })


# ==========================================
# 5. RESUME_EXTRACTOR -> resume_journalier / matiere_premiere /
#    mod_global / resume_production_poisson / table_codes
# ==========================================

def get_or_create_resume_journalier(session, fk_resolver, date_production, reference_jour, site_code):
    """Table `resume_journalier`.
    Pattern get_or_create explicite (pas de contrainte UNIQUE exploitable
    dans le schema actuel -> voir migration_v8.sql pour en ajouter une
    sur reference_jour, recommande).
    """
    existing = session.execute(
        text("SELECT id_resume FROM resume_journalier WHERE reference_jour = :ref"),
        {"ref": reference_jour}
    ).fetchone()
    if existing:
        return existing[0]

    id_site = fk_resolver.get_or_create_site(site_code)  # point ouvert A : site a fournir par l'appelant
    res = session.execute(
        text("""
            INSERT INTO resume_journalier (date_production, reference_jour, id_site)
            VALUES (:date_production, :reference_jour, :id_site)
            RETURNING id_resume;
        """),
        {"date_production": date_production, "reference_jour": reference_jour, "id_site": id_site}
    ).fetchone()
    return res[0]


def upsert_matiere_premiere(session, id_resume, df_matiere_premiere):
    """Table `matiere_premiere`. Pas de contrainte UNIQUE -> on
    remplace toutes les lignes du jour pour eviter les doublons si
    l'ETL est relance."""
    session.execute(
        text("DELETE FROM matiere_premiere WHERE id_resume = :id_resume"),
        {"id_resume": id_resume}
    )
    if df_matiere_premiere is None or df_matiere_premiere.empty:
        return

    query = text("""
        INSERT INTO matiere_premiere (id_resume, fournisseur, partie, pu, qte)
        VALUES (:id_resume, :fournisseur, :partie, :pu, :qte);
    """)
    for row in df_matiere_premiere.to_dict(orient="records"):
        session.execute(query, {
            "id_resume": id_resume,
            "fournisseur": row.get("fournisseur"),
            "partie": row.get("partie"),
            "pu": row.get("pu"),
            "qte": row.get("qte"),
        })


def upsert_mod_global(session, id_resume, df_mod_global):
    """Table `mod_global`. UNIQUE(id_resume) deja en place -> ON CONFLICT ok."""
    if df_mod_global is None or df_mod_global.empty:
        return
    row = df_mod_global.iloc[0].to_dict()
    session.execute(
        text("""
            INSERT INTO mod_global (id_resume, mo, mg, mod_c, mg_c)
            VALUES (:id_resume, :mo, :mg, :mod_c, :mg_c)
            ON CONFLICT (id_resume) DO UPDATE SET
                mo = EXCLUDED.mo, mg = EXCLUDED.mg,
                mod_c = EXCLUDED.mod_c, mg_c = EXCLUDED.mg_c;
        """),
        {
            "id_resume": id_resume,
            "mo": row.get("mo"), "mg": row.get("mg"),
            "mod_c": row.get("mod_c"), "mg_c": row.get("mg_c"),
        }
    )


def upsert_resume_production_poisson(session, fk_resolver, id_resume, df_production):
    """Table `resume_production_poisson`. UNIQUE(id_resume, id_type_poisson)."""
    if df_production is None or df_production.empty:
        return
    for row in df_production.to_dict(orient="records"):
        id_poisson = fk_resolver.get_or_create_poisson(row.get("poisson"))
        session.execute(
            text("""
                INSERT INTO resume_production_poisson (
                    id_resume, id_type_poisson, qte_poisson, qte_filet, rdt_pct,
                    pu_moy, pct_jour, pct_prod_c, pct_prod_r
                ) VALUES (
                    :id_resume, :id_poisson, :qte_poisson, :qte_filet, :rdt_pct,
                    :pu_moy, :pct_jour, :pct_prod_c, :pct_prod_r
                )
                ON CONFLICT (id_resume, id_type_poisson) DO UPDATE SET
                    qte_poisson = EXCLUDED.qte_poisson,
                    qte_filet = EXCLUDED.qte_filet,
                    rdt_pct = EXCLUDED.rdt_pct,
                    pu_moy = EXCLUDED.pu_moy,
                    pct_jour = EXCLUDED.pct_jour,
                    pct_prod_c = EXCLUDED.pct_prod_c,
                    pct_prod_r = EXCLUDED.pct_prod_r;
            """),
            {
                "id_resume": id_resume,
                "id_poisson": id_poisson,
                "qte_poisson": row.get("qte"),
                "qte_filet": row.get("filet"),
                "rdt_pct": row.get("rdt"),
                "pu_moy": row.get("pu_moy"),
                "pct_jour": row.get("pct_jour"),
                "pct_prod_c": row.get("pct_prod_c"),
                "pct_prod_r": row.get("pct_prod_r"),
            }
        )


def upsert_table_codes(session, fk_resolver, id_resume, df_mod_par_code):
    """Table `table_codes` (Egoutte/Casse/Huile/MOD/Mg/FrFabDh par
    code), alimentee par ResumeExtractor.extract_matiere_premiere_et_codes()
    -> `mod_par_code`. UNIQUE(id_resume, id_article)."""
    if df_mod_par_code is None or df_mod_par_code.empty:
        return
    for row in df_mod_par_code.to_dict(orient="records"):
        id_article = fk_resolver.get_article_id(row.get("code"))
        if id_article is None:
            logger.warning(f"table_codes : article inconnu pour le code '{row.get('code')}' -> ligne ignoree")
            continue
        session.execute(
            text("""
                INSERT INTO table_codes (
                    id_resume, id_article, code, pct_prod, egoutte_std, egoutte_reel,
                    poids_produit, pct_casse, huile_reel, huile_std, mod_reel, mod_std,
                    mg_reel, mg_std, frfabdh_reel, frfabdh_std
                ) VALUES (
                    :id_resume, :id_article, :code, :pct_prod, :egoutte_std, :egoutte_reel,
                    :poids_produit, :pct_casse, :huile_reel, :huile_std, :mod_reel, :mod_std,
                    :mg_reel, :mg_std, :frfabdh_reel, :frfabdh_std
                )
                ON CONFLICT (id_resume, id_article) DO UPDATE SET
                    code = EXCLUDED.code,
                    pct_prod = EXCLUDED.pct_prod,
                    egoutte_std = EXCLUDED.egoutte_std,
                    egoutte_reel = EXCLUDED.egoutte_reel,
                    poids_produit = EXCLUDED.poids_produit,
                    pct_casse = EXCLUDED.pct_casse,
                    huile_reel = EXCLUDED.huile_reel,
                    huile_std = EXCLUDED.huile_std,
                    mod_reel = EXCLUDED.mod_reel,
                    mod_std = EXCLUDED.mod_std,
                    mg_reel = EXCLUDED.mg_reel,
                    mg_std = EXCLUDED.mg_std,
                    frfabdh_reel = EXCLUDED.frfabdh_reel,
                    frfabdh_std = EXCLUDED.frfabdh_std;
            """),
            {
                "id_resume": id_resume,
                "id_article": id_article,
                "code": row.get("code"),
                "pct_prod": row.get("pct_prod"),
                "egoutte_std": row.get("egoutte_std"),
                "egoutte_reel": row.get("egoutte_reel"),
                "poids_produit": row.get("poids_produit"),
                "pct_casse": row.get("pct_casse"),
                "huile_reel": row.get("huile_reel"),
                "huile_std": row.get("huile_std"),
                "mod_reel": row.get("mod_reel"),
                "mod_std": row.get("mod_std"),
                "mg_reel": row.get("mg_reel"),
                "mg_std": row.get("mg_std"),
                "frfabdh_reel": row.get("frfabdh_reel"),
                "frfabdh_std": row.get("frfabdh_std"),
            }
        )


# ==========================================
# 6. MOD_S1 / MOD_S2 EXTRACTORS -> mod_communs_journaliers / mod_durees_espece_poste
# ==========================================


def _parse_date_ddmmyyyy(value):
    """Parse une date au format DD/MM/YYYY (celui utilise par les PDF)
    en objet `date` Python.

    Indispensable avant toute insertion dans une colonne PostgreSQL de
    type `date` : sans ca, une chaine "05/06/2026" est envoyee telle
    quelle au serveur, qui peut l'interpreter en MDY (5 mai) au lieu de
    DMY (5 juin) selon son DateStyle -- une date fausse SANS erreur
    levee. Le format explicite "%d/%m/%Y" leve toute ambiguite.

    Retourne None si `value` est absente/vide (ex. date_reception non
    trouvee sur la fiche par_article). Si `value` est deja un objet
    date/datetime (ex. renvoye par CoutGlobalExtractor.extraire_date_rapport()
    ou RendementExtractor.extraire_date_rapport()), il est retourne tel
    quel (converti en `date` si c'est un `datetime`).
    """
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, _date_cls):
        return value
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
    return datetime.strptime(value, "%d/%m/%Y").date()


def upsert_mod_long_format(session, fk_resolver, df_mod, site_code):
    """Table `mod_communs_journaliers` + `mod_durees_espece_poste`.

    df_mod : DataFrame issu de ModExtractor.extract() ou
             ModExtractor_2.extract() -- colonnes (date, categorie,
             type_poisson, service, valeur).

    site_code : A FOURNIR EXPLICITEMENT (point ouvert C : les
    extracteurs mod_S1/mod_S2 ne mettent pas le site dans leurs
    lignes malgre le parametre `site=` du constructeur).
    """
    if df_mod is None or df_mod.empty:
        return

    id_site = fk_resolver.get_or_create_site(site_code)

    # ---- 0) Referentiel : garantit que les 7 postes MOD existent dans
    # postes_production avec le bon nom_poste/categorie ('production'
    # pour ET/EMB/FIL/SRTI, 'commun' pour PR_MP/NLE/COMM), meme si ce
    # fichier ne contient pas encore de ligne pour l'un d'eux.
    fk_resolver.seed_postes_referentiel_mod()

    # ---- 1) "Service Comm" : PR_MP / NLE / COMM -> mod_communs_journaliers
    # NB liaison : le schema de mod_communs_journaliers (db_v7.sql) a des
    # colonnes fixes (pr_mp, nle, comm) et PAS de colonne id_poste -> il
    # n'y a donc pas de FK litterale vers postes_production sur cette
    # table (contrairement a mod_durees_espece_poste.id_poste). La
    # "liaison" entre les deux tables passe par le CODE (PR_MP/NLE/COMM),
    # que l'on retrouve a l'identique comme postes_production.code_poste
    # (categorie='commun') grace au seed ci-dessus -- utile pour les
    # jointures de reporting cote lecture. Si tu veux une vraie FK ici,
    # il faudrait normaliser mod_communs_journaliers en format long
    # (date_production, id_site, id_poste, valeur) comme
    # mod_durees_espece_poste 
    comm = df_mod[df_mod["categorie"] == "Service Comm"]
    for date_str, group in comm.groupby("date"):
        date_prod = _parse_date_ddmmyyyy(date_str)
        vals = dict(zip(group["service"], group["valeur"]))
        session.execute(
            text("""
                INSERT INTO mod_communs_journaliers (date_production, id_site, pr_mp, nle, comm)
                VALUES (:date_prod, :id_site, :pr_mp, :nle, :comm)
                ON CONFLICT (date_production, id_site) DO UPDATE SET
                    pr_mp = EXCLUDED.pr_mp, nle = EXCLUDED.nle, comm = EXCLUDED.comm;
            """),
            {
                "date_prod": date_prod,
                "id_site": id_site,
                "pr_mp": vals.get("PR_MP"),
                "nle": vals.get("NLE"),
                "comm": vals.get("COMM"),
            }
        )

    # ---- 2) "Production" : (type_poisson x service) -> mod_durees_espece_poste
    # On ne garde que les 4 vrais postes ET/FIL/EMB/SRTI : "TOT"/"TOT2"
    # (sous-totaux par espece, cf. POSTES_PRODUCTION_A_IGNORER) sont
    # ecartes ici pour ne jamais polluer postes_production ni fausser
    # mod_durees_espece_poste par un double comptage.
    
    prod = df_mod[df_mod["categorie"] == "Production"]

    nb_ignores = 0
    nb_valeurs_absentes = 0

    for _, row in prod.iterrows():

        service_key = (
            str(row["service"]).strip().upper()
            if pd.notna(row["service"])
            else None
        )

        # ---------------------------------------------------------
        # TOT et TOT2 ne sont pas stockes
        # ---------------------------------------------------------
        if service_key in POSTES_PRODUCTION_A_IGNORER:
            nb_ignores += 1
            continue

        # ---------------------------------------------------------
        # Valeur absente -> on n'insere PAS de ligne du tout.
        #
        # `mod_durees_espece_poste.duree_min_kg` est NOT NULL en base :
        # une valeur absente signifie que ce poste n'existe pas pour
        # cette espece (ex. Caballa DS / ET, Sardine Ent / FIL) ou que
        # la cellule etait vide/"-"/"--"/"?" dans le PDF -- ce n'est
        # PAS une duree de 0 min/kg. Creer une ligne avec 0 fausserait
        # les moyennes et rapports ; on saute simplement la ligne.
        #
        # Exemple :
        # Caballa DS / ET  -> None -> ligne non creee
        # Sardine Ent / FIL -> None -> ligne non creee
        # ---------------------------------------------------------
        if pd.isna(row["valeur"]):
            nb_valeurs_absentes += 1
            continue

        valeur = row["valeur"]

        date_prod = _parse_date_ddmmyyyy(row["date"])

        id_poisson = fk_resolver.get_or_create_poisson(
            row["type_poisson"]
        )

        id_poste = fk_resolver.get_or_create_poste(
            row["service"]
        )

        session.execute(
            text("""
                INSERT INTO mod_durees_espece_poste (
                    date_production,
                    id_site,
                    id_type_poisson,
                    id_poste,
                    duree_min_kg
                )
                VALUES (
                    :date_prod,
                    :id_site,
                    :id_poisson,
                    :id_poste,
                    :valeur
                )
                ON CONFLICT (
                    date_production,
                    id_site,
                    id_type_poisson,
                    id_poste
                )
                DO UPDATE SET
                    duree_min_kg = EXCLUDED.duree_min_kg;
            """),
            {
                "date_prod": date_prod,
                "id_site": id_site,
                "id_poisson": id_poisson,
                "id_poste": id_poste,
                "valeur": valeur,
            }
        )

    if nb_ignores:
        logger.info(
            f"mod_{site_code} : {nb_ignores} ligne(s) "
            f"'TOT'/'TOT2' (sous-totaux par espece) "
            f"ignorees, non inserees dans mod_durees_espece_poste."
    )

    if nb_valeurs_absentes:
        logger.info(
            f"mod_{site_code} : {nb_valeurs_absentes} ligne(s) "
            f"sans valeur (poste inexistant pour l'espece, ou cellule "
            f"vide/'-'/'--'/'?' dans le PDF) ignoree(s), non inseree(s) "
            f"dans mod_durees_espece_poste."
        )

# ==========================================
# 7. ORCHESTRATEURS
# ==========================================

def run_etl_par_article(
    session,
    fk_resolver,
    par_article_dict,
    df_cout_global_produits,
    date_cout_global=None,
    strict_dates=False,
):
    """Ingestion complete pour UN article (par_article_extractor.py +
    la ligne correspondante de c_global_extractor.py).

    date_cout_global : [correctif] date globale du rapport C.Global.pdf
    (cle "date" du dict retourne par CoutGlobalExtractor.extraire()).
    Transmise ici pour que _find_cout_global_row() puisse verifier
    qu'elle correspond bien a la date de la fiche par_article avant de
    fusionner les deux sources -- voir _find_cout_global_row() pour le
    detail du probleme (meme code + meme site mais date differente).
    """
    upsert_article(session, fk_resolver, par_article_dict)

    # [correctif] Normalisation du site brut ("CX0"/"CX1" -> "S1"/"S2")
    # UNE SEULE FOIS ici, reutilisee pour le matching C.Global ET pour
    # la creation du site en base (upsert_production_journaliere lit
    # directement par_article_dict["site"], deja normalise a ce stade).
    par_article_dict["site"] = normalize_site_code(par_article_dict.get("site"))

    date_par_article = _parse_date_ddmmyyyy(par_article_dict.get("date_production"))

    df_cout_global_produits = normalize_cglobal_sites(df_cout_global_produits)
    cout_global_row = _find_cout_global_row(
        df_cout_global_produits,
        par_article_dict.get("code_produit"),
        site_code=par_article_dict.get("site"),
        date_par_article=date_par_article,
        date_cout_global=date_cout_global,
        strict_dates=strict_dates,
    )
    if not cout_global_row:
        logger.warning(
            f"Aucune ligne C.Global exploitable pour le code '{par_article_dict.get('code_produit')}' "
            f"(absente, OU rejetee pour incoherence de date -- voir logs precedents) "
            f"-> tot_cd/tot_mb/pmv/pct_mb/pct_cf/pct_mn seront NULL pour cette production."
        )

    id_production = upsert_production_journaliere(session, fk_resolver, par_article_dict, cout_global_row)

    df_table_couts = par_article_dict.get("table_couts")
    replace_ecarts_couts_postes(session, fk_resolver, id_production, df_table_couts)

    return id_production


def upsert_couts_unitaires(session, fk_resolver, id_resume, df_couts_unitaires):
    """Table `couts_unitaires_code` (cout unitaire par code : Poisson,
    Huile, Boite, Etui, MOD, Mg, Fr Fab, Fr Fin, C.D, P.V, M.B, Ch.F,
    M.N, avec les %), alimentee par ResumeExtractor.extract_couts_unitaires()
    -> cle "couts_unitaires". UNIQUE(id_resume, id_article)."""
    if df_couts_unitaires is None or df_couts_unitaires.empty:
        return
    for row in df_couts_unitaires.to_dict(orient="records"):
        id_article = fk_resolver.get_article_id(row.get("code"))
        if id_article is None:
            logger.warning(f"couts_unitaires_code : article inconnu pour le code '{row.get('code')}' -> ligne ignoree")
            continue
        session.execute(
            text("""
                INSERT INTO couts_unitaires_code (
                    id_resume, id_article, code, poisson, huile, boite, etui,
                    mod, mg, f_fab_reel, f_fab_std, f_fin, c_d, p_v,
                    m_b, pct_mb, ch_f, pct_cf, m_n, pct_mn
                ) VALUES (
                    :id_resume, :id_article, :code, :poisson, :huile, :boite, :etui,
                    :mod, :mg, :f_fab_reel, :f_fab_std, :f_fin, :c_d, :p_v,
                    :m_b, :pct_mb, :ch_f, :pct_cf, :m_n, :pct_mn
                )
                ON CONFLICT (id_resume, id_article) DO UPDATE SET
                    code = EXCLUDED.code,
                    poisson = EXCLUDED.poisson,
                    huile = EXCLUDED.huile,
                    boite = EXCLUDED.boite,
                    etui = EXCLUDED.etui,
                    mod = EXCLUDED.mod,
                    mg = EXCLUDED.mg,
                    f_fab_reel = EXCLUDED.f_fab_reel,
                    f_fab_std = EXCLUDED.f_fab_std,
                    f_fin = EXCLUDED.f_fin,
                    c_d = EXCLUDED.c_d,
                    p_v = EXCLUDED.p_v,
                    m_b = EXCLUDED.m_b,
                    pct_mb = EXCLUDED.pct_mb,
                    ch_f = EXCLUDED.ch_f,
                    pct_cf = EXCLUDED.pct_cf,
                    m_n = EXCLUDED.m_n,
                    pct_mn = EXCLUDED.pct_mn;
            """),
            {
                "id_resume": id_resume,
                "id_article": id_article,
                "code": row.get("code"),
                "poisson": row.get("poisson"),
                "huile": row.get("huile"),
                "boite": row.get("boite"),
                "etui": row.get("etui"),
                "mod": row.get("mod"),
                "mg": row.get("mg"),
                "f_fab_reel": row.get("f_fab_reel"),
                "f_fab_std": row.get("f_fab_std"),
                "f_fin": row.get("f_fin"),
                "c_d": row.get("c_d"),
                "p_v": row.get("p_v"),
                "m_b": row.get("m_b"),
                "pct_mb": row.get("pct_mb"),
                "ch_f": row.get("ch_f"),
                "pct_cf": row.get("pct_cf"),
                "m_n": row.get("m_n"),
                "pct_mn": row.get("pct_mn"),
            }
        )


def upsert_couts_par_serie(session, fk_resolver, id_resume, df_couts_serie):
    """Table `couts_par_serie` (montants par serie/lot de fabrication :
    B.Pdtes, Poisson, Boits, Huile, Etui, MOD, Mg, Fr Fab, Fr Fin, C.D,
    M.B, Ch.F, M.N, avec les %), alimentee par
    ResumeExtractor.extract_couts_serie() -> cle "couts_serie".
    UNIQUE(id_resume, id_article, serie).

    [ATTENTION - risque connu] Le champ "serie" extrait par resume.py
    (ex. "A26060") n'est PAS le numero de serie complet (l'"ordre de
    fabrication" complet, ex. "A2606021"/"A2606022" cote par_article) :
    c'est seulement le prefixe commun du jour, identique pour toutes
    les series. Tant qu'un article n'a qu'UNE serie par jour, la
    contrainte UNIQUE(id_resume, id_article, serie) suffit a le
    distinguer correctement (via id_article). MAIS si un meme article
    a 2 series le meme jour, la 2e ecrasera silencieusement la 1ere
    (ON CONFLICT DO UPDATE) -- aucune erreur ne sera levee. A surveiller
    si ce cas de figure existe reellement dans les PDF resume.py ; si
    oui, il faudra corriger extract_couts_serie() pour capturer le
    numero de serie complet (position x du 2e groupe de chiffres,
    juste apres le prefixe "A26060") plutot que le prefixe seul.

    NB : `valeur_extra_N` (colonnes generees par l'extracteur si une
    ligne du PDF contient plus de valeurs que SERIE_COLUMNS n'en
    prevoit) n'est PAS stocke ici -- log un warning si ca arrive, pour
    ne pas perdre l'information silencieusement."""
    if df_couts_serie is None or df_couts_serie.empty:
        return
    for row in df_couts_serie.to_dict(orient="records"):
        extras = {k: v for k, v in row.items() if k.startswith("valeur_extra_")}
        if extras:
            logger.warning(
                f"couts_par_serie : valeur(s) supplementaire(s) non prevue(s) "
                f"pour la serie '{row.get('serie')}'/code '{row.get('code')}' : "
                f"{extras} -> non stockees (colonne absente de couts_par_serie)."
            )

        id_article = fk_resolver.get_article_id(row.get("code"))
        if id_article is None:
            logger.warning(f"couts_par_serie : article inconnu pour le code '{row.get('code')}' -> ligne ignoree")
            continue
        session.execute(
            text("""
                INSERT INTO couts_par_serie (
                    id_resume, id_article, serie, code, b_pdtes, poisson, boits,
                    huile, etui, mod, mg, f_fab_reel, f_fab_std, f_fin, c_d,
                    mb, pct_mb, cf, mn, pct_mn
                ) VALUES (
                    :id_resume, :id_article, :serie, :code, :b_pdtes, :poisson, :boits,
                    :huile, :etui, :mod, :mg, :f_fab_reel, :f_fab_std, :f_fin, :c_d,
                    :mb, :pct_mb, :cf, :mn, :pct_mn
                )
                ON CONFLICT (id_resume, id_article, serie) DO UPDATE SET
                    code = EXCLUDED.code,
                    b_pdtes = EXCLUDED.b_pdtes,
                    poisson = EXCLUDED.poisson,
                    boits = EXCLUDED.boits,
                    huile = EXCLUDED.huile,
                    etui = EXCLUDED.etui,
                    mod = EXCLUDED.mod,
                    mg = EXCLUDED.mg,
                    f_fab_reel = EXCLUDED.f_fab_reel,
                    f_fab_std = EXCLUDED.f_fab_std,
                    f_fin = EXCLUDED.f_fin,
                    c_d = EXCLUDED.c_d,
                    mb = EXCLUDED.mb,
                    pct_mb = EXCLUDED.pct_mb,
                    cf = EXCLUDED.cf,
                    mn = EXCLUDED.mn,
                    pct_mn = EXCLUDED.pct_mn;
            """),
            {
                "id_resume": id_resume,
                "id_article": id_article,
                "serie": row.get("serie"),
                "code": row.get("code"),
                "b_pdtes": row.get("b_pdtes"),
                "poisson": row.get("poisson"),
                "boits": row.get("boits"),
                "huile": row.get("huile"),
                "etui": row.get("etui"),
                "mod": row.get("mod"),
                "mg": row.get("mg"),
                "f_fab_reel": row.get("f_fab_reel"),
                "f_fab_std": row.get("f_fab_std"),
                "f_fin": row.get("f_fin"),
                "c_d": row.get("c_d"),
                "mb": row.get("mb"),
                "pct_mb": row.get("pct_mb"),
                "cf": row.get("cf"),
                "mn": row.get("mn"),
                "pct_mn": row.get("pct_mn"),
            }
        )


def run_etl_resume(session, fk_resolver, resume_data, site_code):
    """Ingestion complete pour resume.py (site_code : point ouvert A,
    a fournir car absent du PDF/extracteur)."""
    info = resume_data["informations_generales"]
    if info.empty:
        logger.warning("resume.py : informations_generales vide, ETL resume annule.")
        return None

    info_row = info.iloc[0]
    id_resume = get_or_create_resume_journalier(
        session, fk_resolver,
        date_production=_parse_date_ddmmyyyy(info_row.get("date")),  # NB : resume.py renvoie deja un objet `date` Python ici (extract_date()) -- _parse_date_ddmmyyyy le laisse passer tel quel.
        reference_jour=info_row.get("reference"),
        site_code=site_code,
    )

    upsert_matiere_premiere(session, id_resume, resume_data.get("matiere_premiere"))
    upsert_mod_global(session, id_resume, resume_data.get("mod_global"))
    upsert_resume_production_poisson(session, fk_resolver, id_resume, resume_data.get("production"))
    upsert_table_codes(session, fk_resolver, id_resume, resume_data.get("mod_par_code"))

    # [correctif] couts_unitaires et couts_serie sont desormais inseres
    # (nouvelles tables couts_unitaires_code / couts_par_serie -- voir
    # migration_v11_couts_unitaires_serie.sql). synthese_production et
    # totaux_journaliers restent un point ouvert (pas de table dediee
    # -- a creer si besoin, meme mecanisme).
    upsert_couts_unitaires(session, fk_resolver, id_resume, resume_data.get("couts_unitaires"))
    upsert_couts_par_serie(session, fk_resolver, id_resume, resume_data.get("couts_serie"))

    return id_resume


def execute_etl(
    par_article_dict=None,
    df_cout_global_produits=None,
    date_cout_global=None,
    resume_data=None,
    resume_site_code=None,
    df_entrees_rendement=None,
    df_summary_rendement=None,
    rendement_context_date=None,
    df_mod_s1=None,
    df_mod_s2=None,
    strict_dates=False,
):
    """Orchestre l'ETL complet dans une transaction unique atomique.
    Tous les parametres sont optionnels : on ingere ce qui est fourni.

    date_cout_global : [correctif] date globale du rapport C.Global.pdf
    (cg_result["date"]), transmise a run_etl_par_article() pour verifier
    la coherence avec la date de par_article avant de fusionner les
    deux sources. Auparavant cette date etait calculee dans le bloc
    __main__ mais jamais transmise a execute_etl() -> le controle
    n'existait pas du tout pour les appels programmatiques.

    strict_dates : si True, une incoherence de date entre par_article
    et C.Global fait lever une exception (et annule toute la
    transaction via le rollback plus bas) au lieu de simplement logger
    un avertissement et ignorer les donnees C.Global pour cette ligne.
    """
    session = Session()
    fk_resolver = FKResolver(session)

    try:
        logger.info("Demarrage de l'ingestion...")

        if par_article_dict is not None:
            run_etl_par_article(
                session,
                fk_resolver,
                par_article_dict,
                df_cout_global_produits,
                date_cout_global=date_cout_global,
                strict_dates=strict_dates,
            )

        if resume_data is not None:
            run_etl_resume(session, fk_resolver, resume_data, resume_site_code)

        if df_entrees_rendement is not None:
            upsert_lots_poisson(session, fk_resolver, df_entrees_rendement, df_summary_rendement, rendement_context_date)

        if df_mod_s1 is not None:
            upsert_mod_long_format(session, fk_resolver, df_mod_s1, site_code="S1")

        if df_mod_s2 is not None:
            upsert_mod_long_format(session, fk_resolver, df_mod_s2, site_code="S2")

        session.commit()
        logger.info("--> Succes de l'ingestion BDD.")

    except Exception as e:
        session.rollback()
        logger.error(f"--> Echec de l'ETL, Annulation (Rollback) effectuee : {e}", exc_info=True)
        raise e
    finally:
        session.close()


