import pdfplumber
import pandas as pd
import re


class ModExtractor:
    """
    Extracteur du rapport MOD - Min / Kg - Site 1.
    Structure fixe des services et colonnes physiques définie au départ.
    """

    def __init__(self, pdf_path: str, site: str = "S1"):
        self.pdf_path = pdf_path
        self.site = site

        # 1. Structure logique complète (résultat final)
        self.groups = [
            ("Service Comm", None, ["PR_MP", "NLE", "COMM"]),
            ("Production", "Cab Normal", ["TOT"]),
            ("Production", "S/Sangacho", ["ET", "FIL", "EMB", "SRTI", "TOT", "TOT2"]),
            ("Production", "SPSA-HGT", ["ET", "FIL", "EMB", "SRTI", "TOT", "TOT2"]),
            ("Production", "Sardine Ent", ["ET", "FIL", "EMB", "SRTI", "TOT"]),
            ("Production", "Caballa DS", ["ET", "FIL", "EMB", "SRTI", "TOT"]),
        ]

        # 2. Colonnes physiques réelles dans le PDF du Site 1
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

            # Sardine Ent (FIL est absent du PDF)
            ("Production", "Sardine Ent", "ET", 458.8),
            ("Production", "Sardine Ent", "EMB", 475.8),
            ("Production", "Sardine Ent", "SRTI", 493.8),
            ("Production", "Sardine Ent", "TOT", 511.8),

            # Caballa DS (ET est absent du PDF)
            ("Production", "Caballa DS", "FIL", 570.7),
            ("Production", "Caballa DS", "EMB", 588.7),
            ("Production", "Caballa DS", "SRTI", 606.7),
            ("Production", "Caballa DS", "TOT", 632.9),
        ]

        self.max_distance = 12.0

        # Liste des champs logiques finaux
        self.fields = [
            (cat, type_p, srv)
            for cat, type_p, services in self.groups
            for srv in services
        ]

    @staticmethod
    def clean(value):
        if value is None:
            return None
        value = str(value).strip()
        if value in ("", "-", "--", "?", "??"):
            return None
        value = value.replace(",", ".")
        try:
            return float(value)
        except ValueError:
            return None

    def read_date_rows(self):
        date_rows = []
        with pdfplumber.open(self.pdf_path) as pdf:
            for page in pdf.pages:
                # x_tolerance=1.0 empêche la fusion de deux chiffres proches
                words = sorted(
                    page.extract_words(x_tolerance=1.0, y_tolerance=3.0),
                    key=lambda w: (w["top"], w["x0"])
                )
                if not words:
                    continue

                tol = 3.5
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

    def _assign_to_physical_columns(self, value_words):
        result = {}
        for w in value_words:
            text = w["text"].strip()
            if text in ("", "-", "--", "?", "??"):
                continue

            x = (w["x0"] + w["x1"]) / 2.0
            best_column = None
            best_distance = None

            for cat, type_p, srv, anchor_x in self.physical_columns:
                distance = abs(x - anchor_x)
                if best_distance is None or distance < best_distance:
                    best_distance = distance
                    best_column = (cat, type_p, srv)

            if best_column is not None and best_distance <= self.max_distance:
                result[best_column] = text

        return result

    def extract(self):
        records = []
        for row_words in self.read_date_rows():
            date = row_words[0]["text"]
            physical_values = self._assign_to_physical_columns(row_words[1:])

            for cat, type_p, srv in self.fields:
                raw_val = physical_values.get((cat, type_p, srv))
                records.append({
                    "date": date,
                    "categorie": cat,
                    "type_poisson": type_p,
                    "service": srv,
                    "valeur": self.clean(raw_val)
                })

        return pd.DataFrame(records)


if __name__ == "__main__":
    PDF_PATH = r"d:\Cumarex\Proposed project\Proposed project\Production\2026\06_Juin\03_06_2026\Mod S1.pdf"
    extractor = ModExtractor(PDF_PATH)
    df = extractor.extract()
    print(df.to_string(index=False))