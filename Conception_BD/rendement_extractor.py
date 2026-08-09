import re
import pdfplumber
import pandas as pd
from datetime import datetime


class RendementExtractor:
    """
    Extracteur pour le rapport 'Rendement.pdf'.
    Découpe le PDF en colonnes basées sur les coordonnées X des mots.

    ATTENTION [correctif] : le PDF affiche une date globale du rapport
    tout en haut (ex. "02/06/2026"), AVANT l'en-tete du tableau -- elle
    n'a rien a voir avec les colonnes "Date D'entrée" (qui donnent la
    date d'entree en frigo de CHAQUE lot). Cette date globale n'etait
    auparavant jamais recuperee : la ligne correspondante passait par
    `_has_label()` (qui la validait comme un libelle d'espece valide),
    puis etait ecrasee par le prochain vrai libelle rencontre (l'en-tete
    de colonnes "Libelle", puis les vrais noms d'especes). Elle est
    desormais extraite a part, avant toute classification, et exposee
    comme cle "date" du dict retourne par `extract()`.
    """

    def __init__(self, pdf_path):
        self.pdf_path = pdf_path

        self.etat_mapping = {
            "C": "Congelé",
            "F": "Frais"
        }

        # Bornes des colonnes (x0), calées sur l'entête du tableau.
        self.columns = [
            ("libelle",     0,   118),
            ("pct_c",     118,   158),
            ("etat",      158,   178),
            ("date",      178,   245),
            ("nb_jrs",    245,   280),
            ("frigo",     280,   305),
            ("fournisseur", 305, 385),
            ("br",        385,   450),
            ("poids",     450,   500),
            ("origine",   500,   560),
            ("moule",     560,   610),
            ("pct_poids", 610,   670),
            ("filets",    670,   725),
            ("rdt_pct",   725,   775),
            ("mrc_pct",   775,  1000),
        ]

        self.numeric_cols = {
            "nb_jrs", "poids", "pct_c", "pct_poids",
            "filets", "rdt_pct", "mrc_pct"
        }

    # =========================================================
    # OUTILS
    # =========================================================

    @staticmethod
    def clean_number(value):
        if value is None:
            return None

        value = str(value).strip()

        if not value or value == "-":
            return None

        value = value.replace("%", "")
        value = value.replace(" ", "")
        value = value.replace(",", ".")

        try:
            number = float(value)
            if number.is_integer():
                return int(number)
            return number
        except ValueError:
            return None

    def _column_for_x(self, x0):
        for name, x_min, x_max in self.columns:
            if x_min <= x0 < x_max:
                return name
        return None

    def extraire_date_rapport(self):
        """
        [correctif] Recupere la date globale du rapport, affichee tout
        en haut du PDF, avant l'en-tete du tableau (ex. "02/06/2026").

        On la cherche uniquement sur la 1ere page, dans le texte AVANT
        la 1ere occurrence de "Libelle" (en-tete de colonnes) -- ainsi
        on ne risque jamais de capturer par erreur une "Date D'entrée"
        de lot (qui apparait plus bas, apres l'en-tete).

        Retourne un objet `date` Python, ou None si non trouvee.
        """
        with pdfplumber.open(self.pdf_path) as pdf:
            if not pdf.pages:
                return None
            texte = pdf.pages[0].extract_text() or ""

        avant_entete = texte.split("Libelle", 1)[0]

        m = re.search(r"\b(\d{2})/(\d{2})/(\d{4})\b", avant_entete)
        if not m:
            return None

        jour, mois, annee = (int(g) for g in m.groups())
        try:
            return datetime(annee, mois, jour).date()
        except ValueError:
            return None

    # =========================================================
    # LECTURE DU PDF -> LIGNES DE MOTS GROUPES PAR COLONNE
    # =========================================================

    def read_rows(self):
        """
        Retourne une liste de "lignes logiques",
        chaque ligne étant un dict {colonne: texte}.
        """
        rows = []

        with pdfplumber.open(self.pdf_path) as pdf:
            for page in pdf.pages:
                words = page.extract_words()

                if not words:
                    continue

                words = sorted(words, key=lambda w: (w["top"], w["x0"]))

                tol = 3.0
                current_top = None
                current_words = []

                def flush():
                    if not current_words:
                        return
                    bucket = {}
                    for w in sorted(current_words, key=lambda w: w["x0"]):
                        col = self._column_for_x(w["x0"])
                        if col is None:
                            continue
                        bucket.setdefault(col, []).append(w["text"])

                    row = {}
                    for name, _, _ in self.columns:
                        tokens = bucket.get(name, [])
                        if not tokens:
                            row[name] = ""
                        elif name in self.numeric_cols:
                            row[name] = "".join(tokens)
                        else:
                            row[name] = " ".join(tokens)
                    rows.append(row)

                for w in words:
                    if current_top is None or abs(w["top"] - current_top) <= tol:
                        current_words.append(w)
                        if current_top is None:
                            current_top = w["top"]
                    else:
                        flush()
                        current_words = [w]
                        current_top = w["top"]

                flush()

        return rows

    # =========================================================
    # CLASSIFICATION DES LIGNES
    # =========================================================

    @staticmethod
    def _is_cumarex_row(row):
        return "CUMAREX" in row["libelle"].upper()

    @staticmethod
    def _site_from_row(row):
        match = re.search(r"S\d+", row["libelle"].upper())
        return match.group(0) if match else None

    @staticmethod
    def _is_entry_row(row):
        return (
            row["etat"] in ("C", "F")
            and bool(re.match(r"^\d{2}/\d{2}/\d{4}$", row["date"]))
        )

    @staticmethod
    def _is_total_row(row):
        return (
            row["etat"] == ""
            and row["date"] == ""
            and row["br"] == ""
            and row["poids"] != ""
            and row["pct_poids"].replace("%", "") == "100"
        )

    @staticmethod
    def _has_label(row):
        libelle = row["libelle"].strip()
        if not libelle:
            return False
        if "CUMAREX" in libelle.upper():
            return False
        if libelle.replace(" ", "").isdigit():
            return False
        # [correctif] Une date isolee (ex. "02/06/2026", la date globale
        # du rapport) n'est jamais un libelle d'espece valide -- sans ce
        # garde-fou, elle serait acceptee comme group_label transitoire
        # puis silencieusement ecrasee par le vrai libelle suivant.
        if re.match(r"^\d{2}/\d{2}/\d{4}$", libelle):
            return False
        return True

    # =========================================================
    # PARSING D'UNE LIGNE D'ENTREE
    # =========================================================

    def _parse_entry(self, row, site, libelle):
        etat = self.etat_mapping.get(row["etat"])

        return {
            "site": site,
            "libelle": libelle,
            "etat": etat,
            "date_entree": row["date"],
            "nb_jrs": self.clean_number(row["nb_jrs"]),
            "frigo": row["frigo"] if row["frigo"] else "-",
            "fournisseur": row["fournisseur"],
            "br": row["br"],
            "poids": self.clean_number(row["poids"]),
            "origine": row["origine"],
            "moule": row["moule"],
            "poids_pct": self.clean_number(row["pct_poids"]),
        }

    # =========================================================
    # EXTRACTION COMPLETE
    # =========================================================

    def extract(self):
        entries_records = []
        rendement_records = []
        site_block = []

        # [correctif] Date globale du rapport, extraite a part.
        date_rapport = self.extraire_date_rapport()

        # Utilisation de read_rows() définie au-dessus
        rows = self.read_rows()

        def process_site(site, site_rows):
            group_buffer = []
            group_label = None

            def close_group():
                nonlocal group_buffer, group_label
                libelle = group_label["libelle"] if group_label else None
                for r in group_buffer:
                    entries_records.append(
                        self._parse_entry(r, site, libelle)
                    )
                if group_label:
                    rendement_records.append({
                        "site": site,
                        "libelle": group_label["libelle"],
                        "libelle_pct": self.clean_number(group_label["pct_c"]),
                        "filets": self.clean_number(group_label["filets"]),
                        "rdt_pct": self.clean_number(group_label["rdt_pct"]),
                        "mrc_pct": self.clean_number(group_label["mrc_pct"]),
                    })
                group_buffer = []
                group_label = None

            for row in site_rows:
                if self._has_label(row):
                    group_label = {
                        "libelle": row["libelle"].strip(),
                        "pct_c": row["pct_c"],
                        "filets": row["filets"],
                        "rdt_pct": row["rdt_pct"],
                        "mrc_pct": row["mrc_pct"],
                    }

                if self._is_entry_row(row):
                    group_buffer.append(row)
                    continue

                if self._is_total_row(row):
                    close_group()

            if group_buffer or group_label:
                close_group()

        for row in rows:
            if self._is_cumarex_row(row):
                site = self._site_from_row(row)
                process_site(site, site_block)
                site_block = []
                continue

            site_block.append(row)

        if site_block:
            has_data = any(
                self._is_entry_row(r) or self._has_label(r)
                for r in site_block
            )
            if has_data:
                process_site("INCONNU", site_block)

        df_entrees = pd.DataFrame(entries_records)
        df_rendement = pd.DataFrame(rendement_records)

        return {
            "date": date_rapport,
            "df_entrees": df_entrees,
            "df_summary": df_rendement
        }


if __name__ == "__main__":
    PDF_PATH = r"D:\Cumarex_1\Backend\data_sources\Rendement.pdf"

    extractor = RendementExtractor(PDF_PATH)
    extracted_data = extractor.extract()

    df_entrees = extracted_data["df_entrees"]
    df_rendement = extracted_data["df_summary"]

    print("\n" + "=" * 100)
    print("DATE DU RAPPORT")
    print("=" * 100)
    print(extracted_data["date"])

    print("\n" + "=" * 100)
    print("DATAFRAME DES ENTREES")
    print("=" * 100)
    print(df_entrees.to_string(index=False))

    print("\n" + "=" * 100)
    print("DATAFRAME RENDEMENT")
    print("=" * 100)
    print(df_rendement.to_string(index=False))