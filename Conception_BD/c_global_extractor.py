import pdfplumber
import re
import pandas as pd
from datetime import date as _date


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
    # PARSING D'UNE LIGNE PRODUIT
    # =========================================================

    def parse_produit(self, ligne):

        m = ligne.split()

        # Une ligne produit doit contenir
        # au minimum 12 éléments
        if len(m) < 12:
            return None

        return {

            "site": None,

            "type_poisson": None,

            "code": m[0],

            "marque": m[1],

            "production":
                self.to_number(m[2]),

            "tot_cd":
                self.to_number(m[3]),

            "tot_mb":
                self.to_number(m[4]),

            "pct_mb":
                self.to_number(m[5]),

            "charges_fixes":
                self.to_number(m[6]),

            "pct_cf":
                self.to_number(m[7]),

            "pmv":
                self.to_number(m[8]),

            "tot_pr":
                self.to_number(m[9]),

            "pct_mn":
                self.to_number(m[10]),

            "tot_mn":
                self.to_number(m[11])
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

                p = self.parse_produit(ligne)

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

                    "tot_pr":
                        self.to_number(m[8]),

                    "pct_mn":
                        self.to_number(m[9]),

                    "tot_mn":
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

                    "tot_pr":
                        self.to_number(m[7]),

                    "pct_mn":
                        self.to_number(m[8]),

                    "tot_mn":
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


# =============================================================
# TEST
# =============================================================

if __name__ == "__main__":

    print(
        "===== TEST DU COUT GLOBAL ====="
    )

    # Chemin de ton PDF
    pdf_path = (
        r"D:\Cumarex_1\Backend\data_sources\C.Global.pdf"
    )

    # Création de l'extracteur
    extracteur = CoutGlobalExtractor(
        pdf_path
    )

    # Extraction
    result = extracteur.extraire()

    # =========================================================
    # DATE DU RAPPORT
    # =========================================================

    print("\n")
    print("=" * 70)
    print("DATE DU RAPPORT")
    print("=" * 70)

    print(result["date"])

    # =========================================================
    # DATAFRAME PRODUITS
    # =========================================================

    df_produits = result["produits"]

    print("\n")
    print("=" * 70)
    print("DATAFRAME PRODUITS")
    print("=" * 70)

    print(
        df_produits.to_string(
            index=False
        )
    )

    # =========================================================
    # DATAFRAME TOTAUX SITES
    # =========================================================

    df_totaux_sites = result["totaux_sites"]

    print("\n")
    print("=" * 70)
    print("DATAFRAME TOTAUX SITES")
    print("=" * 70)

    print(
        df_totaux_sites.to_string(
            index=False
        )
    )

    # =========================================================
    # DATAFRAME TOTAL GENERAL
    # =========================================================

    df_total_general = result["total_general"]

    print("\n")
    print("=" * 70)
    print("DATAFRAME TOTAL GENERAL")
    print("=" * 70)

    print(
        df_total_general.to_string(
            index=False
        )
    )

    # =========================================================
    # INFORMATIONS
    # =========================================================

    print("\n")
    print("=" * 70)
    print("INFORMATIONS")
    print("=" * 70)

    print(
        "Nombre de produits :",
        len(df_produits)
    )

    print(
        "Nombre de sites :",
        len(df_totaux_sites)
    )

    print(
        "Nombre de lignes total général :",
        len(df_total_general)
    )