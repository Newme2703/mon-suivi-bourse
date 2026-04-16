import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime

# --- CONFIGURATION ---
st.set_page_config(layout="wide", page_title="Mon Patrimoine Live")

# 🔗 REMPLACE CE LIEN par le lien "Publier sur le web (CSV)" de ton Google Sheets
URL_GOOGLE_SHEETS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTVsBPRwm4RlBiWyRJlw1GTKnYRyFweDEv1rkbgcF2E-tXJhMxa5i2qaYmX6wqZ-q2k8ldYKpdQ3oPG/pub?gid=0&single=true&output=csv"

st.title("🌍 Mon Patrimoine Global (Sync Google Sheets)")

# --- 1. FONCTIONS DE RÉCUPÉRATION ---
def charger_donnees():
    try:
        # On lit directement le Google Sheets publié en CSV
        return pd.read_csv(URL_GOOGLE_SHEETS).to_dict('records')
    except:
        st.error("Impossible de lire le Google Sheets. Vérifie le lien 'Publier sur le web'.")
        return []

# Note : Pour l'instant, l'écriture se fait manuellement dans ton Google Sheets 
# pour garantir que tes données sont "immortelles".

def style_plus_value(val):
    if val > 0: return 'color: #28a745; font-weight: bold'
    elif val < 0: return 'color: #dc3545; font-weight: bold'
    return 'color: #6c757d'

# --- 2. INITIALISATION ---
# On recharge les données à chaque rafraîchissement pour être à jour avec le Sheets
portefeuille_data = charger_donnees()

if not portefeuille_data:
    st.info("Ton Google Sheets semble vide ou mal connecté.")
else:
    df = pd.DataFrame(portefeuille_data)
    
    with st.spinner('Synchronisation avec les marchés mondiaux...'):
        try:
            taux_usd_eur = yf.Ticker("EUR=X").history(period="1d")['Close'].iloc[-1]
        except:
            taux_usd_eur = 0.92
            
        cours_actuels_eur, divs_eur, devises = [], [], []
        
        for ticker in df["Ticker"]:
            try:
                data = yf.Ticker(str(ticker))
                prix_local = data.history(period="1d")['Close'].iloc[-1]
                devise = data.fast_info.get("currency", "EUR")
                info = data.info
                div_local = info.get('dividendRate', 0) or 0
                
                c_eur = prix_local * taux_usd_eur if devise == "USD" else prix_local
                d_eur = div_local * taux_usd_eur if devise == "USD" else div_local
                
                cours_actuels_eur.append(c_eur)
                divs_eur.append(d_eur)
                devises.append(devise)
            except:
                cours_actuels_eur.append(0); divs_eur.append(0); devises.append("Err")

    # Calculs
    df["Cours (€)"] = cours_actuels_eur
    df["Valeur Actuelle (€)"] = df["Quantité"] * df["Cours (€)"]
    df["Valeur Investie (€)"] = df["Quantité"] * df["PRU"]
    df["Plus-Value (%)"] = ((df["Cours (€)"] - df["PRU"]) / df["PRU"] * 100).fillna(0)
    df["Rente Annuelle (€)"] = df["Quantité"] * divs_eur

    # --- AFFICHAGE MÉTRIQUES ---
    total_investi = df["Valeur Investie (€)"].sum()
    total_actuel = df["Valeur Actuelle (€)"].sum()
    total_div_an = df["Rente Annuelle (€)"].sum()

    col1, col2, col3 = st.columns(3)
    col1.metric("Patrimoine Total", f"{total_actuel:.2f} €")
    col2.metric("Plus-Value Globale", f"{(total_actuel - total_investi):.2f} €", f"{((total_actuel/total_investi-1)*100 if total_investi > 0 else 0):.2f} %")
    col3.metric("Rente Mensuelle", f"{(total_div_an/12):.2f} € / mois")

    st.divider()

    # --- TABLEAU ---
    st.dataframe(
        df[["Compte", "Ticker", "Quantité", "PRU", "Cours (€)", "Valeur Actuelle (€)", "Plus-Value (%)", "Rente Annuelle (€)"]]
        .style.format({"PRU": "{:.2f} €", "Cours (€)": "{:.2f} €", "Valeur Actuelle (€)": "{:.2f} €", "Plus-Value (%)": "{:.2f} %", "Rente Annuelle (€)": "{:.2f} €"})
        .map(style_plus_value, subset=['Plus-Value (%)']),
        use_container_width=True
    )

    # --- RÉPARTITION ---
    st.subheader("☀️ Répartition du Patrimoine")
    fig_sun = px.sunburst(df, path=['Compte', 'Ticker'], values='Valeur Actuelle (€)')
    st.plotly_chart(fig_sun, use_container_width=True)
