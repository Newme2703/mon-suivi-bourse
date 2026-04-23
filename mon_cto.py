import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# Configuration de la page
st.set_page_config(layout="wide", page_title="Tableau de bord financier")

# 🔗 L'ID DE TON GOOGLE SHEET
ID_SHEET = "14sSa2p27u2oY9EsJxaNP6CFX4HUznYJojnPprI6vDBY"

# ==========================================
# 🎨 STYLE CSS (INDIVIDUAL WHITE CARDS DESIGN)
# ==========================================
st.markdown("""
<style>
    /* 1. Fond global de l'application (Gris clair moderne) */
    [data-testid="stAppViewContainer"] {
        background-color: #f0f2f5;
    }

    /* 2. TRANSFORMATION DES METRICS EN CASES BLANCHES INDIVIDUELLES */
    /* On cible le conteneur spécifique de chaque métrique */
    div[data-testid="metric-container"] {
        background-color: #ffffff !important;
        border: 1px solid #e0e4e8 !important;
        padding: 25px !important;
        border-radius: 16px !important; /* Bords très arrondis */
        box-shadow: 0 4px 15px rgba(0,0,0,0.05) !important; /* Ombre douce pour le relief */
        text-align: center;
    }

    /* Style du libellé (ex: Valorisation actuelle) */
    div[data-testid="metric-container"] label {
        color: #65676b !important;
        font-size: 15px !important;
        font-weight: 500 !important;
        margin-bottom: 8px !important;
    }

    /* Style du chiffre principal */
    div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
        color: #1c1e21 !important;
        font-size: 28px !important;
        font-weight: 700 !important;
    }

    /* 3. Style pour les blocs de graphiques et tableaux */
    [data-testid="stPlotlyChart"], [data-testid="stDataFrame"], [data-testid="stDataEditor"] {
        background-color: #ffffff;
        border: 1px solid #e0e4e8;
        padding: 20px;
        border-radius: 16px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05);
    }

    /* 4. Nettoyage des titres et espacements */
    h1 {
        font-weight: 700 !important;
        color: #1c1e21 !important;
        margin-bottom: 30px !important;
    }
    
    h3 {
        font-weight: 600 !important;
        color: #4b4f56 !important;
        margin-top: 40px !important;
        margin-bottom: 20px !important;
    }

    /* Suppression des lignes de séparation par défaut pour un look plus aéré */
    hr {
        margin: 2em 0 !important;
        background-color: transparent !important;
        border: none !important;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. FONCTIONS DE CONNEXION ET CHARGEMENT
# ==========================================
@st.cache_resource
def connecter_client():
    """Initialise la connexion avec Google Sheets."""
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds).open_by_key(ID_SHEET)

def charger_donnees():
    """Charge les données de l'onglet Portefeuille."""
    try:
        sheet = connecter_client().get_worksheet(0)
        data = sheet.get_all_records(value_render_option='UNFORMATTED_VALUE')
        if not data: 
            return []
        
        df_sheet = pd.DataFrame(data)
        for col in ["Quantité", "PRU"]:
            if col in df_sheet.columns:
                df_sheet[col] = pd.to_numeric(df_sheet[col].astype(str).str.replace(',', '.'), errors='coerce')
                
        return df_sheet.dropna(subset=["Ticker"]).to_dict('records')
    except Exception as e:
        st.error(f"Erreur de lecture : {e}")
        return []

def sauvegarder_donnees(portefeuille):
    """Met à jour l'onglet Portefeuille sur Google Sheets."""
    try:
        df = pd.DataFrame(portefeuille)
        sheet = connecter_client().get_worksheet(0)
        sheet.clear()
        sheet.update([df.columns.values.tolist()] + df.values.tolist())
    except Exception as e:
        st.error(f"Erreur de sauvegarde : {e}")

def charger_transactions():
    """Charge les données de l'onglet Transactions."""
    try:
        sheet = connecter_client().worksheet("Transactions")
        data = sheet.get_all_records(value_render_option='UNFORMATTED_VALUE')
        return pd.DataFrame(data)
    except Exception as e:
        return pd.DataFrame()

def sauvegarder_transactions(df_trans):
    """Met à jour l'onglet Transactions sur Google Sheets."""
    try:
        sheet = connecter_client().worksheet("Transactions")
        sheet.clear()
        df_save = df_trans.copy()
        sheet.update([df_save.columns.values.tolist()] + df_save.values.tolist())
        st.success("Historique sauvegardé.")
    except Exception as e:
        st.error(f"Erreur de sauvegarde : {e}")

def ajouter_transaction(date, t_type, ticker, qte, prix, frais, compte):
    """Ajoute une transaction unique au journal."""
    try:
        sheet = connecter_client().worksheet("Transactions")
        sheet.append_row([date, t_type, ticker.upper(), qte, prix, frais, compte])
        return True
    except Exception as e:
        st.error(f"Erreur d'ajout : {e}")
        return False

def style_plus_value(val):
    """Définit la couleur des gains (vert) et pertes (rouge)."""
    if pd.isna(val): return ''
    if val > 0: return 'color: #00873c; font-weight: bold' 
    elif val < 0: return 'color: #eb4034; font-weight: bold'
    return 'color: #65676b'

# ==========================================
# 2. VARIABLES ET SÉCURITÉ
# ==========================================
LISTE_COMPTES = ["CTO", "PEA", "Crypto", "Espèce", "Autre"]
LISTE_MOTIFS = ["ACHAT", "VENTE", "DIVIDENDE", "PAIEMENT", "DÉPÔT", "RETRAIT"]

st.sidebar.header("Administration")
mot_de_passe_saisi = st.sidebar.text_input("Mot de passe", type="password")

try:
    est_autorise = (mot_de_passe_saisi == st.secrets["APP_PASSWORD"])
except:
    est_autorise = False
    st.sidebar.error("Configuration 'APP_PASSWORD' manquante.")

st.sidebar.divider()
page = st.sidebar.radio("Navigation", [
    "Tableau de bord", 
    "Journal des opérations", 
    "Bilan de performance"
])

# ==========================================
# PAGE 1 : TABLEAU DE BORD
# ==========================================
if page == "Tableau de bord":
    st.title("Tableau de bord")
    
    if 'portefeuille' not in st.session_state:
        st.session_state.portefeuille = charger_donnees()

    if st.sidebar.button("Actualiser les cours"):
        st.session_state.portefeuille = charger_donnees()
        st.rerun()

    if est_autorise:
        with st.sidebar.form("form_ajout"):
            st.write("Ajouter un actif")
            cpte = st.selectbox("Compte", LISTE_COMPTES)
            tk = st.text_input("Ticker")
            qt = st.text_input("Quantité", value="0")
            pru = st.text_input("PRU", value="0")
            if st.form_submit_button("Ajouter"):
                try:
                    nouvelle_ligne = {
                        "Compte": cpte, "Ticker": tk.upper(),
                        "Quantité": float(qt.replace(',','.')),
                        "PRU": float(pru.replace(',','.'))
                    }
                    st.session_state.portefeuille.append(nouvelle_ligne)
                    sauvegarder_donnees(st.session_state.portefeuille)
                    st.rerun()
                except: st.error("Erreur de format.")

    if not st.session_state.portefeuille:
        st.info("Le portefeuille est vide.")
    else:
        df = pd.DataFrame(st.session_state.portefeuille)
        
        with st.spinner("Récupération des données marché..."):
            try: taux_usd_eur = yf.Ticker("EUR=X").history(period="1d")['Close'].iloc[-1]
            except: taux_usd_eur = 0.92
                
            cours_actuels, dividendes, noms = [], [], []
            for ticker in df["Ticker"]:
                try:
                    t_str = str(ticker).upper()
                    data = yf.Ticker(t_str)
                    noms.append(data.info.get('shortName', t_str))
                    prix = data.history(period="1d")['Close'].iloc[-1]
                    dev = data.fast_info.get("currency", "EUR")
                    coef = taux_usd_eur if dev == "USD" else 1
                    cours_actuels.append(prix * coef)
                    dividendes.append((data.info.get('dividendRate', 0) or 0) * coef)
                except:
                    noms.append(str(ticker)); cours_actuels.append(0); dividendes.append(0)

        df["Nom"], df["Cours"] = noms, cours_actuels
        df["Total Investi"] = df["Quantité"] * df["PRU"]
        df["Valeur Actuelle"] = df["Quantité"] * df["Cours"]
        df["Gains (€)"] = df["Valeur Actuelle"] - df["Total Investi"]
        df["Gains (%)"] = (df["Gains (€)"] / df["Total Investi"] * 100).fillna(0)
        
        val_totale = df["Valeur Actuelle"].sum()
        inv_total = df["Total Investi"].sum()
        df["Poids (%)"] = (df["Valeur Actuelle"] / val_totale * 100).fillna(0)
        df["Dividende Annuel"] = df["Quantité"] * dividendes

        # -----------------------------
        # SECTION 1 : CHIFFRES CLES (CASES BLANCHES)
        # -----------------------------
        st.subheader("Synthèse globale")
        c1, c2, c3 = st.columns(3)
        # Chaque metric sera dans sa case blanche individuelle grâce au CSS
        c1.metric("Valorisation actuelle", f"{val_totale:,.2f} €".replace(',', ' '))
        c2.metric("Montant investi", f"{inv_total:,.2f} €".replace(',', ' '))
        c3.metric("Plus-value latente", f"{(val_totale - inv_total):,.2f} €".replace(',', ' '), 
                  f"{((val_totale/inv_total-1)*100 if inv_total>0 else 0):.2f} %")
        
        st.subheader("Dividendes")
        div_total = df["Dividende Annuel"].sum()
        c4, c5, c6 = st.columns(3)
        c4.metric("Revenu annuel estimé", f"{div_total:,.2f} €".replace(',', ' '))
        c5.metric("Moyenne mensuelle", f"{(div_total / 12):,.2f} €".replace(',', ' '))
        c6.metric("Rendement sur PRU", f"{(div_total / inv_total * 100 if inv_total > 0 else 0):.2f} %")

        # -----------------------------
        # SECTION 2 : TABLEAU DÉTAILLÉ
        # -----------------------------
        st.subheader("Détail des positions")
        f1, f2, f3 = st.columns([2, 1, 1])
        rech = f1.text_input("Filtrer par nom ou symbole", placeholder="Rechercher...")
        f_cpte = f2.selectbox("Compte", ["Tous"] + LISTE_COMPTES)
        f_perf = f3.selectbox("Performance", ["Toutes", "Gagnantes", "Perdantes"])

        df_f = df.copy()
        if rech: 
            df_f = df_f[df_f["Ticker"].str.contains(rech, case=False) | df_f["Nom"].str.contains(rech, case=False)]
        if f_cpte != "Tous": 
            df_f = df_f[df_f["Compte"] == f_cpte]
        if f_perf == "Gagnantes": 
            df_f = df_f[df_f["Gains (€)"] > 0]
        elif f_perf == "Perdantes": 
            df_f = df_f[df_f["Gains (€)"] < 0]

        colonnes = ["Compte", "Ticker", "Nom", "Quantité", "PRU", "Cours", "Valeur Actuelle", "Gains (€)", "Gains (%)", "Poids (%)", "Dividende Annuel"]
        
        st.dataframe(df_f[colonnes].style.format({
            "Quantité": "{:.4f}", "PRU": "{:.2f} €", "Cours": "{:.2f} €", "Valeur Actuelle": "{:.2f} €",
            "Gains (€)": "{:.2f} €", "Gains (%)": "{:.2f} %", "Poids (%)": "{:.1f} %", "Dividende Annuel": "{:.2f} €"
        }).map(style_plus_value, subset=['Gains (€)', 'Gains (%)']), use_container_width=True, hide_index=True)

        # -----------------------------
        # SECTION 3 : GRAPHIQUES
        # -----------------------------
        st.subheader("Analyse graphique")
        g1, g2 = st.columns(2)
        with g1:
            st.plotly_chart(px.sunburst(df_f, path=['Compte', 'Ticker'], values='Valeur Actuelle', 
                                        title="Répartition du capital", color_discrete_sequence=px.colors.qualitative.Pastel), use_container_width=True)
        with g2:
            df_b = df_f.sort_values("Gains (€)", ascending=False)
            fig = px.bar(df_b, x="Ticker", y="Gains (€)", color=df_b["Gains (€)"] >= 0, 
                         title="Gains et pertes par ligne",
                         color_discrete_map={True: "#00873c", False: "#eb4034"}, text_auto='.0f')
            fig.update_layout(showlegend=False, xaxis_title="", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)

# ==========================================
# PAGE 2 : JOURNAL DES OPÉRATIONS
# ==========================================
elif page == "Journal des opérations":
    st.title("Journal des opérations")
    
    if est_autorise:
        with st.expander("Enregistrer une transaction"):
            with st.form("form_trans"):
                ca, cb, cc = st.columns(3)
                d_t = ca.date_input("Date")
                m_t = cb.selectbox("Type", LISTE_MOTIFS)
                tk_t = cc.text_input("Symbole")
                cd, ce, cf = st.columns(3)
                q_t = cd.text_input("Quantité", "0")
                p_t = ce.text_input("Prix", "0")
                f_t = cf.text_input("Frais", "0")
                c_t = st.selectbox("Compte", LISTE_COMPTES)
                if st.form_submit_button("Valider"):
                    ajouter_transaction(d_t.strftime("%d/%m/%Y"), m_t, tk_t.upper(), float(q_t.replace(',','.')), float(p_t.replace(',','.')), float(f_t.replace(',','.')), c_t)
                    st.rerun()

    df_t = charger_transactions()
    if not df_t.empty:
        r_t = st.text_input("Filtrer l'historique", placeholder="Ticker, date...")
        df_ta = df_t.copy()
        if r_t:
            mask = df_ta.astype(str).apply(lambda x: x.str.contains(r_t, case=False)).any(axis=1)
            df_ta = df_ta[mask]
        
        if est_autorise and not r_t:
            df_mod = st.data_editor(df_ta, num_rows="dynamic", use_container_width=True, hide_index=True)
            if not df_ta.equals(df_mod):
                sauvegarder_transactions(df_mod); st.rerun()
        else:
            st.dataframe(df_ta, use_container_width=True, hide_index=True)

# ==========================================
# PAGE 3 : BILAN COMPTABLE
# ==========================================
elif page == "Bilan de performance":
    st.title("Bilan de performance")
    df_t = charger_transactions()
    if not df_t.empty:
        for c in ["Quantité", "Prix", "Frais"]: 
            df_t[c] = pd.to_numeric(df_t[c].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
        
        df_c = df_t[df_t["Ticker"].str.upper() == "CASH"]
        dep = df_c[df_c["Type"] == "DÉPÔT"]["Prix"].sum()
        ret = df_c[df_c["Type"].isin(["RETRAIT", "PAIEMENT"])]["Prix"].sum()
        
        st.subheader("Flux de trésorerie")
        k1, k2, k3 = st.columns(3)
        k1.metric("Dépôts totaux", f"{dep:,.2f} €".replace(',', ' '))
        k2.metric("Sorties / Impôts", f"- {ret:,.2f} €".replace(',', ' '))
        k3.metric("Net injecté", f"{(dep - ret):,.2f} €".replace(',', ' '))
        
        st.subheader("Performance par ligne")
        df_a = df_t[df_t["Ticker"].str.upper() != "CASH"]
        if not df_a.empty:
            rec = []
            with st.spinner("Calcul en cours..."):
                try: taux = yf.Ticker("EUR=X").history(period="1d")['Close'].iloc[-1]
                except: taux = 0.92
                for t in df_a["Ticker"].unique():
                    dft = df_a[df_a["Ticker"] == t]
                    ach = dft[dft["Type"] == "ACHAT"]
                    ven = dft[dft["Type"] == "VENTE"]
                    div = dft[dft["Type"] == "DIVIDENDE"]
                    v_ach, v_ven = (ach["Quantité"] * ach["Prix"]).sum(), (ven["Quantité"] * ven["Prix"]).sum()
                    v_div = div.apply(lambda r: (r["Quantité"] * r["Prix"]) if r["Quantité"] > 1 else r["Prix"], axis=1).sum()
                    sq = ach["Quantité"].sum() - ven["Quantité"].sum()
                    pa = 0
                    if sq > 0.0001:
                        try:
                            s = yf.Ticker(str(t))
                            pa = s.history(period="1d")['Close'].iloc[-1] * (taux if s.fast_info.get("currency")=="USD" else 1)
                        except: pa = 0
                    val = sq * pa
                    pnl = (val + v_ven + v_div) - (v_ach + dft["Frais"].sum())
                    rec.append({"Actif": t, "Qté": sq, "Investi": v_ach, "Vendu": v_ven, "Gains": pnl})
            
            st.dataframe(pd.DataFrame(rec).style.format({"Qté":"{:.2f}", "Investi":"{:.2f} €", "Vendu":"{:.2f} €", "Gains":"{:.2f} €"}).map(style_plus_value, subset=['Gains']), use_container_width=True, hide_index=True)
