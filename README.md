# shanghai-gis-data

Open GIS data for Shanghai, for transport and urban research. Each dataset lists its source, when
it was collected, and a direct link to load it.

## Datasets

| Dataset | Source | Coverage | Updated | Format |
|---|---|---|---|---|
| [Administrative boundaries](#administrative-boundaries) | to be documented | Municipality and 16 districts | static | GeoJSON |
| [Road network](#road-network-openstreetmap) | OpenStreetMap | Shanghai + 20 km | every 6 months | GeoParquet, GeoPackage |
| [All OpenStreetMap data](#all-openstreetmap-data) | OpenStreetMap | Shanghai + 20 km | every 6 months | OSM PBF |

All data are in WGS-84 (EPSG:4326). Use UTM 51N (EPSG:32651) for distances and areas.

---

### Administrative boundaries

The municipality of Shanghai and its 16 districts (17 features).

- **Source:** to be documented.
- **Download:** https://raw.githubusercontent.com/zhengpei-xu/shanghai-gis-data/main/boundaries/shanghai_municipal_and_district_boundaries.geojson

```python
import geopandas as gpd
bnd = gpd.read_file("https://raw.githubusercontent.com/zhengpei-xu/shanghai-gis-data/main/boundaries/shanghai_municipal_and_district_boundaries.geojson")
city = bnd[bnd["类型"] == "市"]
districts = bnd[bnd["类型"] == "区县"]
```

| Field | Meaning |
|---|---|
| `类型` | `市` = municipality, `区县` = district |
| `NAME` | District name (Chinese) |
| `PAC` | District code, e.g. 310101 Huangpu, 310115 Pudong |
| `市`, `市代码`, `省`, `省代码` | City and province name and code (all Shanghai, 310000) |

**Notes:** the geometry is simplified (13–198 vertices per district) and includes estuary and
coastal water (about 7,205 km² against about 6,340 km² of land). Fine for clipping and maps; not
for density calculations. The declared CRS (WGS-84) has not been checked against GCJ-02.

---

### Road network (OpenStreetMap)

Every OpenStreetMap way tagged `highway=*` (roads, paths, cycleways, footways) in Shanghai plus a
20 km buffer, one row per way, with the original OSM tags.

- **Source:** OpenStreetMap, via the [Geofabrik](https://download.geofabrik.de/asia/china.html)
  extracts for Shanghai, Jiangsu and Zhejiang.
- **Collected:** January and July each year. The date of the newest snapshot is in [`osm/latest.json`](osm/latest.json).
- **Download (latest):**
  - GeoParquet: https://github.com/zhengpei-xu/shanghai-gis-data/releases/latest/download/shanghai_osm_highways.parquet
  - GeoPackage: https://github.com/zhengpei-xu/shanghai-gis-data/releases/latest/download/shanghai_osm_highways.gpkg
- **Download (a fixed snapshot):** replace `latest/download` with `download/osm-YYYYMMDD`, i.e.
  `https://github.com/zhengpei-xu/shanghai-gis-data/releases/download/osm-YYYYMMDD/shanghai_osm_highways.parquet`
  (dates are listed under [Releases](https://github.com/zhengpei-xu/shanghai-gis-data/releases)).

```python
import geopandas as gpd, urllib.request
url = "https://github.com/zhengpei-xu/shanghai-gis-data/releases/latest/download/shanghai_osm_highways.parquet"
urllib.request.urlretrieve(url, "shanghai_osm_highways.parquet")
roads = gpd.read_parquet("shanghai_osm_highways.parquet")
roads = roads[roads["in_shanghai"]]          # drop the buffer
```

| Column | Meaning |
|---|---|
| `osm_id` | OSM way id (`openstreetmap.org/way/<osm_id>`) |
| `highway` | Road class: `motorway`, `trunk`, `primary`, `secondary`, `tertiary`, `residential`, `service`, `cycleway`, `footway`, … |
| `name`, `ref` | Street name, road number |
| `maxspeed` (+ `:forward`, `:backward`, `:type`, `source:maxspeed`, `zone:maxspeed`) | Speed limit as tagged |
| `lanes` (+ `:forward`, `:backward`) | Number of lanes |
| `oneway`, `junction`, `bridge`, `tunnel`, `layer`, `motorroad`, `surface`, `access`, `bicycle`, `service` | As tagged |
| `cycleway` (+ `:left`, `:right`, `:both`), `segregated` | Cycle facilities |
| `tags_json` | All tags of the way as JSON, including any not listed above |
| `version`, `last_edit` | OSM version and time of last edit |
| `in_shanghai` | `True` if the way intersects the municipal boundary |

Values are the raw OSM text, or empty where the tag is missing.

**Tag completeness** (2026-10-14, share of road length inside Shanghai):

| | maxspeed | lanes | name |
|---|---|---|---|
| Main roads (trunk, primary, secondary, tertiary) | 6 % | 23 % | 83 % |
| Minor roads (unclassified, residential, living_street) | 0.6 % | 1.6 % | 26 % |

Speed limits and lane counts are therefore too sparse to use directly in most studies. Full
tables by road class, district and distance from the centre are in
[`osm/snapshots/`](osm/snapshots/).

---

### All OpenStreetMap data

Everything in OpenStreetMap for Shanghai plus 20 km: roads, public transport, buildings, land
use, points of interest and so on.

- **Source and collection:** as for the road network.
- **Download (latest):** https://github.com/zhengpei-xu/shanghai-gis-data/releases/latest/download/shanghai_osm.osm.pbf
- **Read with:** [pyrosm](https://pyorg.github.io/pyrosm/), [pyosmium](https://osmcode.org/pyosmium/),
  [osmium-tool](https://osmcode.org/osmium-tool/), or QGIS (drag the file in).

```python
from pyrosm import OSM
osm = OSM("shanghai_osm.osm.pbf")
pois = osm.get_pois()
buildings = osm.get_buildings()
```

---

## All snapshots

Every snapshot is a [Release](https://github.com/zhengpei-xu/shanghai-gis-data/releases) tagged
`osm-YYYYMMDD`, where the date is the date of the OSM data. Old snapshots are kept, so a study can
cite the exact version it used. `osm/latest.json` gives the date of the newest one.

## How the data are updated

A [GitHub Actions job](.github/workflows/osm-snapshot.yml) runs
[`scripts/osm_snapshot.py`](scripts/osm_snapshot.py) on 1 January and 1 July. It downloads the
latest Geofabrik extracts, checks their checksums, keeps what lies within 20 km of Shanghai, and
publishes a new Release. It can also be run by hand from the Actions tab, or locally with
`pip install -r requirements.txt && python scripts/osm_snapshot.py`.
[`notebooks/shanghai_osm_quality_check.ipynb`](notebooks/shanghai_osm_quality_check.ipynb) does
the same steps interactively.

## Citing and licence

Please cite the repository and the snapshot date, e.g. *shanghai-gis-data, OSM snapshot
20261014, https://github.com/zhengpei-xu/shanghai-gis-data*.

OpenStreetMap data are © OpenStreetMap contributors and available under the
[Open Database License](https://opendatacommons.org/licenses/odbl/1-0/); credit OpenStreetMap
when you use them. The licence of the boundary file and of the code is to be documented.
