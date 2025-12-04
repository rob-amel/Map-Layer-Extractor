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

# --- CONFIGURATION & STYLING (English & Centered) ---

st.set_page_config(
    page_title="🗺️ Vector Data Extractor GIS", 
    layout="centered", # Set the layout to 'centered'
    initial_sidebar_state="collapsed"
)

# Custom CSS for the download button (red background, white text)
st.markdown("""
<style>
/* Target the main button style, specific to the download button for safety */
.stDownloadButton > button {
    background-color: #FF4B4B !important; /* Red */
    color: white !important; /* White text */
    border-radius: 8px;
    padding: 10px 24px;
    font-weight: bold;
    border: none;
}
.stDownloadButton > button:hover {
    background-color: #CC0000 !important; /* Darker Red on hover */
    color: white !important;
}
</style>
""", unsafe_allow_html=True)

# ----------------------------------------------------------------------
# --------------------- MAIN STREAMLIT FUNCTION ------------------------
# ----------------------------------------------------------------------

def vector_extractor_app():
    
    st.title("🗺️ Universal Vector Data Extractor GIS (V11)")
    st.subheader("Extract layers and attribute data from online maps (incl. ArcGIS FeatureServices).")
    st.markdown("---")

    # --- DATA INPUT (URL OR FILE UPLOAD) ---
    st.header("1. 🔗 Data Source")
    
    source_method = st.radio(
        "Select Input Method:",
        options=["Direct URL", "Upload Local File"],
        horizontal=True
    )
    
    url_endpoint = ""
    uploaded_file = None
    
    if source_method == "Direct URL":
        st.caption("Paste the URL of the vector data service. **For ArcGIS, use the clean FeatureServer URL** (e.g., ending in `/FeatureServer/0`).")
        url_endpoint = st.text_input(
            "Direct JSON/WFS URL:",
            placeholder="Example: https://services.arcgis.com/layer/FeatureServer/0",
        )
    else:
        st.caption("Upload your local JSON/GeoJSON file.")
        st.caption("⚠️ **ATTENTION:** Do not upload map configuration files, only raw vector data.")
        uploaded_file = st.file_uploader(
            "Upload JSON/GeoJSON File",
            type=["json", "geojson"],
            accept_multiple_files=False
        )

    # --- GENERAL SETTINGS ---
    feature_name = st.text_input(
        "Output Layer Name:",
        placeholder="Example: historic_buildings",
        value="layer_extract",
        help="The name for the final output file."
    )
    
    st.markdown("---")

    # --- OUTPUT COLUMN ---
    
    st.header("2. 💾 Output Settings")
    
    output_format = st.selectbox(
        "GIS Output Format:",
        options=["Shapefile (.shp)", "GeoJSON", "GeoPackage (.gpkg)", "CSV (with coordinates)"],
        index=0,
        help="Select the standard format for your GIS software."
    )
    
    st.markdown("---")

    # --- MAIN ACTION BUTTON ---
    
    download_disabled = not ((url_endpoint or uploaded_file) and feature_name)
    
    # Indicate the final step for the user
    st.markdown(
        "> **Operation Complete:** The download button will appear below when the file is ready."
    )
    st.markdown("---")
    
    if st.button("⬇️ Start Extraction and Conversion", type="primary", disabled=download_disabled):
        
        if download_disabled:
                st.error("Please enter the URL/upload the file and provide an Output Layer Name.")
                st.stop()
        
        st.empty()

        with st.spinner(f"Starting processing of layer '{feature_name}'..."):
            
            base_filename = feature_name
            json_data = None 
            
            # --- PHASE 1: DATA ACQUISITION AND JSON PARSING ---
            try:
                st.info("Step 1/3: Acquiring data...")
                
                if source_method == "Direct URL":
                    target_url = url_endpoint
                    
                    # Handle FeatureServer: add GeoJSON query if missing
                    if "FeatureServer" in url_endpoint and "/query" not in url_endpoint.lower():
                        st.info("ArcGIS FeatureServer URL detected. Appending standard GeoJSON query for full data extraction...")
                        target_url = url_endpoint.rstrip('/') + "/query?f=geojson&where=1=1&outFields=*"
                            
                    response = requests.get(target_url)
                    response.raise_for_status() 
                    json_data = response.json()
                    
                elif source_method == "Upload Local File" and uploaded_file is not None:
                    json_data = json.load(uploaded_file)
                    
            except requests.exceptions.RequestException as e:
                st.error(f"❌ Error during URL download: {e}. The server may not have responded or the link is incorrect.")
                return
            except json.JSONDecodeError:
                st.error("❌ Error: The content downloaded/uploaded is not valid JSON.")
                return
            except Exception as e:
                st.error(f"❌ Error during data source acquisition: {e}")
                return

            # --- PHASE 2: GIS DATA PREPARATION (Conversion and Cleaning) ---
            try:
                st.info("Step 2/3: Cleaning JSON and loading GIS data...")
                
                gdf = None
                
                # ATTEMPT 1: JSON is a LIST of objects with lat/lon fields (e.g., White Phosphorus)
                if isinstance(json_data, list) and all(isinstance(d, dict) and 'lat' in d and 'lon' in d for d in json_data):
                    st.warning("JSON identified as a **list of objects with lat/lon fields**. Performing manual GeoDataFrame conversion...")
                    
                    # CRITICAL Filter: removes objects with missing or None lat/lon
                    valid_data = [d for d in json_data if d.get('lat') is not None and d.get('lon') is not None]

                    if not valid_data:
                        st.error("❌ Error: No valid objects found after removing those with missing lat/lon. GeoDataFrame conversion failed.")
                        st.stop()
                        
                    geometry = [Point(d['lon'], d['lat']) for d in valid_data]
                    
                    df = pd.DataFrame(valid_data)
                    df.drop(columns=['lat', 'lon'], inplace=True, errors='ignore')

                    gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")
                    
                # ATTEMPT 2: JSON is a DICTIONARY (Standard or Nested GeoJSON)
                elif isinstance(json_data, dict):
                    
                    final_geojson_content = None
                    
                    # Tries 2.1: Standard GeoJSON
                    if json_data.get('type') == 'FeatureCollection' or 'features' in json_data:
                        final_geojson_content = json_data
                        
                    # Tries 2.2: Nested JSON ('geoData')
                    if final_geojson_content is None and 'geoData' in json_data and isinstance(json_data['geoData'], list):
                        st.warning("JSON identified with 'geoData' key. Encapsulating in GeoJSON Collection.")
                        final_geojson_content = {"type": "FeatureCollection", "features": json_data['geoData']}
                        
                    # Tries 2.3: ArcGIS Esri Format (Feature container)
                    if final_geojson_content is None and 'featureSet' in json_data and 'features' in json_data['featureSet']:
                        st.warning("JSON identified as ArcGIS format. Extracting features.")
                        final_geojson_content = {"type": "FeatureCollection", "features": json_data['featureSet']['features']}

                    # Tries 2.4: Unwrapped list of Features
                    if final_geojson_content is None and 'features' in json_data and not json_data.get('type'):
                        st.warning("JSON identified as an unwrapped list of Features. Adding FeatureCollection wrapper.")
                        final_geojson_content = {"type": "FeatureCollection", "features": json_data['features']}


                    if final_geojson_content:
                        json_string = json.dumps(final_geojson_content)
                        raw_data_buffer = io.BytesIO(json_string.encode('utf-8'))
                        gdf = gpd.read_file(raw_data_buffer)
                    
                if gdf is None:
                    st.error("❌ Unrecognized JSON Format. Content is neither GeoJSON nor a list of lat/lon objects. Please ensure you are providing the raw data URL or file, not a map configuration file.")
                    return
                
                if gdf.empty:
                    st.warning("⚠️ No objects found in the data. The file may be empty.")
                    return
                
                # NO FILTERS APPLIED - PROCEED TO FULL DOWNLOAD
                gdf_filtered = gdf
                st.success(f"✅ Found {len(gdf_filtered)} objects. Proceeding to download.")

            except Exception as e:
                st.error(f"❌ Critical error during GIS loading. GeoPandas failed to interpret the final data. Details: {e}")
                st.warning("Verify the geometry validity (e.g., coordinates are not null, feature structure is correct).")
                return

            # --- PHASE 3: SAVE TO BUFFER AND PREPARE DOWNLOAD ---
            
            download_data = None
            mime_type = "application/octet-stream"
            label = f"Download {base_filename}"
            file_name = f"{base_filename}"

            if output_format == "Shapefile (.shp)":
                st.info("Step 3/3: Compressing into Shapefile (ZIP)...")
                
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
                label = f"Download {base_filename}.zip (Shapefile)"

            elif output_format == "GeoPackage (.gpkg)":
                st.info("Step 3/3: Converting to GeoPackage...")
                download_buffer = io.BytesIO()
                gdf_filtered.to_file(download_buffer, driver='GPKG', encoding='utf-8')
                download_buffer.seek(0)
                
                download_data = download_buffer.getvalue()
                file_name = f"{base_filename}.gpkg"
                mime_type = "application/octet-stream"
                label = f"Download {base_filename}.gpkg"

            elif output_format == "GeoJSON":
                st.info("Step 3/3: Generating GeoJSON...")
                output_content = gdf_filtered.to_json(na='drop')
                download_data = output_content.encode('utf-8')
                mime_type = "application/geo+json"
                file_name = f"{base_filename}.geojson"
                label = f"Download {base_filename}.geojson"
            
            else: # CSV
                st.info("Step 3/3: Generating CSV...")
                gdf_csv = gdf_filtered.copy()
                gdf_csv['WKT_Geometry'] = gdf_csv.geometry.apply(lambda x: x.wkt) 
                gdf_csv = gdf_csv.drop(columns=['geometry'])
                output_content = gdf_csv.to_csv(index=False, na_rep='')
                download_data = output_content.encode('utf-8')
                mime_type = "text/csv"
                file_name = f"{base_filename}.csv"
                label = f"Download {base_filename}.csv"
                
            # 4. FINAL DOWNLOAD BUTTON (RED/WHITE)
            st.success("🎉 Conversion completed successfully! Click to download your GIS file.")
            st.download_button(
                label=label,
                data=download_data,
                file_name=file_name,
                mime=mime_type
            )
            
            # Summary of parameters used
            st.markdown("#### Extraction Summary")
            st.json({
                "source_used": source_method,
                "url_or_file": url_endpoint if url_endpoint else "File Uploaded",
                "layer_output": base_filename,
                "output_format": output_format,
                "final_objects_extracted": len(gdf_filtered)
            })

# ----------------------------------------------------------------------
# --------------------- ENTRY POINT ------------------------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    try:
        vector_extractor_app()
    except ImportError:
        st.error("⚠️ **Dependency Error:** Required GIS libraries are not installed.")
