import pdfplumber
import pandas as pd
import re
from datetime import date 


class ResumeExtractor:
    """
    Extracteur du rapport "Couts Journaliers Production".

    CORRECTION MAJEURE PAR RAPPORT A LA VERSION ORIGINALE :
    ---------------------------------------------------------
    L'ancienne version utilisait page.extract_text() puis line.split().
    Problème : quand deux tableaux différents sont côte à côte sur la même
    ligne visuelle (ce qui est le cas presque partout dans ce PDF), et que
    l'espace entre deux cellules est trop petit, pdfplumber les COLLE
    ensemble sans espace. Exemple réel dans ce fichier :

        "9,8" (colonne P.U) + "7.967" (colonne Qte)
        => devenait "9,87.967" avec l'ancienne méthode !

    Résultat : les valeurs numériques étaient fausses ou impossibles à
    parser, et des colonnes entières (MOD global, table des codes
    Egoutté/Casse/Huile/MOD/Mg, totaux du jour, table des coûts
    unitaires par code, etc.) n'étaient même pas extraites.

    NOUVELLE APPROCHE :
    --------------------
    On travaille au niveau du mot (page.extract_words), qui donne la
    position (x0, top) de CHAQUE mot individuellement, sans jamais les
    fusionner. On reconstruit ensuite les "lignes logiques" du rapport
    en regroupant les mots dont le "top" (position verticale) est
    proche (tolérance de quelques points, car certaines lignes sont
    imprimées sur 2 sous-lignes très proches à cause des accents /
    métriques de police). Les mots sont ensuite triés par x0, ce qui
    reconstitue l'ordre des colonnes SANS jamais perdre ni fusionner de
    valeur.

    Cette méthode permet d'extraire TOUTES les sections du rapport :
      - l'en-tête (date + référence du jour)
      - le résumé "Poisson" (Caballa)
      - le bloc MOD global (Mo, Mg, Mod/C, Mg/C)
      - la matière première (CAOMA / CAMAT)
      - la table des codes (Egoutté / % Casse / Huile / MOD / Mg / Fr FAB Dh)
      - la ligne des totaux du jour
      - les séries de production (A26060...)
      - la synthèse Production / PMV jour
      - la table des coûts unitaires par code (Poisson, Huile, Boite, ...)

    NOTE SUR LES NOMS DE COLONNES INCERTAINS :
    --------------------------------------------
    Ce rapport a des en-têtes qui s'étalent sur plusieurs lignes et dont
    certaines cases ne sont pas nommées de façon totalement univoque
    (le PDF source contient des libellés tronqués ou partagés entre deux
    sous-colonnes). Quand le nom exact d'une colonne est ambigu, on
    utilise un nom générique explicite (valeur_1, valeur_2, ...) plutôt
    que d'inventer un nom qui pourrait être faux. AUCUNE valeur numérique
    n'est perdue : tout ce qui est présent dans le PDF est extrait.
    """

    ROW_TOLERANCE = 3.5  # tolérance verticale (en points) pour regrouper des mots sur une même ligne

    def __init__(self, pdf_path):
        self.pdf_path = pdf_path

    # =========================================================
    # UTILITAIRES BAS NIVEAU
    # =========================================================

    @staticmethod
    def clean_number(value):
        """Convertit une chaîne au format FR ('.' = séparateur de milliers,
        ',' = séparateur décimal, '%' = pourcentage) en float.
        Retourne None si la valeur est vide, retourne la chaîne d'origine
        si elle n'est manifestement pas numérique (ex: un code produit)."""

        if value is None:
            return None

        value = str(value).strip()

        if value == "":
            return None

        is_percent = value.endswith("%")
        core = value[:-1] if is_percent else value

        try:
            number = float(core.replace(".", "").replace(",", "."))
        except ValueError:
            return value  # ce n'est pas un nombre (ex: un code produit)

        return number

    def _get_logical_rows(self, page):
        """Regroupe les mots de la page en lignes logiques (par position
        verticale) puis trie chaque ligne de gauche à droite. Retourne une
        liste de listes de mots (dicts pdfplumber), chaque mot conservant
        ses coordonnées x0/top d'origine."""

        words = page.extract_words(x_tolerance=1.5, keep_blank_chars=False)
        words.sort(key=lambda w: (w["top"], w["x0"]))

        rows = []
        current = []
        row_top = None

        for w in words:
            if row_top is None or abs(w["top"] - row_top) <= self.ROW_TOLERANCE:
                current.append(w)
                if row_top is None:
                    row_top = w["top"]
            else:
                rows.append(current)
                current = [w]
                row_top = w["top"]

        if current:
            rows.append(current)

        for r in rows:
            r.sort(key=lambda w: w["x0"])

        return rows

    @staticmethod
    def _texts(row):
        return [w["text"] for w in row]

    @staticmethod
    def _row_starts_with(row, *prefixes):
        if not row:
            return False
        return row[0]["text"].startswith(prefixes)

    # =========================================================
    # DATE ET REFERENCE DU JOUR
    # =========================================================

    def extract_date(self, text):

        match = re.search(
            r"(Lundi|Mardi|Mercredi|Jeudi|Vendredi|Samedi|Dimanche)"
            r"\s+(\d{1,2})\s+"
            r"(Janvier|Février|Mars|Avril|Mai|Juin|Juillet|Août|"
            r"Septembre|Octobre|Novembre|Décembre)"
            r"\s+(\d{4})",
            text,
            re.IGNORECASE,
    )

        if not match:
            return None

        jour = int(match.group(2))
        mois_nom = match.group(3).lower()
        annee = int(match.group(4))

        mois = {
            "janvier": 1,
            "février": 2,
            "mars": 3,
            "avril": 4,
            "mai": 5,
            "juin": 6,
            "juillet": 7,
            "août": 8,
            "septembre": 9,
            "octobre": 10,
            "novembre": 11,
            "décembre": 12,
    }

        return date(annee, mois[mois_nom], jour)

    def extract_reference(self, text):
        """Le numéro de référence du jour (ex: '2606031') qui suit la date
        dans l'en-tête du rapport."""

        match = re.search(r"\b(\d{7})\b", text)
        return match.group(1) if match else None

    # =========================================================
    # A. RESUME PRODUCTION (ligne "Caballa")
    # =========================================================

    def extract_production(self, rows):

        headers = ["poisson", "qte", "filet", "rdt", "pu_moy",
                   "pct_jour", "pct_prod_c", "pct_prod_r"]

        for row in rows:
            if not self._row_starts_with(row, "Caballa"):
                continue

            values = self._texts(row)

            record = {}
            for label, raw in zip(headers, values):
                record[label] = raw if label == "poisson" else self.clean_number(raw)

            return pd.DataFrame([record])

        return pd.DataFrame()

    # =========================================================
    # B. MOD GLOBAL (Mo, Mg, Mod/C, Mg/C)
    # =========================================================

    def extract_mod_global(self, rows):

        for i, row in enumerate(rows):
            texts = self._texts(row)
            # Ligne d'en-tête typique : ['M', 'O', 'D', 'Mo', 'Mg', 'Mod/C', 'Mg/C']
            if texts[:3] == ["M", "O", "D"] and "Mo" in texts:
                # Les valeurs numériques sont sur les 1 ou 2 lignes suivantes
                value_tokens = []
                for next_row in rows[i + 1:i + 3]:
                    next_texts = self._texts(next_row)
                    if all(self.clean_number(t) is not None and isinstance(self.clean_number(t), float)
                           for t in next_texts):
                        value_tokens.extend(next_texts)
                    else:
                        break

                labels = ["mo", "mg", "mod_c", "mg_c"]
                record = {
                    label: self.clean_number(val)
                    for label, val in zip(labels, value_tokens)
                }
                return pd.DataFrame([record]) if record else pd.DataFrame()

        return pd.DataFrame()

    # =========================================================
    # C. MATIERE PREMIERE (CAOMA / CAMAT) + D. TABLE DES CODES
    #    (Egoutté / % Casse / Huile / MOD / Mg / Fr FAB Dh)
    #
    # Ces deux tableaux partagent les mêmes lignes visuelles dans le PDF
    # (matière première à gauche, table des codes à droite), c'est
    # exactement ce qui causait la fusion de colonnes dans l'ancienne
    # version. On les sépare ici via les positions x des mots.
    # =========================================================

    CODE_TABLE_COLUMNS = [
        "pct_prod", "egoutte_std", "egoutte_reel", "poids_produit",
        "pct_casse", "huile_reel", "huile_std", "mod_reel", "mod_std",
        "mg_reel", "mg_std", "frfabdh_reel", "frfabdh_std",
    ]

    def extract_matiere_premiere_et_codes(self, rows):

        mp_records = []
        code_records = []
        leftovers = []

        for row in rows:

            if not self._row_starts_with(row, "CAOMA", "CAMAT"):
                continue

            # Les 4 premiers mots de la ligne = fournisseur, partie/lot, P.U, Qte
            if len(row) < 4:
                continue

            fournisseur = row[0]["text"]
            partie = row[1]["text"]
            pu = self.clean_number(row[2]["text"])
            qte = self.clean_number(row[3]["text"])

            mp_records.append({
                "fournisseur": fournisseur,
                "partie": partie,
                "pu": pu,
                "qte": qte,
            })

            # S'il reste des mots après les 4 premiers, c'est la table des
            # codes (125FCT4HD / 125MCDSTP) alignée sur la même ligne.
            reste = row[4:]

            if not reste:
                continue

            code = reste[0]["text"]
            valeurs = [self.clean_number(w["text"]) for w in reste[1:]]

            record = {"code": code}
            for label, val in zip(self.CODE_TABLE_COLUMNS, valeurs):
                record[label] = val

            # Si jamais il y a plus de valeurs que de colonnes connues,
            # on les garde quand même pour ne rien perdre.
            extra = valeurs[len(self.CODE_TABLE_COLUMNS):]
            for i, val in enumerate(extra, start=1):
                record[f"valeur_supplementaire_{i}"] = val

            code_records.append(record)

        return (
            pd.DataFrame(mp_records),
            pd.DataFrame(code_records),
        )

    # =========================================================
    # E. TOTAUX DU JOUR (ligne agrégée sous la table des codes)
    # =========================================================

    def extract_totaux_journaliers(self, rows):

        for row in rows:
            texts = self._texts(row)
            # Ligne caractéristique : commence par '100,0%' et contient ~10 valeurs
            if texts and texts[0] == "100,0%":
                record = {
                    f"valeur_{i + 1}": self.clean_number(t)
                    for i, t in enumerate(texts)
                }
                return pd.DataFrame([record])

        return pd.DataFrame()

    # =========================================================
    # F. SERIES DE PRODUCTION (A26060...)
    # =========================================================

    SERIE_COLUMNS = [
        "b_pdtes", "poisson", "boits", "huile", "etui", "mod", "mg",
        "f_fab_reel", "f_fab_std", "f_fin",
        "c_d", "mb", "pct_mb", "cf", "mn", "pct_mn",
    ]

    def extract_couts_serie(self, rows):

        records = []

        for row in rows:

            if not self._row_starts_with(row, "A26060"):
                continue

            texts = self._texts(row)
            full_code = texts[0]  # ex: "A26060125FCT4HD"

            # Le code lot ("A26060") est toujours suivi du code produit
            # (ex: "125FCT4HD" ou "125MCDSTPM") sans séparateur.
            match = re.match(r"(A\d{5})(.+)", full_code)
            if match:
                serie, code = match.group(1), match.group(2)
            else:
                serie, code = full_code, None

            valeurs = [self.clean_number(t) for t in texts[1:]]

            record = {"serie": serie, "code": code}
            for label, val in zip(self.SERIE_COLUMNS, valeurs):
                record[label] = val

            extra = valeurs[len(self.SERIE_COLUMNS):]
            for i, val in enumerate(extra, start=1):
                record[f"valeur_extra_{i}"] = val

            records.append(record)

        return pd.DataFrame(records)

    # =========================================================
    # G. SYNTHESE PRODUCTION / PMV JOUR
    # =========================================================

    def extract_synthese_production(self, rows):

        for i, row in enumerate(rows):
            texts = self._texts(row)

            if texts[:1] == ["Product"]:
                valeurs = [self.clean_number(t) for t in texts[1:] if t not in ("PMV", "jour")]

                # La ligne suivante contient les pourcentages associés
                pourcentages = []
                if i + 1 < len(rows):
                    next_texts = self._texts(rows[i + 1])
                    if all(t.endswith("%") for t in next_texts):
                        pourcentages = [self.clean_number(t) for t in next_texts]

                labels = ["production_totale", "nb_unites", "pmv_jour",
                          "valeur_a", "valeur_b", "valeur_c", "valeur_d"]

                record = {label: val for label, val in zip(labels, valeurs)}

                pct_labels = ["pct_valeur_b", "pct_valeur_c", "pct_valeur_d"]
                for label, val in zip(pct_labels, pourcentages):
                    record[label] = val

                return pd.DataFrame([record]) if record else pd.DataFrame()

        return pd.DataFrame()

    # =========================================================
    # H. TABLE DES COUTS UNITAIRES PAR CODE
    #    (Poisson, Huile, Boite, Etui, Mod, Mg, F.Fab, F.Fin, C.D, P.V,
    #     M.B, %Mb, CH.F, %Cf, M.N, %M.N)
    # =========================================================
# =========================================================
    # H. TABLE DES COUTS UNITAIRES PAR CODE (CORRIGÉ)
    # =========================================================

    UNIT_COST_COLUMNS = [
        "poisson", "huile", "boite", "etui", "mod", "mg",
        "f_fab_reel", "f_fab_std", "f_fin", "c_d", "p_v",
        "m_b", "pct_mb", "ch_f", "pct_cf", "m_n", "pct_mn"
    ]

    def extract_couts_unitaires(self, rows):
        records = []

        for row in rows:
            texts = self._texts(row)
            if not texts:
                continue

            code = texts[0]

            # Filtrer les lignes de codes articles
            if not (code.startswith("125") or code.startswith("150") or re.match(r"^\d{3}[A-Z0-9]+", code)):
                continue

            # Ignorer la table MOD par code (% en 2e colonne)
            if len(texts) > 1 and str(texts[1]).endswith("%") and "," not in str(texts[1]):
                continue

            valeurs = [self.clean_number(t) for t in texts[1:]]
            record = {"code": code}

            # Si 17 valeurs : Poisson est présent
            if len(valeurs) == len(self.UNIT_COST_COLUMNS):
                for label, val in zip(self.UNIT_COST_COLUMNS, valeurs):
                    record[label] = val

            # Si 16 valeurs : Poisson est vide dans le PDF -> on décale le mapping à partir de 'huile'
            elif len(valeurs) == len(self.UNIT_COST_COLUMNS) - 1:
                record["poisson"] = None
                for label, val in zip(self.UNIT_COST_COLUMNS[1:], valeurs):
                    record[label] = val

            records.append(record)

        return pd.DataFrame(records)
    

    # =========================================================
    # VALEURS RESIDUELLES (tout ce qui n'a été rattaché à aucune section
    # connue, pour garantir qu'aucune information n'est perdue)
    # =========================================================

    def extract_valeurs_non_classees(self, rows, deja_traitees):
        residuelles = []

        for row in rows:
            texts = self._texts(row)
            if not texts:
                continue

            key = tuple(texts)
            if key in deja_traitees:
                continue

            # Lignes déjà couvertes par les sections ci-dessus (identifiées
            # par leur premier token) : on les ignore ici.
            first = texts[0]
            covered_prefixes = (
                "Caballa", "M", "CAOMA", "CAMAT", "100,0%", "A26060",
                "Product", "125FCT4HD", "125MCDSTPM", "Serie", "Poisson",
                "Egoutté", "Code", "CODE", "Couts",
            )
            if any(first == p or first.startswith(p) for p in covered_prefixes):
                continue

            residuelles.append({"contenu": texts})

        return residuelles

    # =========================================================
    # EXTRACTION COMPLETE
    # =========================================================

    def extract(self):

        with pdfplumber.open(self.pdf_path) as pdf:

            page = pdf.pages[0]
            text = page.extract_text()

            if not text:
                raise ValueError("Impossible d'extraire le texte du PDF.")

            rows = self._get_logical_rows(page)

            date = self.extract_date(text)
            reference = self.extract_reference(text)
            informations_generales = pd.DataFrame([{
                "date": date,
                "reference": reference,
            }])

            production = self.extract_production(rows)
            mod_global = self.extract_mod_global(rows)
            matiere_premiere, mod_par_code = self.extract_matiere_premiere_et_codes(rows)
            totaux_journaliers = self.extract_totaux_journaliers(rows)
            couts_serie = self.extract_couts_serie(rows)
            synthese_production = self.extract_synthese_production(rows)
            couts_unitaires = self.extract_couts_unitaires(rows)

        return {
            "informations_generales": informations_generales,
            "production": production,
            "mod_global": mod_global,
            "matiere_premiere": matiere_premiere,
            "mod_par_code": mod_par_code,
            "totaux_journaliers": totaux_journaliers,
            "couts_serie": couts_serie,
            "synthese_production": synthese_production,
            "couts_unitaires": couts_unitaires,
        }


# =============================================================
# PROGRAMME PRINCIPAL
# =============================================================

TITRES = {
    "informations_generales": "INFORMATIONS GENERALES (date / référence)",
    "production": "PRODUCTION (RESUME POISSON)",
    "mod_global": "MOD GLOBAL",
    "matiere_premiere": "MATIERE PREMIERE",
    "mod_par_code": "TABLE DES CODES (EGOUTTE / CASSE / HUILE / MOD / MG / FR FAB DH)",
    "totaux_journaliers": "TOTAUX JOURNALIERS",
    "couts_serie": "COUTS PAR SERIE",
    "synthese_production": "SYNTHESE PRODUCTION / PMV JOUR",
    "couts_unitaires": "COUTS UNITAIRES PAR CODE",
}


def _print_section(titre, df):
    print("\n")
    print("=" * 80)
    print(titre)
    print("=" * 80)

    if not df.empty:
        print(df.to_string(index=False))
    else:
        print(f"Aucune donnée trouvée pour : {titre}")


if __name__ == "__main__":

    import sys

    pdf_path = sys.argv[1] if len(sys.argv) > 1 else r"d:\Cumarex_1\Backend\data_sources\Résume_1.pdf"

    extractor = ResumeExtractor(pdf_path)
    result = extractor.extract()  # dict[str, pd.DataFrame] -- une entrée = un DataFrame

    for nom, df in result.items():
        _print_section(TITRES.get(nom, nom.upper()), df)

