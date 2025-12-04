import streamlit as st
import os
import io
import requests
import geopandas as gpd
import json
import tempfile
import zipfile

# --- CONFIGURAZIONE E STILE ---

st.set_page_config(page_title="🗺️ Vector Data Extractor GIS", layout="wide")

# ----------------------------------------------------------------------
# --------------------- FUNZIONE PRINCIPALE STREAMLIT ------------------
# ----------------------------------------------------------------------

def vector_extractor_app():
    
    st.title("🗺️ Estrattore di Dati Vettoriali GIS Online (V2)")
    st.subheader("Inserisci l'URL diretto intercettato (F12 Network) per estrarre e convertire i layer.")
    st.markdown("---")

    # --- COLONNE PER IL LAYOUT ---
    col1, col2 = st.columns([1, 1])

    with col1:
        st.header("1. 🔗 Sorgente Dati Intercettata")
        
        # URL intercettato (l'input principale del metodo F12)
        url_endpoint = st.text_input(
            "URL Diretto del File GeoJSON/WFS (Copia da F12 > Network):",
            placeholder="Esempio: https://api.example.com/data/layer?bbox=...&format=geojson",
            help="L'indirizzo web esatto del dato vettoriale intercettato dal browser."
        )
        
        # Nome del Layer (serve per il nome del file di output)
        feature_name = st.text_input(
            "Nome del Layer (per il salvataggio del file):",
            placeholder="Esempio: edifici_storici",
            value="layer_test",
            help="Il nome che vuoi dare al file vettoriale finale."
        )
        
        # Tipo di Sorgente (utile solo per la logica interna, ma non è il focus)
        st.markdown("---")
        source_type = st.selectbox(
            "Tipo di Servizio (per riferimento interno):",
            options=["GeoJSON Diretto", "WFS", "API Standard"],
            help="Definisce il formato di richiesta che è stato intercettato."
        )
    
    with col2:
        st.header("2. 🎯 Filtraggio e Area di Interesse")
        
        st.markdown("**Area di Filtro (Bounding Box WGS84)**")
        st.caption("Usa questo filtro per limitare i dati geograficamente (lat/lon).")
        
        # Input per il Bounding Box (Lat/Lon)
        bbox_min_lat = st.number_input("Latitudine Minima (Ymin)", min_value=-90.0, max_value=90.0, value=45.45, step=0.01, format="%.4f")
        bbox_min_lon = st.number_input("Longitudine Minima (Xmin)", min_value=-180.0, max_value=180.0, value=9.15, step=0.01, format="%.4f")
        bbox_max_lat = st.number_input("Latitudine Massima (Ymax)", min_value=-90.0, max_value=90.0, value=45.50, step=0.01, format="%.4f")
        bbox_max_lon = st.number_input("Longitudine Massima (Xmax)", min_value=-180.0, max_value=180.0, value=9.25, step=0.01, format="%.4f")

        st.markdown("---")
        
        st.markdown("**Filtro Attributo (Query SQL-Like)**")
        attribute_filter = st.text_input(
            "Filtro Attributo Aggiuntivo:",
            placeholder="Esempio: name=='Parco Sempione'",
            help="Filtra ulteriormente gli oggetti, applicato dopo il download usando la sintassi Pandas/Python."
        )

    st.markdown("---")
    
    # --- CONTROLLI DI OUTPUT E AZIONE ---
    st.header("3. 💾 Output e Download")
    
    st.text_input(
        "Directory (Solo un nome per il file, il download è diretto):",
        value="./gis_downloads",
        disabled=True
    )

    col_output_format, col_action = st.columns([1, 1])

    with col_output_format:
        output_format = st.selectbox(
            "Formato di Output GIS:",
            options=["GeoJSON", "GeoPackage (.gpkg)", "Shapefile (.shp)", "CSV (con coordinate)"],
            help="Seleziona il formato standard per il tuo software GIS."
        )
    
    with col_action:
        download_disabled = not (url_endpoint and feature_name)
        
        if st.button("⬇️ Avvia Estrazione, Filtro e Download", type="primary", disabled=download_disabled):
            
            if download_disabled:
                 st.error("Per favore, inserisci l'URL diretto e il Nome del Layer.")
                 st.stop()
            
            # Nasconde il precedente output e log
            st.empty()

            with st.spinner(f"Inizio l'estrazione e la conversione del layer '{feature_name}'..."):
                
                url = url_endpoint
                base_filename = feature_name
                
                # 1. SCARICA IL DATO GREZZO GeoJSON
                try:
                    st.info("Passaggio 1/4: Scarico l'URL intercettato...")
                    response = requests.get(url)
                    response.raise_for_status()
                    raw_geojson = response.json()
                except requests.exceptions.RequestException as e:
                    st.error(f"❌ Errore durante il download dell'URL: {e}")
                    return
                except json.JSONDecodeError:
                    st.error("❌ Errore: Il contenuto scaricato non è un JSON valido. Controlla l'URL.")
                    return

                # 2. CARICA E FILTRA I DATI
                try:
                    st.info("Passaggio 2/4: Caricamento e filtraggio dei dati...")
                    
                    # Carica il GeoJSON in un GeoDataFrame
                    gdf = gpd.GeoDataFrame.from_features(raw_geojson)

                    # Filtro geografico (Bounding Box)
                    # Sintassi geopandas: gdf.cx[xmin:xmax, ymin:ymax]
                    gdf_filtered = gdf.cx[bbox_min_lon:bbox_max_lon, bbox_min_lat:bbox_max_lat]
                    
                    # Filtro per attributo (se l'utente ha inserito una query)
                    if attribute_filter:
                        # La funzione .query() di pandas/geopandas usa sintassi Python
                        gdf_filtered = gdf_filtered.query(attribute_filter)

                    if gdf_filtered.empty:
                        st.warning("⚠️ L'area filtrata non contiene oggetti o la query attributo è troppo restrittiva.")
                        st.stop()
                    
                    st.success(f"Trovati {len(gdf_filtered)} oggetti dopo il filtraggio.")

                except Exception as e:
                    st.error(f"❌ Errore durante il filtraggio GIS (Geopandas): Controlla la sintassi del filtro attributo. Dettagli: {e}")
                    return

                # 3. SALVATAGGIO IN MEMORIA (BUFFER) E PREPARAZIONE DOWNLOAD
                
                download_data = None
                mime_type = "application/octet-stream"
                label = f"Scarica {base_filename}"
                file_name = f"{base_filename}"

                if output_format == "Shapefile (.shp)":
                    st.info("Passaggio 3/4: Compressione in formato Shapefile (ZIP)...")
                    
                    zip_buffer = io.BytesIO()
                    
                    # Lo shapefile richiede un driver e deve essere zippato
                    with tempfile.TemporaryDirectory() as tmpdir:
                        temp_filepath = os.path.join(tmpdir, base_filename + '.shp')
                        gdf_filtered.to_file(temp_filepath, driver='ESRI Shapefile', encoding='utf-8')
                        
                        # Zippa tutti i file dello Shapefile (shp, shx, dbf, prj)
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

                else: # GeoJSON o CSV
                    st.info("Passaggio 3/4: Generazione di GeoJSON/CSV...")
                    
                    if output_format == "GeoJSON":
                        output_content = gdf_filtered.to_json(na='drop')
                        mime_type = "application/geo+json"
                        file_name = f"{base_filename}.geojson"
                    else: # CSV
                        gdf_csv = gdf_filtered.copy()
                        # Esporta la geometria in testo WKT (Well-Known Text)
                        gdf_csv['WKT_Geometry'] = gdf_csv.geometry.apply(lambda x: x.wkt)
                        gdf_csv = gdf_csv.drop(columns=['geometry'])
                        output_content = gdf_csv.to_csv(index=False, na_rep='')
                        mime_type = "text/csv"
                        file_name = f"{base_filename}.csv"
                    
                    download_data = output_content.encode('utf-8')
                    label = f"Scarica {file_name}"
                    
                # 4. PULSANTE DI DOWNLOAD FINALE
                st.success("✅ Estrazione completata! Clicca per scaricare il tuo file GIS.")
                st.download_button(
                    label=label,
                    data=download_data,
                    file_name=file_name,
                    mime=mime_type
                )
                
                # Riepilogo dei parametri usati
                st.markdown("#### Parametri di Estrazione Eseguiti")
                st.json({
                    "url_sorgente": url,
                    "layer_output": base_filename,
                    "bbox_filtro_wgs84": f"{bbox_min_lon}, {bbox_min_lat}, {bbox_max_lon}, {bbox_max_lat}",
                    "formato_output": output_format,
                    "oggetti_estratti_finali": len(gdf_filtered)
                })

# ----------------------------------------------------------------------
# --------------------- PUNTO DI INGRESSO ------------------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    vector_extractor_app()
