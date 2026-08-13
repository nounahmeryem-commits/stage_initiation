import pdfplumber
import re
import pandas as pd
import logging
from datetime import date as _date

logger = logging.getLogger(__name__)


# Mois francais -> numero, pour parser une date du type
# "mardi 02 juin 2026" (jour de semaine ignore, jour/mois/annee captures).
MOIS_FR = {
    "janvier": 1, "fevrier": 2, "février": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "aout": 8, "août": 8,
    "septembre": 9, "octobre": 10, "novembre": 11,
    "decembre": 12, "décembre": 12,
}

_DATE_RAPPORT_RE = re.compile(
    r"(\d{1,2})\s+(" + "|".join(MOIS_FR.keys()) + r")\s+(\d{4})",
    re.IGNORECASE,
)

# [généralisation] Un token "code+marque" peut apparaître collé sans
# espace (ex. "125MCDSTPMEALIA" au lieu de "125MCDSTPME ALIA") quand les
# caractères se touchent réellement dans le PDF source à cet endroit
# précis. Comme la marque est une donnée métier qui change d'un fichier
# à l'autre (nouvelle marque = nouveau client), on ne veut PAS d'une
# liste de marques figée à l'avance : elle casserait dès qu'une marque
# non-listée apparaît collée.
#
# À la place, le vocabulaire des marques est appris DYNAMIQUEMENT à
# chaque extraction, à partir des lignes du même fichier où le code et
# la marque sont bien séparés par un espace (cas normal, largement
# majoritaire). Une marque n'est donc reconnaissable en suffixe collé
# que si elle apparaît au moins une fois correctement espacée ailleurs
# dans CE fichier -- ce qui est le cas normal puisque le collage semble
# être un accident de rendu PDF ponctuel, pas une caractéristique de la
# marque elle-même. Voir _collect_marques_dynamiques() et extraire().


def _split_code_marque(token, marques_connues):
    """Tente de separer un token "code+marque" colle sans espace, en
    reconnaissant une marque vue ailleurs dans le meme fichier (voir
    _collect_marques_dynamiques). Retourne (code, marque) ou
    (token, None) si aucune marque connue ne matche."""
    for marque in sorted(marques_connues, key=len, reverse=True):
        if token.endswith(marque) and len(token) > len(marque):
            return token[: -len(marque)], marque
    return token, None


class CoutGlobalExtractor:
    """
    Extracteur du fichier C.Global.pdf

    Retourne 4 elements :
        - date (objet `date` Python, ou None si non trouvee)
        - produits
        - totaux_sites
        - total_general

    ATTENTION [correctif] : l'extraction ne recuperait auparavant AUCUNE
    date -- le PDF affiche pourtant en 2e ligne une date complete en
    francais (ex. "mardi 02 juin 2026", juste sous le titre). Elle est
    desormais extraite via `extraire_date_rapport()` et exposee comme
    cle "date" du dict retourne par `extraire()`.
    """

    def __init__(self, pdf_path):
        self.pdf_path = pdf_path

    # =========================================================
    # DATE DU RAPPORT (nouveau)
    # =========================================================

    def extraire_date_rapport(self, texte):
        """
        Cherche une date complete en francais (ex. "mardi 02 juin 2026")
        n'importe ou dans le texte du PDF -- elle apparait juste sous le
        titre, avant le tableau des produits.

        Retourne un objet `date` Python, ou None si aucune date de ce
        format n'est trouvee (le PDF ne comportait aucune garantie de
        format avant ce correctif : mieux vaut retourner None qu'une
        date fausse en cas de mise en page inattendue).
        """
        m = _DATE_RAPPORT_RE.search(texte)
        if not m:
            return None

        jour = int(m.group(1))
        mois = MOIS_FR.get(m.group(2).lower())
        annee = int(m.group(3))

        if mois is None:
            return None

        try:
            return _date(annee, mois, jour)
        except ValueError:
            # jour/mois incoherents (ex. 31 fevrier) -> mieux vaut
            # signaler l'absence de date que d'en stocker une fausse.
            return None

    # =========================================================
    # OUTILS
    # =========================================================

    def to_number(self, value):
        """
        Convertit les nombres du PDF en nombres Python.

        Exemple :
            "9,8"    -> 9.8
            "32,4%"  -> 32.4
            "7.967"  -> 7967
        """

        if value is None:
            return None

        value = str(value).strip()

        value = value.replace("%", "")
        value = value.replace(".", "")
        value = value.replace(",", ".")

        try:
            return float(value)

        except (ValueError, AttributeError):
            return value

    # =========================================================
    # IDENTIFICATION DES LIGNES
    # =========================================================

    def est_produit(self, ligne):
        """
        Une ligne produit commence par un code numérique
        suivi d'une lettre.
        """

        return re.match(r'^\d+[A-Z]', ligne) is not None

    def est_total_site(self, ligne):
        """
        Une ligne total site commence par CX...
        """

        return re.match(r'^CX\d+', ligne) is not None

    def est_total_general(self, ligne):
        """
        Le total général contient au moins 10 valeurs numériques.
        """

        morceaux = ligne.split()

        if len(morceaux) < 10:
            return False

        return re.match(
            r'^\d+\.\d+$',
            morceaux[0]
        ) is not None

    # =========================================================
    # VOCABULAIRE DYNAMIQUE DES MARQUES (généralisation)
    # =========================================================

    def _collect_marques_dynamiques(self, texte):
        """
        Parcourt tout le texte du PDF et construit l'ensemble des
        marques déjà vues sur des lignes produit CORRECTEMENT espacées
        (code et marque en 2 tokens distincts). Ce vocabulaire sert
        ensuite de seul repère pour re-séparer les tokens collés sans
        espace -- sans dépendre d'une liste figée à l'avance, donc
        valable même si de nouvelles marques apparaissent dans un futur
        fichier.
        """
        marques = set()
        for ligne in texte.split("\n"):
            ligne = ligne.strip()
            if not self.est_produit(ligne):
                continue
            m = ligne.split()
            # Ligne normale : code (1 token) + marque (1 token) + 10
            # valeurs numeriques = 12 tokens. Si la marque elle-meme
            # contient un espace, le decoupage ci-dessous ne la
            # capturera pas correctement, mais on prefere rater un cas
            # rare plutot que reintroduire une liste figee.
            if len(m) == 12:
                marques.add(m[1])
        return marques

    # =========================================================
    # PARSING D'UNE LIGNE PRODUIT
    # =========================================================

    def parse_produit(self, ligne, marques_connues):

        m = ligne.split()

        # Une ligne produit doit contenir au minimum 11 elements (12
        # dans le cas normal code+marque separes ; 11 si colles sans
        # espace, voir _split_code_marque).
        if len(m) < 11:
            return None

        if len(m) == 11:
            # [généralisation] code et marque collés sans espace
            # (ex. "125MCDSTPMEALIA") -> tentative de séparation à
            # partir des marques déjà vues, correctement espacées,
            # ailleurs dans ce même fichier (voir
            # _collect_marques_dynamiques).
            code, marque = _split_code_marque(m[0], marques_connues)
            if marque is None:
                logger.warning(
                    f"C.Global : impossible de separer code/marque sur "
                    f"le token colle '{m[0]}' (aucune marque connue "
                    f"n'a ete vue, correctement espacee, ailleurs dans "
                    f"ce fichier) -> ligne ignoree."
                )
                return None
            valeurs = m[1:]
        else:
            code, marque = m[0], m[1]
            valeurs = m[2:]

        if len(valeurs) < 10:
            return None

        # [correctif] L'en-tete reel du PDF est :
        #   Code Marque B.Produc Tot CD Tot MB %MB Ch Fixes %CF
        #   Tot PMV Tot M.N %MN Tot PR
        # -> apres "Tot PMV" (valeurs[6]) vient "Tot M.N" (valeurs[7]),
        # PUIS "%MN" (valeurs[8]), PUIS "Tot PR" (valeurs[9]). Les deux
        # derniers champs etaient inverses dans une version precedente
        # (tot_pr et tot_mn echanges).
        return {

            "site":
                None,

            "type_poisson":
                None,

            "code":
                code,

            "marque":
                marque,

            "production":
                self.to_number(valeurs[0]),

            "tot_cd":
                self.to_number(valeurs[1]),

            "tot_mb":
                self.to_number(valeurs[2]),

            "pct_mb":
                self.to_number(valeurs[3]),

            "charges_fixes":
                self.to_number(valeurs[4]),

            "pct_cf":
                self.to_number(valeurs[5]),

            "pmv":
                self.to_number(valeurs[6]),

            "tot_mn":
                self.to_number(valeurs[7]),

            "pct_mn":
                self.to_number(valeurs[8]),

            "tot_pr":
                self.to_number(valeurs[9])
        }

    # =========================================================
    # LECTURE DU PDF
    # =========================================================

    def _lire_texte(self):

        morceaux_texte = []

        with pdfplumber.open(self.pdf_path) as pdf:

            for page in pdf.pages:

                texte_page = page.extract_text()

                if texte_page:

                    morceaux_texte.append(
                        texte_page
                    )

        return "\n".join(
            morceaux_texte
        )

    # =========================================================
    # EXTRACTION COMPLETE
    # =========================================================

    def extraire(self):

        texte = self._lire_texte()

        # [correctif] Date du rapport (ex. "mardi 02 juin 2026"),
        # cherchee sur le texte complet avant tout decoupage en lignes.
        date_rapport = self.extraire_date_rapport(texte)

        # [généralisation] Vocabulaire des marques appris sur CE fichier
        # (voir _collect_marques_dynamiques), utilisé pour re-séparer les
        # tokens "code+marque" collés sans espace.
        marques_connues = self._collect_marques_dynamiques(texte)

        # -----------------------------------------------------
        # LISTES TEMPORAIRES
        # -----------------------------------------------------

        produits = []

        produits_attente = []

        totaux_sites = []

        total_general = {}

        site_en_attente = []

        # -----------------------------------------------------
        # PARCOURS DES LIGNES
        # -----------------------------------------------------

        for ligne in texte.split("\n"):

            ligne = ligne.strip()

            if ligne == "":
                continue

            # =================================================
            # PRODUIT
            # =================================================

            if self.est_produit(ligne):

                p = self.parse_produit(ligne, marques_connues)

                if p is None:
                    continue

                produits.append(p)

                # Produits qui attendent leur type de poisson
                produits_attente.append(p)

                # Produits qui attendent leur site
                site_en_attente.append(p)

                continue

            # =================================================
            # TOTAL SITE
            # =================================================

            if self.est_total_site(ligne):

                m = ligne.split()

                if len(m) < 11:
                    continue

                site = m[0]

                # -------------------------------------------------
                # Tous les produits précédents appartiennent
                # à ce site
                # -------------------------------------------------

                for p in site_en_attente:

                    p["site"] = site

                site_en_attente = []

                # -------------------------------------------------
                # Enregistrement du total du site
                # -------------------------------------------------

                totaux_sites.append({

                    "site":
                        site,

                    "production":
                        self.to_number(m[1]),

                    "tot_cd":
                        self.to_number(m[2]),

                    "tot_mb":
                        self.to_number(m[3]),

                    "pct_mb":
                        self.to_number(m[4]),

                    "charges_fixes":
                        self.to_number(m[5]),

                    "pct_cf":
                        self.to_number(m[6]),

                    "pmv":
                        self.to_number(m[7]),

                    # [correctif] tot_mn/tot_pr etaient inverses (voir
                    # parse_produit pour l'explication de l'ordre reel)
                    "tot_mn":
                        self.to_number(m[8]),

                    "pct_mn":
                        self.to_number(m[9]),

                    "tot_pr":
                        self.to_number(m[10])
                })

                continue

            # =================================================
            # TOTAL GENERAL
            # =================================================

            if self.est_total_general(ligne):

                m = ligne.split()

                total_general = {

                    "production":
                        self.to_number(m[0]),

                    "tot_cd":
                        self.to_number(m[1]),

                    "tot_mb":
                        self.to_number(m[2]),

                    "pct_mb":
                        self.to_number(m[3]),

                    "charges_fixes":
                        self.to_number(m[4]),

                    "pct_cf":
                        self.to_number(m[5]),

                    "pmv":
                        self.to_number(m[6]),

                    # [correctif] tot_mn/tot_pr etaient inverses
                    "tot_mn":
                        self.to_number(m[7]),

                    "pct_mn":
                        self.to_number(m[8]),

                    "tot_pr":
                        self.to_number(m[9])
                }

                continue

            # =================================================
            # TYPE DE POISSON
            # =================================================

            morceaux = ligne.split()

            if len(morceaux) >= 2:

                type_poisson = " ".join(
                    morceaux[:2]
                )

                # -------------------------------------------------
                # Association du type de poisson aux produits
                # précédemment détectés
                # -------------------------------------------------

                for p in produits_attente:

                    p["type_poisson"] = type_poisson

                produits_attente = []

        # =====================================================
        # CONVERSION EN DATAFRAMES
        # =====================================================

        df_produits = pd.DataFrame(
            produits
        )

        df_totaux_sites = pd.DataFrame(
            totaux_sites
        )

        if total_general:

            df_total_general = pd.DataFrame(
                [total_general]
            )

        else:

            df_total_general = pd.DataFrame()

        # =====================================================
        # RETOUR
        # =====================================================

        return {

            "date":
                date_rapport,

            "produits":
                df_produits,

            "totaux_sites":
                df_totaux_sites,

            "total_general":
                df_total_general
        }


