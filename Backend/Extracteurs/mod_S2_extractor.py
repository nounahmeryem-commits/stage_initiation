import pdfplumber
import pandas as pd
import re


class ModExtractor_2:
    """
    Extracteur GENERIQUE du rapport MOD - Min / Kg - Site 2.

    Comme l'extracteur Site 1, RIEN n'est code en dur (ni les groupes, ni les
    positions X) : tout est reconstruit a partir de CHAQUE PDF. Seules les
    donnees changent d'une date a l'autre ; la forme du PDF (groupes,
    sous-colonnes ET/FIL/EMB/SRTI/TOT, ordre) est stable et sert de reference.

    Particularites du gabarit Site 2, gerees automatiquement :
      - Les libelles de groupe (ex: "S/Sangacho" et "Thon(Sarda Melva)") sont
        parfois tres proches en X -> le rattachement de chaque mot de titre a
        son groupe se fait par proximite avec le repere "ET" du groupe (pas
        par simple fusion de mots adjacents, qui peut coller deux groupes
        voisins).
      - Certains groupes ont plus de colonnes que ce qu'annonce l'en-tete
        (ex: un 2eme "Tot" -> TOT2, TOT3, ...) : detecte via les positions
        reelles des donnees, comme sur le Site 1.
      - Un groupe peut avoir un libelle d'en-tete corrompu/absent pour une
        sous-colonne (ex: "Fil" invisible pour "Sardine", les caracteres se
        chevauchant avec "Emb" -> "ETEmb"): comme l'ordre des sous-colonnes
        (ET, Fil, Emb, Srti, Tot puis Tot2, Tot3, ...) fait partie de la forme
        stable du rapport, il est reapplique par POSITION (pas par texte) a
        chaque groupe de production une fois que les vraies colonnes de
        donnees ont ete localisees. Ca evite qu'un libelle corrompu ne
        decale/pollue les colonnes suivantes du groupe.
      - Les colonnes de synthese tout a droite ("Global") sont exclues meme
        si leurs valeurs debordent legerement sous le titre "Global".

    Si une colonne existe mais n'a jamais de valeur pour une ligne donnee,
    elle apparait quand meme dans le resultat avec valeur=None : rien n'est
    ignore silencieusement.
    """

    # Vocabulaire stable des sous-colonnes du rapport (ordre = forme du PDF).
    PRODUCTION_CANONICAL = ["ET", "FIL", "EMB", "SRTI", "TOT"]
    SERVICE_CANONICAL = ["PR_MP", "NLE", "COMM"]

    # alias -> libelle canonique (le PDF abrege parfois "Emb" en "Em")
    _SUBCOL_ALIASES = {
        "comm": "comm", "srti": "srti", "fil": "fil",
        "emb": "emb", "em": "emb",
        "tot": "tot", "nle": "nle", "et": "et", "mp": "mp", "pr": "pr",
    }
    _SUBCOL_VOCAB = sorted(_SUBCOL_ALIASES.keys(), key=len, reverse=True)
    _IGNORE_TITLE_KEYWORDS = ["date", "prod", "global", "site", "mom", "glob",
                               "service", "comm"]

    def __init__(self, pdf_path: str, site: str = "S2",
                 header_line_tol: float = 3.0, row_tol: float = 3.5,
                 data_cluster_tol: float = 4.0, header_match_tol: float = 13.0,
                 max_distance: float = 12.0):
        self.pdf_path = pdf_path
        self.site = site
        self.header_line_tol = header_line_tol
        self.row_tol = row_tol
        self.data_cluster_tol = data_cluster_tol
        self.header_match_tol = header_match_tol
        self.max_distance = max_distance
        self.column_map = None  # liste de (categorie, type_poisson, sous_colonne, x_ancre)

    # ------------------------------------------------------------------ #
    # Utilitaires
    # ------------------------------------------------------------------ #
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

    @staticmethod
    def _cluster_by_top(words, tol):
        lines, current, current_top = [], [], None
        for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
            if current_top is None or abs(w["top"] - current_top) <= tol:
                current.append(w)
                current_top = current_top if current_top is not None else w["top"]
            else:
                lines.append(current)
                current, current_top = [w], w["top"]
        if current:
            lines.append(current)
        return lines

    def _tokenize_subcol(self, text):
        text = text.lower().replace(" ", "")
        labels = []
        while text:
            match = next((c for c in self._SUBCOL_VOCAB if text.startswith(c)), None)
            if match:
                labels.append(self._SUBCOL_ALIASES[match])
                text = text[len(match):]
            else:
                return labels, text
        return labels, ""

    # ------------------------------------------------------------------ #
    # 1. Lecture brute du PDF : mots de la 1ere page + lignes de dates
    # ------------------------------------------------------------------ #
    def _first_page_words(self):
        with pdfplumber.open(self.pdf_path) as pdf:
            return pdf.pages[0].extract_words(x_tolerance=1.0, y_tolerance=3.0)

    def read_date_rows(self):
        date_rows = []
        with pdfplumber.open(self.pdf_path) as pdf:
            for page in pdf.pages:
                words = sorted(page.extract_words(x_tolerance=1.0, y_tolerance=3.0),
                                key=lambda w: (w["top"], w["x0"]))
                if not words:
                    continue
                current_top, current_words = None, []

                def flush():
                    if not current_words:
                        return
                    row_words = sorted(current_words, key=lambda w: w["x0"])
                    if re.match(r"^\d{2}/\d{2}/\d{4}$", row_words[0]["text"]):
                        date_rows.append(row_words)

                for w in words:
                    if current_top is None or abs(w["top"] - current_top) <= self.row_tol:
                        current_words.append(w)
                        if current_top is None:
                            current_top = w["top"]
                    else:
                        flush()
                        current_words = [w]
                        current_top = w["top"]
                flush()
        return date_rows

    # ------------------------------------------------------------------ #
    # 2. Parsing de l'en-tete -> segments de production (delimites par "ET")
    #    + libelles de groupe rattaches par proximite (pas par fusion de mots)
    # ------------------------------------------------------------------ #
    def _parse_header(self, first_page_words, first_date_top):
        header_words = [w for w in first_page_words if 40 < w["top"] < first_date_top]
        lines = self._cluster_by_top(header_words, tol=self.header_line_tol)
        lines.sort(key=lambda ln: min(w["top"] for w in ln))

        title_words = lines[0]
        subcol_words = sorted([w for ln in lines[1:] for w in ln], key=lambda w: w["x0"])

        # -- 2.a Reperage du bord droit ("Global"/synthese) via le titre --
        right_cutoff = None
        for w in title_words:
            low = w["text"].lower()
            if any(kw in low for kw in ("global", "site")):
                right_cutoff = w["x0"] if right_cutoff is None else min(right_cutoff, w["x0"])

        # -- 2.b Tokenisation des sous-colonnes (gere les fragments type "ETE"/"mb") --
        resolved = []  # (label, x0, x1)
        pending_text, pending_x0 = "", None
        for w in subcol_words:
            text = w["text"]
            if pending_text:
                combined = pending_text + text.lower()
                labels, rest = self._tokenize_subcol(combined)
                if labels:
                    for lbl in labels:
                        resolved.append((lbl, pending_x0, w["x1"]))
                    pending_text, pending_x0 = (rest, w["x0"]) if rest else ("", None)
                    continue
                else:
                    pending_text, pending_x0 = "", None
            labels, rest = self._tokenize_subcol(text)
            for lbl in labels:
                resolved.append((lbl, w["x0"], w["x1"]))
            if rest:
                pending_text, pending_x0 = rest, w["x0"]

        merged_resolved = []
        i = 0
        while i < len(resolved):
            lbl, x0, x1 = resolved[i]
            if lbl == "pr" and i + 1 < len(resolved) and resolved[i + 1][0] == "mp":
                merged_resolved.append(("PR_MP", x0, resolved[i + 1][2]))
                i += 2
                continue
            if lbl in ("et", "fil", "emb", "srti", "tot", "comm", "nle"):
                merged_resolved.append((lbl.upper(), x0, x1))
            i += 1

        if right_cutoff is not None:
            merged_resolved = [c for c in merged_resolved if c[1] < right_cutoff]

        # -- 2.c Decoupage en segments : Service Comm (avant le 1er "ET") puis
        #        un segment de production par occurrence de "ET" --
        first_et_idx = next((i for i, c in enumerate(merged_resolved) if c[0] == "ET"), None)
        service_comm_cols = merged_resolved[:first_et_idx] if first_et_idx is not None else merged_resolved
        rest_cols = merged_resolved[first_et_idx:] if first_et_idx is not None else []

        segments = []
        for lbl, x0, x1 in rest_cols:
            if lbl == "ET" or not segments:
                segments.append([])
            segments[-1].append((lbl, x0, x1))

        segment_starts = [seg[0][1] for seg in segments]  # x0 du 1er token ("ET") de chaque segment

        # -- 2.d Bord droit resserre : exclut les libelles de synthese
        #        ("ModMoM"/"Glob", ...) qui trainent apres le dernier segment
        #        et dont les valeurs peuvent deborder sous le seuil "Global" --
        if segment_starts:
            last_segment_end = segments[-1][-1][2]
            for w in subcol_words:
                if w["x0"] <= last_segment_end:
                    continue
                labels, _ = self._tokenize_subcol(w["text"])
                if not labels:
                    right_cutoff = w["x0"] if right_cutoff is None else min(right_cutoff, w["x0"])

        # -- 2.e Libelles de groupe : chaque mot du titre (hors mots-cles a
        #        ignorer) est rattache au segment de production dont le
        #        repere "ET" est le plus proche en X, puis les mots d'un
        #        meme segment sont joints dans l'ordre --
        group_words = {i: [] for i in range(len(segments))}
        for w in title_words:
            low = w["text"].lower()
            if any(kw in low for kw in self._IGNORE_TITLE_KEYWORDS):
                continue
            if not segment_starts:
                continue
            idx = min(range(len(segment_starts)), key=lambda i: abs(w["x0"] - segment_starts[i]))
            group_words[idx].append(w)

        group_names = []
        for i in range(len(segments)):
            words_i = sorted(group_words[i], key=lambda w: w["x0"])
            name = " ".join(w["text"] for w in words_i).strip()
            group_names.append(name if name else f"Groupe_{i + 1}")

        header_columns = []
        for lbl, x0, x1 in service_comm_cols:
            header_columns.append(("Service Comm", None, lbl, (x0 + x1) / 2))
        for name, seg in zip(group_names, segments):
            for lbl, x0, x1 in seg:
                header_columns.append(("Production", name, lbl, (x0 + x1) / 2))

        return header_columns, right_cutoff

    # ------------------------------------------------------------------ #
    # 3. Affinage avec les positions reelles des donnees (+ detection TOT2, TOT3, ...)
    # ------------------------------------------------------------------ #
    def _cluster_data_positions(self, date_rows):
        raw_x = []
        for row in date_rows:
            for w in row[1:]:
                t = w["text"].strip()
                if re.match(r"^[\d,\.]+$", t):
                    raw_x.append((w["x0"] + w["x1"]) / 2)
        raw_x.sort()
        clusters = []
        for x in raw_x:
            if clusters and x - clusters[-1][-1] <= self.data_cluster_tol:
                clusters[-1].append(x)
            else:
                clusters.append([x])
        return [sum(c) / len(c) for c in clusters]

    def _refine_with_data(self, header_columns, data_anchors, right_cutoff):
        # affectation gloutonne SANS reutilisation d'une meme ancre de donnees.
        # A ce stade le LIBELLE peut encore etre faux si l'en-tete etait
        # corrompu (ex: Sardine) mais le GROUPE (cat, type_p) auquel une
        # colonne appartient reste correct : c'est ce que _normalize_labels
        # exploite ensuite pour reappliquer l'ordre canonique par position.
        data_anchors = sorted(data_anchors)
        used = [False] * len(data_anchors)
        refined = []
        for cat, type_p, lbl, x in header_columns:
            best_i, best_d = None, None
            for i, a in enumerate(data_anchors):
                if used[i]:
                    continue
                d = abs(a - x)
                if d <= self.header_match_tol and (best_d is None or d < best_d):
                    best_d, best_i = d, i
            if best_i is not None:
                used[best_i] = True
                refined.append([cat, type_p, lbl, data_anchors[best_i]])
            else:
                refined.append([cat, type_p, lbl, x])

        claimed = {data_anchors[i] for i, u in enumerate(used) if u}
        unclaimed = sorted(a for a in data_anchors if a not in claimed)
        for a in unclaimed:
            if right_cutoff is not None and a >= right_cutoff:
                continue
            candidates = [c for c in refined if c[3] < a]
            if not candidates:
                continue
            nearest_left = min(candidates, key=lambda c: a - c[3])
            cat, type_p = nearest_left[0], nearest_left[1]
            refined.append([cat, type_p, "EXTRA", a])

        refined.sort(key=lambda c: c[3])
        return [tuple(c) for c in refined]

    def _normalize_labels(self, refined):
        """
        Reapplique le vocabulaire stable du rapport (ordre des sous-colonnes)
        PAR POSITION a l'interieur de chaque groupe, independamment du texte
        d'en-tete lu (qui peut etre corrompu/incomplet pour une colonne).
        Le nombre et la position des colonnes restent 100% dynamiques
        (deduits du PDF) ; seul l'ORDRE canonique (ET, Fil, Emb, Srti, Tot,
        puis Tot2, Tot3... au-dela) est une regle metier stable du rapport.
        """
        by_group = {}
        for cat, type_p, lbl, x in refined:
            by_group.setdefault((cat, type_p), []).append((lbl, x))

        normalized = []
        for (cat, type_p), cols in by_group.items():
            cols.sort(key=lambda c: c[1])
            canonical = self.SERVICE_CANONICAL if cat == "Service Comm" else self.PRODUCTION_CANONICAL
            for i, (_, x) in enumerate(cols):
                if i < len(canonical):
                    new_lbl = canonical[i]
                else:
                    new_lbl = f"TOT{i - len(canonical) + 2}"
                normalized.append((cat, type_p, new_lbl, x))

        normalized.sort(key=lambda c: c[3])
        return normalized

    def _build_column_map(self):
        first_page_words = self._first_page_words()
        date_tops = [w["top"] for w in first_page_words if re.match(r"^\d{2}/\d{2}/\d{4}$", w["text"])]
        if not date_tops:
            raise ValueError("Aucune ligne de date trouvee : impossible de localiser l'en-tete.")

        header_columns, right_cutoff = self._parse_header(first_page_words, min(date_tops))
        date_rows = self.read_date_rows()
        data_anchors = self._cluster_data_positions(date_rows)
        refined = self._refine_with_data(header_columns, data_anchors, right_cutoff)
        return self._normalize_labels(refined)

    # ------------------------------------------------------------------ #
    # 4. Extraction finale
    # ------------------------------------------------------------------ #
    def _assign_to_columns(self, value_words):
        result = {}
        for w in value_words:
            text = w["text"].strip()
            if text in ("", "-", "--", "?", "??"):
                continue
            x = (w["x0"] + w["x1"]) / 2.0
            best_column, best_distance = None, None
            for cat, type_p, srv, anchor_x in self.column_map:
                distance = abs(x - anchor_x)
                if best_distance is None or distance < best_distance:
                    best_distance, best_column = distance, (cat, type_p, srv)
            if best_column is not None and best_distance <= self.max_distance:
                result[best_column] = text
        return result

    def extract(self):
        self.column_map = self._build_column_map()
        fields = [(cat, type_p, srv) for cat, type_p, srv, _ in self.column_map]

        records = []
        for row_words in self.read_date_rows():
            date = row_words[0]["text"]
            values = self._assign_to_columns(row_words[1:])
            for cat, type_p, srv in fields:
                raw_val = values.get((cat, type_p, srv))
                records.append({
                    "date": date,
                    "categorie": cat,
                    "type_poisson": type_p,
                    "service": srv,
                    "valeur": self.clean(raw_val)
                })
        return pd.DataFrame(records)


