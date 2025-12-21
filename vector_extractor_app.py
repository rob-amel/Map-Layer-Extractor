import streamlit as st
import pandas as pd
import geopandas as gpd
import io
import fiona
from io import BytesIO

# --- CONFIGURAZIONE INTERFACCIA ---
st.set_page_config(page_title="🗺️ Universal Map Layer Extractor", layout="wide")

st.markdown("""
<style>
.stDownloadButton > button {
    background-color: #FF4B4B !important;
    color: white !important;
    font-weight: bold;
    width: 100%;
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)

st.title("🗺️ Universal Map Layer Extractor")
st.markdown("""
Questo strumento estrae dati da layer vettoriali (**GeoJSON, KML, Shapefile**) e li converte in un Excel leggibile, 
includendo coordinate, aree e tutte le descrizioni originali.
""")

# --- FUNZIONE CORE DI ESTRAZIONE ---
def extract_map_data(source):
    try:
        # 1. Caricamento del layer (gestisce URL o file caricati)
        gdf = gpd.read_file(source)

        # 2. Pulizia: Rimuoviamo righe dove la geometria è completamente assente
        gdf = gdf.dropna(subset=['geometry'])

        # 3. Calcolo Coordinate (Centroide)
        # Anche se sono poligoni, estraiamo un punto Lat/Lon semplice per il CSV/Excel
        gdf['latitude'] = gdf.geometry.centroid.y
        gdf['longitude'] = gdf.geometry.centroid.x

        # 4. Calcolo Area (Approssimativa in gradi quadrati)
        gdf['geometry_area'] = gdf.geometry.area

        # 5. Conversione Geometria in Testo (WKT)
        # PROTEZIONE ATTRIBUTERROR: Controlliamo se x è valido prima di chiamare .wkt
        gdf['WKT_Format'] = gdf.geometry.apply(lambda x: x.wkt if x is not None else "No Geometry")

        # 6. Preparazione DataFrame Finale
        # Manteniamo TUTTE le colonne originali (descrizioni, target, date) 
        # e rimuoviamo solo l'oggetto geometria grezzo
        df_final = pd.DataFrame(gdf.drop(columns='geometry'))
        
        return df_final

    except Exception as e:
        st.error(f"❌ Errore durante l'estrazione: {e}")
        return None

# --- INTERFACCIA UTENTE ---
st.info("💡 Inserisci l'URL di un file GeoJSON (es. Palestine Wheel) o carica un file locale.")

input_type = st.radio("Scegli la sorgente:", ["URL", "Carica File locale"])

source_data = None

if input_type == "URL":
    url = st.text_input("Inserisci URL GeoJSON/KML:", value="https://pw-israeli-strikes.vercel.app/target.geojson")
    if url:
        source_data = url
else:
    uploaded_file = st.file_uploader("Carica file geografico", type=['geojson', 'kml', 'zip', 'json'])
    if uploaded_file:
        source_data = uploaded_file

# --- AZIONE DI ESTRAZIONE ---
if st.button("🚀 AVVIA ESTRAZIONE LAYER", type="primary"):
    if source_data:
        with st.spinner("Analisi geometrie e recupero metadati in corso..."):
            df = extract_map_data(source_data)
            
            if df is not None:
                st.success(f"✅ Estrazione completata! Trovati {len(df)} elementi.")
                
                # Anteprima dei dati
                st.subheader("📊 Anteprima Dati Estratti")
                st.dataframe(df, use_container_width=True)

                # --- GENERAZIONE EXCEL ---
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name='LayerData')
                
                st.markdown("---")
                st.download_button(
                    label="📥 SCARICA DATI IN EXCEL (ROSSO)",
                    data=output.getvalue(),
                    file_name=f"estrazione_mappa_{pd.Timestamp.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
    else:
        st.warning("Per favore, inserisci un URL o carica un file.")

# --- FOOTER ---
st.markdown("---")
st.caption("Strumento ottimizzato per gestire geometrie complesse e valori nulli.")
