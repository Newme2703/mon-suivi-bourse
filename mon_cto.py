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
ID_SHEET = "1vTVsBPRwm4RlBiWyRJlw1GTKnYRyFweDEv1rkbgcF2E-tXJhMxa5i2qaYmX6wqZ-q2k8ldYKpdQ3oPG"
FICHIER_HISTORIQUE = "historique_patrimoine.csv"

st.title("🌍 Mon Patrimoine Global (Sécurisé)")

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
        data = sheet.get_all_records()
        
        if not data:
            st.warning("⚠️ Le Google Sheet est connecté mais semble vide (aucune donnée sous les titres).")
            return []
            
        df_sheet = pd.DataFrame(data)
        
        # Vérification des colonnes indispensables
        colonnes_requises = ["Compte", "Ticker", "Quantité", "PRU"]
        for col in colonnes_requises:
            if col not in df_sheet.columns:
                st.error(f"❌ Erreur : La colonne '{col}' est introuvable. Vérifie la ligne 1 de ton Sheets.")
                return []
        
        # Conversion sécurisée
        for col in ["Quantité", "PRU"]:
            df_sheet[col] = pd.to_numeric(df_sheet[col].astype(str).str.replace(',', '.'), errors='coerce')
        
        return df_sheet.dropna(subset=["Ticker"]).to_dict('records')
        
    except gspread.exceptions.PermissionError:
        st.error("❌ Erreur de permission : As-tu partagé le Sheets avec l'email du bot ?")
        return []
    except Exception as e:
        st.error(f"❌ Erreur inconnue : {e}")
        return []

def sauvegarder_donnees(portefeuille):
    try:
        df = pd.DataFrame(portefeuille)
        sheet = connecter_google_sheets()
        sheet.clear()
        sheet.update([df.columns.values.tolist()] + df.values.tolist())
    except Exception as e:
        st.error(f"Erreur de sauvegarde : {e}")

# CES FONCTIONS SONT BIEN DE RETOUR 👇
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

# --- FONCTION DE COULEUR ---
def style_plus_value(val):
    if val > 0:
        return 'color: #28a745; font-weight: bold' # Vert
    elif val < 0:
        return 'color: #dc3545; font-weight: bold' # Rouge
    return 'color: #6c757d' # Gris

# --- 2. SÉCURITÉ : VÉRIFICATION DU MOT DE PASSE ---
st.sidebar.header("🔐 Accès Restreint")
mot_de_passe_saisi = st.sidebar.text_input("Mot de passe pour modifier", type="password")

# On vérifie si le mot de passe correspond à celui des Secrets
# Si "APP_PASSWORD" n'est pas trouvé dans les secrets, on bloque par défaut pour éviter les fuites
try:
    est_autorise = (mot_de_passe_saisi == st.secrets["APP_PASSWORD"])
except:
    est_autorise = False
    st.sidebar.error("⚠️ Clé 'APP_PASSWORD' manquante dans les Secrets Streamlit.")

if est_autorise:
    st.sidebar.success("Mode Édition Activé")
else:
    if mot_de_passe_saisi:
        st.sidebar.error("Mot de passe incorrect")
    st.sidebar.info("Mode consultation actif. Mot de passe requis pour modifier.")

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
                qte_finale = float(nouvelle_quantite_str.replace(',', '.'))
                pru_final = float(nouveau_pru_str.replace(',', '.'))
                
                nouvelle_action = {
                    "Compte": type_compte,
                    "Ticker": nouveau_ticker.upper().strip(),
                    "Quantité": qte_finale,
                    "PRU": pru_final
                }
                st.session_state.portefeuille.append(nouvelle_action)
                sauvegarder_donnees(st.session_state.portefeuille)
                st.success(f"{nouveau_ticker} ajouté dans {type_compte} !")
                st.rerun()
            except ValueError:
                st.error("⚠️ Erreur : Veille à bien taper uniquement des chiffres.")
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
    
    with st.spinner('Récupération des données...'):
        try:
            taux_usd_eur = yf.Ticker("EUR=X").history(period="1d")['Close'].iloc[-1]
        except:
            taux_usd_eur = 0.92
            
        cours_actuels_eur = []
        devises_origine = []
        dividendes_par_action = []
        
        for ticker in df["Ticker"]:
            t = str(ticker).strip().upper()
            try:
                data = yf.Ticker(t)
                prix_local = data.history(period="1d")['Close'].iloc[-1]
                devise = data.fast_info.get("currency", "EUR")
                
                div_local = 0
                try:
                    div_local = data.info.get('dividendRate', 0) or 0
                except:
                    div_local = 0
                
                if devise == "USD":
                    prix_eur = prix_local * taux_usd_eur
                    div_eur = div_local * taux_usd_eur
                else:
                    prix_eur = prix_local
                    div_eur = div_local
                    
                cours_actuels_eur.append(prix_eur)
                devises_origine.append(devise)
                dividendes_par_action.append(div_eur)
            except:
                cours_actuels_eur.append(0); devises_origine.append("Erreur"); dividendes_par_action.append(0)

    # Calculs
    df["Devise"] = devises_origine
    df["Cours Actuel (€)"] = cours_actuels_eur
    df["Valeur Investie (€)"] = df["Quantité"] * df["PRU"]
    df["Valeur Actuelle (€)"] = df["Quantité"] * df["Cours Actuel (€)"]
    df["Plus-Value (€)"] = df["Valeur Actuelle (€)"] - df["Valeur Investie (€)"]
    df["Plus-Value (%)"] = (df["Plus-Value (€)"] / df["Valeur Investie (€)"]) * 100
    df["Dividende / Action (€)"] = dividendes_par_action
    df["Rente Annuelle (€)"] = df["Quantité"] * df["Dividende / Action (€)"]

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
    
    st.subheader("💸 Ma Machine à Cash")
    total_div_an = df["Rente Annuelle (€)"].sum()
    rendement_moyen = (total_div_an / total_investi * 100) if total_investi > 0 else 0
    
    c4, c5, c6 = st.columns(3)
    c4.metric("Rente Annuelle", f"{total_div_an:.2f} € / an")
    c5.metric("Soit par mois", f"{(total_div_an / 12):.2f} € / mois")
    c6.metric("Rendement (Yield on Cost)", f"{rendement_moyen:.2f} %")
    
    st.divider()

    # --- 8. TABLEAU AVEC COULEURS ---
    colonnes_a_afficher = ["Compte", "Ticker", "Devise", "Quantité", "PRU", "Cours Actuel (€)", "Valeur Actuelle (€)", "Plus-Value (%)", "Dividende / Action (€)", "Rente Annuelle (€)"]
    df_final = df[colonnes_a_afficher].sort_values(by="Compte")
    df_final = df_final.fillna(0) 

    st.dataframe(df_final.style.format({
        "Quantité": "{:.4f}", "PRU": "{:.2f} €", "Cours Actuel (€)": "{:.2f} €",
        "Valeur Actuelle (€)": "{:.2f} €", "Plus-Value (%)": "{:.2f} %",
        "Dividende / Action (€)": "{:.2f} €", "Rente Annuelle (€)": "{:.2f} €"
    }).map(style_plus_value, subset=['Plus-Value (%)']), use_container_width=True)

    # --- 9. LES GRAPHIQUES (SUNBURST + LIGNE DE TEMPS) ---
    st.divider()
    col_gauche, col_droite = st.columns(2)
    with col_gauche:
        st.subheader("☀️ Répartition")
        fig_sun = px.sunburst(df_final, path=['Compte', 'Ticker'], values='Valeur Actuelle (€)')
        fig_sun.update_traces(textinfo='label+percent entry')
        st.plotly_chart(fig_sun, use_container_width=True)
    with col_droite:
        st.subheader("📈 Évolution")
        
        # Le bouton d'enregistrement n'est visible que si on est autorisé
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
