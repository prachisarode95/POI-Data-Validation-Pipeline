# =============================================================================
#               POI Data Validation & Quality Analysis
# =============================================================================
import os
import warnings
import osmnx as ox
import geopandas as gpd
import pandas as pd

warnings.filterwarnings('ignore')

# =============================================================================
# FOLDER SETUP
# =============================================================================

os.makedirs('output',  exist_ok=True)
os.makedirs('reports', exist_ok=True)

# =============================================================================
# CONFIGURATION
# =============================================================================

CITY_NAME = "Bangalore, Karnataka, India"

POI_TAGS = {
    "amenity": [
        "hospital",
        "bank",
        "atm",
        "restaurant",
        "fuel",
        "pharmacy",
        "school",
        "police"
    ]
}

# Bengaluru bounding box for coordinate boundary validation
BBOX = {
    'lat_min': 12.7,
    'lat_max': 13.2,
    'lon_min': 77.3,
    'lon_max': 77.9
}

# Format → amenity : (main_category, sub_category, priority_level)
# Priority: 1 = Emergency/Essential, 2 = Important daily-use, 3 = General
CATEGORY_MAP = {
    'hospital'  : ('Healthcare',            'Hospital',        1),
    'pharmacy'  : ('Healthcare',            'Pharmacy',        1),
    'police'    : ('Emergency Services',    'Police Station',  1),
    'bank'      : ('Financial Services',    'Bank',            2),
    'atm'       : ('Financial Services',    'ATM',             2),
    'fuel'      : ('Transport & Mobility',  'Fuel Station',    2),
    'school'    : ('Education',             'School',          2),
    'restaurant': ('Food & Beverage',       'Restaurant',      3),
}

# =============================================================================
# STEP 1 — DATA COLLECTION
# =============================================================================

print("[ Phase 1 ] Fetching POI data from OpenStreetMap ...")

raw_poi = ox.features_from_place(CITY_NAME, tags=POI_TAGS)

print(f"           Raw POIs fetched : {len(raw_poi)}")

# =============================================================================
# STEP 2 — CLEAN & STRUCTURE
# =============================================================================

print("[ Phase 2 ] Cleaning and structuring data ...")

# Keep only core columns
poi_clean = raw_poi[['name', 'amenity', 'geometry']].copy()
poi_clean = poi_clean.reset_index()

# Keep only POINT geometries (drop polygons and linestrings)
poi_clean = poi_clean[poi_clean.geometry.geom_type == 'Point'].copy()

# Extract latitude and longitude as separate columns
poi_clean['longitude'] = poi_clean.geometry.x
poi_clean['latitude']  = poi_clean.geometry.y

# Assign unique POI IDs in format BLR_000001
poi_clean['poi_id'] = [f"BLR_{str(i+1).zfill(6)}" for i in range(len(poi_clean))]

# Final column order
poi_clean = poi_clean[['poi_id', 'name', 'amenity', 'latitude', 'longitude', 'geometry']].copy()

print(f"           POIs after cleaning : {len(poi_clean)}")

# =============================================================================
# STEP 3 — VALIDATION & QA FLAGGING
# =============================================================================

print("[ Phase 3 ] Running validation rules ...")

# --- Rule Functions ---

def check_missing_name(row):
    if pd.isna(row['name']) or str(row['name']).strip() == '':
        return 'FAIL', 'Missing name'
    return 'PASS', 'Name present'

def check_coordinates(row):
    lat, lon = row['latitude'], row['longitude']
    if not (BBOX['lat_min'] <= lat <= BBOX['lat_max']):
        return 'FAIL', f"Latitude {lat} outside Bengaluru range"
    if not (BBOX['lon_min'] <= lon <= BBOX['lon_max']):
        return 'FAIL', f"Longitude {lon} outside Bengaluru range"
    return 'PASS', 'Coordinates within boundary'

def check_name_quality(row):
    if pd.isna(row['name']):
        return 'REVIEW', 'Cannot check — name missing'
    if len(str(row['name']).strip()) == 1:
        return 'REVIEW', 'Name is only 1 character — likely a tagging error'
    return 'PASS', 'Name length acceptable'

def check_numeric_name(row):
    if pd.isna(row['name']):
        return 'REVIEW', 'Cannot check — name missing'
    if str(row['name']).strip().isnumeric():
        return 'FAIL', 'Name is purely numeric — invalid POI name'
    return 'PASS', 'Name is not numeric'

def check_amenity_valid(row):
    valid_categories = list(CATEGORY_MAP.keys())
    if row['amenity'] not in valid_categories:
        return 'FAIL', f"Unknown category: {row['amenity']}"
    return 'PASS', 'Valid amenity category'

def assign_final_status(row):
    statuses = [
        row['rule1_status'], row['rule2_status'],
        row['rule3_status'], row['rule4_status'],
        row['rule5_status']
    ]
    if 'FAIL'   in statuses: return 'FAIL'
    if 'REVIEW' in statuses: return 'REVIEW'
    return 'PASS'

# --- Apply Rules ---

poi_validated = poi_clean.copy()

poi_validated[['rule1_status', 'rule1_reason']] = poi_validated.apply(
    lambda row: pd.Series(check_missing_name(row)), axis=1)

poi_validated[['rule2_status', 'rule2_reason']] = poi_validated.apply(
    lambda row: pd.Series(check_coordinates(row)), axis=1)

poi_validated[['rule3_status', 'rule3_reason']] = poi_validated.apply(
    lambda row: pd.Series(check_name_quality(row)), axis=1)

poi_validated[['rule4_status', 'rule4_reason']] = poi_validated.apply(
    lambda row: pd.Series(check_numeric_name(row)), axis=1)

poi_validated[['rule5_status', 'rule5_reason']] = poi_validated.apply(
    lambda row: pd.Series(check_amenity_valid(row)), axis=1)

poi_validated['final_status'] = poi_validated.apply(assign_final_status, axis=1)

total  = len(poi_validated)
passed = (poi_validated['final_status'] == 'PASS').sum()
failed = (poi_validated['final_status'] == 'FAIL').sum()
review = (poi_validated['final_status'] == 'REVIEW').sum()

print(f"           PASS   : {passed} ({round(passed/total*100,1)}%)")
print(f"           FAIL   : {failed} ({round(failed/total*100,1)}%)")
print(f"           REVIEW : {review} ({round(review/total*100,1)}%)")

# =============================================================================
# STEP 4 — CATEGORIZE & ENRICH
# =============================================================================

print("[ Phase 4 ] Applying 3-tier category enrichment ...")

poi_enriched = poi_validated.copy()

poi_enriched['main_category']  = poi_enriched['amenity'].map(
    lambda x: CATEGORY_MAP.get(x, ('Unknown', 'Unknown', 0))[0])

poi_enriched['sub_category']   = poi_enriched['amenity'].map(
    lambda x: CATEGORY_MAP.get(x, ('Unknown', 'Unknown', 0))[1])

poi_enriched['priority_level'] = poi_enriched['amenity'].map(
    lambda x: CATEGORY_MAP.get(x, ('Unknown', 'Unknown', 0))[2])

poi_enriched['map_ready'] = poi_enriched['final_status'].map(
    lambda s: 'YES' if s == 'PASS' else 'NO')

# =============================================================================
# STEP 5 — EXPORT OUTPUT FILES
# =============================================================================

print("[ Phase 5 ] Exporting output files ...")

# --- Export 1: Map-ready GeoJSON (PASS only) to output folder ---
poi_map_ready = poi_enriched[poi_enriched['map_ready'] == 'YES'].copy()

geojson_cols = [
    'poi_id', 'name', 'amenity',
    'main_category', 'sub_category', 'priority_level',
    'latitude', 'longitude', 'map_ready', 'geometry'
]

poi_map_ready_geo = gpd.GeoDataFrame(
    poi_map_ready[geojson_cols],
    geometry='geometry',
    crs='EPSG:4326'
)

geojson_path = os.path.join('output', 'bengaluru_poi_map_ready.geojson')
poi_map_ready_geo.to_file(geojson_path, driver='GeoJSON')
print(f"           Saved : {geojson_path}  ({len(poi_map_ready_geo)} POIs)")

# --- Export 2: Validation report CSV to reports folder ---
validation_report_cols = [
    'poi_id', 'name', 'amenity', 'latitude', 'longitude',
    'rule1_status', 'rule1_reason',
    'rule2_status', 'rule2_reason',
    'rule3_status', 'rule3_reason',
    'rule4_status', 'rule4_reason',
    'rule5_status', 'rule5_reason',
    'final_status'
]

validation_report_path = os.path.join('reports', 'bengaluru_poi_validation_report.csv')
poi_enriched[validation_report_cols].to_csv(validation_report_path, index=False)
print(f"           Saved : {validation_report_path}  ({total} rows)")

# --- Export 3: Final enriched CSV to reports folder ---
final_csv_cols = [
    'poi_id', 'name', 'amenity',
    'main_category', 'sub_category', 'priority_level',
    'latitude', 'longitude',
    'final_status', 'map_ready',
    'rule1_reason', 'rule2_reason',
    'rule3_reason', 'rule4_reason', 'rule5_reason'
]

final_csv_path = os.path.join('reports', 'bengaluru_poi_final.csv')
poi_enriched[final_csv_cols].to_csv(final_csv_path, index=False)
print(f"           Saved : {final_csv_path}  ({total} rows)")

# =============================================================================
# FINAL SUMMARY
# =============================================================================

print(f"  Total POIs processed  : {total}")
print(f"  Map-ready (PASS)      : {passed} ({round(passed/total*100,1)}%)")
print(f"  Failed validation     : {failed} ({round(failed/total*100,1)}%)")

print("  Output Files:")
print(f"    {geojson_path}")
print(f"    {validation_report_path}")
print(f"    {final_csv_path}")
