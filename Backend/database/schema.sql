--
-- PostgreSQL database dump
--

\restrict YkCtqYhYacWXZhmjfrllfzD25srjg9NRzGhFi8P6ZfVguOCEIfnKp5AXSfrbv6H

-- Dumped from database version 17.10
-- Dumped by pg_dump version 17.10

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: articles; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.articles (
    id_article integer NOT NULL,
    code_article character varying(20) NOT NULL,
    designation character varying(200),
    id_type_poisson integer,
    id_client integer,
    fiche_type character varying(20) DEFAULT 'RR-125A'::character varying,
    code_interne character varying(50),
    type_format character varying(20),
    sauce character varying(50),
    poids_unitaire numeric(8,4),
    actif boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.articles OWNER TO postgres;

--
-- Name: articles_id_article_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.articles_id_article_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.articles_id_article_seq OWNER TO postgres;

--
-- Name: articles_id_article_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.articles_id_article_seq OWNED BY public.articles.id_article;


--
-- Name: clients; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.clients (
    id_client integer NOT NULL,
    code_client character varying(50) NOT NULL,
    nom_client character varying(100) NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.clients OWNER TO postgres;

--
-- Name: clients_id_client_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.clients_id_client_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.clients_id_client_seq OWNER TO postgres;

--
-- Name: clients_id_client_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.clients_id_client_seq OWNED BY public.clients.id_client;


--
-- Name: codes_alias; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.codes_alias (
    id_code_alias integer NOT NULL,
    id_article integer NOT NULL,
    code_alias character varying(20) NOT NULL,
    longueur smallint NOT NULL,
    source character varying(30),
    date_creation timestamp without time zone DEFAULT now()
);


ALTER TABLE public.codes_alias OWNER TO postgres;

--
-- Name: TABLE codes_alias; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.codes_alias IS 'Table de correspondance code -> id_article, incluant les formes tronquees utilisees par resume.py (9/10/11 caracteres). Remplace le matching par prefixe dynamique de FKResolver.get_article_id.';


--
-- Name: codes_alias_id_code_alias_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.codes_alias_id_code_alias_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.codes_alias_id_code_alias_seq OWNER TO postgres;

--
-- Name: codes_alias_id_code_alias_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.codes_alias_id_code_alias_seq OWNED BY public.codes_alias.id_code_alias;


--
-- Name: codes_non_resolus; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.codes_non_resolus (
    id integer NOT NULL,
    code character varying(20) NOT NULL,
    id_resume integer,
    table_source character varying(30) NOT NULL,
    date_detection timestamp without time zone DEFAULT now(),
    resolu boolean DEFAULT false,
    date_resolution timestamp without time zone
);


ALTER TABLE public.codes_non_resolus OWNER TO postgres;

--
-- Name: TABLE codes_non_resolus; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.codes_non_resolus IS 'Lignes ignorees par l''ETL resume car le code produit n''a pas trouve de correspondance dans codes_alias au moment du traitement. A rejouer via une passe de rattrapage une fois les articles crees.';


--
-- Name: codes_non_resolus_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.codes_non_resolus_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.codes_non_resolus_id_seq OWNER TO postgres;

--
-- Name: codes_non_resolus_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.codes_non_resolus_id_seq OWNED BY public.codes_non_resolus.id;


--
-- Name: couts_par_serie; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.couts_par_serie (
    id_cout_serie integer NOT NULL,
    id_resume integer NOT NULL,
    id_article integer NOT NULL,
    serie character varying(20) NOT NULL,
    code character varying(50) NOT NULL,
    b_pdtes numeric(14,4),
    poisson numeric(14,4),
    boits numeric(14,4),
    huile numeric(14,4),
    etui numeric(14,4),
    mod numeric(14,4),
    mg numeric(14,4),
    f_fab_reel numeric(14,4),
    f_fab_std numeric(14,4),
    f_fin numeric(14,4),
    c_d numeric(14,4),
    mb numeric(14,4),
    pct_mb numeric(8,2),
    cf numeric(14,4),
    mn numeric(14,4),
    pct_mn numeric(8,2),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.couts_par_serie OWNER TO postgres;

--
-- Name: TABLE couts_par_serie; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.couts_par_serie IS 'Cout par serie de fabrication (montants, pas des couts unitaires), une ligne par jour+article+serie. Source : ResumeExtractor.extract_couts_serie().';


--
-- Name: couts_par_serie_id_cout_serie_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

ALTER TABLE public.couts_par_serie ALTER COLUMN id_cout_serie ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.couts_par_serie_id_cout_serie_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: couts_unitaires_code; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.couts_unitaires_code (
    id_cout_unitaire integer NOT NULL,
    id_resume integer NOT NULL,
    id_article integer NOT NULL,
    code character varying(50) NOT NULL,
    poisson numeric(12,4),
    huile numeric(12,4),
    boite numeric(12,4),
    etui numeric(12,4),
    mod numeric(12,4),
    mg numeric(12,4),
    f_fab_reel numeric(12,4),
    f_fab_std numeric(12,4),
    f_fin numeric(12,4),
    c_d numeric(12,4),
    p_v numeric(12,4),
    m_b numeric(12,4),
    pct_mb numeric(8,2),
    ch_f numeric(12,4),
    pct_cf numeric(8,2),
    m_n numeric(12,4),
    pct_mn numeric(8,2),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.couts_unitaires_code OWNER TO postgres;

--
-- Name: TABLE couts_unitaires_code; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.couts_unitaires_code IS 'Cout unitaire par code produit (Poisson/Huile/Boite/Etui/MOD/Mg/...), une ligne par jour+article. Source : ResumeExtractor.extract_couts_unitaires().';


--
-- Name: couts_unitaires_code_id_cout_unitaire_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

ALTER TABLE public.couts_unitaires_code ALTER COLUMN id_cout_unitaire ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.couts_unitaires_code_id_cout_unitaire_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: ecarts_couts_postes; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.ecarts_couts_postes (
    id_ecart integer NOT NULL,
    id_production integer NOT NULL,
    reel_unitaire numeric(10,4),
    stnd_unitaire numeric(10,4),
    reel_total numeric(12,2),
    stnd_total numeric(12,2),
    ecart_total numeric(12,2),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    id_poste_cout integer NOT NULL,
    quantite_reelle numeric,
    quantite_stnd numeric,
    reel_secondaire numeric,
    stnd_secondaire numeric
);


ALTER TABLE public.ecarts_couts_postes OWNER TO postgres;

--
-- Name: COLUMN ecarts_couts_postes.quantite_reelle; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.ecarts_couts_postes.quantite_reelle IS '1ere paire Reel/Stnd du tableau des couts par poste (quantites) -- ParArticleExtractor.extract_table_couts() : colonne reel_0.';


--
-- Name: COLUMN ecarts_couts_postes.quantite_stnd; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.ecarts_couts_postes.quantite_stnd IS '1ere paire Reel/Stnd du tableau des couts par poste (quantites) -- ParArticleExtractor.extract_table_couts() : colonne stnd_0.';


--
-- Name: COLUMN ecarts_couts_postes.reel_secondaire; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.ecarts_couts_postes.reel_secondaire IS '2e paire Reel/Stnd du tableau (colonnes de droite, juste avant la colonne Dev finale) -- extract_table_couts() : colonne reel_1. A renommer si le metier confirme sa signification exacte.';


--
-- Name: COLUMN ecarts_couts_postes.stnd_secondaire; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.ecarts_couts_postes.stnd_secondaire IS '2e paire Reel/Stnd du tableau (colonnes de droite, juste avant la colonne Dev finale) -- extract_table_couts() : colonne stnd_1.';


--
-- Name: ecarts_couts_postes_id_ecart_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.ecarts_couts_postes_id_ecart_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.ecarts_couts_postes_id_ecart_seq OWNER TO postgres;

--
-- Name: ecarts_couts_postes_id_ecart_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.ecarts_couts_postes_id_ecart_seq OWNED BY public.ecarts_couts_postes.id_ecart;


--
-- Name: fiches_techniques; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.fiches_techniques (
    id_fiche integer NOT NULL,
    id_article integer NOT NULL,
    version character varying(10) DEFAULT '1.0'::character varying,
    date_validite date NOT NULL,
    std_poisson numeric(10,4),
    std_huile numeric(10,4),
    std_additif numeric(10,4),
    std_boite numeric(10,4),
    std_etui numeric(10,4),
    std_mod numeric(10,4),
    std_momg numeric(10,4),
    std_frfab numeric(10,4),
    std_port numeric(10,4),
    std_gfin numeric(10,4),
    std_com numeric(10,4),
    std_cd numeric(10,4),
    std_pmv numeric(10,4),
    std_mb numeric(10,4),
    std_pct_mb numeric(5,2),
    actif boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.fiches_techniques OWNER TO postgres;

--
-- Name: fiches_techniques_id_fiche_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.fiches_techniques_id_fiche_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.fiches_techniques_id_fiche_seq OWNER TO postgres;

--
-- Name: fiches_techniques_id_fiche_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.fiches_techniques_id_fiche_seq OWNED BY public.fiches_techniques.id_fiche;


--
-- Name: lots_poisson; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.lots_poisson (
    id_lot integer NOT NULL,
    date_production date NOT NULL,
    id_site integer,
    no_lot character varying(50) NOT NULL,
    date_entree date,
    nb_jours_frigo integer,
    frigo character varying(10),
    fournisseur character varying(50),
    br character varying(50),
    poids_kg numeric(10,3),
    origine character varying(50),
    moule character varying(20),
    poids_filets_kg numeric(10,3),
    rdt_pct numeric(5,2),
    pct_mrc numeric(5,2),
    id_type_poisson integer,
    pct_repartition numeric(5,2),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    etat character varying(20)
);


ALTER TABLE public.lots_poisson OWNER TO postgres;

--
-- Name: COLUMN lots_poisson.etat; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.lots_poisson.etat IS 'Etat du lot au moment de la reception (Congele / Frais) - source: rendement_extractor.py';


--
-- Name: lots_poisson_id_lot_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.lots_poisson_id_lot_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.lots_poisson_id_lot_seq OWNER TO postgres;

--
-- Name: lots_poisson_id_lot_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.lots_poisson_id_lot_seq OWNED BY public.lots_poisson.id_lot;


--
-- Name: matiere_premiere; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.matiere_premiere (
    id_matiere_premiere integer NOT NULL,
    id_resume integer NOT NULL,
    fournisseur character varying(100),
    partie character varying(100),
    pu numeric(12,2),
    qte numeric(14,2)
);


ALTER TABLE public.matiere_premiere OWNER TO postgres;

--
-- Name: matiere_premiere_id_matiere_premiere_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.matiere_premiere_id_matiere_premiere_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.matiere_premiere_id_matiere_premiere_seq OWNER TO postgres;

--
-- Name: matiere_premiere_id_matiere_premiere_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.matiere_premiere_id_matiere_premiere_seq OWNED BY public.matiere_premiere.id_matiere_premiere;


--
-- Name: mod_communs_journaliers; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.mod_communs_journaliers (
    id_mod_commun integer NOT NULL,
    date_production date NOT NULL,
    id_site integer NOT NULL,
    pr_mp numeric(8,3),
    nle numeric(8,3),
    comm numeric(8,3),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.mod_communs_journaliers OWNER TO postgres;

--
-- Name: mod_communs_journaliers_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.mod_communs_journaliers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.mod_communs_journaliers_id_seq OWNER TO postgres;

--
-- Name: mod_communs_journaliers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.mod_communs_journaliers_id_seq OWNED BY public.mod_communs_journaliers.id_mod_commun;


--
-- Name: mod_durees_espece_poste; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.mod_durees_espece_poste (
    id_mod_detail integer NOT NULL,
    date_production date NOT NULL,
    id_site integer NOT NULL,
    id_type_poisson integer NOT NULL,
    id_poste integer NOT NULL,
    duree_min_kg numeric(8,3) NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.mod_durees_espece_poste OWNER TO postgres;

--
-- Name: mod_durees_espece_poste_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.mod_durees_espece_poste_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.mod_durees_espece_poste_id_seq OWNER TO postgres;

--
-- Name: mod_durees_espece_poste_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.mod_durees_espece_poste_id_seq OWNED BY public.mod_durees_espece_poste.id_mod_detail;


--
-- Name: mod_global; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.mod_global (
    id_mod_global integer NOT NULL,
    id_resume integer NOT NULL,
    mo numeric(14,2),
    mg numeric(14,2),
    mod_c numeric(12,2),
    mg_c numeric(12,2)
);


ALTER TABLE public.mod_global OWNER TO postgres;

--
-- Name: mod_global_id_mod_global_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.mod_global_id_mod_global_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.mod_global_id_mod_global_seq OWNER TO postgres;

--
-- Name: mod_global_id_mod_global_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.mod_global_id_mod_global_seq OWNED BY public.mod_global.id_mod_global;


--
-- Name: mod_totaux_espece; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.mod_totaux_espece (
    id_mod_total integer NOT NULL,
    date_production date NOT NULL,
    id_site integer NOT NULL,
    id_type_poisson integer NOT NULL,
    code_total character varying(10) NOT NULL,
    valeur numeric
);


ALTER TABLE public.mod_totaux_espece OWNER TO postgres;

--
-- Name: TABLE mod_totaux_espece; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.mod_totaux_espece IS 'Sous-totaux (TOT/TOT2) par espece x jour x site, issus des rapports Mod S1.pdf / Mod S2.pdf. Stockes a part de mod_durees_espece_poste pour ne jamais fausser un SUM(duree_min_kg) sur ET+FIL+EMB+SRTI par un double comptage -- voir pipeline_etl.py / upsert_mod_long_format().';


--
-- Name: mod_totaux_espece_id_mod_total_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.mod_totaux_espece_id_mod_total_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.mod_totaux_espece_id_mod_total_seq OWNER TO postgres;

--
-- Name: mod_totaux_espece_id_mod_total_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.mod_totaux_espece_id_mod_total_seq OWNED BY public.mod_totaux_espece.id_mod_total;


--
-- Name: postes_couts_reference; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.postes_couts_reference (
    id_poste_cout integer NOT NULL,
    code_poste_cout character varying(20) NOT NULL,
    nom_poste_cout character varying(100) NOT NULL,
    ordre_affichage integer DEFAULT 0,
    actif boolean DEFAULT true
);


ALTER TABLE public.postes_couts_reference OWNER TO postgres;

--
-- Name: TABLE postes_couts_reference; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.postes_couts_reference IS 'Referentiel des lignes de cout des fiches "par article" (Poisson, Huile, Additif, Boite, Etui-carton, MOD, MOMG, Fr Fab, Port, ...). Distinct de postes_production, qui est reservee aux postes MOD (S1/S2) de transformation/communs.';


--
-- Name: postes_couts_reference_id_poste_cout_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

ALTER TABLE public.postes_couts_reference ALTER COLUMN id_poste_cout ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.postes_couts_reference_id_poste_cout_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: postes_production; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.postes_production (
    id_poste integer NOT NULL,
    code_poste character varying(20) NOT NULL,
    nom_poste character varying(100) NOT NULL,
    categorie character varying(50),
    ordre_affichage integer DEFAULT 0,
    actif boolean DEFAULT true
);


ALTER TABLE public.postes_production OWNER TO postgres;

--
-- Name: postes_production_id_poste_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.postes_production_id_poste_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.postes_production_id_poste_seq OWNER TO postgres;

--
-- Name: postes_production_id_poste_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.postes_production_id_poste_seq OWNED BY public.postes_production.id_poste;


--
-- Name: productions_journalieres; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.productions_journalieres (
    id_production integer NOT NULL,
    date_production date NOT NULL,
    id_site integer NOT NULL,
    id_article integer NOT NULL,
    no_s_produit character varying(20),
    no_poisson character varying(20),
    t_boites integer,
    caisses integer,
    t_boites_utilises integer,
    taux_utilisation character varying(20),
    poisson_kg numeric(10,3),
    filet_kg numeric(10,3),
    rdt_filet_pct numeric(5,2),
    rdt_calcule_pct numeric(5,2),
    px_mp numeric(8,4),
    huile_kg numeric(10,3),
    pu_huile numeric(8,2),
    fr_fab numeric(12,2),
    mod_total numeric(12,2),
    mod_pct numeric(5,2),
    momg numeric(12,2),
    momg_pct numeric(5,2),
    ch_fixes numeric(12,2),
    devise character varying(3) NOT NULL,
    taux_change numeric(10,4),
    tot_cd_dhs numeric(12,2),
    tot_pmv_dhs numeric(12,2),
    tot_mn_dhs numeric(12,2),
    tot_pr_dhs numeric(12,2),
    pct_mb numeric(5,2),
    pct_cf numeric(5,2),
    pct_mn numeric(5,2),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    tot_mb_dhs numeric(12,2),
    numero_serie character varying(20) NOT NULL,
    reference_client character varying(50),
    date_reception date,
    ligne_production character varying(20),
    cout_min_reel numeric(10,4),
    cout_min_stnd numeric(10,4)
);


ALTER TABLE public.productions_journalieres OWNER TO postgres;

--
-- Name: COLUMN productions_journalieres.tot_mb_dhs; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.productions_journalieres.tot_mb_dhs IS 'Marge brute totale (DHS) - source: c_global_extractor.py, champ "tot_mb"';


--
-- Name: productions_journalieres_id_production_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.productions_journalieres_id_production_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.productions_journalieres_id_production_seq OWNER TO postgres;

--
-- Name: productions_journalieres_id_production_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.productions_journalieres_id_production_seq OWNED BY public.productions_journalieres.id_production;


--
-- Name: resume_journalier; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.resume_journalier (
    id_resume integer NOT NULL,
    date_production date NOT NULL,
    reference_jour character varying(50) NOT NULL,
    id_site integer,
    id_type_poisson integer
);


ALTER TABLE public.resume_journalier OWNER TO postgres;

--
-- Name: COLUMN resume_journalier.id_type_poisson; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.resume_journalier.id_type_poisson IS 'Espece du bloc resume (poisson_bloc extrait par ResumeExtractor). Nullable tant que le libelle n''a pas de correspondance en base.';


--
-- Name: resume_journalier_id_resume_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.resume_journalier_id_resume_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.resume_journalier_id_resume_seq OWNER TO postgres;

--
-- Name: resume_journalier_id_resume_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.resume_journalier_id_resume_seq OWNED BY public.resume_journalier.id_resume;


--
-- Name: resume_production_poisson; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.resume_production_poisson (
    id_resume_production integer NOT NULL,
    id_resume integer NOT NULL,
    id_type_poisson integer NOT NULL,
    qte_poisson numeric(12,2),
    qte_filet numeric(12,2),
    rdt_pct numeric(8,2),
    pu_moy numeric(12,2),
    pct_jour numeric(8,2),
    pct_prod_c numeric(8,2),
    pct_prod_r numeric(8,2)
);


ALTER TABLE public.resume_production_poisson OWNER TO postgres;

--
-- Name: resume_production_poisson_id_resume_production_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.resume_production_poisson_id_resume_production_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.resume_production_poisson_id_resume_production_seq OWNER TO postgres;

--
-- Name: resume_production_poisson_id_resume_production_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.resume_production_poisson_id_resume_production_seq OWNED BY public.resume_production_poisson.id_resume_production;


--
-- Name: sites_production; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.sites_production (
    id_site integer NOT NULL,
    code_site character varying(10) NOT NULL,
    nom_site character varying(100) NOT NULL,
    localisation character varying(100),
    actif boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.sites_production OWNER TO postgres;

--
-- Name: sites_production_id_site_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.sites_production_id_site_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.sites_production_id_site_seq OWNER TO postgres;

--
-- Name: sites_production_id_site_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.sites_production_id_site_seq OWNED BY public.sites_production.id_site;


--
-- Name: table_codes; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.table_codes (
    id_code integer NOT NULL,
    id_resume integer NOT NULL,
    id_article integer NOT NULL,
    code character varying(50) NOT NULL,
    pct_prod numeric(8,2),
    egoutte_std numeric(12,2),
    egoutte_reel numeric(12,2),
    poids_produit numeric(12,2),
    pct_casse numeric(8,2),
    huile_reel numeric(12,2),
    huile_std numeric(12,2),
    mod_reel numeric(12,2),
    mod_std numeric(12,2),
    mg_reel numeric(12,2),
    mg_std numeric(12,2),
    frfabdh_reel numeric(12,2),
    frfabdh_std numeric(12,2)
);


ALTER TABLE public.table_codes OWNER TO postgres;

--
-- Name: table_codes_id_code_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.table_codes_id_code_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.table_codes_id_code_seq OWNER TO postgres;

--
-- Name: table_codes_id_code_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.table_codes_id_code_seq OWNED BY public.table_codes.id_code;


--
-- Name: types_poisson; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.types_poisson (
    id_type_poisson integer NOT NULL,
    code_type character varying(50) NOT NULL,
    nom_type character varying(100) NOT NULL,
    famille character varying(50),
    description text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.types_poisson OWNER TO postgres;

--
-- Name: types_poisson_id_type_poisson_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.types_poisson_id_type_poisson_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.types_poisson_id_type_poisson_seq OWNER TO postgres;

--
-- Name: types_poisson_id_type_poisson_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.types_poisson_id_type_poisson_seq OWNED BY public.types_poisson.id_type_poisson;


--
-- Name: v_dashboard_global; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.v_dashboard_global AS
 SELECT p.date_production,
    s.code_site,
    count(DISTINCT p.id_article) AS nb_articles,
    sum(p.t_boites) AS total_boites,
    sum(p.poisson_kg) AS total_poisson_kg,
    sum(p.filet_kg) AS total_filets_kg,
    round(avg(p.rdt_filet_pct), 2) AS rdt_moyen,
    sum(p.tot_cd_dhs) AS total_cd_dhs,
    sum(p.tot_pmv_dhs) AS total_pmv_dhs,
    sum(p.tot_mn_dhs) AS total_marge_nette,
    round(avg(p.pct_mn), 2) AS marge_nette_moyenne,
    sum(p.mod_total) AS total_mod,
    sum(p.ch_fixes) AS total_charges_fixes
   FROM (public.productions_journalieres p
     JOIN public.sites_production s ON ((p.id_site = s.id_site)))
  GROUP BY p.date_production, s.code_site;


ALTER VIEW public.v_dashboard_global OWNER TO postgres;

--
-- Name: v_mod_par_kg; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.v_mod_par_kg AS
 SELECT p.date_production,
    s.code_site,
    a.code_article,
    tp.nom_type AS type_poisson,
    p.mod_total,
    p.filet_kg,
        CASE
            WHEN (p.filet_kg > (0)::numeric) THEN round((p.mod_total / p.filet_kg), 2)
            ELSE (0)::numeric
        END AS mod_par_kg_filet,
        CASE
            WHEN (p.poisson_kg > (0)::numeric) THEN round((p.mod_total / p.poisson_kg), 2)
            ELSE (0)::numeric
        END AS mod_par_kg_poisson,
    p.momg,
    p.ch_fixes
   FROM (((public.productions_journalieres p
     JOIN public.sites_production s ON ((p.id_site = s.id_site)))
     JOIN public.articles a ON ((p.id_article = a.id_article)))
     JOIN public.types_poisson tp ON ((a.id_type_poisson = tp.id_type_poisson)));


ALTER VIEW public.v_mod_par_kg OWNER TO postgres;

--
-- Name: v_rendements_matiere; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.v_rendements_matiere AS
 SELECT p.date_production,
    s.code_site,
    a.code_article,
    tp.nom_type AS type_poisson,
    p.poisson_kg,
    p.filet_kg,
    p.rdt_filet_pct,
    p.rdt_calcule_pct,
    c.nom_client,
    p.t_boites
   FROM ((((public.productions_journalieres p
     JOIN public.sites_production s ON ((p.id_site = s.id_site)))
     JOIN public.articles a ON ((p.id_article = a.id_article)))
     JOIN public.types_poisson tp ON ((a.id_type_poisson = tp.id_type_poisson)))
     JOIN public.clients c ON ((a.id_client = c.id_client)));


ALTER VIEW public.v_rendements_matiere OWNER TO postgres;

--
-- Name: v_tracabilite_lots; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.v_tracabilite_lots AS
 SELECT l.date_production,
    s.code_site,
    l.no_lot,
    l.date_entree,
    l.nb_jours_frigo,
    l.fournisseur,
    l.origine,
    l.moule,
    l.poids_kg,
    l.poids_filets_kg,
    l.rdt_pct,
    tp.nom_type AS type_poisson,
    l.pct_repartition
   FROM ((public.lots_poisson l
     JOIN public.sites_production s ON ((l.id_site = s.id_site)))
     JOIN public.types_poisson tp ON ((l.id_type_poisson = tp.id_type_poisson)));


ALTER VIEW public.v_tracabilite_lots OWNER TO postgres;

--
-- Name: articles id_article; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.articles ALTER COLUMN id_article SET DEFAULT nextval('public.articles_id_article_seq'::regclass);


--
-- Name: clients id_client; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.clients ALTER COLUMN id_client SET DEFAULT nextval('public.clients_id_client_seq'::regclass);


--
-- Name: codes_alias id_code_alias; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.codes_alias ALTER COLUMN id_code_alias SET DEFAULT nextval('public.codes_alias_id_code_alias_seq'::regclass);


--
-- Name: codes_non_resolus id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.codes_non_resolus ALTER COLUMN id SET DEFAULT nextval('public.codes_non_resolus_id_seq'::regclass);


--
-- Name: ecarts_couts_postes id_ecart; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ecarts_couts_postes ALTER COLUMN id_ecart SET DEFAULT nextval('public.ecarts_couts_postes_id_ecart_seq'::regclass);


--
-- Name: fiches_techniques id_fiche; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fiches_techniques ALTER COLUMN id_fiche SET DEFAULT nextval('public.fiches_techniques_id_fiche_seq'::regclass);


--
-- Name: lots_poisson id_lot; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lots_poisson ALTER COLUMN id_lot SET DEFAULT nextval('public.lots_poisson_id_lot_seq'::regclass);


--
-- Name: matiere_premiere id_matiere_premiere; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.matiere_premiere ALTER COLUMN id_matiere_premiere SET DEFAULT nextval('public.matiere_premiere_id_matiere_premiere_seq'::regclass);


--
-- Name: mod_communs_journaliers id_mod_commun; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mod_communs_journaliers ALTER COLUMN id_mod_commun SET DEFAULT nextval('public.mod_communs_journaliers_id_seq'::regclass);


--
-- Name: mod_durees_espece_poste id_mod_detail; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mod_durees_espece_poste ALTER COLUMN id_mod_detail SET DEFAULT nextval('public.mod_durees_espece_poste_id_seq'::regclass);


--
-- Name: mod_global id_mod_global; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mod_global ALTER COLUMN id_mod_global SET DEFAULT nextval('public.mod_global_id_mod_global_seq'::regclass);


--
-- Name: mod_totaux_espece id_mod_total; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mod_totaux_espece ALTER COLUMN id_mod_total SET DEFAULT nextval('public.mod_totaux_espece_id_mod_total_seq'::regclass);


--
-- Name: postes_production id_poste; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.postes_production ALTER COLUMN id_poste SET DEFAULT nextval('public.postes_production_id_poste_seq'::regclass);


--
-- Name: productions_journalieres id_production; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.productions_journalieres ALTER COLUMN id_production SET DEFAULT nextval('public.productions_journalieres_id_production_seq'::regclass);


--
-- Name: resume_journalier id_resume; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.resume_journalier ALTER COLUMN id_resume SET DEFAULT nextval('public.resume_journalier_id_resume_seq'::regclass);


--
-- Name: resume_production_poisson id_resume_production; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.resume_production_poisson ALTER COLUMN id_resume_production SET DEFAULT nextval('public.resume_production_poisson_id_resume_production_seq'::regclass);


--
-- Name: sites_production id_site; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sites_production ALTER COLUMN id_site SET DEFAULT nextval('public.sites_production_id_site_seq'::regclass);


--
-- Name: table_codes id_code; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.table_codes ALTER COLUMN id_code SET DEFAULT nextval('public.table_codes_id_code_seq'::regclass);


--
-- Name: types_poisson id_type_poisson; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.types_poisson ALTER COLUMN id_type_poisson SET DEFAULT nextval('public.types_poisson_id_type_poisson_seq'::regclass);


--
-- Name: articles articles_code_article_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.articles
    ADD CONSTRAINT articles_code_article_key UNIQUE (code_article);


--
-- Name: articles articles_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.articles
    ADD CONSTRAINT articles_pkey PRIMARY KEY (id_article);


--
-- Name: clients clients_code_client_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.clients
    ADD CONSTRAINT clients_code_client_key UNIQUE (code_client);


--
-- Name: clients clients_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.clients
    ADD CONSTRAINT clients_pkey PRIMARY KEY (id_client);


--
-- Name: codes_alias codes_alias_code_alias_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.codes_alias
    ADD CONSTRAINT codes_alias_code_alias_key UNIQUE (code_alias);


--
-- Name: codes_alias codes_alias_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.codes_alias
    ADD CONSTRAINT codes_alias_pkey PRIMARY KEY (id_code_alias);


--
-- Name: codes_non_resolus codes_non_resolus_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.codes_non_resolus
    ADD CONSTRAINT codes_non_resolus_pkey PRIMARY KEY (id);


--
-- Name: couts_par_serie couts_par_serie_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.couts_par_serie
    ADD CONSTRAINT couts_par_serie_pkey PRIMARY KEY (id_cout_serie);


--
-- Name: couts_par_serie couts_par_serie_resume_article_serie_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.couts_par_serie
    ADD CONSTRAINT couts_par_serie_resume_article_serie_key UNIQUE (id_resume, id_article, serie);


--
-- Name: couts_unitaires_code couts_unitaires_code_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.couts_unitaires_code
    ADD CONSTRAINT couts_unitaires_code_pkey PRIMARY KEY (id_cout_unitaire);


--
-- Name: couts_unitaires_code couts_unitaires_code_resume_article_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.couts_unitaires_code
    ADD CONSTRAINT couts_unitaires_code_resume_article_key UNIQUE (id_resume, id_article);


--
-- Name: ecarts_couts_postes ecarts_couts_postes_id_production_id_poste_cout_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ecarts_couts_postes
    ADD CONSTRAINT ecarts_couts_postes_id_production_id_poste_cout_key UNIQUE (id_production, id_poste_cout);


--
-- Name: ecarts_couts_postes ecarts_couts_postes_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ecarts_couts_postes
    ADD CONSTRAINT ecarts_couts_postes_pkey PRIMARY KEY (id_ecart);


--
-- Name: fiches_techniques fiches_techniques_id_article_version_date_validite_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fiches_techniques
    ADD CONSTRAINT fiches_techniques_id_article_version_date_validite_key UNIQUE (id_article, version, date_validite);


--
-- Name: fiches_techniques fiches_techniques_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fiches_techniques
    ADD CONSTRAINT fiches_techniques_pkey PRIMARY KEY (id_fiche);


--
-- Name: lots_poisson lots_poisson_br_site_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lots_poisson
    ADD CONSTRAINT lots_poisson_br_site_key UNIQUE (br, id_site);


--
-- Name: lots_poisson lots_poisson_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lots_poisson
    ADD CONSTRAINT lots_poisson_pkey PRIMARY KEY (id_lot);


--
-- Name: matiere_premiere matiere_premiere_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.matiere_premiere
    ADD CONSTRAINT matiere_premiere_pkey PRIMARY KEY (id_matiere_premiere);


--
-- Name: mod_communs_journaliers mod_communs_journaliers_date_site_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mod_communs_journaliers
    ADD CONSTRAINT mod_communs_journaliers_date_site_key UNIQUE (date_production, id_site);


--
-- Name: mod_communs_journaliers mod_communs_journaliers_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mod_communs_journaliers
    ADD CONSTRAINT mod_communs_journaliers_pkey PRIMARY KEY (id_mod_commun);


--
-- Name: mod_durees_espece_poste mod_durees_espece_poste_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mod_durees_espece_poste
    ADD CONSTRAINT mod_durees_espece_poste_pkey PRIMARY KEY (id_mod_detail);


--
-- Name: mod_durees_espece_poste mod_durees_espece_poste_uniq; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mod_durees_espece_poste
    ADD CONSTRAINT mod_durees_espece_poste_uniq UNIQUE (date_production, id_site, id_type_poisson, id_poste);


--
-- Name: mod_global mod_global_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mod_global
    ADD CONSTRAINT mod_global_pkey PRIMARY KEY (id_mod_global);


--
-- Name: mod_totaux_espece mod_totaux_espece_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mod_totaux_espece
    ADD CONSTRAINT mod_totaux_espece_pkey PRIMARY KEY (id_mod_total);


--
-- Name: postes_couts_reference postes_couts_reference_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.postes_couts_reference
    ADD CONSTRAINT postes_couts_reference_code_key UNIQUE (code_poste_cout);


--
-- Name: postes_couts_reference postes_couts_reference_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.postes_couts_reference
    ADD CONSTRAINT postes_couts_reference_pkey PRIMARY KEY (id_poste_cout);


--
-- Name: postes_production postes_production_code_poste_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.postes_production
    ADD CONSTRAINT postes_production_code_poste_key UNIQUE (code_poste);


--
-- Name: postes_production postes_production_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.postes_production
    ADD CONSTRAINT postes_production_pkey PRIMARY KEY (id_poste);


--
-- Name: productions_journalieres prod_journ_date_site_article_serie_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.productions_journalieres
    ADD CONSTRAINT prod_journ_date_site_article_serie_key UNIQUE (date_production, id_site, id_article, numero_serie);


--
-- Name: productions_journalieres productions_journalieres_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.productions_journalieres
    ADD CONSTRAINT productions_journalieres_pkey PRIMARY KEY (id_production);


--
-- Name: resume_journalier resume_journalier_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.resume_journalier
    ADD CONSTRAINT resume_journalier_pkey PRIMARY KEY (id_resume);


--
-- Name: resume_journalier resume_journalier_reference_jour_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.resume_journalier
    ADD CONSTRAINT resume_journalier_reference_jour_key UNIQUE (reference_jour);


--
-- Name: resume_production_poisson resume_production_poisson_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.resume_production_poisson
    ADD CONSTRAINT resume_production_poisson_pkey PRIMARY KEY (id_resume_production);


--
-- Name: sites_production sites_production_code_site_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sites_production
    ADD CONSTRAINT sites_production_code_site_key UNIQUE (code_site);


--
-- Name: sites_production sites_production_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sites_production
    ADD CONSTRAINT sites_production_pkey PRIMARY KEY (id_site);


--
-- Name: table_codes table_codes_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.table_codes
    ADD CONSTRAINT table_codes_pkey PRIMARY KEY (id_code);


--
-- Name: types_poisson types_poisson_code_type_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.types_poisson
    ADD CONSTRAINT types_poisson_code_type_key UNIQUE (code_type);


--
-- Name: types_poisson types_poisson_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.types_poisson
    ADD CONSTRAINT types_poisson_pkey PRIMARY KEY (id_type_poisson);


--
-- Name: table_codes uq_codes_resume_article; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.table_codes
    ADD CONSTRAINT uq_codes_resume_article UNIQUE (id_resume, id_article);


--
-- Name: mod_global uq_mod_resume; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mod_global
    ADD CONSTRAINT uq_mod_resume UNIQUE (id_resume);


--
-- Name: mod_totaux_espece uq_mod_totaux_espece; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mod_totaux_espece
    ADD CONSTRAINT uq_mod_totaux_espece UNIQUE (date_production, id_site, id_type_poisson, code_total);


--
-- Name: resume_production_poisson uq_rpp; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.resume_production_poisson
    ADD CONSTRAINT uq_rpp UNIQUE (id_resume, id_type_poisson);


--
-- Name: idx_codes_alias_id_article; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_codes_alias_id_article ON public.codes_alias USING btree (id_article);


--
-- Name: idx_codes_non_resolus_resolu; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_codes_non_resolus_resolu ON public.codes_non_resolus USING btree (resolu);


--
-- Name: idx_ecarts_production; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_ecarts_production ON public.ecarts_couts_postes USING btree (id_production);


--
-- Name: idx_lots_date; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_lots_date ON public.lots_poisson USING btree (date_production);


--
-- Name: idx_lots_type; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_lots_type ON public.lots_poisson USING btree (id_type_poisson);


--
-- Name: idx_mod_communs_date; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_mod_communs_date ON public.mod_communs_journaliers USING btree (date_production);


--
-- Name: idx_mod_communs_site; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_mod_communs_site ON public.mod_communs_journaliers USING btree (id_site);


--
-- Name: idx_mod_durees_date; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_mod_durees_date ON public.mod_durees_espece_poste USING btree (date_production);


--
-- Name: idx_mod_durees_poste; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_mod_durees_poste ON public.mod_durees_espece_poste USING btree (id_poste);


--
-- Name: idx_mod_durees_site; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_mod_durees_site ON public.mod_durees_espece_poste USING btree (id_site);


--
-- Name: idx_mod_durees_type; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_mod_durees_type ON public.mod_durees_espece_poste USING btree (id_type_poisson);


--
-- Name: idx_prod_article; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_prod_article ON public.productions_journalieres USING btree (id_article);


--
-- Name: idx_prod_date; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_prod_date ON public.productions_journalieres USING btree (date_production);


--
-- Name: idx_prod_site; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_prod_site ON public.productions_journalieres USING btree (id_site);


--
-- Name: articles articles_id_client_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.articles
    ADD CONSTRAINT articles_id_client_fkey FOREIGN KEY (id_client) REFERENCES public.clients(id_client);


--
-- Name: articles articles_id_type_poisson_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.articles
    ADD CONSTRAINT articles_id_type_poisson_fkey FOREIGN KEY (id_type_poisson) REFERENCES public.types_poisson(id_type_poisson);


--
-- Name: codes_alias codes_alias_id_article_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.codes_alias
    ADD CONSTRAINT codes_alias_id_article_fkey FOREIGN KEY (id_article) REFERENCES public.articles(id_article) ON DELETE CASCADE;


--
-- Name: codes_non_resolus codes_non_resolus_id_resume_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.codes_non_resolus
    ADD CONSTRAINT codes_non_resolus_id_resume_fkey FOREIGN KEY (id_resume) REFERENCES public.resume_journalier(id_resume) ON DELETE CASCADE;


--
-- Name: couts_par_serie couts_par_serie_id_article_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.couts_par_serie
    ADD CONSTRAINT couts_par_serie_id_article_fkey FOREIGN KEY (id_article) REFERENCES public.articles(id_article);


--
-- Name: couts_par_serie couts_par_serie_id_resume_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.couts_par_serie
    ADD CONSTRAINT couts_par_serie_id_resume_fkey FOREIGN KEY (id_resume) REFERENCES public.resume_journalier(id_resume);


--
-- Name: couts_unitaires_code couts_unitaires_code_id_article_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.couts_unitaires_code
    ADD CONSTRAINT couts_unitaires_code_id_article_fkey FOREIGN KEY (id_article) REFERENCES public.articles(id_article);


--
-- Name: couts_unitaires_code couts_unitaires_code_id_resume_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.couts_unitaires_code
    ADD CONSTRAINT couts_unitaires_code_id_resume_fkey FOREIGN KEY (id_resume) REFERENCES public.resume_journalier(id_resume);


--
-- Name: ecarts_couts_postes ecarts_couts_postes_id_poste_cout_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ecarts_couts_postes
    ADD CONSTRAINT ecarts_couts_postes_id_poste_cout_fkey FOREIGN KEY (id_poste_cout) REFERENCES public.postes_couts_reference(id_poste_cout);


--
-- Name: ecarts_couts_postes ecarts_couts_postes_id_production_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ecarts_couts_postes
    ADD CONSTRAINT ecarts_couts_postes_id_production_fkey FOREIGN KEY (id_production) REFERENCES public.productions_journalieres(id_production) ON DELETE CASCADE;


--
-- Name: fiches_techniques fiches_techniques_id_article_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fiches_techniques
    ADD CONSTRAINT fiches_techniques_id_article_fkey FOREIGN KEY (id_article) REFERENCES public.articles(id_article);


--
-- Name: table_codes fk_codes_article; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.table_codes
    ADD CONSTRAINT fk_codes_article FOREIGN KEY (id_article) REFERENCES public.articles(id_article);


--
-- Name: table_codes fk_codes_resume; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.table_codes
    ADD CONSTRAINT fk_codes_resume FOREIGN KEY (id_resume) REFERENCES public.resume_journalier(id_resume) ON DELETE CASCADE;


--
-- Name: mod_global fk_mod_resume; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mod_global
    ADD CONSTRAINT fk_mod_resume FOREIGN KEY (id_resume) REFERENCES public.resume_journalier(id_resume) ON DELETE CASCADE;


--
-- Name: matiere_premiere fk_mp_resume; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.matiere_premiere
    ADD CONSTRAINT fk_mp_resume FOREIGN KEY (id_resume) REFERENCES public.resume_journalier(id_resume) ON DELETE CASCADE;


--
-- Name: resume_journalier fk_resume_site; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.resume_journalier
    ADD CONSTRAINT fk_resume_site FOREIGN KEY (id_site) REFERENCES public.sites_production(id_site);


--
-- Name: resume_production_poisson fk_rpp_resume; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.resume_production_poisson
    ADD CONSTRAINT fk_rpp_resume FOREIGN KEY (id_resume) REFERENCES public.resume_journalier(id_resume) ON DELETE CASCADE;


--
-- Name: resume_production_poisson fk_rpp_type_poisson; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.resume_production_poisson
    ADD CONSTRAINT fk_rpp_type_poisson FOREIGN KEY (id_type_poisson) REFERENCES public.types_poisson(id_type_poisson);


--
-- Name: lots_poisson lots_poisson_id_site_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lots_poisson
    ADD CONSTRAINT lots_poisson_id_site_fkey FOREIGN KEY (id_site) REFERENCES public.sites_production(id_site);


--
-- Name: lots_poisson lots_poisson_id_type_poisson_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lots_poisson
    ADD CONSTRAINT lots_poisson_id_type_poisson_fkey FOREIGN KEY (id_type_poisson) REFERENCES public.types_poisson(id_type_poisson);


--
-- Name: mod_communs_journaliers mod_communs_journaliers_id_site_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mod_communs_journaliers
    ADD CONSTRAINT mod_communs_journaliers_id_site_fkey FOREIGN KEY (id_site) REFERENCES public.sites_production(id_site);


--
-- Name: mod_durees_espece_poste mod_durees_espece_poste_id_poste_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mod_durees_espece_poste
    ADD CONSTRAINT mod_durees_espece_poste_id_poste_fkey FOREIGN KEY (id_poste) REFERENCES public.postes_production(id_poste);


--
-- Name: mod_durees_espece_poste mod_durees_espece_poste_id_site_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mod_durees_espece_poste
    ADD CONSTRAINT mod_durees_espece_poste_id_site_fkey FOREIGN KEY (id_site) REFERENCES public.sites_production(id_site);


--
-- Name: mod_durees_espece_poste mod_durees_espece_poste_id_type_poisson_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mod_durees_espece_poste
    ADD CONSTRAINT mod_durees_espece_poste_id_type_poisson_fkey FOREIGN KEY (id_type_poisson) REFERENCES public.types_poisson(id_type_poisson);


--
-- Name: mod_totaux_espece mod_totaux_espece_id_site_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mod_totaux_espece
    ADD CONSTRAINT mod_totaux_espece_id_site_fkey FOREIGN KEY (id_site) REFERENCES public.sites_production(id_site);


--
-- Name: mod_totaux_espece mod_totaux_espece_id_type_poisson_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mod_totaux_espece
    ADD CONSTRAINT mod_totaux_espece_id_type_poisson_fkey FOREIGN KEY (id_type_poisson) REFERENCES public.types_poisson(id_type_poisson);


--
-- Name: productions_journalieres productions_journalieres_id_article_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.productions_journalieres
    ADD CONSTRAINT productions_journalieres_id_article_fkey FOREIGN KEY (id_article) REFERENCES public.articles(id_article);


--
-- Name: productions_journalieres productions_journalieres_id_site_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.productions_journalieres
    ADD CONSTRAINT productions_journalieres_id_site_fkey FOREIGN KEY (id_site) REFERENCES public.sites_production(id_site);


--
-- Name: resume_journalier resume_journalier_id_type_poisson_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.resume_journalier
    ADD CONSTRAINT resume_journalier_id_type_poisson_fkey FOREIGN KEY (id_type_poisson) REFERENCES public.types_poisson(id_type_poisson);


--
-- PostgreSQL database dump complete
--

\unrestrict YkCtqYhYacWXZhmjfrllfzD25srjg9NRzGhFi8P6ZfVguOCEIfnKp5AXSfrbv6H

