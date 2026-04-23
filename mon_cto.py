import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# Configuration de la page
st.set_page_config(layout="wide", page_title="Mon Portefeuille")

# 🔗 L'ID DE TON GOOGLE SHEET
ID_SHEET = "14sSa2p27u2oY9EsJxaNP6CFX4HUznYJojnPprI6vDBY"

# ==========================================
# 🎨 STYLE CSS AVANCÉ (SOBRE & PRO)
# ==========================================
st.markdown("""
<style>
    /* Cartes d'indicateurs (KPIs) - Design épuré */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #eef0f2;
        padding: 15px 20px;
        border-radius: 8px; /* Bords légèrement ronds, plus sérieux */
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    
    /* Titres des métriques (Gris ardoise, sans majuscules forcées) */
    div[data-testid="metric-container"] label {
        color: #5f6368 !important;
        font-size: 14px !important;
        font-weight: 500 !important; /* Gras léger */
    }
    
    /* Valeurs numériques principales */
    div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
        font-size: 24px !important;
        color: #1a73e8 !important; /* Bleu institutionnel */
        font-weight: 600 !important;
    }
    
    /* Cadres des graphiques Plotly */
    [data-testid="stPlotlyChart"] {
        background-color: #ffffff;
        border: 1px solid #eef0f2;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    
    /* Titres des pages */
    h1 {
        font-weight: 400 !important;
        color: #202124 !important;
        padding-bottom: 20px;
    }
    h3 {
        font-weight: 500 !important;
        color: #3c4043 !important;
        margin-top: 30px !important;
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
        st.success("Historique mis à jour dans Google Sheets.")
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
    if val > 0: return 'color: #1e8e3e; font-weight: bold' # Vert plus professionnel
    elif val < 0: return 'color: #d93025; font-weight: bold' # Rouge plus professionnel
    return 'color: #5f6368'

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
    st.sidebar.error("Clé 'APP_PASSWORD' manquante dans les Secrets.")

st.sidebar.divider()
page = st.sidebar.radio("Navigation", [
    "Tableau de bord", 
    "Historique des transactions", 
    "Bilan comptable"
])

# ==========================================
# PAGE 1 : TABLEAU DE BORD (PORTEFEUILLE)
# ==========================================
if page == "Tableau de bord":
    st.title("Mon portefeuille")
    
    if est_autorise: st.sidebar.success("Mode Édition : Activé")
    else: st.sidebar.info("Mode Consultation : Activé")

    if 'portefeuille' not in st.session_state:
        st.session_state.portefeuille = charger_donnees()

    st.sidebar.header("Nouvelle position")
    if st.sidebar.button("Actualiser les données"):
        st.session_state.portefeuille = charger_donnees()
        st.rerun()

    if est_autorise:
        with st.sidebar.form("ajout_ligne", clear_on_submit=True):
            type_compte = st.selectbox("Compte", LISTE_COMPTES)
            nouveau_ticker = st.text_input("Symbole (ex: AI.PA)")
            nouvelle_quantite_str = st.text_input("Quantité", value="0")
            nouveau_pru_str = st.text_input("PRU (€)", value="0")
            
            if st.form_submit_button("Ajouter la ligne"):
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
                    st.error("Chiffres invalides.")
    else:
        st.sidebar.warning("Saisie verrouillée")

    if est_autorise:
        with st.expander("Éditer les positions actives"):
            df_base = pd.DataFrame(st.session_state.portefeuille)
            if df_base.empty: df_base = pd.DataFrame(columns=["Compte", "Ticker", "Quantité", "PRU"])
            df_modifie = st.data_editor(df_base, num_rows="dynamic", use_container_width=True, hide_index=True, key="editeur")
            if not df_base.equals(df_modifie):
                st.session_state.portefeuille = df_modifie.to_dict('records')
                sauvegarder_donnees(st.session_state.portefeuille)
                st.rerun()

    if not st.session_state.portefeuille:
        st.info("Le portefeuille est vide.")
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
                    st.toast(f"Impossible de charger {ticker}")
                    noms.append(str(ticker))
                    cours_actuels.append(0)
                    devises.append("Err")
                    dividendes.append(0)
                    objectifs.append(0)

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

        # -----------------------------
        # METRIQUES PRO
        # -----------------------------
        st.markdown("### Performances")
        c1, c2, c3 = st.columns(3)
        c1.metric("Valorisation actuelle", f"{t_act:,.2f} €".replace(',', ' '))
        c2.metric("Montant investi", f"{t_inv:,.2f} €".replace(',', ' '))
        c3.metric("Plus-value latente", f"{(t_act-t_inv):,.2f} €".replace(',', ' '), f"{((t_act/t_inv-1)*100 if t_inv>0 else 0):.2f} %")
        
        st.markdown("### Dividendes")
        total_div_an = df["Rente Annuelle (€)"].sum()
        c4, c5, c6 = st.columns(3)
        c4.metric("Revenu annuel estimé", f"{total_div_an:,.2f} €".replace(',', ' '))
        c5.metric("Moyenne mensuelle", f"{(total_div_an / 12):,.2f} €".replace(',', ' '))
        c6.metric("Rendement sur PRU", f"{(total_div_an / t_inv * 100 if t_inv>0 else 0):.2f} %")
        
        st.divider()

        st.markdown("### Détail des positions")
        f1, f2, f3 = st.columns([2, 1, 1])
        recherche = f1.text_input("Rechercher un actif", placeholder="Ex: LVMH, AI.PA...")
        filtre_compte = f2.selectbox("Compte", ["Tous"] + LISTE_COMPTES)
        filtre_perf = f3.selectbox("Statut performance", ["Toutes", "Gagnantes 🟢", "Perdantes 🔴"])

        df_filtre = df.copy()
        if recherche:
            df_filtre = df_filtre[df_filtre["Ticker"].str.contains(recherche, case=False) | df_filtre["Nom"].str.contains(recherche, case=False)]
        if filtre_compte != "Tous":
            df_filtre = df_filtre[df_filtre["Compte"] == filtre_compte]
        if filtre_perf == "Gagnantes 🟢":
            df_filtre = df_filtre[df_filtre["Plus-Value (€)"] > 0]
        elif filtre_perf == "Perdantes 🔴":
            df_filtre = df_filtre[df_filtre["Plus-Value (€)"] < 0]

        cols_tab = ["Compte", "Ticker", "Nom", "Quantité", "PRU", "Cours Actuel (€)", "Objectif (€)", "Potentiel (%)", "Potentiel / PRU (%)", "Valeur Actuelle (€)", "Plus-Value (€)", "Plus-Value (%)", "Poids (%)", "Rente Annuelle (€)"]
        
        st.dataframe(df_filtre[cols_tab].style.format({
            "Quantité": "{:.4f}", "PRU": "{:.2f} €", "Cours Actuel (€)": "{:.2f} €", "Objectif (€)": "{:.2f} €",
            "Potentiel (%)": "{:.2f} %", "Potentiel / PRU (%)": "{:.2f} %", "Valeur Actuelle (€)": "{:.2f} €",
            "Plus-Value (€)": "{:.2f} €", "Plus-Value (%)": "{:.2f} %", "Poids (%)": "{:.1f} %", "Rente Annuelle (€)": "{:.2f} €"
        }).map(style_plus_value, subset=['Plus-Value (€)', 'Plus-Value (%)', 'Potentiel (%)', 'Potentiel / PRU (%)']), 
        use_container_width=True, hide_index=True)

        st.divider()
        
        col_g, col_d = st.columns(2)
        with col_g:
            st.markdown("### Répartition par actif")
            fig_pie = px.sunburst(df_filtre, path=['Compte', 'Ticker'], values='Valeur Actuelle (€)')
            fig_pie.update_layout(margin=dict(t=20, l=20, r=20, b=20))
            st.plotly_chart(fig_pie, use_container_width=True)
            
        with col_d:
            st.markdown("### Gains et pertes par ligne")
            df_bar = df_filtre.copy()
            df_bar["Couleur"] = df_bar["Plus-Value (€)"].apply(lambda x: "Gain" if x >= 0 else "Perte")
            
            fig_bar = px.bar(
                df_bar.sort_values("Plus-Value (€)", ascending=False),
                x="Ticker",
                y="Plus-Value (€)",
                color="Couleur",
                color_discrete_map={"Gain": "#1e8e3e", "Perte": "#d93025"},
                text_auto='.0f'
            )
            fig_bar.update_layout(
                showlegend=False, xaxis_title="", 
                margin=dict(t=20, l=20, r=20, b=20)
            )
            st.plotly_chart(fig_bar, use_container_width=True)


# ==========================================
# PAGE 2 : HISTORIQUE DES TRANSACTIONS
# ==========================================
elif page == "Historique des transactions":
    st.title("Journal des opérations")
    
    if est_autorise:
        with st.expander("Enregistrer une nouvelle transaction", expanded=True):
            with st.form("form_transac", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                date_t = c1.date_input("Date de la transaction", datetime.now())
                type_t = c2.selectbox("Type d'opération", LISTE_MOTIFS)
                ticker_t = c3.text_input("Symbole (ou 'CASH')")
                
                c4, c5, c6 = st.columns(3)
                qte_t = c4.text_input("Quantité", value="0")
                prix_t = c5.text_input("Prix Unitaire (€)", value="0")
                frais_t = c6.text_input("Frais de courtage (€)", value="0")
                
                compte_t = st.selectbox("Compte impacté", LISTE_COMPTES)
                
                if st.form_submit_button("Valider la transaction"):
                    try:
                        success = ajouter_transaction(date_t.strftime("%d/%m/%Y"), type_t, ticker_t.strip().upper(), 
                                                      float(qte_t.replace(',', '.')), float(prix_t.replace(',', '.')), 
                                                      float(frais_t.replace(',', '.')), compte_t)
                        if success: 
                            st.rerun()
                    except ValueError: 
                        st.error("Valeurs numériques invalides.")
    else:
        st.warning("Veuillez saisir le mot de passe pour ajouter des transactions.")

    df_trans = charger_transactions()
    if not df_trans.empty:
        st.markdown("### Historique complet")
        
        recherche_trans = st.text_input("Filtrer l'historique", placeholder="Chercher un ticker, une date, un motif...")
        
        df_trans_affiche = df_trans.copy()
        if recherche_trans:
            mask = df_trans_affiche.astype(str).apply(lambda x: x.str.contains(recherche_trans, case=False)).any(axis=1)
            df_trans_affiche = df_trans_affiche[mask]
        
        if est_autorise and not recherche_trans:
            st.info("Vous pouvez éditer ou supprimer une ligne directement dans le tableau.")
            df_trans_mod = st.data_editor(df_trans_affiche, num_rows="dynamic", use_container_width=True, hide_index=True, key="trans_editor")
            if not df_trans_affiche.equals(df_trans_mod):
                sauvegarder_transactions(df_trans_mod)
                st.rerun()
        elif est_autorise and recherche_trans:
            st.caption("Mode édition désactivé pendant la recherche.")
            st.dataframe(df_trans_affiche, use_container_width=True, hide_index=True)
        else:
            st.dataframe(df_trans_affiche, use_container_width=True, hide_index=True)
    else:
        st.info("Aucune transaction trouvée.")

# ==========================================
# PAGE 3 : BILAN ET PERFORMANCE (COMPTA)
# ==========================================
elif page == "Bilan comptable":
    st.title("Bilan de performance globale")
    
    df_trans = charger_transactions()
    if df_trans.empty:
        st.info("Aucune donnée pour générer le bilan.")
    else:
        for col in ["Quantité", "Prix", "Frais"]:
            df_trans[col] = pd.to_numeric(df_trans[col].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
            
        df_cash = df_trans[df_trans["Ticker"].str.upper() == "CASH"]
        depots = df_cash[df_cash["Type"] == "DÉPÔT"]["Prix"].sum()
        retraits = df_cash[df_cash["Type"].isin(["RETRAIT", "PAIEMENT"])]["Prix"].sum()
        net_injecte = depots - retraits
        total_frais = df_trans["Frais"].sum()
        
        st.markdown("### Synthèse des flux de capitaux")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Dépôts totaux", f"{depots:,.2f} €".replace(',', ' '))
        c2.metric("Retraits et impôts", f"- {retraits:,.2f} €".replace(',', ' '))
        c3.metric("Capital net investi", f"{net_injecte:,.2f} €".replace(',', ' '))
        c4.metric("Frais de courtage", f"{total_frais:,.2f} €".replace(',', ' '))
        
        st.divider()
        st.markdown("### Rentabilité consolidée (Latent + Réalisé)")
        
        df_assets = df_trans[df_trans["Ticker"].str.upper() != "CASH"]
        if not df_assets.empty:
            recap = []
            tickers = df_assets["Ticker"].unique()
            
            with st.spinner("Calcul des performances en cours..."):
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
                        except:
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
            st.markdown("### Résultat net d'investissement")
            tot_pnl = df_recap["Gain / Perte Total (€)"].sum()
            tot_achete = df_recap["Acheté (€)"].sum()
            tot_pnl_pct = (tot_pnl / tot_achete * 100) if tot_achete > 0 else 0
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Plus-value globale nette", f"{tot_pnl:,.2f} €".replace(',', ' '))
            m2.metric("Rentabilité pondérée", f"{tot_pnl_pct:.2f} %")
            m3.metric("Dividendes encaissés", f"{df_recap['Dividendes (€)'].sum():,.2f} €".replace(',', ' '))
            
            st.divider()
            
            st.markdown("### Analyse par ligne")
            fb1, fb2 = st.columns([2, 1])
            recherche_bilan = fb1.text_input("Rechercher un actif", placeholder="Ex: AMZN, LVMH...", key="rech_bilan")
            filtre_perf_bilan = fb2.selectbox("Statut performance", ["Toutes", "Gagnantes 🟢", "Perdantes 🔴"], key="perf_bilan")

            df_recap_filtre = df_recap.copy()
            if recherche_bilan:
                mask_bilan = df_recap_filtre.astype(str).apply(lambda x: x.str.contains(recherche_bilan, case=False)).any(axis=1)
                df_recap_filtre = df_recap_filtre[mask_bilan]
            if filtre_perf_bilan == "Gagnantes 🟢":
                df_recap_filtre = df_recap_filtre[df_recap_filtre["Gain / Perte Total (€)"] > 0]
            elif filtre_perf_bilan == "Perdantes 🔴":
                df_recap_filtre = df_recap_filtre[df_recap_filtre["Gain / Perte Total (€)"] < 0]

            st.dataframe(df_recap_filtre.style.format({
                "Solde Actions": "{:.4f}", "Acheté (€)": "{:.2f} €", "Vendu (€)": "{:.2f} €", "Dividendes (€)": "{:.2f} €",
                "Frais (€)": "{:.2f} €", "Valeur Actuelle (€)": "{:.2f} €", "Gain / Perte Total (€)": "{:.2f} €", "Rentabilité (%)": "{:.2f} %"
            }).map(style_plus_value, subset=['Gain / Perte Total (€)', 'Rentabilité (%)']), 
            use_container_width=True, hide_index=True)
