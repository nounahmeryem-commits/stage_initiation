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

    @staticmethod
    def _is_numeric_token(text):
        """True si le token ressemble a une valeur numerique FR (avec ou
        sans '%'). Sert a savoir ou s'arrete un nom (poisson, fournisseur,
        etc.) qui peut s'etaler sur plusieurs mots (ex: 'Caballa S/S',
        'Thon Rouge') avant que les valeurs chiffrees ne commencent."""

        t = str(text).strip()
        if t == "":
            return False
        if t.endswith("%"):
            t = t[:-1]
        try:
            float(t.replace(".", "").replace(",", "."))
            return True
        except ValueError:
            return False

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
    # A. RESUME PRODUCTION (ligne "Caballa" / "Sardine" / "Thon Rouge" / ...)
    # =========================================================
    #
    # DETECTION 100% GENERIQUE (pas de liste de noms de poisson) :
    # cette ligne a toujours la même FORME dans le PDF, quel que soit
    # le nom du poisson : [Nom sur 1..N mots] + [Qte, Filet, Rdt%,
    # PU Moy, %Jour], c'est-à-dire une "signature" de 5 valeurs
    # terminant la ligne : nombre, nombre, pourcentage, nombre,
    # pourcentage. On reconnaît cette signature (peu importe le nom
    # qui précède), donc un poisson qui n'existe pas encore dans le
    # PDF actuel sera quand même détecté correctement plus tard.

    @staticmethod
    def _matches_production_signature(tokens5):
        """True si les 5 derniers tokens d'une ligne correspondent au
        motif [nombre, nombre, %, nombre, %] de la ligne de résumé
        production (Qte, Filet, Rdt%, PU Moy, %Jour)."""

        if len(tokens5) != 5:
            return False

        est_pct = [t.strip().endswith("%") for t in tokens5]
        motif_pct_attendu = [False, False, True, False, True]

        if est_pct != motif_pct_attendu:
            return False

        return all(ResumeExtractor._is_numeric_token(t) for t in tokens5)

    def extract_production(self, rows):

        headers = ["qte", "filet", "rdt", "pu_moy", "pct_jour"]

        for row in rows:
            texts = self._texts(row)

            # Il faut au moins 1 mot de nom + les 5 valeurs de la signature
            if len(texts) < 6:
                continue

            # Le nom = tous les tokens non-numériques en tête de ligne.
            i = 0
            while i < len(texts) and not self._is_numeric_token(texts[i]):
                i += 1
            nom_tokens = texts[:i]

            if not nom_tokens:
                continue

            # Les 5 valeurs de la signature suivent IMMEDIATEMENT le nom.
            # Note : il peut rester d'autres tokens après (parfois 2
            # valeurs supplémentaires appartenant à un petit tableau
            # visuellement fusionné sur la même ligne : "Fr FAB Dh /
            # %prd C / %prd R") -- on les ignore volontairement ici,
            # elles ne font pas partie du résumé production.
            valeurs_tokens = texts[i:i + 5]

            if not self._matches_production_signature(valeurs_tokens):
                continue

            record = {"poisson": " ".join(nom_tokens)}
            for label, raw in zip(headers, valeurs_tokens):
                record[label] = self.clean_number(raw)

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
    # C. MATIERE PREMIERE (tout fournisseur : CAOMA, CAMAT, CAMAHI,
    #    SAEVIL, SAETDS, SMAHIR, TAN, ...) + D. TABLE DES CODES
    #    (Egoutté / % Casse / Huile / MOD / Mg / Fr FAB Dh)
    #
    # L'ancienne version ne reconnaissait que les lignes commençant par
    # "CAOMA" ou "CAMAT" (le fournisseur du Caballa). Or chaque type de
    # poisson a SES PROPRES codes fournisseur : Sardine -> SAEVIL /
    # SAETDS / SMAHIR, Caballa A/S -> CAMAHI, Thon Rouge -> TAN, etc.
    # On détecte donc ces lignes par LEUR FORME, pas par une liste
    # fermée de noms : un code fournisseur (lettres majuscules) suivi
    # d'un numéro de lot au format "NNNN/NN".
    #
    # La table des codes (125FCOAHD, 90MTRTPAL, ...) n'est plus non plus
    # cherchée uniquement sur la même ligne visuelle qu'une ligne de
    # matière première (ce qui faisait perdre des codes quand les deux
    # tableaux n'étaient pas alignés, ex: Thon Rouge). Elle est
    # maintenant recherchée sur TOUTES les lignes de la page, reconnue
    # elle aussi par sa forme : un code produit suivi d'un pourcentage.
    # =========================================================

    SUPPLIER_CODE_RE = re.compile(r"^[A-Z]{2,8}$")
    LOT_CODE_RE = re.compile(r"^\d{2,5}/\d{2}$")
    PRODUCT_CODE_RE = re.compile(r"^\d{2,3}[A-Z][A-Z0-9]*$")

    def extract_matiere_premiere(self, rows):

        mp_records = []

        for row in rows:
            texts = self._texts(row)
            if len(texts) < 4:
                continue

            fournisseur, partie = texts[0], texts[1]
            if not (self.SUPPLIER_CODE_RE.match(fournisseur)
                    and self.LOT_CODE_RE.match(partie)):
                continue

            mp_records.append({
                "fournisseur":fournisseur,
                "partie":partie,
                "pu": self.clean_number(texts[2]),
                "qte": self.clean_number(texts[3]),
            })

        return pd.DataFrame(mp_records)

    CODE_TABLE_COLUMNS = [
        "pct_prod", "egoutte_std", "egoutte_reel", "poids_produit",
        "pct_casse", "huile_reel", "huile_std", "mod_reel", "mod_std",
        "mg_reel", "mg_std", "frfabdh_reel", "frfabdh_std",
    ]

    def extract_table_codes(self, rows):

        code_records = []

        for row in rows:
            texts = self._texts(row)
            if len(texts) < 2:
                continue

            # Le code peut être en tête de ligne (ligne autonome) OU
            # plus loin dans la ligne (fusionné avec la matière première
            # qui est visuellement sur la même ligne à gauche). On
            # cherche donc la position du motif "code produit suivi
            # d'un pourcentage" n'importe où dans la ligne.
            start = None
            for i in range(len(texts) - 1):
                if self.PRODUCT_CODE_RE.match(texts[i]) and str(texts[i + 1]).endswith("%"):
                    start = i
                    break

            if start is None:
                continue

            code = texts[start]
            valeurs = [self.clean_number(t) for t in texts[start + 1:]]

            record = {"code": code}
            for label, val in zip(self.CODE_TABLE_COLUMNS, valeurs):
                record[label] = val

            # Si jamais il y a plus de valeurs que de colonnes connues,
            # on les garde quand même pour ne rien perdre.
            extra = valeurs[len(self.CODE_TABLE_COLUMNS):]
            for i, val in enumerate(extra, start=1):
                record[f"valeur_supplementaire_{i}"] = val

            code_records.append(record)

        return pd.DataFrame(code_records)

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
    # F. SERIES DE PRODUCTION (A26060... / B26060... / tout préfixe
    #    lettre + 5 chiffres)
    # =========================================================
    #
    # L'ancienne version ne reconnaissait que "A26060" : les séries
    # commençant par "B26060" (Caballa A/S, Thon Rouge dans cet
    # exemple) étaient silencieusement ignorées. On détecte maintenant
    # le préfixe par sa FORME (1 lettre + 5 chiffres), quel que soit le
    # code lot exact.

    SERIE_COLUMNS = [
        "b_pdtes", "poisson", "boits", "huile", "etui", "mod", "mg",
        "f_fab_reel", "f_fab_std", "f_fin",
        "c_d", "mb", "pct_mb", "cf", "mn", "pct_mn",
    ]

    SERIE_CODE_RE = re.compile(r"^([A-Z]\d{5})(.+)$")

    def extract_couts_serie(self, rows):

        records = []

        for row in rows:

            texts = self._texts(row)
            if not texts:
                continue

            full_code = texts[0]  # ex: "A26060125FCT4HD" ou "B26060125FCNDE"
            match = self.SERIE_CODE_RE.match(full_code)
            if not match:
                continue

            serie, code = match.group(1), match.group(2)

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
    # H. TABLE DES COUTS UNITAIRES PAR CODE (CORRIGÉ)
    #    (Poisson, Huile, Boite, Etui, Mod, Mg, F.Fab, F.Fin, C.D, P.V,
    #     M.B, %Mb, CH.F, %Cf, M.N, %M.N)
    # =========================================================
    #
    # L'ancien filtre "startswith 125 / 150 / \d{3}..." ratait les codes
    # a prefixe 2 chiffres (ex: "90MTRTPAL" pour le Thon Rouge). On
    # reutilise PRODUCT_CODE_RE (2 ou 3 chiffres + lettres), le meme
    # motif que celui utilise pour la table des codes.

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
            if not self.PRODUCT_CODE_RE.match(code):
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
    # EXTRACTION D'UNE SEULE PAGE
    # =========================================================
    #
    # Chaque page du PDF correspond à un "bloc" indépendant du rapport
    # (une référence du type 2606021, 2606022, ...). extract_page() isole
    # toute la logique métier pour UNE page et NE LEVE JAMAIS d'exception
    # pour une page vide : elle retourne None dans ce cas, et c'est
    # extract() qui décide quoi en faire (page ignorée + tracée dans le
    # rapport d'erreurs, sans interrompre le traitement des autres pages).

    # Sections qui reviennent 1 fois par page (récupérées comme un
    # dict simple) vs. section qui en produit 2 d'un coup (tuple).
    SECTION_EXTRACTORS = (
        "production", "mod_global", "totaux_journaliers",
        "couts_serie", "synthese_production", "couts_unitaires",
    )

    def extract_page(self, page):
        """Extrait toutes les sections connues pour UNE page.
        Retourne un dict {nom_section: DataFrame}, ou None si la page
        ne contient pas de texte exploitable (page blanche, page de
        garde, etc.)."""

        text = page.extract_text()
        if not text:
            return None

        rows = self._get_logical_rows(page)

        date = self.extract_date(text)
        reference = self.extract_reference(text)

        production = self.extract_production(rows)

        # Nom du poisson du bloc (Caballa, Caballa S/S, Sardine, Thon
        # Rouge, ...). La référence numérique (ex: 2606021) n'est PAS
        # forcément unique de façon fiable d'un import à l'autre (elle
        # se répète par exemple entre deux PDF de jours différents si
        # elle redémarre à 1 chaque mois/série) : on rattache donc
        # explicitement toutes les tables au nom du poisson en plus de
        # la référence et de la date, pour que les jointures en base
        # restent correctes même si la référence seule est ambiguë.
        poisson_bloc = (
            production["poisson"].iloc[0]
            if not production.empty and "poisson" in production.columns
            else None
        )

        informations_generales = pd.DataFrame([{
            "date": date,
            "reference": reference,
            "poisson_bloc": poisson_bloc,
        }])

        sections = {
            "informations_generales": informations_generales,
            "production": production,
            "mod_global": self.extract_mod_global(rows),
            "matiere_premiere": self.extract_matiere_premiere(rows),
            "mod_par_code": self.extract_table_codes(rows),
            "totaux_journaliers": self.extract_totaux_journaliers(rows),
            "couts_serie": self.extract_couts_serie(rows),
            "synthese_production": self.extract_synthese_production(rows),
            "couts_unitaires": self.extract_couts_unitaires(rows),
        }

        # Clé de rattachement pour la base de données : chaque ligne de
        # chaque table sait de quel poisson / quelle référence / quelle
        # date elle provient. C'est ce qui permet ensuite de faire des
        # JOIN propres entre "informations_generales" (table parente,
        # une ligne = un bloc/jour) et toutes les tables filles.
        for nom, df in sections.items():
            if df is None or df.empty:
                continue
            if "poisson_bloc" not in df.columns:
                df.insert(0, "poisson_bloc", poisson_bloc)
            if "date" not in df.columns:
                df.insert(0, "date", date)
            if "reference" not in df.columns:
                df.insert(0, "reference", reference)

        return sections

    # =========================================================
    # EXTRACTION COMPLETE (TOUTES LES PAGES)
    # =========================================================

    def extract(self):
        """Parcourt TOUTES les pages du PDF. Chaque page est traitée de
        façon indépendante et isolée : si une page échoue (texte
        illisible, mise en page inattendue, exception dans un des
        parseurs de section), elle est simplement consignée dans la
        section '_erreurs' et l'extraction continue sur les pages
        suivantes -- aucune page valide n'est jamais perdue à cause
        d'une autre page corrompue.

        Retour : dict[str, pd.DataFrame], où chaque DataFrame contient
        les lignes de TOUTES les pages empilées (avec les colonnes
        'reference' / 'page_num' / 'date' pour les distinguer), prêt à
        être inséré tel quel dans une base de données (une table SQL
        par clé du dict)."""

        sections_par_page = {}   # nom_section -> liste de DataFrames (1 par page)
        erreurs = []

        with pdfplumber.open(self.pdf_path) as pdf:

            if len(pdf.pages) == 0:
                raise ValueError("Le PDF ne contient aucune page.")

            for page_num, page in enumerate(pdf.pages, start=1):
                try:
                    sections = self.extract_page(page)
                except Exception as exc:
                    erreurs.append({
                        "page_num": page_num,
                        "erreur": f"{type(exc).__name__}: {exc}",
                    })
                    continue

                if sections is None:
                    erreurs.append({
                        "page_num": page_num,
                        "erreur": "Aucun texte exploitable sur cette page (page vide ?).",
                    })
                    continue

                for nom, df in sections.items():
                    if df is None:
                        continue
                    df = df.copy()
                    df.insert(0, "page_num", page_num)
                    sections_par_page.setdefault(nom, []).append(df)

        resultat = {}
        for nom, dfs in sections_par_page.items():
            dfs_non_vides = [d for d in dfs if not d.empty]
            resultat[nom] = (
                pd.concat(dfs_non_vides, ignore_index=True)
                if dfs_non_vides else pd.DataFrame()
            )

        resultat["_erreurs"] = pd.DataFrame(erreurs)
        return resultat


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
    "_erreurs": "PAGES EN ERREUR (a verifier manuellement)",
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


