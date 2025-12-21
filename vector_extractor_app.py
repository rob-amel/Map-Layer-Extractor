import streamlit as st
import pandas as pd
import geopandas as gpd
import io
import os
import shutil
import tempfile
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

st.title("🗺️ Universal Map Layer Extractor Pro")
st.markdown("Estrai, analizza e converti layer geografici in molteplici formati senza errori.")

# --- FUNZIONI DI SUPPORTO ---
def prepare_download(gdf, format_choice):
    """Gestisce la creazione dei file per il download nei vari formati."""
    tmpdir = tempfile.mkdtemp()
    
    try:
        if format_choice == "Excel":
            output = io.BytesIO()
            # Puliamo per Excel (rimuoviamo l'oggetto geometria grezzo)
            df_excel = pd.DataFrame(gdf.drop(columns='geometry'))
            df_excel['WKT_Geometry'] = gdf.geometry.apply(lambda x: x.wkt if x is not None else None)
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_excel.to_excel(writer, index=False)
            return output.getvalue(), "layer_export.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

        elif format_choice == "CSV":
            df_csv = pd.DataFrame(gdf.drop(columns='geometry'))
            df_csv['WKT_Geometry'] = gdf.geometry.apply(lambda x: x.wkt if x is not None else None)
            return df_csv.to_csv(index=False).encode('utf-8'), "layer_export.csv", "text/csv"

        elif format_choice == "GeoJSON":
            return gdf.to_json().encode('utf-8'), "layer_export.geojson", "application/json"

        elif format_choice == "GeoPackage (GPKG)":
            path = os.path.join(tmpdir, "export.gpkg")
            gdf.to_file(path, driver="GPKG")
            with open(path, "rb") as f:
                data = f.read()
            return data, "layer_export.gpkg", "application/octet-stream"

        elif format_choice == "ESRI Shapefile":
            # Lo Shapefile richiede più file, creiamo uno ZIP
            path = os.path.join(tmpdir, "export_shp")
            os.makedirs(path)
            gdf.to_file(os.path.join(path, "export.shp"))
            shutil.make_archive(path, 'zip', path)
            with open(f"{path}.zip", "rb") as f:
                data = f.read()
            return data, "layer_export_shp.zip", "application/zip"

    except Exception as e:
        st.error(f"Errore nella generazione del file: {e}")
        return None, None, None
    finally:
        shutil.rmtree(tmpdir)

# --- FUNZIONE CORE DI ANALISI ---
def process_data(source):
    try:
        gdf = gpd.read_file(source)
        # Protezione AttributeError: pulizia geometrie nulle
        gdf = gdf.dropna(subset=['geometry'])
        
        # Estrazione automatica metadati utili
        gdf['latitude'] = gdf.geometry.centroid.y
        gdf['longitude'] = gdf.geometry.centroid.x
        gdf['area_approx'] = gdf.geometry.area
        
        return gdf
    except Exception as e:
        st.error(f"Impossibile leggere il layer: {e}")
        return None

# --- INTERFACCIA UTENTE ---
input_type = st.sidebar.radio("Sorgente dati:", ["URL", "File Locale"])
if input_type == "URL":
    source = st.sidebar.text_input("URL (GeoJSON/KML):", value="https://pw-israeli-strikes.vercel.app/target.geojson")
else:
    source = st.sidebar.file_uploader("Carica File:", type=['geojson', 'kml', 'json', 'zip', 'gpkg'])

if source:
    with st.spinner("Analisi in corso..."):
        gdf = process_data(source)
        
        if gdf is not None:
            st.success(f"Trovati {len(gdf)} elementi con relative descrizioni.")
            
            # Anteprima
            st.subheader("📊 Anteprima Dati")
            st.dataframe(gdf.drop(columns='geometry').head(10), use_container_width=True)
            
            # Opzioni di Esportazione
            st.markdown("---")
            st.subheader("📥 Opzioni di Download")
            
            col1, col2 = st.columns([2, 1])
            with col1:
                format_choice = st.selectbox(
                    "Scegli il formato di uscita:",
                    ["Excel", "CSV", "GeoJSON", "GeoPackage (GPKG)", "ESRI Shapefile"]
                )
            
            with col2:
                data, filename, mime = prepare_download(gdf, format_choice)
                if data:
                    st.download_button(
                        label=f"SCARICA {format_choice.upper()}",
                        data=data,
                        file_name=filename,
                        mime=mime
                    )

# --- REQUISITI (da mettere in requirements.txt) ---
# streamlit
# pandas
# geopandas
# shapely
# fiona
# pyogrio
# xlsxwriter
