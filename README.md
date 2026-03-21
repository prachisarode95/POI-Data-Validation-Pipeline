# Point of Interest (POI) data validation and enrichment pipeline

## Project Overview

| Stage | Description |
|-------|-------------|
| **Collection** | Fetched 9,692 real POIs from OpenStreetMap for Bengaluru |
| **Cleaning** | Filtered to 8,004 valid point geometries with structured schema |
| **Validation** | Applied 5 QA rules — flagged 648 records as FAIL (8.1%) |
| **Enrichment** | Mapped OSM tags to 3-tier category hierarchy |
| **Export** | Produced GeoJSON + validation report CSV |

---

## Tools & Libraries

- **osmnx** — OpenStreetMap POI data collection
- **geopandas** — spatial data processing
- **pandas** — data cleaning and validation logic

---

**Validation Results:**
- PASS : 7,356 POIs (91.9%)
- FAIL : 648 POIs (8.1%)

---
