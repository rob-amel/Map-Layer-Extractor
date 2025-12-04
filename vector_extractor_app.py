import streamlit as st
import os
import io

# --- CONFIGURAZIONE E STILE ---

# L'emoji del mappamondo è appropriata per il contesto GIS
st.set_page_config(page_title="🗺️ Vector Data Extractor GIS", layout="wide")

# ----------------------------------------------------------------------
# --------------------- FUNZIONE PRINCIPALE STREAMLIT ------------------
# ----------------------------------------------------------------------

def vector_extractor_app():
    
    st.title("🗺️ Estrattore di Dati Vettoriali GIS Online")
    st.subheader("Configura la sorgente e l'area per l'estrazione dei layer vettoriali.")
    st.markdown("---")

    # --- COLONNE PER IL LAYOUT ---
    col1, col2 = st.columns([1, 1])

    with col1:
        st.header("1. 🔗 Sorgente Dati e Layer")
        
        # Tipo di Sorgente
        source_type = st.selectbox(
            "Tipo di Sorgente Vettoriale:",
            options=["WFS (Web Feature Service)", "API Vettoriale Standard (GeoJSON)", "Overpass API (OpenStreetMap)"],
            help="Seleziona il tipo di servizio che fornisce i dati vettoriali."
        )
        
        # URL del Servizio
        url_endpoint = st.text_input(
            "URL del Servizio/Endpoint:",
            placeholder="Esempio: https://geoserver.example.com/wfs",
            help="L'indirizzo del server che ospita il servizio dati."
        )
        
        # Nome del Layer
        feature_name = st.text_input(
            "Nome del Layer (Feature Type):",
            placeholder="Esempio: strade_principali, edifici_storici",
            help="Il nome specifico del layer o della tabella da estrarre."
        )
    
    with col2:
        st.header("2. 🎯 Filtraggio e Area di Interesse")
        
        # Controlli di Filtraggio (Definizione del Contenuto)
        st.markdown("**Area di Interesse (Bounding Box WGS84)**")
        
        # Input per il Bounding Box (Lat/Lon)
        # Ho impostato dei valori predefiniti per Milano, Italia
        bbox_min_lat = st.number_input("Latitudine Minima (Ymin)", min_value=-90.0, max_value=90.0, value=45.45, step=0.01, format="%.4f")
        bbox_min_lon = st.number_input("Longitudine Minima (Xmin)", min_value=-180.0, max_value=180.0, value=9.15, step=0.01, format="%.4f")
        bbox_max_lat = st.number_input("Latitudine Massima (Ymax)", min_value=-90.0, max_value=90.0, value=45.50, step=0.01, format="%.4f")
        bbox_max_lon = st.number_input("Longitudine Massima (Xmax)", min_value=-180.0, max_value=180.0, value=9.25, step=0.01, format="%.4f")

        st.markdown("---")
        
        st.markdown("**Filtro Attributo (Clausola WHERE)**")
        attribute_filter = st.text_input(
            "Query di Filtraggio:",
            placeholder="Esempio: nome='Ponte Vecchio' AND tipo='storico'",
            help="Filtra gli oggetti in base agli attributi (sintassi dipende dal servizio API)."
        )

    st.markdown("---")
    
    # --- CONTROLLI DI OUTPUT E AZIONE (A PIENA LARGHEZZA) ---
    st.header("3. 💾 Output e Download")
    
    output_dir = st.text_input(
        "Directory di Salvataggio Locale (Nota: In Streamlit Cloud, salva in una cartella temporanea):",
        placeholder="./gis_downloads",
        value="./gis_downloads", # Valore predefinito
        help="Il percorso relativo o assoluto dove verrà salvato il file vettoriale."
    )

    col_output_format, col_action = st.columns([1, 1])

    with col_output_format:
        output_format = st.selectbox(
            "Formato di Output GIS:",
            options=["GeoJSON", "GeoPackage (.gpkg)", "Shapefile (.shp)", "CSV (con coordinate)"],
            help="Seleziona il formato standard per il tuo software GIS."
        )
    
    with col_action:
        # Controlli essenziali per abilitare il pulsante
        download_disabled = not (url_endpoint and output_dir and feature_name)
        
        if st.button("⬇️ Avvia Estrazione e Download", type="primary", disabled=download_disabled):
            
            # --- VALIDAZIONE E PREPARAZIONE ---
            
            if download_disabled:
                 st.error("Per favore, inserisci l'URL del Servizio, la Directory e il Nome del Layer.")
                 return

            # Esecuzione del Bounding Box
            bbox = f"{bbox_min_lon},{bbox_min_lat},{bbox_max_lon},{bbox_max_lat}"
            
            # --- LOGICA DI ESECUZIONE (PLACEHOLDER) ---
            
            st.info("Inizio l'estrazione dei dati. **ATTENZIONE:** La logica di download con `requests` e `geopandas` deve ancora essere implementata qui.")
            
            st.code(f"""
# 1. Creare la directory di output (se non esiste)
# os.makedirs("{output_dir}", exist_ok=True)

# 2. Costruire la richiesta WFS/API (es. per WFS)
# wfs_params = {{
#     'service': 'WFS',
#     'request': 'GetFeature',
#     'version': '1.1.0',
#     'typeName': '{feature_name}',
#     'bbox': '{bbox}', 
#     'outputFormat': 'application/json' # Formato richiesto
# }}

# 3. Eseguire la richiesta:
# response = requests.get("{url_endpoint}", params=wfs_params)
# data = response.json()

# 4. Caricare i dati in GeoPandas e salvare:
# gdf = geopandas.GeoDataFrame.from_features(data)
# output_filepath = os.path.join("{output_dir}", "{feature_name}.{output_format.split(' ')[0].lower()}")
# gdf.to_file(output_filepath, driver='<Driver Specifico>')
            """, language="python")

            
            st.success("✅ Interfaccia testata!")
            st.warning("Per far funzionare il download, **devi** implementare il codice Python qui sopra, installare `geopandas` e `requests` e avviare il processo di estrazione.")
            
            # Riepilogo dei parametri usati
            st.json({
                "source": source_type,
                "url": url_endpoint,
                "layer": feature_name,
                "bbox_wgs84": bbox,
                "filter_query": attribute_filter or "Nessuno",
                "format_output": output_format
            })
            
# ----------------------------------------------------------------------
# --------------------- PUNTO DI INGRESSO ------------------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    vector_extractor_app()