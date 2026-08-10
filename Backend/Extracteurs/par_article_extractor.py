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

    ESPECES = [
        "Caballa Merca",
        "Caballa S/S",
        "Caballa A/S",
        "Sardine SPSA",
        "Sardine Entière",
        "Thon Rouge",
    ]

    RECETTES = [
        "OLIVE",
        "OLIVE",
        "OLIVE",
        "Tomate",
        "NATU",
    ]

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
    # Section 1 : entête / cartouche (le grand encadré rouge en haut)
    # ------------------------------------------------------------------

    def extract_entete(self, layout_text):
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

        # --- Ligne "N° Poisson ... date ... espèce ... recette ... n°" ---
        poisson_line = next(
            (l for l in layout_text.split("\n") if "N°" in l and "Poisson" in l),
            "",
        )
        m = re.search(
            r"N°\s*Poisson\s+([AB]\d{7,8})\s+(\d{1,2}/\d{1,2}/\d{4})", poisson_line
        )
        if m:
            data["numero_poisson"] = m.group(1)
            data["date_reception"] = m.group(2)
            # [correctif] La fiche affiche DEUX dates : "date_fabrication"
            # (ligne "N° S Prduit", ex. 3/06/2026) et "date_reception"
            # (ligne "N° Poisson", ex. 02/06/2026). C'est date_reception
            # qui correspond a la date affichee sur C.Global.pdf et
            # Rendement.pdf pour la meme journee -- confirme avec le
            # metier. "date_production" est un alias explicite dessus,
            # a utiliser par le pipeline plutot que date_fabrication.
            data["date_production"] = m.group(2)

        m = re.search(r"(\d+)\s*$", poisson_line.rstrip())
        if m:
            data["reference_client"] = self.clean_number(m.group(1))

        # Espaces multiples (mise en page en colonnes) neutralisés pour la
        # recherche de libellés connus sur plusieurs mots.
        normalized_text = re.sub(r"\s+", " ", layout_text)

        data["espece"] = next((e for e in self.ESPECES if e in normalized_text), None)
        data["recette"] = next((r for r in self.RECETTES if r in normalized_text), None)

        # --- Ligne "Code 125FCOAHD RR-125A A125FCO RR-125 OLIVE Hacendado" ---
        m = re.search(
            r"Code\s+(\S+)\s+(RR-\d+A?)\s+(A125[A-Z0-9]+)\s+(RR-\d+A?)\s+"
            r"(OLIVE|NATU|Tomate)\s+(\S+)",
            layout_text,
        )
        if m:
            data["code_produit"] = m.group(1)
            data["code_rr_1"] = m.group(2)
            data["code_interne"] = m.group(3)
            data["ligne"] = m.group(4)
            data["type_huile"] = m.group(5)
            data["marque"] = m.group(6)
            if not data.get("recette"):
                data["recette"] = f"{m.group(5)} {m.group(6)}"
        else:
            # Repli sur les anciennes règles individuelles si la ligne
            # complète ne matche pas (mise en page légèrement différente)
            m = re.search(r"\b(125[A-Z0-9]+)\b", layout_text)
            if m:
                data["code_produit"] = m.group(1)
            m = re.search(r"\b(A125[A-Z0-9]+)\b", layout_text)
            if m:
                data["code_interne"] = m.group(1)
            lignes = re.findall(r"RR-\d+A?", layout_text)
            if lignes:
                data["ligne"] = lignes[1] if len(lignes) > 1 else lignes[0]

        # --- Ligne "T.Boites ... caisses ... T Boites Utilisés ... Huile" ---
        m = re.search(
            r"T\.Boites\s+([\d.,]+)\s+caisses\s+(\d+)\s+T Boites Utilisés\s+"
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
            r"([\d,]+)\s+Rdts\s+([\d,]+)%([\d,]+)%\s+MOMg\s+([\d.,]+)\s+([\d,]+)",
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
    # label ~0-60 | qté reel ~60-140 | qté stnd (idem) | coût reel ~140-175
    # | coût stnd ~175-215 | dev ~215-255 | %dev ~255-320
    COST_TABLE_TOP_RANGE = (230, 500)
    COST_TABLE_X_MAX = 320  # au-delà : bloc de droite (totaux en devise), ignoré
    COST_TABLE_COLUMNS = {
        "cout_reel": (140, 175),
        "cout_stnd": (175, 215),
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
        Construit un DataFrame [poste, cout_reel, cout_stnd] à partir du
        premier tableau sous le cartouche (bloc de gauche), en se basant
        sur la position x des mots pour retrouver la bonne colonne,
        plutôt que sur le texte linéaire (peu fiable ici). La déviation
        (Reel - Stnd) n'est volontairement pas stockée : à calculer côté
        appelant si besoin.
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

            record = {"poste": label, "cout_reel": None, "cout_stnd": None}

            for w in row_words:
                if w["x0"] < 60:
                    continue
                for champ, (x_min, x_max) in self.COST_TABLE_COLUMNS.items():
                    if x_min <= w["x0"] < x_max and record[champ] is None:
                        record[champ] = w["text"]
                        break

            records.append(record)

        df = pd.DataFrame(records, columns=["poste", "cout_reel", "cout_stnd"])

        # Nettoyage numérique
        for col in ("cout_reel", "cout_stnd"):
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
        data.update(self.extract_entete(layout_text))

        # Section 2 : tableau des coûts Reel vs Stnd (Poisson, Huile,
        # Additif, Boite, ... jusqu'à %MB) -> nécessite la page pdfplumber
        # (positions x/y des mots), pas seulement le texte.
        if page is not None:
            data["table_couts"] = self.extract_table_couts(page)

        return data


# ==========================
# Exemple d'utilisation
# ==========================
pdf_path = r"d:\Cumarex_1\Backend\data_sources\par_article_1.pdf"
if __name__ == "__main__":
    with pdfplumber.open(r"d:\Cumarex_1\Backend\data_sources\par_article_1.pdf") as pdf:
        page = pdf.pages[0]
        extractor = ParArticleExtractor(pdf_path)
        article = extractor.extract(page)

        for cle, valeur in article.items():
            if cle == "table_couts":
                continue
            print(f"{cle:28} : {valeur}")

        print()
        print("Tableau des coûts (Reel vs Stnd) :")
        print(article["table_couts"].to_string(index=False))