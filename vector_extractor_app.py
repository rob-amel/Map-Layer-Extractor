import streamlit as st
import os
import io
import requests
import geopandas as gpd
import json
import tempfile
import zipfile
# Nessuna dipendenza esterna oltre le basi

# --- CONFIGURAZIONE E STILE ---

st.set_page_config(page_title="🗺️ Vector Data Extractor GIS", layout="wide")

# ----------------------------------------------------------------------
# --------------------- FUNZIONE PRINCIPALE STREAMLIT ------------------
# ----------------------------------------------------------------------

def vector_extractor_app():
    
    st.title("🗺️ Estrattore di Dati Vettoriali GIS Online (V6)")
    st.subheader("Massima compatibilità JSON: Carica da URL o file locale e converti.")
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
        st.caption("Copia l'URL del servizio dati vettoriali (intercettato con F12).")
        url_endpoint = st.text_input(
            "URL Diretto del File JSON/WFS:",
            placeholder="Esempio: https://api.example.com/data/layer?f=geojson",
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

    # --- COLONNE PER FILTRAGGIO E OUTPUT ---
    col2, col3 = st.columns([1, 1])

    with col2:
        st.header("2. 🎯 Filtraggio e Area")
        st.markdown("**Area di Filtro (Bounding Box WGS84)**")
        st.caption("Filtra i dati geograficamente (lat/lon). Utile per dataset grandi.")
        
        bbox_min_lat = st.number_input("Latitudine Minima (Ymin)", min_value=-90.0, max_value=90.0, value=45.45, step=0.01, format="%.4f")
        bbox_min_lon = st.number_input("Longitudine Minima (Xmin)", min_value=-180.0, max_value=180.0, value=9.15, step=0.01, format="%.4f")
        bbox_max_lat = st.number_input("Latitudine Massima (Ymax)", min_value=-90.0, max_value=90.0, value=45.50, step=0.01, format="%.4f")
        bbox_max_lon = st.number_input("Longitudine Massima (Xmax)", min_value=-180.0, max_value=180.0, value=9.25, step=0.01, format="%.4f")

        st.markdown("---")
        
        st.markdown("**Filtro Attributo (Query)**")
        attribute_filter = st.text_input(
            "Filtro Attributo Aggiuntivo:",
            placeholder="Esempio: name=='Parco Sempione'",
            help="Filtra ulteriormente gli oggetti, applicato dopo il download (sintassi Pandas/Python)."
        )

    with col3:
        st.header("3. 💾 Output e Conversione")
        
        output_format = st.selectbox(
            "Formato di Output GIS:",
            options=["Shapefile (.shp)", "GeoJSON", "GeoPackage (.gpkg)", "CSV (con coordinate)"],
            index=0,
            help="Seleziona il formato standard per il tuo software GIS."
        )
        
        st.markdown("---")
        
        download_disabled = not ((url_endpoint or uploaded_file) and feature_name)
        
        if st.button("⬇️ Avvia Estrazione, Filtro e Conversione", type="primary", disabled=download_disabled):
            
            if download_disabled:
                 st.error("Per favore, inserisci l'URL/carica il file e inserisci il Nome del Layer.")
                 st.stop()
            
            st.empty()

            with st.spinner(f"Inizio l'elaborazione del layer '{feature_name}'..."):
                
                base_filename = feature_name
                json_data = None 
                
                # --- FASE 1: ACQUISIZIONE DATI E PARSING IN JSON ---
                try:
                    st.info("Passaggio 1/4: Acquisizione dei dati...")
                    
                    if source_method == "URL Diretto":
                        response = requests.get(url_endpoint)
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
                    st.info("Passaggio 2/4: Pulizia del JSON e caricamento GIS...")
                    
                    final_geojson_content = None

                    if isinstance(json_data, dict):
                        
                        # Tentativo 1: GeoJSON standard
                        if json_data.get('type') == 'FeatureCollection' or 'features' in json_data:
                            final_geojson_content = json_data
                            
                        # Tentativo 2: JSON Annidato (CASO SPECIFICO: geoData)
                        elif 'geoData' in json_data and isinstance(json_data['geoData'], list):
                            st.warning("JSON identificato con chiave 'geoData'. Sto incapsulando la lista in un GeoJSON Collection.")
                            # Assumiamo che 'geoData' sia una lista di Feature GeoJSON
                            final_geojson_content = {"type": "FeatureCollection", "features": json_data['geoData']}
                            
                        # Tentativo 3: Formato ArcGIS Esri (comune per il primo URL fornito)
                        elif 'featureSet' in json_data and 'features' in json_data['featureSet']:
                            st.warning("JSON identificato come formato ArcGIS. Estraggo le feature.")
                            final_geojson_content = {"type": "FeatureCollection", "features": json_data['featureSet']['features']}
                            
                        elif 'features' in json_data and not json_data.get('type'):
                            st.warning("JSON identificato come lista di Feature non incapsulata. Aggiungo FeatureCollection.")
                            final_geojson_content = {"type": "FeatureCollection", "features": json_data['features']}

                    if final_geojson_content is None:
                        st.error("❌ Formato JSON non riconosciuto. Il JSON non contiene 'features' in una posizione standard o sotto la chiave 'geoData'.")
                        st.stop()

                    # Carica il GeoJSON pulito in memoria (buffer)
                    json_string = json.dumps(final_geojson_content)
                    raw_data_buffer = io.BytesIO(json_string.encode('utf-8'))
                    
                    # Carica il GeoJSON pulito in un GeoDataFrame
                    gdf = gpd.read_file(raw_data_buffer)

                    # Filtro geografico (Bounding Box)
                    gdf_filtered = gdf.cx[bbox_min_lon:bbox_max_lon, bbox_min_lat:bbox_max_lat]
                    
                    # Filtro per attributo (se l'utente ha inserito una query)
                    if attribute_filter:
                        gdf_filtered = gdf_filtered.query(attribute_filter)

                    if gdf_filtered.empty:
                        st.warning("⚠️ L'area filtrata non contiene oggetti o la query attributo è troppo restrittiva. Nessun download disponibile.")
                        st.stop()
                    
                    st.success(f"Trovati {len(gdf_filtered)} oggetti dopo il filtraggio.")

                except Exception as e:
                    st.error(f"❌ Errore critico durante il caricamento o il filtraggio GIS: GeoPandas non è riuscito a interpretare il dato finale. Dettagli: {e}")
                    st.warning("Verifica che le geometrie all'interno del file JSON siano valide (coordinate non nulle, struttura Feature corretta).")
                    return

                # --- FASE 3: SALVATAGGIO IN MEMORIA (BUFFER) E PREPARAZIONE DOWNLOAD ---
                
                download_data = None
                mime_type = "application/octet-stream"
                label = f"Scarica {base_filename}"
                file_name = f"{base_filename}"

                if output_format == "Shapefile (.shp)":
                    st.info("Passaggio 3/4: Compressione in formato Shapefile (ZIP)...")
                    
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
                    st.info("Passaggio 3/4: Conversione in GeoPackage...")
                    download_buffer = io.BytesIO()
                    gdf_filtered.to_file(download_buffer, driver='GPKG', encoding='utf-8')
                    download_buffer.seek(0)
                    
                    download_data = download_buffer.getvalue()
                    file_name = f"{base_filename}.gpkg"
                    mime_type = "application/octet-stream"
                    label = f"Scarica {base_filename}.gpkg"

                elif output_format == "GeoJSON":
                    st.info("Passaggio 3/4: Generazione di GeoJSON...")
                    output_content = gdf_filtered.to_json(na='drop')
                    download_data = output_content.encode('utf-8')
                    mime_type = "application/geo+json"
                    file_name = f"{base_filename}.geojson"
                    label = f"Scarica {base_filename}.geojson"
                
                else: # CSV
                    st.info("Passaggio 3/4: Generazione di CSV...")
                    gdf_csv = gdf_filtered.copy()
                    gdf_csv['WKT_Geometry'] = gdf_csv.geometry.apply(lambda x: x.wkt)
                    gdf_csv = gdf_csv.drop(columns=['geometry'])
                    output_content = gdf_csv.to_csv(index=False, na_rep='')
                    download_data = output_content.encode('utf-8')
                    mime_type = "text/csv"
                    file_name = f"{base_filename}.csv"
                    label = f"Scarica {base_filename}.csv"
                    
                # 4. PULSANTE DI DOWNLOAD FINALE
                st.success("✅ Conversione completata! Clicca per scaricare il tuo file GIS.")
                st.download_button(
                    label=label,
                    data=download_data,
                    file_name=file_name,
                    mime=mime_type
                )
                
                # Riepilogo dei parametri usati
                st.markdown("#### Parametri di Estrazione Eseguiti")
                st.json({
                    "sorgente_utilizzata": source_method,
                    "url_o_file": url_endpoint if url_endpoint else "File Caricato",
                    "layer_output": base_filename,
                    "bbox_filtro_wgs84": f"{bbox_min_lon}, {bbox_min_lat}, {bbox_max_lon}, {bbox_max_lat}",
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
        st.error("⚠️ **Errore di dipendenza:** Le librerie GIS (`geopandas`, `fiona`, `requests`) non sono installate.")
