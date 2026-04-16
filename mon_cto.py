import streamlit as st
import yfinance as yf
import pandas as pd
import os
import plotly.express as px
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(layout="wide", page_title="Mon Patrimoine Pro")

# 🔗 L'ID DE TON GOOGLE SHEET
ID_SHEET = "14sSa2p27u2oY9EsJxaNP6CFX4HUznYJojnPprI6vDBY"
FICHIER_HISTORIQUE = "historique_patrimoine.csv"

# --- 1. FONCTIONS DE CONNEXION ---
@st.cache_resource
def connecter_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds).open_by_key(ID_SHEET)

def charger_donnees():
    try:
        # On lit le premier onglet (index 0) pour le portefeuille
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
        # On lit l'onglet spécifique des transactions
        sheet = connecter_client().worksheet("Transactions")
        data = sheet.get_all_records(value_render_option='UNFORMATTED_VALUE')
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

def ajouter_transaction(date, t_type, ticker, qte, prix, frais, compte):
    try:
        sheet = connecter_client().worksheet("Transactions")
        sheet.append_row([date, t_type, ticker.upper(), qte, prix, frais, compte])
        return True
    except Exception as e:
        st.error(f"Erreur d'ajout transaction : {e}")
        return False

def charger_historique():
    if os.path.exists(FICHIER_HISTORIQUE):
        return pd.read_csv(FICHIER_HISTORIQUE)
    return pd.DataFrame(columns=["Date", "Patrimoine Total (€)"])

def enregistrer_snapshot(valeur_totale):
    df_hist = charger_historique()
    date_jour = datetime.now().strftime("%Y-%m-%d")
    df_hist = df_hist[df_hist["Date"] != date_jour]
    nouvelle_ligne = pd.DataFrame([{"Date": date_jour, "Patrimoine Total (€)": valeur_totale}])
    df_hist = pd.concat([df_hist, nouvelle_ligne], ignore_index=True)
    df_hist = df_hist.sort_values(by="Date")
    df_hist.to_csv(FICHIER_HISTORIQUE, index=False)

def style_plus_value(val):
    if pd.isna(val): return ''
    if val > 0: return 'color: #28a745; font-weight: bold'
    elif val < 0: return 'color: #dc3545; font-weight: bold'
    return 'color: #6c757d'

# --- 2. SÉCURITÉ ---
st.sidebar.header("🔐 Accès Restreint")
mot_de_passe_saisi = st.sidebar.text_input("Mot de passe pour modifier", type="password")
try:
    est_autorise = (mot_de_passe_saisi == st.secrets["APP_PASSWORD"])
except:
    est_autorise = False
    st.sidebar.error("⚠️ Clé 'APP_PASSWORD' manquante.")

# --- NAVIGATION MULTI-PAGES ---
st.sidebar.divider()
page = st.sidebar.radio("Navigation", ["📊 Portefeuille Global", "📜 Historique des Transactions"])

# ==========================================
# PAGE 1 : PORTEFEUILLE GLOBAL (LE CODE INTACT)
# ==========================================
if page == "📊 Portefeuille Global":
    st.title("🌍 Mon Patrimoine Global")
    
    if est_autorise:
        st.sidebar.success("Mode Édition Activé")
    else:
        if mot_de_passe_saisi: st.sidebar.error("Mot de passe incorrect")
        st.sidebar.info("Mode consultation actif.")

    # INITIALISATION
    if 'portefeuille' not in st.session_state:
        st.session_state.portefeuille = charger_donnees()

    # FORMULAIRE D'AJOUT RAPIDE
    st.sidebar.header("➕ Ajouter une ligne")
    if st.sidebar.button("🔄 Forcer Synchro Sheets"):
        st.session_state.portefeuille = charger_donnees()
        st.rerun()

    if est_autorise:
        with st.sidebar.form("ajout_ligne", clear_on_submit=True):
            type_compte = st.selectbox("Choix du Compte", ["CTO", "PEA", "Crypto", "Autre"])
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
                    st.success(f"{nouveau_ticker} ajouté !")
                    st.rerun()
                except ValueError:
                    st.error("Chiffres invalides !")
    else:
        st.sidebar.warning("🔒 Saisie verrouillée")

    # GESTION DES LIGNES
    if est_autorise:
        with st.expander("🛠️ Gérer mes actifs (Modifier ou Supprimer)"):
            df_base = pd.DataFrame(st.session_state.portefeuille)
            if df_base.empty:
                df_base = pd.DataFrame(columns=["Compte", "Ticker", "Quantité", "PRU"])
            df_modifie = st.data_editor(df_base, num_rows="dynamic", use_container_width=True, key="editeur")
            if not df_base.equals(df_modifie):
                st.session_state.portefeuille = df_modifie.to_dict('records')
                sauvegarder_donnees(st.session_state.portefeuille)
                st.rerun()

    # AFFICHAGE ET CALCULS
    if not st.session_state.portefeuille:
        st.info("Ton portefeuille est vide.")
    else:
        df = pd.DataFrame(st.session_state.portefeuille)
        with st.spinner("Analyse du potentiel..."):
            try: taux_usd_eur = yf.Ticker("EUR=X").history(period="1d")['Close'].iloc[-1]
            except: taux_usd_eur = 0.92
            cours_actuels, devises, dividendes, objectifs = [], [], [], []
            for ticker in df["Ticker"]:
                try:
                    data = yf.Ticker(str(ticker).strip().upper())
                    prix_local = data.history(period="1d")['Close'].iloc[-1]
                    devise = data.fast_info.get("currency", "EUR")
                    div_local = data.info.get('dividendRate', 0) or 0
                    obj_local = data.info.get('targetMeanPrice', 0) or 0
                    
                    coef = taux_usd_eur if devise == "USD" else 1
                    cours_actuels.append(prix_local * coef)
                    devises.append(devise)
                    dividendes.append(div_local * coef)
                    objectifs.append(obj_local * coef)
                except:
                    cours_actuels.append(0); devises.append("Err"); dividendes.append(0); objectifs.append(0)

        df["Devise"] = devises
        df["Cours Actuel (€)"] = cours_actuels
        df["Valeur Investie (€)"] = df["Quantité"] * df["PRU"]
        df["Valeur Actuelle (€)"] = df["Quantité"] * df["Cours Actuel (€)"]
        df["Plus-Value (%)"] = ((df["Cours Actuel (€)"] - df["PRU"]) / df["PRU"] * 100).fillna(0)
        df["Rente Annuelle (€)"] = df["Quantité"] * dividendes
        
        # CALCULS DU POTENTIEL
        df["Objectif (€)"] = objectifs
        df["Potentiel (%)"] = df.apply(lambda r: ((r["Objectif (€)"] - r["Cours Actuel (€)"]) / r["Cours Actuel (€)"] * 100) if r["Objectif (€)"] > 0 else 0, axis=1)
        df["Potentiel / PRU (%)"] = df.apply(lambda r: ((r["Objectif (€)"] - r["PRU"]) / r["PRU"] * 100) if r["Objectif (€)"] > 0 and r["PRU"] > 0 else 0, axis=1)

        # RÉSUMÉS
        st.header("📊 Vue Détaillée")
        total_investi = df["Valeur Investie (€)"].sum()
        total_actuel = df["Valeur Actuelle (€)"].sum()
        total_pv = total_actuel - total_investi
        total_pv_pct = (total_pv / total_investi * 100) if total_investi > 0 else 0

        c1, c2, c3 = st.columns(3)
        c1.metric("Patrimoine Total", f"{total_actuel:.2f} €")
        c2.metric("Total Investi", f"{total_investi:.2f} €")
        c3.metric("Performance Globale", f"{total_pv:.2f} €", f"{total_pv_pct:.2f} %")
        
        # MACHINE A CASH
        st.subheader("💸 Ma Machine à Cash")
        total_div_an = df["Rente Annuelle (€)"].sum()
        rendement_moyen = (total_div_an / total_investi * 100) if total_investi > 0 else 0
        
        c4, c5, c6 = st.columns(3)
        c4.metric("Rente Annuelle", f"{total_div_an:.2f} € / an")
        c5.metric("Soit par mois", f"{(total_div_an / 12):.2f} € / mois")
        c6.metric("Rendement (Yield on Cost)", f"{rendement_moyen:.2f} %")
        
        st.divider()

        # TABLEAU FINAL
        cols = ["Compte", "Ticker", "Quantité", "PRU", "Cours Actuel (€)", "Objectif (€)", "Potentiel (%)", "Potentiel / PRU (%)", "Valeur Actuelle (€)", "Plus-Value (%)", "Rente Annuelle (€)"]
        df_final = df[cols].sort_values(by="Compte").fillna(0)
        
        st.dataframe(df_final.style.format({
            "Quantité": "{:.4f}", "PRU": "{:.2f} €", "Cours Actuel (€)": "{:.2f} €", 
            "Objectif (€)": "{:.2f} €", "Potentiel (%)": "{:.2f} %", "Potentiel / PRU (%)": "{:.2f} %",
            "Valeur Actuelle (€)": "{:.2f} €", "Plus-Value (%)": "{:.2f} %", "Rente Annuelle (€)": "{:.2f} €"
        }).map(style_plus_value, subset=['Plus-Value (%)', 'Potentiel (%)', 'Potentiel / PRU (%)']), use_container_width=True)

        # GRAPHIQUES
        st.divider()
        col_g, col_d = st.columns(2)
        with col_g:
            st.subheader("☀️ Répartition")
            st.plotly_chart(px.sunburst(df_final, path=['Compte', 'Ticker'], values='Valeur Actuelle (€)'), use_container_width=True)
        with col_d:
            st.subheader("📈 Évolution")
            if est_autorise:
                if st.button("📸 Enregistrer la valeur d'aujourd'hui"):
                    enregistrer_snapshot(total_actuel)
                    st.success("Enregistré !")
            else:
                st.info("🔒 Connecte-toi avec le mot de passe pour enregistrer un point d'historique.")
                
            df_h = charger_historique()
            if not df_h.empty:
                st.plotly_chart(px.line(df_h, x="Date", y="Patrimoine Total (€)", markers=True).update_traces(fill='tozeroy', line_color='#00b4d8'), use_container_width=True)


# ==========================================
# PAGE 2 : HISTORIQUE DES TRANSACTIONS
# ==========================================
elif page == "📜 Historique des Transactions":
    st.title("📜 Journal des Opérations")
    
    if est_autorise:
        with st.expander("➕ Enregistrer une nouvelle transaction", expanded=True):
            with st.form("form_transac", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                date_t = c1.date_input("Date", datetime.now())
                type_t = c2.selectbox("Type", ["ACHAT", "VENTE", "DIVIDENDE", "DÉPÔT", "RETRAIT"])
                ticker_t = c3.text_input("Ticker (ex: AI.PA)")
                
                c4, c5, c6 = st.columns(3)
                qte_t = c4.text_input("Quantité", value="0")
                prix_t = c5.text_input("Prix Unitaire (€)", value="0")
                frais_t = c6.text_input("Frais (€)", value="0")
                
                compte_t = st.selectbox("Compte", ["PEA", "CTO", "Crypto", "Autre"])
                
                if st.form_submit_button("Enregistrer la transaction"):
                    try:
                        date_str = date_t.strftime("%d/%m/%Y")
                        success = ajouter_transaction(
                            date_str, type_t, ticker_t.strip().upper(), 
                            float(qte_t.replace(',', '.')), 
                            float(prix_t.replace(',', '.')), 
                            float(frais_t.replace(',', '.')), 
                            compte_t
                        )
                        if success:
                            st.success("✅ Transaction enregistrée !")
                            st.rerun()
                    except ValueError:
                        st.error("⚠️ Erreur : Que des chiffres pour la Quantité, le Prix et les Frais.")
    else:
        st.warning("🔒 Saisissez le mot de passe dans le menu pour ajouter des transactions.")

    # Affichage de l'historique
    df_trans = charger_transactions()
    if not df_trans.empty:
        # On affiche le dataframe proprement
        st.dataframe(df_trans, use_container_width=True)
    else:
        st.info("Aucune transaction trouvée dans l'onglet 'Transactions' de ton Google Sheets.")
