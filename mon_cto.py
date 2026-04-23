import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# Configuration de la page
st.set_page_config(layout="wide", page_title="Mon Patrimoine Pro")

# 🔗 L'ID DE TON GOOGLE SHEET
ID_SHEET = "14sSa2p27u2oY9EsJxaNP6CFX4HUznYJojnPprI6vDBY"

# ==========================================
# 🎨 STYLE CSS (AMÉLIORATION ESTHÉTIQUE)
# ==========================================
st.markdown("""
<style>
    /* Style pour les indicateurs (KPI Cards) */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #eef0f2;
        padding: 15px 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.02);
        transition: transform 0.2s ease-in-out;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.05);
    }
    /* Style pour les titres de métriques */
    div[data-testid="metric-container"] label {
        color: #5f6368 !important;
        font-size: 14px !important;
        font-weight: 600 !important;
        text-transform: uppercase;
    }
    /* Style pour les valeurs des métriques */
    div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
        font-size: 24px !important;
        color: #1a73e8 !important;
    }
</style>
""", unsafe_allow_html=True)

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
        for col in ["Quantité", "PRU"]:
            if col in df_sheet.columns:
                df_sheet[col] = pd.to_numeric(df_sheet[col].astype(str).str.replace(',', '.'), errors='coerce')
        return df_sheet.dropna(subset=["Ticker"]).to_dict('records')
    except Exception as e:
        st.error(f"Erreur de lecture Portefeuille : {e}")
        return []

def sauvegarder_donnees(portefeuille):
    try:
        df = pd.DataFrame(portefeuille)
        sheet = connecter_client().get_worksheet(0)
        sheet.clear()
        sheet.update([df.columns.values.tolist()] + df.values.tolist())
    except Exception as e:
        st.error(f"Erreur de sauvegarde Portefeuille : {e}")

def charger_transactions():
    try:
        sheet = connecter_client().worksheet("Transactions")
        data = sheet.get_all_records(value_render_option='UNFORMATTED_VALUE')
        return pd.DataFrame(data)
    except Exception as e:
        return pd.DataFrame()

def sauvegarder_transactions(df_trans):
    try:
        sheet = connecter_client().worksheet("Transactions")
        sheet.clear()
        df_save = df_trans.copy()
        sheet.update([df_save.columns.values.tolist()] + df_save.values.tolist())
        st.success("✅ Historique mis à jour dans Google Sheets !")
    except Exception as e:
        st.error(f"Erreur de sauvegarde Transactions : {e}")

def ajouter_transaction(date, t_type, ticker, qte, prix, frais, compte):
    try:
        sheet = connecter_client().worksheet("Transactions")
        sheet.append_row([date, t_type, ticker.upper(), qte, prix, frais, compte])
        return True
    except Exception as e:
        st.error(f"Erreur d'ajout transaction : {e}")
        return False

def style_plus_value(val):
    if pd.isna(val): return ''
    if val > 0: return 'color: #28a745; font-weight: bold'
    elif val < 0: return 'color: #dc3545; font-weight: bold'
    return 'color: #6c757d'

# ==========================================
# 2. VARIABLES GLOBALES & SÉCURITÉ
# ==========================================
LISTE_COMPTES = ["CTO", "PEA", "Crypto", "Espèce", "Autre"]
LISTE_MOTIFS = ["ACHAT", "VENTE", "DIVIDENDE", "PAIEMENT", "DÉPÔT", "RETRAIT"]

st.sidebar.header("🔐 Accès Restreint")
mot_de_passe_saisi = st.sidebar.text_input("Mot de passe pour modifier", type="password")

try:
    est_autorise = (mot_de_passe_saisi == st.secrets["APP_PASSWORD"])
except:
    est_autorise = False
    st.sidebar.error("⚠️ Clé 'APP_PASSWORD' manquante dans les Secrets.")

st.sidebar.divider()
page = st.sidebar.radio("Navigation", [
    "📊 Portefeuille Global", 
    "📜 Historique des Transactions", 
    "📈 Bilan & Performance (Compta)"
])

# ==========================================
# PAGE 1 : PORTEFEUILLE GLOBAL
# ==========================================
if page == "📊 Portefeuille Global":
    st.title("🌍 Mon Patrimoine Global")
    
    if est_autorise: st.sidebar.success("Mode Édition Activé")
    else: st.sidebar.info("Mode consultation actif.")

    if 'portefeuille' not in st.session_state:
        st.session_state.portefeuille = charger_donnees()

    st.sidebar.header("➕ Ajouter une ligne")
    if st.sidebar.button("🔄 Forcer Synchro Sheets"):
        st.session_state.portefeuille = charger_donnees()
        st.rerun()

    if est_autorise:
        with st.sidebar.form("ajout_ligne", clear_on_submit=True):
            type_compte = st.selectbox("Choix du Compte", LISTE_COMPTES)
            nouveau_ticker = st.text_input("Symbole (ex: AI.PA)")
            nouvelle_quantite_str = st.text_input("Quantité", value="0")
            nouveau_pru_str = st.text_input("PRU (€)", value="0")
            
            if st.form_submit_button("Ajouter"):
                try:
                    nouvelle_action = {
                        "Compte": type_compte, "Ticker": nouveau_ticker.upper().strip(),
                        "Quantité": float(nouvelle_quantite_str.replace(',', '.')),
                        "PRU": float(nouveau_pru_str.replace(',', '.'))
                    }
                    st.session_state.portefeuille.append(nouvelle_action)
                    sauvegarder_donnees(st.session_state.portefeuille)
                    st.rerun()
                except ValueError:
                    st.error("Chiffres invalides !")
    else:
        st.sidebar.warning("🔒 Saisie verrouillée")

    if est_autorise:
        with st.expander("🛠️ Gérer mes actifs (Modifier ou Supprimer)"):
            df_base = pd.DataFrame(st.session_state.portefeuille)
            if df_base.empty: df_base = pd.DataFrame(columns=["Compte", "Ticker", "Quantité", "PRU"])
            df_modifie = st.data_editor(df_base, num_rows="dynamic", use_container_width=True, hide_index=True, key="editeur")
            if not df_base.equals(df_modifie):
                st.session_state.portefeuille = df_modifie.to_dict('records')
                sauvegarder_donnees(st.session_state.portefeuille)
                st.rerun()

    if not st.session_state.portefeuille:
        st.info("Ton portefeuille est vide.")
    else:
        df = pd.DataFrame(st.session_state.portefeuille)
        
        with st.spinner("Analyse du marché en cours..."):
            try: taux_usd_eur = yf.Ticker("EUR=X").history(period="1d")['Close'].iloc[-1]
            except: taux_usd_eur = 0.92
                
            cours_actuels, devises, dividendes, objectifs, noms = [], [], [], [], []
            
            for ticker in df["Ticker"]:
                try:
                    t_str = str(ticker).strip().upper()
                    data = yf.Ticker(t_str)
                    nom_entreprise = data.info.get('shortName', t_str)
                    prix_local = data.history(period="1d")['Close'].iloc[-1]
                    devise = data.fast_info.get("currency", "EUR")
                    div_local = data.info.get('dividendRate', 0) or 0
                    obj_local = data.info.get('targetMeanPrice', 0) or 0
                    coef = taux_usd_eur if devise == "USD" else 1
                        
                    noms.append(nom_entreprise)
                    cours_actuels.append(prix_local * coef)
                    devises.append(devise)
                    dividendes.append(div_local * coef)
                    objectifs.append(obj_local * coef)
                except Exception as e:
                    st.toast(f"⚠️ YF n'a pas pu charger {ticker}")
                    noms.append(str(ticker))
                    cours_actuels.append(0)
                    devises.append("Err")
                    dividendes.append(0)
                    objectifs.append(0)

        df["Nom"] = noms
        df["Cours Actuel (€)"] = cours_actuels
        df["Valeur Investie (€)"] = df["Quantité"] * df["PRU"]
        df["Valeur Actuelle (€)"] = df["Quantité"] * df["Cours Actuel (€)"]
        
        # Calculs Plus-Values & Poids
        df["Plus-Value (€)"] = df["Valeur Actuelle (€)"] - df["Valeur Investie (€)"]
        df["Plus-Value (%)"] = ((df["Plus-Value (€)"] / df["Valeur Investie (€)"] * 100) if (df["Valeur Investie (€)"].sum() > 0) else 0).fillna(0)
        
        t_inv, t_act = df["Valeur Investie (€)"].sum(), df["Valeur Actuelle (€)"].sum()
        df["Poids (%)"] = (df["Valeur Actuelle (€)"] / t_act * 100).fillna(0)

        df["Rente Annuelle (€)"] = df["Quantité"] * dividendes
        df["Objectif (€)"] = objectifs
        df["Potentiel (%)"] = df.apply(lambda r: ((r["Objectif (€)"] - r["Cours Actuel (€)"]) / r["Cours Actuel (€)"] * 100) if r["Objectif (€)"] > 0 else 0, axis=1)
        df["Potentiel / PRU (%)"] = df.apply(lambda r: ((r["Objectif (€)"] - r["PRU"]) / r["PRU"] * 100) if r["Objectif (€)"] > 0 and r["PRU"] > 0 else 0, axis=1)

        # AFFICHAGE MÉTRIQUES (DANS DES COLONNES)
        st.header("📊 Vue Détaillée")
        c1, c2, c3 = st.columns(3)
        c1.metric("Patrimoine Total", f"{t_act:.2f} €")
        c2.metric("Total Investi", f"{t_inv:.2f} €")
        c3.metric("Performance Globale", f"{(t_act-t_inv):.2f} €", f"{((t_act/t_inv-1)*100 if t_inv>0 else 0):.2f} %")
        
        st.subheader("💸 Ma Machine à Cash")
        total_div_an = df["Rente Annuelle (€)"].sum()
        c4, c5, c6 = st.columns(3)
        c4.metric("Rente Annuelle", f"{total_div_an:.2f} € / an")
        c5.metric("Soit par mois", f"{(total_div_an / 12):.2f} € / mois")
        c6.metric("Yield on Cost", f"{(total_div_an / t_inv * 100 if t_inv>0 else 0):.2f} %")
        
        st.divider()

        # ==========================================
        # 3. FILTRES AU DESSUS DU TABLEAU
        # ==========================================
        st.subheader("🔍 Filtres & Détail des positions")
        f1, f2, f3 = st.columns([2, 1, 1])
        recherche = f1.text_input("Chercher une valeur (Ticker ou Nom)", placeholder="Ex: LVMH, AI.PA...")
        filtre_compte = f2.selectbox("Compte", ["Tous"] + LISTE_COMPTES)
        filtre_perf = f3.selectbox("Performance", ["Tous", "Gagnantes 🟢", "Perdantes 🔴"])

        # Logique de filtrage du DataFrame
        df_filtre = df.copy()
        if recherche:
            df_filtre = df_filtre[df_filtre["Ticker"].str.contains(recherche, case=False) | df_filtre["Nom"].str.contains(recherche, case=False)]
        if filtre_compte != "Tous":
            df_filtre = df_filtre[df_filtre["Compte"] == filtre_compte]
        if filtre_perf == "Gagnantes 🟢":
            df_filtre = df_filtre[df_filtre["Plus-Value (€)"] > 0]
        elif filtre_perf == "Perdantes 🔴":
            df_filtre = df_filtre[df_filtre["Plus-Value (€)"] < 0]

        # Ordre des colonnes
        cols_tab = ["Compte", "Ticker", "Nom", "Quantité", "PRU", "Cours Actuel (€)", "Objectif (€)", "Potentiel (%)", "Potentiel / PRU (%)", "Valeur Actuelle (€)", "Plus-Value (€)", "Plus-Value (%)", "Poids (%)", "Rente Annuelle (€)"]
        
        st.dataframe(df_filtre[cols_tab].style.format({
            "Quantité": "{:.4f}", "PRU": "{:.2f} €", "Cours Actuel (€)": "{:.2f} €", "Objectif (€)": "{:.2f} €",
            "Potentiel (%)": "{:.2f} %", "Potentiel / PRU (%)": "{:.2f} %", "Valeur Actuelle (€)": "{:.2f} €",
            "Plus-Value (€)": "{:.2f} €", "Plus-Value (%)": "{:.2f} %", "Poids (%)": "{:.1f} %", "Rente Annuelle (€)": "{:.2f} €"
        }).map(style_plus_value, subset=['Plus-Value (€)', 'Plus-Value (%)', 'Potentiel (%)', 'Potentiel / PRU (%)']), 
        use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("☀️ Répartition par Actif")
        st.plotly_chart(px.sunburst(df, path=['Compte', 'Ticker'], values='Valeur Actuelle (€)'), use_container_width=True)

# ==========================================
# PAGE 2 : HISTORIQUE DES TRANSACTIONS
# ==========================================
elif page == "📜 Historique des Transactions":
    st.title("📜 Journal des Opérations")
    
    if est_autorise:
        with st.expander("➕ Enregistrer une nouvelle transaction", expanded=True):
            with st.form("form_transac", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                date_t = c1.date_input("Date de la transaction", datetime.now())
                type_t = c2.selectbox("Motif", LISTE_MOTIFS)
                ticker_t = c3.text_input("Ticker (ou 'CASH')")
                
                c4, c5, c6 = st.columns(3)
                qte_t = c4.text_input("Quantité", value="0")
                prix_t = c5.text_input("Prix Unitaire (€)", value="0")
                frais_t = c6.text_input("Frais de transaction (€)", value="0")
                
                compte_t = st.selectbox("Compte impacté", LISTE_COMPTES)
                
                if st.form_submit_button("Enregistrer la transaction"):
                    try:
                        success = ajouter_transaction(date_t.strftime("%d/%m/%Y"), type_t, ticker_t.strip().upper(), 
                                                      float(qte_t.replace(',', '.')), float(prix_t.replace(',', '.')), 
                                                      float(frais_t.replace(',', '.')), compte_t)
                        if success: 
                            st.success("✅ Transaction enregistrée avec succès !")
                            st.rerun()
                    except ValueError: 
                        st.error("⚠️ Erreur : Que des chiffres pour Quantité, Prix et Frais.")
    else:
        st.warning("🔒 Saisissez le mot de passe dans le menu de gauche pour ajouter des transactions.")

    df_trans = charger_transactions()
    if not df_trans.empty:
        st.subheader("Gérer l'historique")
        if est_autorise:
            df_trans_mod = st.data_editor(df_trans, num_rows="dynamic", use_container_width=True, hide_index=True, key="trans_editor")
            if not df_trans.equals(df_trans_mod):
                sauvegarder_transactions(df_trans_mod)
                st.rerun()
        else:
            st.dataframe(df_trans, use_container_width=True, hide_index=True)
    else:
        st.info("Aucune transaction n'a été trouvée dans Google Sheets.")

# ==========================================
# PAGE 3 : BILAN ET PERFORMANCE (COMPTA)
# ==========================================
elif page == "📈 Bilan & Performance (Compta)":
    st.title("📈 Bilan & Performance (Comptabilité globale)")
    
    df_trans = charger_transactions()
    if df_trans.empty:
        st.info("Aucune transaction trouvée pour générer le bilan.")
    else:
        for col in ["Quantité", "Prix", "Frais"]:
            df_trans[col] = pd.to_numeric(df_trans[col].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
            
        df_cash = df_trans[df_trans["Ticker"].str.upper() == "CASH"]
        depots = df_cash[df_cash["Type"] == "DÉPÔT"]["Prix"].sum()
        retraits = df_cash[df_cash["Type"].isin(["RETRAIT", "PAIEMENT"])]["Prix"].sum()
        net_injecte = depots - retraits
        total_frais = df_trans["Frais"].sum()
        
        st.header("🏦 Synthèse des Flux")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Dépôts", f"{depots:.2f} €")
        c2.metric("Total Retraits / Paiements", f"- {retraits:.2f} €")
        c3.metric("Capital Net Injecté", f"{net_injecte:.2f} €")
        c4.metric("Frais Totaux Payés", f"{total_frais:.2f} €")
        
        st.divider()
        st.header("📊 Rentabilité par Actif (Réalisé + Latent)")
        
        df_assets = df_trans[df_trans["Ticker"].str.upper() != "CASH"]
        if not df_assets.empty:
            recap = []
            tickers = df_assets["Ticker"].unique()
            
            with st.spinner("Calcul des gains..."):
                try: taux_usd_eur = yf.Ticker("EUR=X").history(period="1d")['Close'].iloc[-1]
                except: taux_usd_eur = 0.92
                
                for t in tickers:
                    dft = df_assets[df_assets["Ticker"] == t]
                    achats = dft[dft["Type"] == "ACHAT"]
                    ventes = dft[dft["Type"] == "VENTE"]
                    divs = dft[dft["Type"] == "DIVIDENDE"]
                    
                    vol_achat = (achats["Quantité"] * achats["Prix"]).sum()
                    vol_vente = (ventes["Quantité"] * ventes["Prix"]).sum()
                    vol_div = divs.apply(lambda r: (r["Quantité"] * r["Prix"]) if r["Quantité"] > 1 else r["Prix"], axis=1).sum()
                    frais_actif = dft["Frais"].sum()
                    solde_qte = achats["Quantité"].sum() - ventes["Quantité"].sum()
                    
                    prix_actuel = 0
                    nom_entreprise = str(t).upper() 
                    
                    if solde_qte > 0.0001:
                        try:
                            t_str = str(t).strip().upper()
                            data = yf.Ticker(t_str)
                            nom_entreprise = data.info.get('shortName', t_str)
                            p_local = data.history(period="1d")['Close'].iloc[-1]
                            dev = data.fast_info.get("currency", "EUR")
                            coef = taux_usd_eur if dev == "USD" else 1
                            prix_actuel = p_local * coef
                        except Exception as e:
                            st.toast(f"⚠️ YF n'a pas pu charger {t}")
                            prix_actuel = 0
                    else:
                        try:
                            t_str = str(t).strip().upper()
                            data = yf.Ticker(t_str)
                            nom_entreprise = data.info.get('shortName', t_str)
                        except: pass
                            
                    valeur_actuelle = solde_qte * prix_actuel
                    pnl = (valeur_actuelle + vol_vente + vol_div) - (vol_achat + frais_actif)
                    pnl_pct = (pnl / vol_achat * 100) if vol_achat > 0 else 0
                    
                    recap.append({
                        "Ticker": t, "Nom": nom_entreprise, "Solde Actions": solde_qte, "Acheté (€)": vol_achat,
                        "Vendu (€)": vol_vente, "Dividendes (€)": vol_div, "Frais (€)": frais_actif,
                        "Valeur Actuelle (€)": valeur_actuelle, "Gain / Perte Total (€)": pnl, "Rentabilité (%)": pnl_pct
                    })
            
            df_recap = pd.DataFrame(recap)
            st.subheader("🏆 Résultat Global des Investissements")
            tot_pnl = df_recap["Gain / Perte Total (€)"].sum()
            tot_achete = df_recap["Acheté (€)"].sum()
            tot_pnl_pct = (tot_pnl / tot_achete * 100) if tot_achete > 0 else 0
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Gains/Pertes Nets", f"{tot_pnl:.2f} €")
            m2.metric("Rentabilité Globale", f"{tot_pnl_pct:.2f} %")
            m3.metric("Total Dividendes", f"{df_recap['Dividendes (€)'].sum():.2f} €")
            
            st.divider()
            st.dataframe(df_recap.style.format({
                "Solde Actions": "{:.4f}", "Acheté (€)": "{:.2f} €", "Vendu (€)": "{:.2f} €", "Dividendes (€)": "{:.2f} €",
                "Frais (€)": "{:.2f} €", "Valeur Actuelle (€)": "{:.2f} €", "Gain / Perte Total (€)": "{:.2f} €", "Rentabilité (%)": "{:.2f} %"
            }).map(style_plus_value, subset=['Gain / Perte Total (€)', 'Rentabilité (%)']), 
            use_container_width=True, hide_index=True)
