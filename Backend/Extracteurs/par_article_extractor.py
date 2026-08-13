import re
import pdfplumber
import pandas as pd


class ParArticleExtractor:
    """
    Extracteur pour les fiches "COUTS JOURNALIERS PRODUCTIONS" (Cumarex).

    Le texte brut renvoyé par pdfplumber.extract_text() "casse" la mise en
    page en colonnes du PDF (le tableau d'en-tête devient une suite de
    lignes désordonnées). On utilise donc extract_text(layout=True), qui
    respecte les positions x/y des caractères et reconstruit des lignes
    fidèles au visuel du document. C'est ce texte "layout" qui est utilisé
    pour toutes les regex ci-dessous.
    """

    def __init__(self, pdf_path):
        self.pdf_path = pdf_path

    # ------------------------------------------------------------------
    # Utilitaires
    # ------------------------------------------------------------------

    def clean_number(self, value):
        """Convertit '1.234,56' -> 1234.56, '33,0%' -> 33.0, '848' -> 848."""

        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None

        if not isinstance(value, str):
            return value

        value = value.strip()
        if not value:
            return None

        # [généralisation] Certaines cases n'ont pas de valeur imprimée
        # (ex. "PU Huile ?" quand aucune huile n'a été achetée) : le "?"
        # remplace le nombre attendu sur la fiche. On le traite comme
        # une valeur manquante plutôt que de casser la regex appelante.
        if value == "?":
            return None

        value = value.replace("%", "")
        value = value.replace(".", "").replace(",", ".")

        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            return value

    def get_layout_text(self, page):
        """Texte avec mise en page préservée (colonnes/tableaux fiables)."""
        return page.extract_text(layout=True) or ""

    # ------------------------------------------------------------------
    # Extraction par position (x0/top) plutôt que par valeur attendue.
    #
    # [généralisation] Les champs "espèce", "recette" et "marque" ne
    # viennent PAS d'une liste fermée de valeurs possibles : ce sont des
    # données métier qui changent à chaque fiche/PDF (nouvelle espèce,
    # nouvelle recette, nouvelle marque...). Une regex ou une liste de
    # valeurs connues (ancien `ESPECES`/`RECETTES`) casse dès qu'une
    # nouvelle valeur apparaît. On extrait donc ces champs par leur
    # POSITION sur la fiche (bande de colonnes x0, comme pour le tableau
    # des coûts plus bas), ce qui reste valable quel que soit le texte
    # qu'elles contiennent, tant que la mise en page du gabarit ne change
    # pas.
    # ------------------------------------------------------------------

    def _find_row(self, words, anchor_text, anchor_x_max, companion_text=None,
                  companion_x_range=None, top_before=6, top_after=3):
        """
        Trouve la ligne (bande verticale) portant un mot-libellé
        `anchor_text` situé tout à gauche (x0 <= anchor_x_max), et
        renvoie tous les mots de cette bande, triés par x0.

        `companion_text`/`companion_x_range` permettent de désambiguïser
        un libellé qui apparaît plusieurs fois sur la page (ex. "Poisson"
        apparaît à la fois dans "N° Poisson" en tête de fiche et dans le
        tableau des coûts) : on exige alors la présence d'un second mot
        proche verticalement, dans une bande x précise.
        """
        for w in words:
            if w["text"] != anchor_text or w["x0"] > anchor_x_max:
                continue
            top = w["top"]
            if companion_text is not None:
                x_min, x_max = companion_x_range
                has_companion = any(
                    w2["text"] == companion_text
                    and abs(w2["top"] - top) <= top_after
                    and x_min <= w2["x0"] <= x_max
                    for w2 in words
                )
                if not has_companion:
                    continue
            row = [w2 for w2 in words if top - top_before <= w2["top"] <= top + top_after]
            return sorted(row, key=lambda w2: w2["x0"])
        return None

    def _words_in_band(self, row_words, x_min, x_max):
        """Sous-ensemble des mots d'une ligne dont x0 tombe dans [x_min, x_max)."""
        return [w["text"] for w in row_words if x_min <= w["x0"] < x_max]

    # ------------------------------------------------------------------
    # Section 1 : entête / cartouche (le grand encadré rouge en haut)
    # ------------------------------------------------------------------

    def extract_entete_positional(self, page):
        """
        Extraction position-based des lignes "N° Poisson" et "Code" du
        cartouche : espèce, recette, marque, code produit/interne, etc.
        ne sont jamais comparés à une valeur attendue, seulement situés
        par leur colonne (x0), donc valable même si de nouvelles
        espèces/recettes/marques apparaissent dans un futur PDF.
        """
        data = {}
        words = page.extract_words()

        # --- Ligne "N° Poisson {numero} {date} {espèce...} {champ2...} {n°} ---
        row = self._find_row(
            words, anchor_text="N°", anchor_x_max=5,
            companion_text="Poisson", companion_x_range=(10, 25),
        )
        if row:
            numero = self._words_in_band(row, 30, 100)
            date = self._words_in_band(row, 100, 195)
            # [ajustement] L'espèce occupe toujours exactement les 2
            # bandes 220 et ~246-257 (jamais au-delà de x0≈290) ; le champ
            # suivant démarre toujours à x0>=300. Frontière resserrée à
            # 296 pour ne pas absorber les codes produit longs qui
            # débordent parfois vers x0≈303 (ex. "A125FCOSSDE00010DE").
            espece = self._words_in_band(row, 195, 296)
            champ2 = self._words_in_band(row, 296, 495)
            ref = self._words_in_band(row, 495, 560)

            if numero:
                data["numero_poisson"] = numero[0]
            if date:
                data["date_reception"] = date[0]
                # [correctif] La fiche affiche DEUX dates : "date_fabrication"
                # (ligne "N° S Prduit") et "date_reception" (ligne "N°
                # Poisson"). C'est date_reception qui correspond à la date
                # affichée sur C.Global.pdf et Rendement.pdf pour la même
                # journée -- confirmé avec le métier. "date_production" est
                # un alias explicite dessus, à utiliser par le pipeline
                # plutôt que date_fabrication.
                data["date_production"] = date[0]
            if espece:
                data["espece"] = " ".join(espece)
            if champ2:
                # [à confirmer côté métier] Ce champ n'est pas toujours la
                # marque : il varie entre un nom de marque ("Hacendado",
                # "Italie") et un code produit ("A125MCTPPF"). On le garde
                # brut sous un nom neutre plutôt que de lui donner un sens
                # métier non confirmé.
                data["libelle_poisson_2"] = " ".join(champ2)
            if ref:
                data["reference_client"] = self.clean_number(ref[0])

        # --- Ligne "Code {code_produit} {RR-..} {code_interne} {RR-..} {recette} {marque}" ---
        row = self._find_row(words, anchor_text="Code", anchor_x_max=15)
        if row:
            code_produit = self._words_in_band(row, 35, 145)
            code_rr_1 = self._words_in_band(row, 145, 200)
            code_interne = self._words_in_band(row, 200, 297)
            ligne = self._words_in_band(row, 297, 345)
            recette = self._words_in_band(row, 345, 395)
            marque = self._words_in_band(row, 395, 460)

            if code_produit:
                data["code_produit"] = code_produit[0]
            if code_rr_1:
                data["code_rr_1"] = code_rr_1[0]
            if code_interne:
                data["code_interne"] = " ".join(code_interne)
            if ligne:
                data["ligne"] = ligne[0]
            if recette:
                data["recette"] = " ".join(recette)
            if marque:
                data["marque"] = " ".join(marque)

        return data

    def extract_entete(self, layout_text, page=None):
        data = {}

        # --- Ligne "N° S Prduit ... mois ... Site ... date ... n° série" ---
        m = re.search(
            r"N°\s*S\s*Prduit\s+([AB]\d{7,8})\s+mois\s+(\S+)\s+Site\s+(\S+)\s+"
            r"(\d{1,2}/\d{1,2}/\d{4})\s+(\d{4,6})",
            layout_text,
        )
        if m:
            data["ordre_fabrication"] = m.group(1)
            data["mois"] = m.group(2)
            data["site"] = m.group(3)
            data["date_fabrication"] = m.group(4)
            data["numero_serie"] = m.group(5)

        # --- Lignes "N° Poisson ..." et "Code ..." : espèce, recette,
        # marque, code produit/interne. [généralisation] Ces champs sont
        # extraits par POSITION (x0), pas par comparaison à une liste de
        # valeurs connues, car ils changent à chaque fiche/PDF (nouvelle
        # espèce, nouvelle recette, nouvelle marque...). Voir
        # extract_entete_positional() plus haut.
        if page is not None:
            data.update(self.extract_entete_positional(page))
        else:
            # Repli texte-seul (aucune page pdfplumber disponible) : mode
            # dégradé, moins fiable, utilisé seulement si extract() a reçu
            # une chaîne de texte brute au lieu d'une page.
            poisson_line = next(
                (l for l in layout_text.split("\n") if "N°" in l and "Poisson" in l),
                "",
            )
            m = re.search(
                r"N°\s*Poisson\s+([AB]\d{7,8})\s+(\d{1,2}/\d{1,2}/\d{4})\s+(.+)",
                poisson_line,
            )
            if m:
                data["numero_poisson"] = m.group(1)
                data["date_reception"] = m.group(2)
                data["date_production"] = m.group(2)
                reste = m.group(3).strip()
                ref_m = re.search(r"(\d+)\s*$", reste)
                if ref_m:
                    data["reference_client"] = self.clean_number(ref_m.group(1))
                    reste = reste[: ref_m.start()].strip()
                data["espece"] = reste or None

            m = re.search(
                r"Code\s+(\S+)\s+(RR-\d+A?)\s+(.+?)\s+(RR-\d+A?)\s+(\S+)\s+(\S+)",
                layout_text,
            )
            if m:
                data["code_produit"] = m.group(1)
                data["code_rr_1"] = m.group(2)
                data["code_interne"] = m.group(3)
                data["ligne"] = m.group(4)
                data["recette"] = m.group(5)
                data["marque"] = m.group(6)

        # --- Ligne "T.Boites ... caisses ... T Boites Utilisés ... Huile" ---
        m = re.search(
            r"T\.Boites\s+([\d.,]+)\s+caisses\s+([\d.,]+)\s+T Boites Utilisés\s+"
            # [généralisation] "caisses" (2e valeur) peut dépasser 999 et
            # s'afficher avec un séparateur de milliers (ex. "1.094") :
            # (\d+) ne matchait alors plus -> élargi à ([\d.,]+).
            r"([\d,]+)%([\d,]+)%\s*([\d.,]+)Huile\s+([\d.,]+)",
            layout_text,
        )
        if m:
            data["t_boites"] = self.clean_number(m.group(1))
            data["caisses"] = self.clean_number(m.group(2))
            data["t_boites_utilisees_dev"] = [
                self.clean_number(m.group(3) + "%"),
                self.clean_number(m.group(4) + "%"),
            ]
            data["t_boites_utilisees"] = self.clean_number(m.group(5))
            data["huile"] = self.clean_number(m.group(6))

        # --- Ligne "poisson ... Filet ... Px MP ... Fr fab ... MOD ..." ---
        m = re.search(
            r"poisson\s+([\d.,]+)\s+Filet\s+([\d.,]+)\s+Px MP\s+([\d,]+)\s+"
            r"Fr fab\s+([\d.,]+)\s+MOD\s+([\d.,]+)\s+([\d,]+)",
            layout_text,
        )
        if m:
            data["poisson"] = self.clean_number(m.group(1))
            data["filet"] = self.clean_number(m.group(2))
            data["prix_mp"] = self.clean_number(m.group(3))          # Px MP
            data["fr_fab"] = self.clean_number(m.group(4))           # Fr fab
            data["mod"] = self.clean_number(m.group(5))              # MOD
            data["mod_taux"] = self.clean_number(m.group(6))         # petite valeur à côté de MOD

        # --- Ligne "Cout min ... change ... PU Huile ... Rdts ... MOMg ..." ---
        m = re.search(
            r"Cout min\s+([\d,]+)\s+([\d,]+)change\s+([\d,]+)\s+PU Huile\s+"
            # [généralisation] "PU Huile" peut afficher "?" au lieu d'un
            # nombre (aucune huile achetée sur cette production) -> on
            # accepte les deux formes, clean_number() traduit "?" en None.
            r"([\d,]+|\?)\s+Rdts\s+([\d,]+)%([\d,]+)%\s+MOMg\s+([\d.,]+)\s+([\d,]+)",
            layout_text,
        )
        if m:
            data["cout_min"] = {
                "reel": self.clean_number(m.group(1)),
                "stnd": self.clean_number(m.group(2)),
            }
            data["change"] = self.clean_number(m.group(3))
            data["pu_huile"] = self.clean_number(m.group(4))
            data["rendement"] = {                                    # Rdts
                "reel": self.clean_number(m.group(5) + "%"),
                "stnd": self.clean_number(m.group(6) + "%"),
            }
            data["momg"] = self.clean_number(m.group(7))             # MOMg
            data["momg_taux"] = self.clean_number(m.group(8))        # petite valeur à côté de MOMg

        # --- Ligne "Ch Fixes ... Devise ..." ---
        m = re.search(r"Ch Fixes\s+([\d.,]+)\s+Devise\s+([A-Z]+)", layout_text)
        if m:
            data["ch_fixes"] = self.clean_number(m.group(1))
            data["devise"] = m.group(2)

        # --- Libellés de rendement "Rdt Filet / Rdt calculé / Rdt calculé
        #     avec 2200". Dans le cartouche, seules 2 valeurs numériques
        #     (data["rendement"]) sont présentes sous ces 3 libellés :
        #     - "Rdt Filet"             -> rendement["reel"]
        #     - "Rdt calculé"           -> rendement["stnd"]
        #     - "Rdt calculé avec 2200" -> pas de valeur imprimée sur cette
        #       fiche (case vide dans le PDF) -> None
        if "Rdt Filet" in layout_text or "Rdt calculé" in layout_text:
            rendement = data.get("rendement", {})
            data["rdt_filet"] = rendement.get("reel")
            data["rdt_calcule"] = rendement.get("stnd")
            #data["rdt_calcule_avec_2200"] = None #a verifier apres

        return data

    # ------------------------------------------------------------------
    # Section 2 : premier tableau sous le cartouche (Poisson, Huile,
    # Additif, Boite, ... jusqu'à %MB) -> coûts Reel vs Stnd (colonnes
    # 3 et 4 du tableau, juste après les 2 colonnes de quantités).
    # ------------------------------------------------------------------

    # Bandes de positions x (en points) observées pour ce gabarit de fiche.
    # Le tableau comporte DEUX paires Reel/Stnd distinctes (confirmé par les
    # en-têtes "Reel Stnd ... Dev %Dev Reel Stnd Dev", à x0 identiques sur
    # toutes les pages testées) :
    #   label ~0-60 | reel_0 ~60-98 | stnd_0 ~98-140 | cout_reel ~140-175
    #   | cout_stnd ~175-215 | dev ~215-255 | %dev ~255-320 | reel_1 ~320-370
    #   | stnd_1 ~370-415 | dev(2) ~415-450 | total (devise) ~450+
    # [généralisation] Ce sont des bandes de POSITION (comme pour l'entête),
    # pas des valeurs attendues : elles restent valables quel que soit le
    # contenu numérique, tant que la mise en page du gabarit ne change pas.
    COST_TABLE_TOP_RANGE = (230, 500)
    COST_TABLE_X_MAX = 415  # au-delà : dev(2) + bloc de droite (totaux en devise), ignorés
    COST_TABLE_COLUMNS = {
        "reel_0": (60, 98),
        "stnd_0": (98, 140),
        "cout_reel": (140, 175),
        "cout_stnd": (175, 215),
        "reel_1": (320, 370),
        "stnd_1": (370, 415),
    }

    def _group_words_into_rows(self, words, y_tolerance=8):
        """Regroupe des mots pdfplumber en lignes selon leur position verticale."""
        words = sorted(words, key=lambda w: w["top"])
        rows, current, current_top = [], [], None
        for w in words:
            if current_top is None or w["top"] - current_top <= y_tolerance:
                current.append(w)
                current_top = w["top"] if current_top is None else min(current_top, w["top"])
            else:
                rows.append(current)
                current, current_top = [w], w["top"]
        if current:
            rows.append(current)
        return rows

    def extract_table_couts(self, page):
        """
        Construit un DataFrame [poste, reel_0, stnd_0, cout_reel, cout_stnd,
        reel_1, stnd_1] à partir du tableau sous le cartouche, en se basant
        sur la position x des mots pour retrouver la bonne colonne, plutôt
        que sur le texte linéaire (peu fiable ici).

        - reel_0 / stnd_0  : 1ère paire Reel/Stnd du tableau (quantités).
        - cout_reel / cout_stnd : coûts réel/standard (déjà extraits avant).
        - reel_1 / stnd_1  : 2e paire Reel/Stnd du tableau (colonnes de
          droite, juste avant la colonne "Dev" finale et le total en devise).

        Les colonnes de déviation (Dev, %Dev) et le total en devise ne sont
        volontairement pas stockés : à calculer/extraire côté appelant si
        besoin.
        """

        top_min, top_max = self.COST_TABLE_TOP_RANGE
        words = [
            w
            for w in page.extract_words()
            if top_min <= w["top"] <= top_max and w["x0"] <= self.COST_TABLE_X_MAX
        ]

        rows_of_words = self._group_words_into_rows(words)

        records = []
        for row_words in rows_of_words:
            row_words = sorted(row_words, key=lambda w: w["x0"])

            # Le libellé = tous les mots avant la première colonne de données (x0 < 60)
            label_words = [w["text"] for w in row_words if w["x0"] < 60]
            label = " ".join(label_words).strip()
            if not label:
                continue  # ligne sans libellé -> pas une ligne de poste exploitable

            record = {"poste": label, **{champ: None for champ in self.COST_TABLE_COLUMNS}}

            for w in row_words:
                if w["x0"] < 60:
                    continue
                for champ, (x_min, x_max) in self.COST_TABLE_COLUMNS.items():
                    if x_min <= w["x0"] < x_max and record[champ] is None:
                        record[champ] = w["text"]
                        break

            records.append(record)

        colonnes = ["poste"] + list(self.COST_TABLE_COLUMNS.keys())
        df = pd.DataFrame(records, columns=colonnes)

        # Nettoyage numérique
        for col in self.COST_TABLE_COLUMNS:
            df[col] = df[col].apply(self.clean_number)

        return df

    # ------------------------------------------------------------------
    # Point d'entrée principal
    # ------------------------------------------------------------------

    def extract(self, source):
        """
        source : soit une page pdfplumber (recommandé, permet le mode
        layout=True indispensable pour l'entête), soit directement une
        chaîne de texte déjà extraite (repli, moins fiable pour la
        section 1).
        """

        if hasattr(source, "extract_text"):
            page = source
            layout_text = self.get_layout_text(page)
        else:
            # on a reçu du texte brut : impossible de refaire un vrai
            # extract_text(layout=True), on fait au mieux avec ce texte
            page = None
            layout_text = source

        data = {}

        # Section 1 : cartouche / entête (toutes les infos demandées :
        # rendement, rdt calculé avec 2200, prix MP, fr fab, MOD, MOMg,
        # coût min, etc.)
        data.update(self.extract_entete(layout_text, page=page))

        # Section 2 : tableau des coûts Reel vs Stnd (Poisson, Huile,
        # Additif, Boite, ... jusqu'à %MB) -> nécessite la page pdfplumber
        # (positions x/y des mots), pas seulement le texte.
        if page is not None:
            data["table_couts"] = self.extract_table_couts(page)

        return data

    # ------------------------------------------------------------------
    # Traitement d'un PDF complet (plusieurs fiches = plusieurs pages)
    # ------------------------------------------------------------------

    def extract_pdf(self, pdf_path=None):
        """
        Parcourt TOUTES les pages du PDF (une fiche "article" par page) et
        retourne la liste des dictionnaires extraits, un par page, dans
        l'ordre du document. Chaque dict conserve sa clé "table_couts"
        (DataFrame) et reçoit en plus une clé "page" (numéro, 1-indexé)
        pour pouvoir retracer la fiche d'origine.

        pdf_path : chemin du PDF à traiter ; si omis, utilise celui donné
        au constructeur (self.pdf_path).
        """
        path = pdf_path or self.pdf_path
        articles = []

        with pdfplumber.open(path) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                data = self.extract(page)
                data["page"] = i
                articles.append(data)

        return articles

    def articles_to_dataframe(self, articles):
        """
        Convertit la liste de dicts renvoyée par extract_pdf() en un seul
        DataFrame "résumé" (une ligne par fiche/page), en excluant le
        détail table_couts (qui reste consultable séparément par fiche).
        Les clés composites (ex. cout_min, rendement) sont aplaties en
        colonnes suffixées _reel / _stnd.
        """
        rows = []
        for article in articles:
            row = {}
            for cle, valeur in article.items():
                if cle == "table_couts":
                    continue
                if isinstance(valeur, dict):
                    for sous_cle, sous_valeur in valeur.items():
                        row[f"{cle}_{sous_cle}"] = sous_valeur
                elif isinstance(valeur, list):
                    for idx, sous_valeur in enumerate(valeur):
                        row[f"{cle}_{idx}"] = sous_valeur
                else:
                    row[cle] = valeur
            rows.append(row)
        return pd.DataFrame(rows)

    def table_couts_combined(self, articles):
        """
        Empile les table_couts de toutes les fiches en un seul DataFrame,
        avec une colonne d'identification de la fiche d'origine (page +
        ordre_fabrication) pour pouvoir filtrer/pivoter ensuite.
        """
        frames = []
        for article in articles:
            df = article["table_couts"].copy()
            df.insert(0, "page", article.get("page"))
            df.insert(1, "ordre_fabrication", article.get("ordre_fabrication"))
            frames.append(df)
        if not frames:
            return pd.DataFrame(
                columns=["page", "ordre_fabrication", "poste"] + list(self.COST_TABLE_COLUMNS.keys())
            )
        return pd.concat(frames, ignore_index=True)


