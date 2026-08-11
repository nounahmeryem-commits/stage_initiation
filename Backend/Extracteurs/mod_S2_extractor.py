import pdfplumber
import pandas as pd
import re


class ModExtractor_2:
    """
    Extracteur du rapport MOD - Min / Kg - Site 2.
    Structure fixe des services et colonnes physiques définie au départ.
    """

    def __init__(self, pdf_path: str, site: str = "S2"):
        self.pdf_path = pdf_path
        self.site = site

        # 1. Structure logique complète
        self.groups = [
            ("Service Comm", None, ["PR_MP", "NLE", "COMM"]),
            ("Production", "Principale", ["ET", "FIL", "EMB", "SRTI", "TOT", "TOT2"]),
            ("Production", "S/Sangacho", ["ET", "FIL", "EMB", "SRTI", "TOT", "TOT2"]),
            ("Production", "Thon(Sarda Melva)", ["ET", "FIL", "EMB", "SRTI", "TOT", "TOT2"]),
            ("Production", "Sardine", ["ET", "FIL", "EMB", "SRTI", "TOT"]),
            ("Production", "Divers 2", ["ET", "FIL", "EMB", "SRTI", "TOT", "TOT2"]),
        ]

        # 2. Colonnes physiques réelles dans le PDF du Site 2
        self.physical_columns = [
            # Service Comm
            ("Service Comm", None, "PR_MP", 65.8),
            ("Service Comm", None, "NLE", 88.8),
            ("Service Comm", None, "COMM", 112.8),

            # Principale
            ("Production", "Principale", "ET", 132.7),
            ("Production", "Principale", "FIL", 149.8),
            ("Production", "Principale", "EMB", 167.8),
            ("Production", "Principale", "SRTI", 184.8),
            ("Production", "Principale", "TOT", 201.7),
            ("Production", "Principale", "TOT2", 219.7),

            # S/Sangacho
            ("Production", "S/Sangacho", "ET", 238.3),
            ("Production", "S/Sangacho", "FIL", 255.4),
            ("Production", "S/Sangacho", "EMB", 273.4),
            ("Production", "S/Sangacho", "SRTI", 291.4),
            ("Production", "S/Sangacho", "TOT", 308.4),
            ("Production", "S/Sangacho", "TOT2", 325.3),

            # Thon(Sarda Melva)
            ("Production", "Thon(Sarda Melva)", "ET", 346.8),
            ("Production", "Thon(Sarda Melva)", "FIL", 363.7),
            ("Production", "Thon(Sarda Melva)", "EMB", 381.7),
            ("Production", "Thon(Sarda Melva)", "SRTI", 399.7),
            ("Production", "Thon(Sarda Melva)", "TOT", 416.8),
            ("Production", "Thon(Sarda Melva)", "TOT2", 433.8),

            # Sardine
            ("Production", "Sardine", "ET", 455.8),
            ("Production", "Sardine", "FIL", 472.8),
            ("Production", "Sardine", "EMB", 490.8),
            ("Production", "Sardine", "SRTI", 508.8),
            ("Production", "Sardine", "TOT", 526.8),

            # Divers 2
            ("Production", "Divers 2", "ET", 656.8),
            ("Production", "Divers 2", "FIL", 674.8),
            ("Production", "Divers 2", "EMB", 691.8),
            ("Production", "Divers 2", "SRTI", 709.8),
            ("Production", "Divers 2", "TOT", 727.8),
            ("Production", "Divers 2", "TOT2", 745.8),
        ]

        self.max_distance = 12.0

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
    PDF_PATH = r"d:\Cumarex\Proposed project\Proposed project\Production\2026\06_Juin\03_06_2026\Mod S2.pdf"
    extractor = ModExtractor_2(PDF_PATH)
    df = extractor.extract()
    print(df.to_string(index=False))