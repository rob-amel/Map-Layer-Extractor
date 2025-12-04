import streamlit as st
import os
import io

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
        
        # La logica di filtraggio è ancora utile se l'URL non contiene già un BBox
        st.markdown("**Area di Filtro (Bounding Box WGS84)**")
        st.caption("Usa questo filtro se l'URL intercettato fornisce troppi dati e devi limitarli geograficamente. Se l'URL è già filtrato, puoi lasciare i valori di default.")
        
        # Input per il Bounding Box (Lat/Lon)
        bbox_min_lat = st.number_input("Latitudine Minima (Ymin)", min_value=-90.0, max_value=90.0, value=45.45, step=0.01, format="%.4f")
        bbox_min_lon = st.number_input("Longitudine Minima (Xmin)", min_value=-180.0, max_value=180.0, value=9.15, step=0.01, format="%.4f")
        bbox_max_lat = st.number_input("Latitudine Massima (Ymax)", min_value=-90.0, max_value=90.0, value=45.50, step=0.01, format="%.4f")
        bbox_max_lon = st.number_input("Longitudine Massima (Xmax)", min_value=-180.0, max_value=180.0, value=9.25, step=0.01, format="%.4f")

        st.markdown("---")
        
        st.markdown("**Filtro Attributo (Query SQL-Like)**")
        attribute_filter = st.text_input(
            "Filtro Attributo Aggiuntivo:",
            placeholder="Esempio: name='Parco Sempione'",
            help="Filtra ulteriormente gli oggetti dopo il download, usando Geopandas."
        )

    st.markdown("---")
    
    # --- CONTROLLI DI OUTPUT E AZIONE ---
    st.header("3. 💾 Output e Download")
    
    # In Streamlit Cloud non puoi specificare una directory locale persistente,
    # quindi l'output sarà temporaneo o un download diretto.
    output_dir = st.text_input(
        "Directory (Nome Base per Salvataggio):",
        placeholder="./gis_downloads",
        value="./gis_downloads",
        help="In Streamlit Cloud, questo è solo un riferimento. Il download sarà probabilmente un pulsante diretto."
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
                 return

            # --- LOGICA DI ESECUZIONE (PLACEHOLDER) ---
            
            st.info("Inizio l'estrazione dei dati.")
            
            st.code(f"""
# 1. Scarica l'URL intercettato:
# response = requests.get('{url_endpoint}')
# raw_geojson = response.json()

# 2. Carica in GeoPandas:
# gdf = geopandas.GeoDataFrame.from_features(raw_geojson)

# 3. Filtra geograficamente (se necessario) e per attributo (se specificato)
# Filtro_bbox = (gdf.cx[{bbox_min_lon}:{bbox_max_lon}, {bbox_min_lat}:{bbox_max_lat}]) 
# gdf_filtered = Filtro_bbox.query('{attribute_filter}') # Se c'è un filtro attributo

# 4. Salva nel formato GIS finale:
# output_filename = '{feature_name}.{output_format.split(" ")[0].lower()}'
# # Esempio di salvataggio in un buffer per un pulsante di download Streamlit:
# # buffer = io.BytesIO()
# # gdf_filtered.to_file(buffer, driver='<Driver Specifico>')
# # st.download_button(...)
            """, language="python")

            
            st.success("✅ Interfaccia testata!")
            st.warning("Ricorda: Per funzionare, devi implementare il codice che usa **`requests`** e **`geopandas`** all'interno del blocco `if st.button(...)`.")
            
            # Riepilogo dei parametri usati
            st.markdown("#### Parametri di Estrazione")
            st.json({
                "url_sorgente": url_endpoint,
                "layer_output": feature_name,
                "bbox_filtro_wgs84": f"{bbox_min_lon}, {bbox_min_lat}, {bbox_max_lon}, {bbox_max_lat}",
                "formato_output": output_format
            })

# ----------------------------------------------------------------------
if __name__ == "__main__":
    vector_extractor_app()
