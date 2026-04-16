import streamlit as st
import yfinance as yf
import pandas as pd
import os
import plotly.express as px
from datetime import datetime

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(layout="wide", page_title="Mon Patrimoine Live")

# 🔗 COLLE TON LIEN "PUBLIER SUR LE WEB (CSV)" ICI
URL_GOOGLE_SHEETS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTVsBPRwm4RlBiWyRJlw1GTKnYRyFweDEv1rkbgcF2E-tXJhMxa5i2qaYmX6wqZ-q2k8ldYKpdQ3oPG/pub?gid=0&single=true&output=csv"

FICHIER_HISTORIQUE = "historique_patrimoine.csv"

st.title("🌍 Mon Patrimoine Global (Sync Google Sheets)")

# --- 1. FONCTIONS DE RÉCUPÉRATION & SAUVEGARDE ---

def charger_donnees():
    """Charge les données depuis le Google Sheets publié en CSV."""
    try:
        # On ajoute un paramètre de temps pour éviter que Google ne serve une version cachée (cache)
        url = f"{URL_GOOGLE_SHEETS}&cachebuster={datetime.now().timestamp()}"
        df_sheet = pd.read_csv(url)
        return df_sheet.to_dict('records')
    except Exception as e:
        st.error(f"Erreur de connexion au Google Sheets : {e}")
        st.info("Vérifiez que vous avez bien choisi 'Valeurs séparées par des virgules (.csv)' dans 'Publier sur le web'.")
        return []

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
    if val > 0: return 'color: #28a745; font-weight: bold'
    elif val < 0: return 'color: #dc3545; font-weight: bold'
    return 'color: #6c757d'

# --- 2. TRAITEMENT DES DONNÉES ---

data_portefeuille = charger_donnees()

if not data_portefeuille:
    st.warning("⚠️ En attente de données. Assure-toi que ton lien Google Sheets est correct et que le fichier n'est pas vide.")
else:
    df = pd.DataFrame(data_portefeuille)
    
    with st.spinner('Synchronisation avec les marchés mondiaux...'):
        try:
            # Récupération du taux de change
            taux_usd_eur = yf.Ticker("EUR=X").history(period="1d")['Close'].iloc[-1]
        except:
            taux_usd_eur = 0.92
            
        cours_actuels_eur, divs_eur, devises = [], [], []
        
        for ticker in df["Ticker"]:
            try:
                data = yf.Ticker(str(ticker).strip())
                # Prix actuel
                prix_local = data.history(period="1d")['Close'].iloc[-1]
                # Devise
                devise = data.fast_info.get("currency", "EUR")
                # Dividende
                div_local = data.info.get('dividendRate', 0) or 0
                
                if devise == "USD":
                    prix_eur = prix_local * taux_usd_eur
                    div_eur = div_local * taux_usd_eur
                else:
                    prix_eur = prix_local
                    div_eur = div_local
                    
                cours_actuels_eur.append(prix_eur)
                divs_eur.append(div_eur)
                devises.append(devise)
            except:
                cours_actuels_eur.append(0); divs_eur.append(0); devises.append("N/A")

    # Calculs colonnes
    df["Cours (€)"] = cours_actuels_eur
    df["Valeur Actuelle (€)"] = df["Quantité"] * df["Cours (€)"]
    df["Valeur Investie (€)"] = df["Quantité"] * df["PRU"]
    df["Plus-Value (€)"] = df["Valeur Actuelle (€)"] - df["Valeur Investie (€)"]
    df["PV (%)"] = (df["Plus-Value (€)"] / df["Valeur Investie (€)"] * 100).fillna(0)
    df["Rente Annuelle (€)"] = df["Quantité"] * divs_eur

    # --- 3. AFFICHAGE DES MÉTRIQUES ---
    total_investi = df["Valeur Investie (€)"].sum()
    total_actuel = df["Valeur Actuelle (€)"].sum()
    total_pv = total_actuel - total_investi
    total_div_an = df["Rente Annuelle (€)"].sum()

    st.header("📊 Tableau de Bord")
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Patrimoine Total", f"{total_actuel:.2f} €")
    m2.metric("Plus-Value Globale", f"{total_pv:.2f} €", f"{((total_actuel/total_investi-1)*100 if total_investi > 0 else 0):.2f} %")
    m3.metric("Rente Mensuelle", f"{(total_div_an/12):.2f} € / mois")

    st.subheader("💸 Ma Machine à Cash")
    c4, c5 = st.columns(2)
    c4.metric("Rente Annuelle", f"{total_div_an:.2f} € / an")
    c5.metric("Yield on Cost Moyen", f"{((total_div_an/total_investi*100) if total_investi > 0 else 0):.2f} %")

    st.divider()

    # --- 4. TABLEAU FINAL ---
    df_final = df[["Compte", "Ticker", "Quantité", "PRU", "Cours (€)", "Valeur Actuelle (€)", "PV (%)", "Rente Annuelle (€)"]].sort_values("Compte")
    df_final = df_final.fillna(0)

    st.dataframe(
        df_final.style.format({
            "Quantité": "{:.4f}", "PRU": "{:.2f} €", "Cours (€)": "{:.2f} €",
            "Valeur Actuelle (€)": "{:.2f} €", "PV (%)": "{:.2f} %", "Rente Annuelle (€)": "{:.2f} €"
        }).map(style_plus_value, subset=['PV (%)']),
        use_container_width=True
    )

    # --- 5. GRAPHIQUES ---
    st.divider()
    g1, g2 = st.columns(2)
    with g1:
        st.subheader("☀️ Répartition")
        fig_sun = px.sunburst(df_final, path=['Compte', 'Ticker'], values='Valeur Actuelle (€)')
        fig_sun.update_traces(textinfo='label+percent entry')
        st.plotly_chart(fig_sun, use_container_width=True)
    with g2:
        st.subheader("📈 Historique")
        if st.button("📸 Sauvegarder la valeur du jour"):
            enregistrer_snapshot(total_actuel)
            st.success("Valeur du jour enregistrée dans l'historique local !")
        
        hist = charger_historique()
        if not hist.empty:
            fig_line = px.line(hist, x="Date", y="Patrimoine Total (€)", markers=True)
            fig_line.update_traces(fill='tozeroy', line_color='#00b4d8')
            st.plotly_chart(fig_line, use_container_width=True)

    st.info("💡 Pour modifier tes positions, fais-le directement dans ton fichier Google Sheets. Le site se mettra à jour au prochain chargement.")
