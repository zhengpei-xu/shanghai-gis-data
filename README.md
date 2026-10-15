# shanghai-gis-data

An open, versioned collection of GIS data for Shanghai, maintained for transport and urban research.
Every dataset below documents where it comes from, how it was made, how to load it, and what its
known limitations are. Snapshots are dated so that a study can cite the exact version it used.

## Catalogue

| Dataset | Path or download | Format | CRS | Updated |
|---|---|---|---|---|
| [Administrative boundaries](#1-administrative-boundaries) | `boundaries/shanghai_municipal_and_district_boundaries.geojson` | GeoJSON | EPSG:4326 (see note) | static |
| [OSM highway network](#2-osm-highway-network) | Release `osm-YYYYMMDD`: `highways_buffer20km_YYYYMMDD.parquet` / `.gpkg` | GeoParquet, GeoPackage | EPSG:4326 | every 6 months |
| [OSM full extract](#3-osm-full-extract) | Release `osm-YYYYMMDD`: `shanghai_buffer20km_YYYYMMDD.osm.pbf` | OSM PBF | EPSG:4326 | every 6 months |
| [OSM tag-quality report](#4-osm-tag-quality-report) | `osm/snapshots/YYYYMMDD/` | CSV, PNG, JSON | – | every 6 months |
| [Snapshot metadata](#5-snapshot-metadata) | `osm/latest.json`, `osm/snapshots/YYYYMMDD/metadata.json` | JSON | – | every 6 months |

Large files are not stored in git (GitHub limits files to 100 MB). They are attached to a
[GitHub Release](https://github.com/zhengpei-xu/shanghai-gis-data/releases) per snapshot, tagged
`osm-YYYYMMDD`, where `YYYYMMDD` is the date of the OSM data (not the date the job ran).

## Repository layout

```
boundaries/                     administrative boundaries
osm/
  latest.json                   metadata of the newest snapshot
  snapshots/YYYYMMDD/           quality report and metadata for each snapshot
scripts/osm_snapshot.py         builds an OSM snapshot (used by the scheduled workflow)
notebooks/                      the same pipeline as an interactive notebook
.github/workflows/              scheduled update job
requirements.txt                Python dependencies
```

## Quick start

```python
import json, urllib.request
import geopandas as gpd
import pandas as pd

REPO = "https://raw.githubusercontent.com/zhengpei-xu/shanghai-gis-data/main"

# Boundaries
bnd = gpd.read_file(f"{REPO}/boundaries/shanghai_municipal_and_district_boundaries.geojson")
city = bnd[bnd["类型"] == "市"]          # municipality (1 feature)
districts = bnd[bnd["类型"] == "区县"]    # 16 districts

# Latest OSM highway network
meta = json.load(urllib.request.urlopen(f"{REPO}/osm/latest.json"))
snap = meta["snapshot"]
url = (f"https://github.com/zhengpei-xu/shanghai-gis-data/releases/download/"
       f"osm-{snap}/highways_buffer{meta['buffer_km']}km_{snap}.parquet")
urllib.request.urlretrieve(url, "highways.parquet")
roads = gpd.read_parquet("highways.parquet")

# Only ways inside Shanghai, main roads only
main = roads[roads["in_shanghai"] & roads["highway"].isin(["trunk", "primary", "secondary", "tertiary"])]

# Any OSM tag that is not a column is in tags_json
roads["sidewalk"] = roads["tags_json"].map(lambda s: json.loads(s).get("sidewalk"))
```

To pin a study to one version, replace `snap` with a fixed date such as `"20261014"` and cite it
(see [Citing](#citing)).

In QGIS, the `.gpkg` and `.geojson` files open directly (Layer → Add Layer → Add Vector Layer).
The `.osm.pbf` file can be opened in QGIS or read with [pyosmium](https://osmcode.org/pyosmium/),
[osmium-tool](https://osmcode.org/osmium-tool/) or [pyrosm](https://pyorg.github.io/pyrosm/).

---

## 1. Administrative boundaries

`boundaries/shanghai_municipal_and_district_boundaries.geojson`

The municipality of Shanghai and its 16 districts, 17 features in one file.

| Field | Type | Meaning |
|---|---|---|
| `类型` | text | Level: `市` = municipality, `区县` = district |
| `NAME` | text | District name in Chinese (empty for the municipality) |
| `PAC` | number | District administrative division code, e.g. `310101` = Huangpu (empty for the municipality) |
| `市`, `市代码` | text | City name and code (`上海市`, `310000`) |
| `省`, `省代码` | text | Province-level name and code (`上海市`, `310000`) |
| `FID` | number | Feature index from the original file |
| geometry | MultiPolygon | Boundary |

District codes: 310101 Huangpu, 310104 Xuhui, 310105 Changning, 310106 Jing'an, 310107 Putuo,
310109 Hongkou, 310110 Yangpu, 310112 Minhang, 310113 Baoshan, 310114 Jiading,
310115 Pudong New Area, 310116 Jinshan, 310117 Songjiang, 310118 Qingpu, 310120 Fengxian,
310151 Chongming.

**Source:** to be documented.

**Known limitations**

- **Simplified geometry.** Each district has only 13–198 boundary vertices. The file suits
  clipping, buffering and maps at city scale. It is not accurate enough for street-level
  assignment near district edges.
- **Includes water.** The municipal polygon measures about 7,205 km² in UTM 51N, against
  about 6,340 km² of land usually reported for Shanghai. Most of the difference is in Pudong
  (1,494 km² here) and Chongming (1,699 km² here), so the polygons appear to include parts of
  the Yangtze estuary and coastal waters. Do not use these areas for population density.
- **Coordinate system not verified.** The file declares WGS-84 (EPSG:4326). Many Chinese
  boundary files are in GCJ-02, which is offset by a few hundred metres. This has not been
  checked against a WGS-84 reference.
- Field names are in Chinese, as in the original file.

---

## 2. OSM highway network

Release asset: `highways_buffer20km_YYYYMMDD.parquet` (GeoParquet) and `highways_buffer20km_YYYYMMDD.gpkg`
(GeoPackage, layer `highways`).

Every OpenStreetMap way with a `highway=*` tag that intersects Shanghai plus a 20 km buffer,
one row per way, with its full geometry (ways that cross the buffer edge are not cut).

| Column | Type | Meaning |
|---|---|---|
| `osm_id` | int | OSM way id (`https://www.openstreetmap.org/way/<osm_id>`) |
| `version` | int | OSM version number of the way |
| `last_edit` | datetime (UTC) | Time of the last edit to the way |
| `in_shanghai` | bool | Way intersects the municipal boundary |
| `highway` | text | Road class, e.g. `trunk`, `primary`, `residential`, `footway` ([OSM wiki](https://wiki.openstreetmap.org/wiki/Key:highway)) |
| `name`, `ref` | text | Street name, road number |
| `maxspeed`, `maxspeed:forward`, `maxspeed:backward` | text | Speed limit as tagged, e.g. `60`, `50;60`, `CN:urban` |
| `maxspeed:type`, `source:maxspeed`, `zone:maxspeed` | text | How the speed limit was set |
| `lanes`, `lanes:forward`, `lanes:backward` | text | Number of motor-traffic lanes |
| `oneway`, `junction` | text | One-way, roundabout |
| `bridge`, `tunnel`, `layer`, `motorroad` | text | Grade separation; `motorroad=yes` = motor vehicles only |
| `surface` | text | Road surface |
| `access`, `bicycle`, `service` | text | Access restrictions, service road type |
| `cycleway`, `cycleway:left`, `cycleway:right`, `cycleway:both`, `segregated` | text | Cycle facilities |
| `tags_json` | text (JSON) | All tags of the way, including those not listed above |
| geometry | LineString | Way geometry, EPSG:4326 |

All tag columns are the raw text values from OSM, or empty when the tag is absent. Parsing
(for example `maxspeed` to km/h) is left to the user; `scripts/osm_snapshot.py` has one way of doing it.

**How it is made** (`scripts/osm_snapshot.py`)

1. Download the latest Geofabrik extracts for Shanghai, Jiangsu and Zhejiang, and check each
   against its published MD5 checksum. Jiangsu and Zhejiang are needed because the buffer
   crosses into them.
2. Buffer the municipal boundary by 20 km in UTM 51N (EPSG:32651).
3. Read every way tagged `highway=*` from the three files with pyosmium, keep the ones that
   intersect the buffer, and remove duplicate ways that appear in two province files.

**Why a 20 km buffer.** The archive is meant to be reused for different modes. 20 km keeps the
cross-border towns that function as part of Shanghai (Huaqiao and Kunshan, Taicang, Jiashan,
Pinghu, Wujiang, and Qidong and Haimen across the Yangtze), and avoids edge effects for trips of up to about
20 km. A study should clip to its own analysis buffer, for example 1–2 km for walking, 3–5 km
for cycling and 10–20 km for car or transit. This is a working choice, not a published standard.

**Known limitations**

- OSM coverage of attributes in China is uneven. In particular, `maxspeed` and `lanes` are often
  missing, so check the [tag-quality report](#4-osm-tag-quality-report) before using them.
- Elevated expressways are separate ways above ground-level roads (`bridge=yes`, `layer>=1`).
  Remove them for walking or cycling analysis.

---

## 3. OSM full extract

Release asset: `shanghai_buffer20km_YYYYMMDD.osm.pbf`

All OSM data (roads, public transport, buildings, land use, points of interest and more) inside
the 20 km buffer, for studies that need more than the highway layer.

**How it is made:** the three Geofabrik files are merged and clipped to the buffer polygon with
`osmium extract --strategy smart` (ways and multipolygon relations that cross the edge are kept
whole).

---

## 4. OSM tag-quality report

`osm/snapshots/YYYYMMDD/tables/*.csv`, `figures/*.png`

Diagnostics of the highway network **inside the municipal boundary**. Lengths are in km, measured
after clipping to the boundary in UTM 51N, and all shares are by length. Main roads are `trunk`,
`primary`, `secondary` and `tertiary` (including their `_link` roads); minor roads are
`unclassified`, `residential` and `living_street`.

| File | Content |
|---|---|
| `01_class_completeness.csv` | Per `highway` value: segments, km, share of network, % of length with `maxspeed` (any / numeric), `lanes`, `name`, `oneway`, `surface`, median year of last edit |
| `02_group_completeness.csv` | The same for main, minor, service, motorway and other roads |
| `03_speed_values_km.csv` | km of each numeric speed limit value, by road class |
| `04_lane_values_km.csv` | km of each lane count, by road class |
| `05_speed_implausible.csv` | km of tagged speed limits outside a rough range per class |
| `05b_speed_implausible_ways.csv` | The ways behind it, for checking in the OSM editor |
| `06_completeness_by_district.csv` | `maxspeed` and `lanes` completeness for main and minor roads, per district |
| `07_completeness_by_distance.csv` | The same by distance from People's Square (0–2, 2–5, 5–10, 10–20, 20–40, 40+ km) |
| `08_named_roads_mixed_class.csv` | Named roads of at least 2 km with less than 80 % of their length in one road class |
| `09_elevated_km.csv` | km of motorway, trunk, primary and secondary on and off bridges or upper layers |
| `figures/class_and_maxspeed.png` | Maps of road class and of tagged speed limits on main roads |

Notes on reading the report:

- The ranges in table 05 are a screening aid, not a legal or design standard: motorway 60–120,
  trunk 40–100, primary 30–80, secondary 30–70, tertiary 20–60, unclassified 5–50,
  residential 5–40, living_street 5–20, service 5–30 km/h.
- `maxspeed` values such as `CN:urban` are implicit limits. They are counted as tagged but
  not as numeric.
- The report measures completeness and plausibility. It cannot tell whether a tagged speed limit
  matches the sign on the street.

---

## 5. Snapshot metadata

`osm/latest.json` (newest) and `osm/snapshots/YYYYMMDD/metadata.json`

| Key | Meaning |
|---|---|
| `snapshot` | OSM data date (`YYYYMMDD`), from the `osmosis_replication_timestamp` header of the Geofabrik files |
| `source_timestamps` | Exact timestamp of each Geofabrik file |
| `source` | Download URLs |
| `buffer_km` | Buffer distance |
| `boundary` | Boundary file used |
| `ways_in_buffer` | Number of highway ways in the buffer |
| `km_in_shanghai`, `main_roads_km` | Network length inside Shanghai, total and main roads |
| `main_maxspeed_%`, `main_lanes_%`, `minor_maxspeed_%` | Headline tag completeness (% of length) |
| `named_roads_mixed_class_%` | Share of named-road length with mixed road classes |
| `created` | Time the snapshot was built |

---

## Updates

The workflow [`.github/workflows/osm-snapshot.yml`](.github/workflows/osm-snapshot.yml) runs on
GitHub Actions:

- **Schedule:** 1 January and 1 July, 02:00 UTC. It can also be started by hand from the
  Actions tab (OSM snapshot → Run workflow).
- **Steps:** run `scripts/osm_snapshot.py`, attach the large files to Release `osm-YYYYMMDD`, and
  commit the quality report and metadata to `osm/snapshots/YYYYMMDD/` and `osm/latest.json`.
- **Keepalive:** GitHub disables scheduled workflows in public repositories after 60 days
  without activity, which is shorter than the six-month interval. The workflow therefore runs on
  the 1st of every month and re-enables itself through the GitHub API. It only takes a
  snapshot in January and July.
- Old snapshots are never overwritten, so earlier versions stay available for reproducibility.

To build a snapshot locally:

```bash
pip install -r requirements.txt
# optional, for the full .osm.pbf extract: conda install -c conda-forge osmium-tool
python scripts/osm_snapshot.py                       # writes to data/osm_shanghai/
DATA_DIR=/path/to/archive BUFFER_KM=10 python scripts/osm_snapshot.py
```

Environment variables: `DATA_DIR` (output folder, default `data/osm_shanghai`), `BOUNDARY_PATH`
(boundary file), `BUFFER_KM` (default 20), `FORCE_DOWNLOAD=1` (download again even if a file from
the last 24 hours exists), `SAVE_GPKG=0` (skip the GeoPackage).

## Coordinate systems

All data in this repository are in WGS-84 (EPSG:4326) unless stated otherwise. Data from Chinese
web map providers (Gaode/Amap, Tencent) are usually in GCJ-02, and Baidu data are in BD-09.
Both must be converted before overlaying them on OSM data. For distances and areas, use UTM
zone 51N (EPSG:32651).

## Citing

Please cite the repository and the snapshot date, for example:

> shanghai-gis-data, OSM snapshot 20261014. https://github.com/zhengpei-xu/shanghai-gis-data

and credit OpenStreetMap for any OSM-derived data: "© OpenStreetMap contributors".

## Licence

- OSM-derived data (sections 2–5) are © OpenStreetMap contributors and available under the
  [Open Database License 1.0](https://opendatacommons.org/licenses/odbl/1-0/). Redistributed or
  modified versions must stay under ODbL and credit OpenStreetMap.
- The licence of the boundary file and of the code in this repository is to be documented.
