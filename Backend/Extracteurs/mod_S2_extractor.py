import pdfplumber
import pandas as pd
import re


class ModExtractor_2:
    """
    Meme cause que pour Mod_S1.pdf : ce PDF n'a pas de vrai quadrillage de
    tableau, donc extract_table() ne renvoie quasiment rien. On reconstruit
    les lignes via la position X de chaque mot (extract_words).

    Particularite de ce fichier (Site 2), visible en rendant la page en
    image : quand un GROUPE ENTIER de colonnes (Thon, Sardine, Vernis,
    Divers 2) n'a aucune donnee pour une date, le PDF affiche un seul "?"
    a la place de tout le groupe (pas un "?" par colonne). On l'ignore
    simplement : comme pour Mod_S1, une valeur "?" devient None, et comme
    ce "?" ne tombe jamais assez pres d'une vraie colonne de donnees, les
    champs du groupe restent naturellement vides.

    ATTENTION - a verifier avec le metier :
    - "Principale", "S/Sangacho", "Thon(Sarda Melva)" et "Divers 2" ont
      chacun 6 colonnes de donnees (et non 5 comme les groupes "poisson"
      habituels). L'entete du PDF n'affiche que 5 libelles lisibles
      (ET/Fil/Emb/Srti/Tot) par groupe : je n'ai pas pu determiner avec
      certitude le nom de la 6e colonne. Je l'ai appelee "TOT2" par
      defaut - a renommer si le metier connait sa vraie signification.
    - "Sardine" a 5 colonnes (ET/FIL/EMB/SRTI/TOT).
    - "Vernis" n'a AUCUNE valeur sur les 12 dates du fichier (toujours
      "?"). Je ne l'extrais donc pas : il n'y a rien a en tirer sans un
      exemple de ligne remplie pour connaitre sa structure.
    - La colonne "Global" (a droite) est ignoree, comme demande pour le
      Site 1.
    """

    def __init__(self, pdf_path):
        self.pdf_path = pdf_path

        self.groups = [
            ("Service Comm", None,
                ["PR_MP", "NLE", "COMM"]),
            ("Production", "Principale",
                ["ET", "FIL", "EMB", "SRTI", "TOT", "TOT2"]),
            ("Production", "S/Sangacho",
                ["ET", "FIL", "EMB", "SRTI", "TOT", "TOT2"]),
            ("Production", "Thon(Sarda Melva)",
                ["ET", "FIL", "EMB", "SRTI", "TOT", "TOT2"]),
            ("Production", "Sardine",
                ["ET", "FIL", "EMB", "SRTI", "TOT"]),
            ("Production", "Divers 2",
                ["ET", "FIL", "EMB", "SRTI", "TOT", "TOT2"]),
            # "Vernis" : jamais de donnees dans ce fichier -> non extrait.
            # "Global" : ignore comme demande.
        ]

        # Position X (x0) de chaque colonne de donnees reelle, relevee sur
        # les lignes du PDF, dans le meme ordre que self.groups.
        self.anchors = [
            65.8, 88.8, 112.8,                              # Service Comm
            132.7, 149.8, 167.8, 184.8, 201.7, 219.7,       # Principale
            238.3, 255.4, 273.4, 291.4, 308.4, 325.3,       # S/Sangacho
            346.8, 363.7, 381.7, 399.7, 416.8, 433.8,       # Thon
            455.8, 472.8, 490.8, 508.8, 526.8,              # Sardine
            656.8, 674.8, 691.8, 709.8, 727.8, 745.8,       # Divers 2
        ]

        self.max_distance = 10.0

        self.fields = []
        for categorie, type_poisson, services in self.groups:
            for service in services:
                self.fields.append((categorie, type_poisson, service))

    # =========================================================
    # OUTILS
    # =========================================================

    @staticmethod
    def clean(value):
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
    # LECTURE DU PDF -> UNE LIGNE PAR DATE
    # =========================================================

    def read_date_rows(self):

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
                    row_words = sorted(current_words, key=lambda w: w["x0"])
                    if re.match(r"^\d{2}/\d{2}/\d{4}$", row_words[0]["text"]):
                        date_rows.append(row_words)

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

        return date_rows

    # =========================================================
    # RATTACHEMENT DES MOTS A LEUR COLONNE
    # =========================================================

    def _assign_to_columns(self, value_words):

        result = [None] * len(self.anchors)

        for w in value_words:
            if w["text"].strip() == "?":
                continue

            best_i, best_dist = None, None
            for i, anchor_x in enumerate(self.anchors):
                dist = abs(w["x0"] - anchor_x)
                if best_dist is None or dist < best_dist:
                    best_dist = dist
                    best_i = i

            if best_dist is not None and best_dist <= self.max_distance:
                result[best_i] = w["text"]

        return result

    # =========================================================
    # EXTRACTION COMPLETE
    # =========================================================

    def extract(self):

        records = []

        for row_words in self.read_date_rows():

            date = row_words[0]["text"]
            values = self._assign_to_columns(row_words[1:])

            for (categorie, type_poisson, service), raw_value in zip(
                self.fields, values
            ):
                records.append({
                    "date": date,
                    "categorie": categorie,
                    "type_poisson": type_poisson,
                    "service": service,
                    "valeur": self.clean(raw_value),
                })

        return pd.DataFrame(records)


if __name__ == "__main__":

    PDF_PATH = r"d:\Cumarex_1\Backend\data_sources\Mod S2.pdf"

    extractor = ModExtractor_2(PDF_PATH)
    df = extractor.extract()

    print(df.to_string(index=False))