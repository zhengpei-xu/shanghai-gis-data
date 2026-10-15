# shanghai-gis-data

Open GIS data for Shanghai, kept for reuse in transport studies.

## Contents

- `boundaries/` Shanghai municipal and district boundaries (GeoJSON).
- `osm/` Half-yearly OpenStreetMap snapshots of Shanghai plus a 20 km buffer.
  - `osm/latest.json` metadata of the newest snapshot.
  - `osm/snapshots/YYYYMMDD/` tag-completeness tables, figures and metadata for each snapshot.
  - Large files for each snapshot are attached to the GitHub Release `osm-YYYYMMDD`:
    - `highways_buffer20km_YYYYMMDD.parquet` / `.gpkg`: every `highway=*` way, key tags as columns, all tags in `tags_json`.
    - `shanghai_buffer20km_YYYYMMDD.osm.pbf`: all OSM data in the buffer.
- `scripts/osm_snapshot.py` builds a snapshot; `notebooks/shanghai_osm_quality_check.ipynb` is the same steps, interactively.

## Updating

`.github/workflows/osm-snapshot.yml` runs on 1 January and 1 July. It can also be started by hand
from the Actions tab ("Run workflow").

Locally: `pip install -r requirements.txt && python scripts/osm_snapshot.py`
(optional: `osmium-tool` for the clipped `.osm.pbf`).

## Source and licence

OSM data from Geofabrik extracts (Shanghai, Jiangsu, Zhejiang). © OpenStreetMap contributors, ODbL 1.0.
