import streamlit as st
import os
import io
import requests
import geopandas as gpd
import json
import tempfile
import zipfile
from shapely.geometry import Point 
import pandas as pd 

# --- CONFIGURAZIONE E STILE ---

st.set_page_config(page_title="🗺️ Vector Data Extractor GIS", layout="wide")

# ----------------------------------------------------------------------
# --------------------- FUNZIONE PRINCIPALE STREAMLIT ------------------
# ----------------------------------------------------------------------

def vector_extractor_app():
    
    st.title("🗺️ Estrattore di Dati Vettoriali GIS Online (V10)")
    st.subheader("Sistema Agile per l'estrazione di Layer e Dati Attributi da URL (incluso ArcGIS).")
    st.markdown("---")

    # --- INPUT DATI (URL O FILE UPLOAD) ---
    st.header("1. 🔗 Sorgente Dati")
    
    source_method = st.radio(
        "Seleziona il metodo di input:",
        options=["URL Diretto", "Carica File Locale"],
        horizontal=True
    )
    
    url_endpoint = ""
    uploaded_file = None
    
    if source_method == "URL Diretto":
        st.caption("Copia l'URL del servizio dati vettoriali. **Per i servizi ArcGIS, usa l'URL che termina con `/FeatureServer/0` o `/FeatureServer/1`**.")
        url_endpoint = st.text_input(
            "URL Diretto del File JSON/WFS:",
            placeholder="Esempio: https://services.arcgis.com/layer/FeatureServer/0",
        )
    else:
        st.caption("Carica il tuo file JSON/GeoJSON locale per convertirlo in Shapefile/GeoPackage.")
        uploaded_file = st.file_uploader(
            "Carica file JSON/GeoJSON",
            type=["json", "geojson"],
            accept_multiple_files=False
        )

    # --- IMPOSTAZIONI GENERALI ---
    feature_name = st.text_input(
        "Nome del Layer (per il file di output):",
        placeholder="Esempio: edifici_storici",
        value="layer_test",
        help="Il nome che vuoi dare al file vettoriale finale."
    )
    
    st.markdown("---")

    # --- COLONNE PER OUTPUT ---
    # Colonna unica rimasta per l'output
    
    st.header("2. 💾 Output e Conversione")
    
    output_format = st.selectbox(
        "Formato di Output GIS:",
        options=["Shapefile (.shp)", "GeoJSON", "GeoPackage (.gpkg)", "CSV (con coordinate)"],
        index=0,
        help="Seleziona il formato standard per il tuo software GIS."
    )
    
    st.markdown("---")
    
    download_disabled = not ((url_endpoint or uploaded_file) and feature_name)
    
    if st.button("⬇️ Avvia Estrazione e Conversione", type="primary", disabled=download_disabled):
        
        if download_disabled:
                st.error("Per favore, inserisci l'URL/carica il file e inserisci il Nome del Layer.")
                st.stop()
        
        st.empty()

        with st.spinner(f"Inizio l'elaborazione del layer '{feature_name}'..."):
            
            base_filename = feature_name
            json_data = None 
            
            # --- FASE 1: ACQUISIZIONE DATI E PARSING IN JSON ---
            try:
                st.info("Passaggio 1/3: Acquisizione dei dati...")
                
                if source_method == "URL Diretto":
                    target_url = url_endpoint
                    
                    # Gestione FeatureServer: aggiunge query GeoJSON se mancante
                    if "FeatureServer" in url_endpoint and "/query" not in url_endpoint.lower():
                        st.info("Rilevato URL FeatureServer ArcGIS. Aggiungo la query GeoJSON standard...")
                        target_url = url_endpoint.rstrip('/') + "/query?f=geojson&where=1=1&outFields=*"
                            
                    response = requests.get(target_url)
                    response.raise_for_status() 
                    json_data = response.json()
                    
                elif source_method == "Carica File Locale" and uploaded_file is not None:
                    json_data = json.load(uploaded_file)
                    
            except requests.exceptions.RequestException as e:
                st.error(f"❌ Errore durante il download dell'URL: {e}. Il server potrebbe non aver risposto o il link è errato.")
                return
            except json.JSONDecodeError:
                st.error("❌ Errore: Il contenuto scaricato/caricato non è un JSON valido.")
                return
            except Exception as e:
                st.error(f"❌ Errore durante l'acquisizione della sorgente dati: {e}")
                return

            # --- FASE 2: PREPARAZIONE DATI GIS (Conversione e Pulizia) ---
            try:
                st.info("Passaggio 2/3: Pulizia del JSON e caricamento GIS...")
                
                gdf = None
                
                # TENTATIVO 1: Il JSON è una LISTA di oggetti con campi lat/lon (Caso whitephosphorus.info)
                if isinstance(json_data, list) and all(isinstance(d, dict) and 'lat' in d and 'lon' in d for d in json_data):
                    st.warning("JSON identificato come **lista di oggetti con campi lat/lon**. Conversione manuale in GeoDataFrame...")
                    
                    # Filtro CRITICO: rimuove gli oggetti con lat/lon mancanti o None
                    valid_data = [d for d in json_data if d.get('lat') is not None and d.get('lon') is not None]

                    if not valid_data:
                        st.error("❌ Errore: Nessun oggetto valido trovato dopo aver rimosso quelli con lat/lon mancanti. La conversione GeoDataFrame fallisce.")
                        st.stop()
                        
                    # Crea la colonna 'geometry' da lon (X) e lat (Y)
                    geometry = [Point(d['lon'], d['lat']) for d in valid_data]
                    
                    # Usa pandas per una gestione pulita degli attributi
                    df = pd.DataFrame(valid_data)
                    df.drop(columns=['lat', 'lon'], inplace=True, errors='ignore')

                    # Crea il GeoDataFrame
                    gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")
                    
                # TENTATIVO 2: Il JSON è un DIZIONARIO (GeoJSON standard o annidato)
                elif isinstance(json_data, dict):
                    
                    final_geojson_content = None
                    
                    # Tenta 2.1: GeoJSON standard
                    if json_data.get('type') == 'FeatureCollection' or 'features' in json_data:
                        final_geojson_content = json_data
                        
                    # Tenta 2.2: JSON Annidato (Caso 'geoData' o altre chiavi comuni)
                    if final_geojson_content is None and 'geoData' in json_data and isinstance(json_data['geoData'], list):
                        st.warning("JSON identificato con chiave 'geoData'. Incapsulamento in GeoJSON Collection.")
                        final_geojson_content = {"type": "FeatureCollection", "features": json_data['geoData']}
                        
                    # Tenta 2.3: Formato ArcGIS Esri (Contenitore di features)
                    if final_geojson_content is None and 'featureSet' in json_data and 'features' in json_data['featureSet']:
                        st.warning("JSON identificato come formato ArcGIS. Estraggo le feature.")
                        final_geojson_content = {"type": "FeatureCollection", "features": json_data['featureSet']['features']}

                    # Tenta 2.4: Lista di Feature non incapsulata
                    if final_geojson_content is None and 'features' in json_data and not json_data.get('type'):
                        st.warning("JSON identificato come lista di Feature non incapsulata. Aggiungo FeatureCollection.")
                        final_geojson_content = {"type": "FeatureCollection", "features": json_data['features']}


                    # Se abbiamo trovato il GeoJSON pulito, lo carichiamo
                    if final_geojson_content:
                        json_string = json.dumps(final_geojson_content)
                        raw_data_buffer = io.BytesIO(json_string.encode('utf-8'))
                        gdf = gpd.read_file(raw_data_buffer)
                    
                if gdf is None:
                    st.error("❌ Formato JSON non riconosciuto. Il contenuto non è né un GeoJSON, né una lista di oggetti con lat/lon. Se hai caricato un file, **assicurati che non sia un file di configurazione** (come datapolimi.json), ma l'URL di download diretto o il file dei dati.")
                    st.stop()
                
                if gdf.empty:
                    st.warning("⚠️ Nessun oggetto trovato nel GeoJSON. Il file è vuoto.")
                    st.stop()
                
                # NESSUN FILTRO APPLICATO - PROCEDI AL DOWNLOAD COMPLETO
                gdf_filtered = gdf
                st.success(f"✅ Trovati {len(gdf_filtered)} oggetti. Nessun filtro applicato.")

            except Exception as e:
                st.error(f"❌ Errore critico durante il caricamento GIS. GeoPandas non è riuscito a interpretare il dato finale. Dettagli: {e}")
                st.warning("Verifica la validità delle geometrie.")
                return

            # --- FASE 3: SALVATAGGIO IN MEMORIA (BUFFER) E PREPARAZIONE DOWNLOAD ---
            
            download_data = None
            mime_type = "application/octet-stream"
            label = f"Scarica {base_filename}"
            file_name = f"{base_filename}"

            if output_format == "Shapefile (.shp)":
                st.info("Passaggio 3/3: Compressione in formato Shapefile (ZIP)...")
                
                zip_buffer = io.BytesIO()
                with tempfile.TemporaryDirectory() as tmpdir:
                    temp_filepath = os.path.join(tmpdir, base_filename + '.shp')
                    gdf_filtered.to_file(temp_filepath, driver='ESRI Shapefile', encoding='utf-8')
                    
                    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                        for file_name_in_dir in os.listdir(tmpdir):
                             zf.write(os.path.join(tmpdir, file_name_in_dir), arcname=file_name_in_dir)

                zip_buffer.seek(0)
                download_data = zip_buffer.getvalue()
                mime_type = "application/zip"
                file_name = f"{base_filename}.zip"
                label = f"Scarica {base_filename}.zip (Shapefile)"

            elif output_format == "GeoPackage (.gpkg)":
                st.info("Passaggio 3/3: Conversione in GeoPackage...")
                download_buffer = io.BytesIO()
                gdf_filtered.to_file(download_buffer, driver='GPKG', encoding='utf-8')
                download_buffer.seek(0)
                
                download_data = download_buffer.getvalue()
                file_name = f"{base_filename}.gpkg"
                mime_type = "application/octet-stream"
                label = f"Scarica {base_filename}.gpkg"

            elif output_format == "GeoJSON":
                st.info("Passaggio 3/3: Generazione di GeoJSON...")
                output_content = gdf_filtered.to_json(na='drop')
                download_data = output_content.encode('utf-8')
                mime_type = "application/geo+json"
                file_name = f"{base_filename}.geojson"
                label = f"Scarica {base_filename}.geojson"
            
            else: # CSV
                st.info("Passaggio 3/3: Generazione di CSV...")
                gdf_csv = gdf_filtered.copy()
                # Aggiunge la geometria in formato WKT (Well Known Text)
                gdf_csv['WKT_Geometry'] = gdf_csv.geometry.apply(lambda x: x.wkt) 
                gdf_csv = gdf_csv.drop(columns=['geometry'])
                output_content = gdf_csv.to_csv(index=False, na_rep='')
                download_data = output_content.encode('utf-8')
                mime_type = "text/csv"
                file_name = f"{base_filename}.csv"
                label = f"Scarica {base_filename}.csv"
                
            # 4. PULSANTE DI DOWNLOAD FINALE
            st.success("✅ Estrazione e conversione completata! Clicca per scaricare il tuo file GIS.")
            st.download_button(
                label=label,
                data=download_data,
                file_name=file_name,
                mime=mime_type
            )
            
            # Riepilogo dei parametri usati
            st.markdown("#### Riepilogo Estrazione")
            st.json({
                "sorgente_utilizzata": source_method,
                "url_o_file": url_endpoint if url_endpoint else "File Caricato",
                "layer_output": base_filename,
                "formato_output": output_format,
                "oggetti_estratti_finali": len(gdf_filtered)
            })

# ----------------------------------------------------------------------
# --------------------- PUNTO DI INGRESSO ------------------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    try:
        vector_extractor_app()
    except ImportError:
        st.error("⚠️ **Errore di dipendenza:** Le librerie GIS (`geopandas`, `fiona`, `requests`, `shapely`, `pandas`) non sono installate.")
