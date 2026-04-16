import streamlit as st
import yfinance as yf
import pandas as pd
import os
import plotly.express as px
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(layout="wide")

# 🔗 L'ID DE TON GOOGLE SHEET
ID_SHEET = "14sSa2p27u2oY9EsJxaNP6CFX4HUznYJojnPprI6vDBY"
FICHIER_HISTORIQUE = "historique_patrimoine.csv"

st.title("🌍 Mon Patrimoine Global (Objectifs & Potentiel)")

# --- 1. FONCTIONS DE CONNEXION ET SAUVEGARDE ---
@st.cache_resource
def connecter_google_sheets():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    return client.open_by_key(ID_SHEET).get_worksheet(0)

def charger_donnees():
    try:
        sheet = connecter_google_sheets()
        data = sheet.get_all_records(value_render_option='UNFORMATTED_VALUE')
        
        if not data:
            st.warning("⚠️ Le Google Sheet est connecté mais semble vide.")
            return []
            
        df_sheet = pd.DataFrame(data)
        
        for col in ["Quantité", "PRU"]:
            if col in df_sheet.columns:
                df_sheet[col] = pd.to_numeric(df_sheet[col].astype(str).str.replace(',', '.'), errors='coerce')
        
        return df_sheet.dropna(subset=["Ticker"]).to_dict('records')
        
    except Exception as e:
        erreur_str = str(e).lower()
        if "permission" in erreur_str or "403" in erreur_str:
            st.error("❌ Erreur 403 : As-tu partagé le Sheets avec l'email du bot en tant qu'Éditeur ?")
        elif "404" in erreur_str:
            st.error("❌ Erreur 404 : Fichier introuvable. L'ID de ton Google Sheet est-il correct ?")
        else:
            st.error(f"❌ Erreur de lecture : {e}")
        return []

def sauvegarder_donnees(portefeuille):
    try:
        df = pd.DataFrame(portefeuille)
        sheet = connecter_google_sheets()
        sheet.clear()
        sheet.update([df.columns.values.tolist()] + df.values.tolist())
    except Exception as e:
        st.error(f"Erreur de sauvegarde : {e}")

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
    if val > 0: return 'color: #28a745; font-weight: bold' # Vert
    elif val < 0: return 'color: #dc3545; font-weight: bold' # Rouge
    return 'color: #6c757d' # Gris

# --- 2. SÉCURITÉ : VÉRIFICATION DU MOT DE PASSE ---
st.sidebar.header("🔐 Accès Restreint")
mot_de_passe_saisi = st.sidebar.text_input("Mot de passe pour modifier", type="password")

try:
    est_autorise = (mot_de_passe_saisi == st.secrets["APP_PASSWORD"])
except:
    est_autorise = False
    st.sidebar.error("⚠️ Clé 'APP_PASSWORD' manquante dans les Secrets.")

if est_autorise:
    st.sidebar.success("Mode Édition Activé")
else:
    if mot_de_passe_saisi: st.sidebar.error("Mot de passe incorrect")
    st.sidebar.info("Mode consultation actif.")

# --- 3. INITIALISATION ---
if 'portefeuille' not in st.session_state:
    st.session_state.portefeuille = charger_donnees()

# --- 4. FORMULAIRE D'AJOUT RAPIDE (Protégé) ---
st.sidebar.header("➕ Ajouter une ligne")

if st.sidebar.button("🔄 Forcer Synchro Sheets"):
    st.session_state.portefeuille = charger_donnees()
    st.rerun()

if est_autorise:
    with st.sidebar.form("ajout_ligne", clear_on_submit=True):
        type_compte = st.selectbox("Choix du Compte", ["CTO", "PEA", "Crypto", "Autre"])
        nouveau_ticker = st.text_input("Symbole (ex: AI.PA, BTC-EUR)")
        nouvelle_quantite_str = st.text_input("Quantité (utilise , ou .)", value="0")
        nouveau_pru_str = st.text_input("PRU (€)", value="0")
        bouton_ajout = st.form_submit_button("Ajouter")

        if bouton_ajout and nouveau_ticker:
            try:
                nouvelle_action = {
                    "Compte": type_compte,
                    "Ticker": nouveau_ticker.upper().strip(),
                    "Quantité": float(nouvelle_quantite_str.replace(',', '.')),
                    "PRU": float(nouveau_pru_str.replace(',', '.'))
                }
                st.session_state.portefeuille.append(nouvelle_action)
                sauvegarder_donnees(st.session_state.portefeuille)
                st.success(f"{nouveau_ticker} ajouté !")
                st.rerun()
            except ValueError:
                st.error("⚠️ Erreur : Que des chiffres !")
else:
    st.sidebar.warning("🔒 Saisie verrouillée")

# --- 5. GESTION DES LIGNES (Protégé) ---
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

# --- 6. AFFICHAGE ET CALCULS ---
if not st.session_state.portefeuille:
    st.info("Ton portefeuille est vide. Ajoute un actif pour commencer.")
    total_actuel = 0
else:
    df = pd.DataFrame(st.session_state.portefeuille)
    
    with st.spinner("Récupération des données et analyse du potentiel..."):
        try: taux_usd_eur = yf.Ticker("EUR=X").history(period="1d")['Close'].iloc[-1]
        except: taux_usd_eur = 0.92
            
        cours_actuels_eur, devises_origine, dividendes_par_action = [], [], []
        objectifs_cours_eur = [] # Nouvelle liste pour le potentiel
        
        for ticker in df["Ticker"]:
            t = str(ticker).strip().upper()
            try:
                data = yf.Ticker(t)
                # 1. Prix actuel
                prix_local = data.history(period="1d")['Close'].iloc[-1]
                devise = data.fast_info.get("currency", "EUR")
                
                # 2. Dividende
                div_local = 0
                try: div_local = data.info.get('dividendRate', 0) or 0
                except: div_local = 0
                
                # 3. Objectif de cours (Potentiel Analystes)
                obj_local = 0
                try: obj_local = data.info.get('targetMeanPrice', 0) or 0
                except: obj_local = 0
                
                if devise == "USD":
                    prix_eur = prix_local * taux_usd_eur
                    div_eur = div_local * taux_usd_eur
                    obj_eur = obj_local * taux_usd_eur
                else:
                    prix_eur = prix_local
                    div_eur = div_local
                    obj_eur = obj_local
                    
                cours_actuels_eur.append(prix_eur)
                devises_origine.append(devise)
                dividendes_par_action.append(div_eur)
                objectifs_cours_eur.append(obj_eur)
            except:
                cours_actuels_eur.append(0); devises_origine.append("Erreur")
                dividendes_par_action.append(0); objectifs_cours_eur.append(0)

    # Calculs classiques
    df["Devise"] = devises_origine
    df["Cours Actuel (€)"] = cours_actuels_eur
    df["Valeur Investie (€)"] = df["Quantité"] * df["PRU"]
    df["Valeur Actuelle (€)"] = df["Quantité"] * df["Cours Actuel (€)"]
    df["Plus-Value (€)"] = df["Valeur Actuelle (€)"] - df["Valeur Investie (€)"]
    df["Plus-Value (%)"] = (df["Plus-Value (€)"] / df["Valeur Investie (€)"]) * 100
    df["Rente Annuelle (€)"] = df["Quantité"] * dividendes_par_action
    
    # NOUVEAUX CALCULS : Potentiel
    df["Objectif (€)"] = objectifs_cours_eur
    # On calcule le potentiel uniquement si l'objectif est supérieur à 0 (pour éviter les ETF)
    df["Potentiel (%)"] = df.apply(lambda row: ((row["Objectif (€)"] - row["Cours Actuel (€)"]) / row["Cours Actuel (€)"] * 100) if row["Objectif (€)"] > 0 and row["Cours Actuel (€)"] > 0 else 0, axis=1)

    # --- 7. RÉSUMÉS ---
    st.header("📊 Vue Détaillée")
    total_investi = df["Valeur Investie (€)"].sum()
    total_actuel = df["Valeur Actuelle (€)"].sum()
    total_pv = total_actuel - total_investi
    total_pv_pct = (total_pv / total_investi * 100) if total_investi > 0 else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Patrimoine Total", f"{total_actuel:.2f} €")
    c2.metric("Total Investi", f"{total_investi:.2f} €")
    c3.metric("Performance Globale", f"{total_pv:.2f} €", f"{total_pv_pct:.2f} %")
    
    st.divider()

    # --- 8. TABLEAU AVEC COULEURS ---
    # On ajoute Objectif et Potentiel à l'affichage !
    colonnes_a_afficher = ["Compte", "Ticker", "Quantité", "PRU", "Cours Actuel (€)", "Objectif (€)", "Potentiel (%)", "Valeur Actuelle (€)", "Plus-Value (%)", "Rente Annuelle (€)"]
    df_final = df[colonnes_a_afficher].sort_values(by="Compte")
    df_final = df_final.fillna(0) 

    # On utilise la même fonction de couleur (style_plus_value) pour la PV et le Potentiel
    st.dataframe(df_final.style.format({
        "Quantité": "{:.4f}", "PRU": "{:.2f} €", "Cours Actuel (€)": "{:.2f} €",
        "Objectif (€)": "{:.2f} €", "Potentiel (%)": "{:.2f} %",
        "Valeur Actuelle (€)": "{:.2f} €", "Plus-Value (%)": "{:.2f} %",
        "Rente Annuelle (€)": "{:.2f} €"
    }).map(style_plus_value, subset=['Plus-Value (%)', 'Potentiel (%)']), use_container_width=True)

    # --- 9. LES GRAPHIQUES ---
    st.divider()
    col_gauche, col_droite = st.columns(2)
    with col_gauche:
        st.subheader("☀️ Répartition")
        fig_sun = px.sunburst(df_final, path=['Compte', 'Ticker'], values='Valeur Actuelle (€)')
        fig_sun.update_traces(textinfo='label+percent entry')
        st.plotly_chart(fig_sun, use_container_width=True)
    with col_droite:
        st.subheader("📈 Évolution")
        
        if est_autorise:
            if st.button("📸 Enregistrer la valeur d'aujourd'hui"):
                enregistrer_snapshot(total_actuel)
                st.success("Enregistré !")
        else:
            st.info("🔒 Connecte-toi avec le mot de passe pour enregistrer un point d'historique.")
            
        df_hist = charger_historique()
        if not df_hist.empty:
            fig_line = px.line(df_hist, x="Date", y="Patrimoine Total (€)", markers=True)
            fig_line.update_traces(fill='tozeroy', line_color='#00b4d8') 
            st.plotly_chart(fig_line, use_container_width=True)
