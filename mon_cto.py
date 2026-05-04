import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
import requests

# Configuration de la page
st.set_page_config(layout="wide", page_title="Tableau de bord financier")

# 🔗 L'ID DE TON GOOGLE SHEET
ID_SHEET = "14sSa2p27u2oY9EsJxaNP6CFX4HUznYJojnPprI6vDBY"

# ==========================================
# 🎨 STYLE CSS (COMPATIBLE LIGHT MODE & DARK MODE)
# ==========================================
st.markdown("""
<style>
    /* Fond de l'application (S'adapte automatiquement au thème clair/sombre) */
    [data-testid="stAppViewContainer"] {
        background-color: var(--secondary-background-color);
    }
    
    /* Encadrement des métriques et des containers (Boîtes/Cartes) */
    [data-testid="stMetric"], [data-testid="metric-container"], 
    [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: var(--background-color) !important;
        border: 1px solid var(--secondary-background-color) !important;
        border-radius: 15px !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05) !important;
    }
    
    /* Padding spécifique pour les métriques */
    [data-testid="stMetric"], [data-testid="metric-container"] {
        padding: 20px !important;
    }
    
    /* Textes des métriques (Gris doux) */
    [data-testid="stMetricLabel"], [data-testid="stMetric"] label, [data-testid="metric-container"] label {
        color: #808495 !important;
        font-size: 14px !important;
        font-weight: 600 !important;
        margin-bottom: 5px !important;
    }
    
    /* Chiffres des métriques (Prend la couleur par défaut selon le mode) */
    [data-testid="stMetricValue"] {
        font-size: 26px !important;
        font-weight: 700 !important;
    }

    /* Ajustement des titres de section */
    h1 {
        font-weight: 600 !important;
        margin-bottom: 20px !important;
    }
    h3 {
        font-weight: 500 !important;
        margin-top: 10px !important;
        margin-bottom: 15px !important;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🛡️ MOTEUR DE COURS "TIR GROUPÉ" (ANTI-BLOCAGE)
# ==========================================
@st.cache_data(ttl=900, show_spinner=False)
def get_market_data(liste_tickers):
    """Télécharge TOUTES les actions en 1 seule requête HTTP directe pour éviter le blocage."""
    resultats = {}
    if not liste_tickers: 
        return resultats
    
    # On nettoie la liste et on ajoute EUR=X pour le taux de conversion USD/EUR
    tickers_propres = [str(t).upper().strip() for t in liste_tickers]
    tickers_api = list(set(tickers_propres)) + ["EUR=X"]
    tickers_str = ",".join(tickers_api)
    
    # Appel direct à l'API cachée de Yahoo (1 seule requête pour tout le portefeuille)
    url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={tickers_str}"
    
    # On se fait passer pour un navigateur classique
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json().get("quoteResponse", {}).get("result", [])
        
        # 1. Isoler le taux de change
        taux_usd_eur = 0.92
        for item in data:
            if item.get("symbol") == "EUR=X":
                taux_usd_eur = item.get("regularMarketPrice", 0.92)
        
        # 2. Extraire les données des actions
        for item in data:
            sym = item.get("symbol")
            if sym == "EUR=X": 
                continue
            
            devise = item.get("currency", "EUR")
            coef = taux_usd_eur if devise == "USD" else 1
            
            nom_complet = item.get("shortName", item.get("longName", sym))
            
            resultats[sym] = {
                "Nom": nom_complet,
                "Prix": item.get("regularMarketPrice", 0.0) * coef,
                "Div": item.get("trailingAnnualDividendRate", 0.0) * coef,
                "Objectif": item.get("targetMeanPrice", 0.0) * coef,
                "Erreur": False
            }
    except Exception as e:
        pass
        
    # Sécurité : Si une action n'a pas été trouvée, on met des 0 au lieu de faire planter
    for t in tickers_propres:
        if t not in resultats:
            resultats[t] = {"Nom": t, "Prix": 0.0, "Div": 0.0, "Objectif": 0.0, "Erreur": True}
            
    return resultats

# ==========================================
# 1. FONCTIONS DE CONNEXION GOOGLE SHEETS
# ==========================================
@st.cache_resource
def connecter_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds).open_by_key(ID_SHEET)

def charger_donnees():
    try:
        sheet = connecter_client().get_worksheet(0)
        data = sheet.get_all_records(value_render_option='UNFORMATTED_VALUE')
        if not data: return []
        df_sheet = pd.DataFrame(data)
        df_sheet.columns = df_sheet.columns.str.strip()
        for col in ["Quantité", "PRU"]:
            if col in df_sheet.columns:
                df_sheet[col] = pd.to_numeric(df_sheet[col].astype(str).str.replace(',', '.'), errors='coerce')
        return df_sheet.dropna(subset=["Ticker"]).to_dict('records')
    except Exception as e:
        st.error(f"Erreur de lecture Portefeuille : {e}")
        return []

def charger_transactions():
    try:
        sheet = connecter_client().worksheet("Transactions")
        data = sheet.get_all_records(value_render_option='UNFORMATTED_VALUE')
        df = pd.DataFrame(data)
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        return pd.DataFrame()

def sauvegarder_donnees(portefeuille):
    try:
        df = pd.DataFrame(portefeuille)
        sheet = connecter_client().get_worksheet(0)
        sheet.clear()
        sheet.update([df.columns.values.tolist()] + df.values.tolist())
    except Exception as e:
        st.error(f"Erreur de sauvegarde : {e}")

def sauvegarder_transactions(df_trans):
    try:
        sheet = connecter_client().worksheet("Transactions")
        sheet.clear()
        sheet.update([df_trans.columns.values.tolist()] + df_trans.values.tolist())
        st.success("Historique mis à jour.")
    except Exception as e:
        st.error(f"Erreur de sauvegarde Transactions : {e}")

def ajouter_transaction(date, t_type, ticker, qte, prix, frais, compte):
    try:
        sheet = connecter_client().worksheet("Transactions")
        sheet.append_row([date, t_type, ticker.upper(), qte, prix, frais, compte])
        return True
    except Exception as e:
        st.error(f"Erreur d'ajout : {e}")
        return False

def style_plus_value(val):
    if pd.isna(val): return ''
    if val > 0: return 'color: #1e8e3e; font-weight: bold'
    elif val < 0: return 'color: #d93025; font-weight: bold'
    return ''

# ==========================================
# 2. VARIABLES GLOBALES & SÉCURITÉ
# ==========================================
LISTE_COMPTES = ["CTO", "PEA", "Crypto", "Espèce", "Autre"]
LISTE_MOTIFS = ["ACHAT", "VENTE", "DIVIDENDE", "PAIEMENT", "DÉPÔT", "RETRAIT"]

st.sidebar.header("Accès sécurisé")
mot_de_passe_saisi = st.sidebar.text_input("Mot de passe pour modifier", type="password")

try:
    est_autorise = (mot_de_passe_saisi == st.secrets["APP_PASSWORD"])
except:
    est_autorise = False
    st.sidebar.error("Clé 'APP_PASSWORD' manquante.")

st.sidebar.divider()
page = st.sidebar.radio("Navigation", ["Tableau de bord", "Journal des opérations", "Bilan comptable"])

# ==========================================
# PAGE 1 : TABLEAU DE BORD
# ==========================================
if page == "Tableau de bord":
    st.title("Mon portefeuille")
    
    if 'portefeuille' not in st.session_state:
        st.session_state.portefeuille = charger_donnees()

    if st.sidebar.button("Actualiser les données"):
        st.cache_data.clear()
        st.session_state.portefeuille = charger_donnees()
        st.rerun()

    if est_autorise:
        with st.sidebar.form("ajout_form"):
            st.write("Ajouter une ligne")
            c = st.selectbox("Compte", LISTE_COMPTES)
            t = st.text_input("Ticker")
            q = st.text_input("Quantité", value="0")
            p = st.text_input("PRU", value="0")
            if st.form_submit_button("Ajouter"):
                try:
                    nouvelle = {"Compte": c, "Ticker": t.upper(), "Quantité": float(q.replace(',','.')), "PRU": float(p.replace(',','.'))}
                    st.session_state.portefeuille.append(nouvelle)
                    sauvegarder_donnees(st.session_state.portefeuille)
                    st.rerun()
                except: st.error("Erreur de format")

    if est_autorise:
        with st.expander("Éditer les positions actives (Modifier ou Supprimer)"):
            df_base = pd.DataFrame(st.session_state.portefeuille)
            if df_base.empty: 
                df_base = pd.DataFrame(columns=["Compte", "Ticker", "Quantité", "PRU"])
            df_modifie = st.data_editor(df_base, num_rows="dynamic", use_container_width=True, hide_index=True, key="editeur")
            if not df_base.equals(df_modifie):
                st.session_state.portefeuille = df_modifie.to_dict('records')
                sauvegarder_donnees(st.session_state.portefeuille)
                st.rerun()

    if not st.session_state.portefeuille:
        st.info("Portefeuille vide.")
    else:
        df = pd.DataFrame(st.session_state.portefeuille)
        
        with st.spinner("Récupération des cours boursiers..."):
            infos_marche = get_market_data(df["Ticker"].tolist())
            
            cours_actuels, dividendes, objectifs, noms = [], [], [], []
            
            for ticker in df["Ticker"]:
                sym = str(ticker).upper().strip()
                info = infos_marche[sym]
                
                if info["Erreur"]:
                    st.toast(f"Impossible d'actualiser {sym}")
                    
                noms.append(info["Nom"])
                cours_actuels.append(info["Prix"])
                dividendes.append(info["Div"])
                objectifs.append(info["Objectif"])

        df["Nom"] = noms
        df["Cours Actuel (€)"] = cours_actuels
        df["Valeur Investie (€)"] = df["Quantité"] * df["PRU"]
        df["Valeur Actuelle (€)"] = df["Quantité"] * df["Cours Actuel (€)"]
        
        df["Plus-Value (€)"] = df["Valeur Actuelle (€)"] - df["Valeur Investie (€)"]
        df["Plus-Value (%)"] = ((df["Plus-Value (€)"] / df["Valeur Investie (€)"] * 100) if (df["Valeur Investie (€)"].sum() > 0) else 0).fillna(0)
        
        t_inv, t_act = df["Valeur Investie (€)"].sum(), df["Valeur Actuelle (€)"].sum()
        df["Poids (%)"] = (df["Valeur Actuelle (€)"] / t_act * 100).fillna(0)

        df["Rente Annuelle (€)"] = df["Quantité"] * dividendes
        df["Objectif (€)"] = objectifs
        df["Potentiel (%)"] = df.apply(lambda r: ((r["Objectif (€)"] - r["Cours Actuel (€)"]) / r["Cours Actuel (€)"] * 100) if r["Objectif (€)"] > 0 else 0, axis=1)
        df["Potentiel / PRU (%)"] = df.apply(lambda r: ((r["Objectif (€)"] - r["PRU"]) / r["PRU"] * 100) if r["Objectif (€)"] > 0 and r["PRU"] > 0 else 0, axis=1)

        # --- CARTES KPI ---
        c1, c2, c3 = st.columns(3)
        c1.metric("Valorisation actuelle", f"{t_act:,.2f} €".replace(',', ' '))
        c2.metric("Montant investi", f"{t_inv:,.2f} €".replace(',', ' '))
        c3.metric("Plus-value latente", f"{(t_act-t_inv):,.2f} €".replace(',', ' '), f"{((t_act/t_inv-1)*100 if t_inv>0 else 0):.2f} %")
        
        st.write("") 
        
        total_div = df["Rente Annuelle (€)"].sum()
        c4, c5, c6 = st.columns(3)
        c4.metric("Revenu annuel estimé", f"{total_div:,.2f} €".replace(',', ' '))
        c5.metric("Moyenne mensuelle", f"{(total_div / 12):,.2f} €".replace(',', ' '))
        c6.metric("Rendement sur PRU", f"{(total_div / t_inv * 100 if t_inv > 0 else 0):.2f} %")
        
        st.write("")

        # --- TABLEAU ENCAPSULÉ ---
        with st.container(border=True):
            st.markdown("### Détail des positions")
            f1, f2, f3 = st.columns([2, 1, 1])
            rech = f1.text_input("Rechercher un actif", placeholder="Ex: LVMH, AI.PA...")
            f_cpte = f2.selectbox("Filtrer Compte", ["Tous"] + LISTE_COMPTES)
            f_perf = f3.selectbox("Statut performance", ["Toutes", "Gagnantes", "Perdantes"])

            df_f = df.copy()
            if rech: df_f = df_f[df_f["Ticker"].str.contains(rech, case=False) | df_f["Nom"].str.contains(rech, case=False)]
            if f_cpte != "Tous": df_f = df_f[df_f["Compte"] == f_cpte]
            if f_perf == "Gagnantes": df_f = df_f[df_f["Plus-Value (€)"] > 0]
            elif f_perf == "Perdantes": df_f = df_f[df_f["Plus-Value (€)"] < 0]

            cols_tab = ["Compte", "Ticker", "Nom", "Quantité", "PRU", "Cours Actuel (€)", "Objectif (€)", "Potentiel (%)", "Potentiel / PRU (%)", "Valeur Actuelle (€)", "Plus-Value (€)", "Plus-Value (%)", "Poids (%)", "Rente Annuelle (€)"]
            
            st.dataframe(df_f[cols_tab].style.format({
                "Quantité": "{:.4f}", "PRU": "{:.2f} €", "Cours Actuel (€)": "{:.2f} €", "Objectif (€)": "{:.2f} €",
                "Potentiel (%)": "{:.2f} %", "Potentiel / PRU (%)": "{:.2f} %", "Valeur Actuelle (€)": "{:.2f} €",
                "Plus-Value (€)": "{:.2f} €", "Plus-Value (%)": "{:.2f} %", "Poids (%)": "{:.1f} %", "Rente Annuelle (€)": "{:.2f} €"
            }).map(style_plus_value, subset=['Plus-Value (€)', 'Plus-Value (%)', 'Potentiel (%)', 'Potentiel / PRU (%)']), 
            use_container_width=True, hide_index=True)

        # --- GRAPHIQUES ---
        g1, g2 = st.columns(2)
        with g1:
            with st.container(border=True):
                st.markdown("### Répartition par actif")
                fig_pie = px.sunburst(df_f, path=['Compte', 'Ticker'], values='Valeur Actuelle (€)')
                fig_pie.update_layout(height=380, margin=dict(t=10, l=10, r=10, b=10), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_pie, use_container_width=True)
        with g2:
            with st.container(border=True):
                st.markdown("### Gains et pertes par ligne")
                df_b = df_f.sort_values("Plus-Value (€)", ascending=False)
                fig_bar = px.bar(df_b, x="Ticker", y="Plus-Value (€)", color=df_b["Plus-Value (€)"] >= 0, 
                             color_discrete_map={True: "#1e8e3e", False: "#d93025"}, text_auto='.0f')
                fig_bar.update_layout(height=380, showlegend=False, xaxis_title="", margin=dict(t=10, l=10, r=10, b=10), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_bar, use_container_width=True)

# ==========================================
# PAGE 2 : HISTORIQUE
# ==========================================
elif page == "Journal des opérations":
    st.title("Journal des opérations")
    if est_autorise:
        with st.container(border=True):
            with st.form("t_form", clear_on_submit=True):
                st.markdown("### Enregistrer une nouvelle transaction")
                ca, cb, cc = st.columns(3)
                dt = ca.date_input("Date de la transaction")
                mt = cb.selectbox("Type d'opération", LISTE_MOTIFS)
                tk = cc.text_input("Symbole (ou 'CASH')")
                cd, ce, cf = st.columns(3)
                qt = cd.text_input("Quantité", "0")
                px_u = ce.text_input("Prix Unitaire (€)", "0")
                fr = cf.text_input("Frais de courtage (€)", "0")
                cp = st.selectbox("Compte impacté", LISTE_COMPTES)
                if st.form_submit_button("Valider la transaction"):
                    ajouter_transaction(dt.strftime("%d/%m/%Y"), mt, tk.upper(), float(qt.replace(',','.')), float(px_u.replace(',','.')), float(fr.replace(',','.')), cp)
                    st.rerun()

    df_t = charger_transactions()
    if not df_t.empty:
        with st.container(border=True):
            st.markdown("### Historique complet")
            r = st.text_input("Filtrer l'historique", placeholder="Chercher un ticker, une date, un motif...")
            df_ta = df_t.copy()
            if r:
                mask = df_ta.astype(str).apply(lambda x: x.str.contains(r, case=False)).any(axis=1)
                df_ta = df_ta[mask]
            
            if est_autorise and not r:
                st.info("Vous pouvez éditer ou supprimer une ligne directement dans le tableau ci-dessous.")
                df_mod = st.data_editor(df_ta, num_rows="dynamic", use_container_width=True, hide_index=True)
                if not df_ta.equals(df_mod):
                    sauvegarder_transactions(df_mod); st.rerun()
            elif est_autorise and r:
                st.caption("Mode édition désactivé pendant la recherche.")
                st.dataframe(df_ta, use_container_width=True, hide_index=True)
            else:
                st.dataframe(df_ta, use_container_width=True, hide_index=True)

# ==========================================
# PAGE 3 : BILAN COMPTABLE
# ==========================================
elif page == "Bilan comptable":
    st.title("Bilan de performance globale")
    df_t = charger_transactions()
    if not df_t.empty:
        for c in ["Quantité", "Prix", "Frais"]: 
            df_t[c] = pd.to_numeric(df_t[c].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
        
        df_c = df_t[df_t["Ticker"].str.upper() == "CASH"]
        dep = df_c[df_c["Type"] == "DÉPÔT"]["Prix"].sum()
        ret = df_c[df_c["Type"].isin(["RETRAIT", "PAIEMENT"])]["Prix"].sum()
        net_injecte = dep - ret
        
        st.markdown("### Flux de trésorerie")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Dépôts totaux", f"{dep:,.2f} €".replace(',', ' '))
        k2.metric("Retraits / Impôts", f"- {ret:,.2f} €".replace(',', ' '))
        k3.metric("Capital Net Injecté", f"{net_injecte:,.2f} €".replace(',', ' '))
        k4.metric("Frais de courtage", f"{df_t['Frais'].sum():,.2f} €".replace(',', ' '))
        
        st.write("")
        
        df_a = df_t[df_t["Ticker"].str.upper() != "CASH"]
        if not df_a.empty:
            rec = []
            with st.spinner("Calcul des performances..."):
                tickers_actifs = df_a["Ticker"].unique().tolist()
                infos_marche = get_market_data(tickers_actifs)
                
                for t in tickers_actifs:
                    sym = str(t).upper().strip()
                    dft = df_a[df_a["Ticker"] == t]
                    ach = dft[dft["Type"] == "ACHAT"]
                    ven = dft[dft["Type"] == "VENTE"]
                    div = dft[dft["Type"] == "DIVIDENDE"]
                    
                    v_ach = (ach["Quantité"] * ach["Prix"]).sum()
                    v_ven = (ven["Quantité"] * ven["Prix"]).sum()
                    v_div = div.apply(lambda r: (r["Quantité"] * r["Prix"]) if r["Quantité"] > 1 else r["Prix"], axis=1).sum()
                    sq = ach["Quantité"].sum() - ven["Quantité"].sum()
                    frais_tot = dft["Frais"].sum()
                    
                    info = infos_marche[sym]
                    nom_entreprise = info["Nom"]
                    prix_act = info["Prix"] if sq > 0.0001 else 0.0
                    
                    val = sq * prix_act
                    pnl = (val + v_ven + v_div) - (v_ach + frais_tot)
                    pnl_pct = (pnl / v_ach * 100) if v_ach > 0 else 0
                    
                    rec.append({
                        "Ticker": t, "Nom": nom_entreprise, "Solde Actions": sq, "Acheté (€)": v_ach,
                        "Vendu (€)": v_ven, "Dividendes (€)": v_div, "Frais (€)": frais_tot,
                        "Valeur Actuelle (€)": val, "Gain / Perte Total (€)": pnl, "Rentabilité (%)": pnl_pct
                    })
            
            df_recap = pd.DataFrame(rec)
            
            st.markdown("### Résultat net d'investissement")
            tot_pnl = df_recap["Gain / Perte Total (€)"].sum()
            tot_achete = df_recap["Acheté (€)"].sum()
            tot_pnl_pct = (tot_pnl / tot_achete * 100) if tot_achete > 0 else 0
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Plus-value globale nette", f"{tot_pnl:,.2f} €".replace(',', ' '))
            m2.metric("Rentabilité pondérée", f"{tot_pnl_pct:.2f} %")
            m3.metric("Dividendes encaissés", f"{df_recap['Dividendes (€)'].sum():,.2f} €".replace(',', ' '))
            
            st.write("")
            
            with st.container(border=True):
                st.markdown("### Analyse détaillée par actif")
                fb1, fb2 = st.columns([2, 1])
                recherche_bilan = fb1.text_input("Rechercher un actif", placeholder="Ex: AMZN, LVMH...", key="rech_bilan")
                filtre_perf_bilan = fb2.selectbox("Statut performance", ["Toutes", "Gagnantes", "Perdantes"], key="perf_bilan")

                df_recap_filtre = df_recap.copy()
                if recherche_bilan:
                    mask_bilan = df_recap_filtre.astype(str).apply(lambda x: x.str.contains(recherche_bilan, case=False)).any(axis=1)
                    df_recap_filtre = df_recap_filtre[mask_bilan]
                    
                if filtre_perf_bilan == "Gagnantes":
                    df_recap_filtre = df_recap_filtre[df_recap_filtre["Gain / Perte Total (€)"] > 0]
                elif filtre_perf_bilan == "Perdantes":
                    df_recap_filtre = df_recap_filtre[df_recap_filtre["Gain / Perte Total (€)"] < 0]

                st.dataframe(df_recap_filtre.style.format({
                    "Solde Actions": "{:.4f}", "Acheté (€)": "{:.2f} €", "Vendu (€)": "{:.2f} €", "Dividendes (€)": "{:.2f} €",
                    "Frais (€)": "{:.2f} €", "Valeur Actuelle (€)": "{:.2f} €", "Gain / Perte Total (€)": "{:.2f} €", "Rentabilité (%)": "{:.2f} %"
                }).map(style_plus_value, subset=['Gain / Perte Total (€)', 'Rentabilité (%)']), 
                use_container_width=True, hide_index=True)
