import pdfplumber
import pandas as pd
import re


class ModExtractor:
    """
    Extracteur du rapport MOD - Min / Kg - Site 1.

    Structure réelle du PDF :

        Service Comm
        Cab Normal
        S/Sangacho
        SPSA-HGT
        Sardine Ent
        Caballa DS
        Global Site 1 et 2

    Règles particulières :

    - Sardine Ent :
        ET / EMB / SRTI / TOT
        FIL n'existe pas dans le PDF -> NULL

    - Caballa DS :
        FIL / EMB / SRTI / TOT
        ET n'existe pas dans le PDF -> NULL

    - Toute valeur vide, "-", "--" ou "?" -> None

    - Global Site 1 et 2 est ignoré.
    """

    def __init__(self, pdf_path: str, site: str = "S1"):
        self.pdf_path = pdf_path
        self.site = site

        # ---------------------------------------------------------
        # Structure logique finale
        # ---------------------------------------------------------
        #
        # Même si FIL n'existe pas physiquement dans Sardine Ent,
        # on le garde dans le résultat final avec valeur None.
        #
        # Même chose pour ET dans Caballa DS.
        # ---------------------------------------------------------

        self.groups = [
            # Service commercial
            (
                "Service Comm",
                None,
                ["PR_MP", "NLE", "COMM"]
            ),

            # Cab Normal : seul TOT existe dans le PDF
            (
                "Production",
                "Cab Normal",
                ["TOT"]
            ),

            # S/Sangacho
            (
                "Production",
                "S/Sangacho",
                ["ET", "FIL", "EMB", "SRTI", "TOT", "TOT2"]
            ),

            # SPSA-HGT
            (
                "Production",
                "SPSA-HGT",
                ["ET", "FIL", "EMB", "SRTI", "TOT", "TOT2"]
            ),

            # Sardine Ent :
            # FIL n'existe PAS physiquement.
            (
                "Production",
                "Sardine Ent",
                ["ET", "FIL", "EMB", "SRTI", "TOT"]
            ),

            # Caballa DS :
            # ET n'existe PAS physiquement.
            (
                "Production",
                "Caballa DS",
                ["ET", "FIL", "EMB", "SRTI", "TOT"]
            ),
        ]

        # ---------------------------------------------------------
        # Colonnes physiques présentes dans le PDF
        # ---------------------------------------------------------
        #
        # IMPORTANT :
        #
        # Sardine Ent :
        #     ET      -> 458.8
        #     FIL     -> PAS DE COLONNE
        #     EMB     -> 475.8
        #     SRTI    -> 493.8
        #     TOT     -> 511.8
        #
        # Caballa DS :
        #     ET      -> PAS DE COLONNE
        #     FIL     -> 570.7
        #     EMB     -> 588.7
        #     SRTI    -> 606.7
        #     TOT     -> 632.9
        #
        # Global commence ensuite vers 662.0 -> ignoré.
        # ---------------------------------------------------------

        self.physical_columns = [
            # Service Comm
            ("Service Comm", None, "PR_MP", 65.8),
            ("Service Comm", None, "NLE", 88.8),
            ("Service Comm", None, "COMM", 112.8),

            # Cab Normal
            ("Production", "Cab Normal", "TOT", 220.8),

            # S/Sangacho
            ("Production", "S/Sangacho", "ET", 242.8),
            ("Production", "S/Sangacho", "FIL", 259.8),
            ("Production", "S/Sangacho", "EMB", 277.8),
            ("Production", "S/Sangacho", "SRTI", 295.8),
            ("Production", "S/Sangacho", "TOT", 313.8),
            ("Production", "S/Sangacho", "TOT2", 330.7),

            # SPSA-HGT
            ("Production", "SPSA-HGT", "ET", 351.7),
            ("Production", "SPSA-HGT", "FIL", 368.8),
            ("Production", "SPSA-HGT", "EMB", 386.8),
            ("Production", "SPSA-HGT", "SRTI", 404.8),
            ("Production", "SPSA-HGT", "TOT", 421.8),
            ("Production", "SPSA-HGT", "TOT2", 438.7),

            # Sardine Ent
            ("Production", "Sardine Ent", "ET", 458.8),

            # FIL absent -> aucune position X

            ("Production", "Sardine Ent", "EMB", 475.8),
            ("Production", "Sardine Ent", "SRTI", 493.8),
            ("Production", "Sardine Ent", "TOT", 511.8),

            # Caballa DS
            #
            # ET absent -> aucune position X
            #
            ("Production", "Caballa DS", "FIL", 570.7),
            ("Production", "Caballa DS", "EMB", 588.7),
            ("Production", "Caballa DS", "SRTI", 606.7),
            ("Production", "Caballa DS", "TOT", 632.9),
        ]

        # Distance maximale entre un mot et son anchor
        self.max_distance = 10.0

        # Liste des champs logiques finaux
        self.fields = []

        for categorie, type_poisson, services in self.groups:
            for service in services:
                self.fields.append(
                    (categorie, type_poisson, service)
                )

    # =========================================================
    # NETTOYAGE DES VALEURS
    # =========================================================

    @staticmethod
    def clean(value):
        """
        Convertit une valeur extraite en float.

        Valeurs considérées comme NULL :
            ""
            "-"
            "--"
            "?"
            None
        """

        if value is None:
            return None

        value = str(value).strip()

        if value in ("", "-", "--", "?"):
            return None

        value = value.replace(",", ".")

        try:
            return float(value)

        except ValueError:
            return None

    # =========================================================
    # LECTURE DU PDF
    # =========================================================

    def read_date_rows(self):
        """
        Extrait les lignes correspondant aux différentes dates.
        """

        date_rows = []

        with pdfplumber.open(self.pdf_path) as pdf:

            for page in pdf.pages:

                words = sorted(
                    page.extract_words(),
                    key=lambda w: (w["top"], w["x0"])
                )

                if not words:
                    continue

                tol = 3.0

                current_top = None
                current_words = []

                def flush():

                    if not current_words:
                        return

                    row_words = sorted(
                        current_words,
                        key=lambda w: w["x0"]
                    )

                    # Première cellule = date
                    if re.match(
                        r"^\d{2}/\d{2}/\d{4}$",
                        row_words[0]["text"]
                    ):
                        date_rows.append(row_words)

                for w in words:

                    if (
                        current_top is None
                        or abs(w["top"] - current_top) <= tol
                    ):
                        current_words.append(w)

                        if current_top is None:
                            current_top = w["top"]

                    else:
                        flush()

                        current_words = [w]
                        current_top = w["top"]

                flush()

        return date_rows

    # =========================================================
    # RATTACHEMENT AUX COLONNES PHYSIQUES
    # =========================================================

    def _assign_to_physical_columns(self, value_words):
        """
        Associe chaque mot à une colonne physique.

        IMPORTANT :
        on ne met PAS de colonne fictive pour les colonnes
        absentes du PDF.

        Donc :
            Sardine Ent -> pas de FIL
            Caballa DS  -> pas de ET
        """

        result = {}

        for w in value_words:

            text = w["text"].strip()

            # Toutes les valeurs spéciales deviennent NULL
            if text in ("", "-", "--", "?"):
                continue

            x = w["x0"]

            best_column = None
            best_distance = None

            for (
                categorie,
                type_poisson,
                service,
                anchor_x
            ) in self.physical_columns:

                distance = abs(x - anchor_x)

                if (
                    best_distance is None
                    or distance < best_distance
                ):
                    best_distance = distance
                    best_column = (
                        categorie,
                        type_poisson,
                        service
                    )

            # On accepte uniquement si suffisamment proche
            if (
                best_column is not None
                and best_distance <= self.max_distance
            ):
                result[best_column] = text

        return result

    # =========================================================
    # EXTRACTION COMPLETE
    # =========================================================

    def extract(self):

        records = []

        for row_words in self.read_date_rows():

            date = row_words[0]["text"]

            # Toutes les valeurs physiques trouvées
            physical_values = self._assign_to_physical_columns(
                row_words[1:]
            )

            # -------------------------------------------------
            # Création des champs logiques
            # -------------------------------------------------
            #
            # On parcourt les champs FINALS.
            #
            # Pour une colonne absente du PDF :
            # physical_values ne contient aucune entrée
            # -> raw_value = None
            #
            # Sardine Ent / FIL -> None
            # Caballa DS / ET  -> None
            # -------------------------------------------------

            for (
                categorie,
                type_poisson,
                service
            ) in self.fields:

                key = (
                    categorie,
                    type_poisson,
                    service
                )

                raw_value = physical_values.get(key)

                # Nettoyage final
                valeur = self.clean(raw_value)

                records.append({
                    "date": date,
                    "categorie": categorie,
                    "type_poisson": type_poisson,
                    "service": service,
                    "valeur": valeur
                })

        return pd.DataFrame(records)


# =============================================================
# PROGRAMME PRINCIPAL
# =============================================================

if __name__ == "__main__":

    PDF_PATH = r"d:\Cumarex_1\Backend\data_sources\Mod S1.pdf"

    extractor = ModExtractor(PDF_PATH)

    df = extractor.extract()

    print(df.to_string(index=False))