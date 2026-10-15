"""Download the latest Geofabrik extracts around Shanghai, archive a dated snapshot,
extract all highway ways in a buffer, and diagnose highway / maxspeed / lanes tags.

Same steps as notebooks/shanghai_osm_quality_check.ipynb, written as a script so
GitHub Actions can run it (.github/workflows/osm-snapshot.yml).

Run locally:  python scripts/osm_snapshot.py
Settings via environment variables: DATA_DIR, BOUNDARY_PATH, BUFFER_KM, FORCE_DOWNLOAD, SAVE_GPKG.
"""
from pathlib import Path
import datetime as dt
import hashlib, json, os, re, shutil, subprocess

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import requests
import osmium
from shapely.geometry import LineString, Point

# ---------------- settings (environment variables override) ----------------
DATA_DIR = Path(os.environ.get("DATA_DIR", "data/osm_shanghai"))
BOUNDARY_URL = os.environ.get("BOUNDARY_PATH",
                              "boundaries/shanghai_municipal_and_district_boundaries.geojson")
BUFFER_KM = int(os.environ.get("BUFFER_KM", "20"))
GEOFABRIK = "https://download.geofabrik.de/asia/china"
PROVINCES = ["shanghai", "jiangsu", "zhejiang"]
FORCE_DOWNLOAD = os.environ.get("FORCE_DOWNLOAD", "0") == "1"
SAVE_GPKG = os.environ.get("SAVE_GPKG", "1") == "1"
METRIC_CRS = "EPSG:32651"
CENTRE = (121.4737, 31.2304)              # People's Square, WGS-84
# ---------------------------------------------------------------------------

RAW_DIR = DATA_DIR / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)


def display(x):
    print(x)


bnd = gpd.read_file(BOUNDARY_URL)
if bnd.crs is None:
    bnd = bnd.set_crs(4326)
bnd = bnd.to_crs(4326)

city = bnd[bnd["类型"] == "市"].dissolve()[["geometry"]]
districts = bnd[bnd["类型"] == "区县"][["NAME", "PAC", "geometry"]].rename(columns={"NAME": "district"})

city_m = city.to_crs(METRIC_CRS)
buffer_m = city_m.buffer(BUFFER_KM * 1000)
buffer_wgs = gpd.GeoDataFrame(geometry=buffer_m.to_crs(4326), crs=4326)
BUFFER_POLY = buffer_wgs.geometry.iloc[0]
CITY_POLY = city.geometry.iloc[0]
BBOX = BUFFER_POLY.bounds   # (minx, miny, maxx, maxy)

print(f"Municipality: {city_m.area.sum()/1e6:,.0f} km²; districts: {len(districts)}")
print(f"Buffer {BUFFER_KM} km: {buffer_m.area.sum()/1e6:,.0f} km²; bbox {np.round(BBOX, 3)}")
ax = buffer_wgs.plot(color="#eeeeee", edgecolor="grey", figsize=(6, 6))
districts.boundary.plot(ax=ax, color="black", linewidth=0.4)
ax.set_title(f"Shanghai and {BUFFER_KM} km buffer"); ax.set_axis_off()


def md5sum(path, chunk=1 << 20):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(chunk), b""):
            h.update(b)
    return h.hexdigest()

def pbf_timestamp(path):
    r = osmium.io.Reader(osmium.io.File(str(path), "pbf"), osmium.osm.osm_entity_bits.NOTHING)   # explicit format: .part has no .pbf suffix
    ts = r.header().get("osmosis_replication_timestamp", "")
    r.close()
    return ts   # e.g. 2026-10-14T20:21:02Z

def download(name):
    url = f"{GEOFABRIK}/{name}-latest.osm.pbf"
    today = dt.date.today().strftime("%Y%m%d")
    existing = sorted(RAW_DIR.glob(f"{name}-*.osm.pbf"))
    if existing and not FORCE_DOWNLOAD and existing[-1].stat().st_mtime > dt.datetime.now().timestamp() - 86400:
        print(f"{name}: reusing {existing[-1].name}")
        return existing[-1]
    part = RAW_DIR / f"{name}-latest.osm.pbf.part"
    with requests.get(url, stream=True, timeout=60) as r:
        if r.status_code == 404:
            raise FileNotFoundError(f"{url} not found; check {GEOFABRIK}.html for the current file names")
        r.raise_for_status()
        size = int(r.headers.get("Content-Length", 0))
        with open(part, "wb") as f:
            for b in r.iter_content(1 << 20):
                f.write(b)
    expected = requests.get(url + ".md5", timeout=60).text.split()[0]
    got = md5sum(part)
    if got != expected:
        raise IOError(f"{name}: MD5 mismatch ({got} vs {expected}); delete {part} and retry")
    stamp = pbf_timestamp(part)[:10].replace("-", "") or today
    final = RAW_DIR / f"{name}-{stamp}.osm.pbf"
    part.replace(final)
    print(f"{name}: {size/1e6:,.0f} MB, data as of {pbf_timestamp(final)}, MD5 ok -> {final.name}")
    return final

raw_files = {p: download(p) for p in PROVINCES}
stamps = {p: pbf_timestamp(f) for p, f in raw_files.items()}
valid = [s[:10] for s in stamps.values() if s]
SNAPSHOT = (min(valid) if valid else dt.date.today().isoformat()).replace("-", "")
OUT = DATA_DIR / f"snapshot_{SNAPSHOT}"
(OUT / "tables").mkdir(parents=True, exist_ok=True)
(OUT / "figures").mkdir(exist_ok=True)
print("Snapshot:", SNAPSHOT, stamps)


buffer_wgs.to_file(OUT / f"buffer_{BUFFER_KM}km.geojson", driver="GeoJSON")
city.to_file(OUT / "shanghai_municipal.geojson", driver="GeoJSON")
districts.to_file(OUT / "shanghai_districts.geojson", driver="GeoJSON")

clipped_pbf = OUT / f"shanghai_buffer{BUFFER_KM}km_{SNAPSHOT}.osm.pbf"
if shutil.which("osmium"):
    merged = OUT / "_merged.osm.pbf"
    subprocess.run(["osmium", "merge", *map(str, raw_files.values()), "-o", str(merged), "--overwrite"], check=True)
    subprocess.run(["osmium", "extract", "-p", str(OUT / f"buffer_{BUFFER_KM}km.geojson"),
                    "-s", "smart", str(merged), "-o", str(clipped_pbf), "--overwrite"], check=True)
    merged.unlink()
    print("Clipped PBF:", clipped_pbf, f"{clipped_pbf.stat().st_size/1e6:,.0f} MB")
else:
    print("osmium-tool not found; skipped the clipped PBF (raw provincial files are kept in", RAW_DIR, ")")


KEY_TAGS = ["highway", "name", "ref", "maxspeed", "maxspeed:forward", "maxspeed:backward",
            "maxspeed:type", "source:maxspeed", "zone:maxspeed", "lanes", "lanes:forward",
            "lanes:backward", "oneway", "junction", "bridge", "tunnel", "layer", "motorroad",
            "surface", "access", "bicycle", "service", "cycleway", "cycleway:left",
            "cycleway:right", "cycleway:both", "segregated"]

def read_highways(pbf):
    minx, miny, maxx, maxy = BBOX
    rows = []
    fp = (osmium.FileProcessor(str(pbf)).with_locations()
          .with_filter(osmium.filter.EntityFilter(osmium.osm.WAY))
          .with_filter(osmium.filter.KeyFilter("highway")))
    for w in fp:
        coords = [(n.lon, n.lat) for n in w.nodes if n.location.valid()]
        if len(coords) < 2:
            continue
        xs, ys = zip(*coords)
        if max(xs) < minx or min(xs) > maxx or max(ys) < miny or min(ys) > maxy:
            continue
        tags = dict(w.tags)
        row = {"osm_id": w.id, "version": w.version, "last_edit": w.timestamp,
               "tags_json": json.dumps(tags, ensure_ascii=False), "geometry": LineString(coords)}
        row.update({k: tags.get(k) for k in KEY_TAGS})
        rows.append(row)
    return rows

rows = []
for p, f in raw_files.items():
    r = read_highways(f)
    print(f"{p}: {len(r):,} highway ways in bbox")
    rows += r

roads = gpd.GeoDataFrame(rows, crs=4326)
roads = roads.sort_values("version").drop_duplicates("osm_id", keep="last")   # border ways appear in two files
roads = roads[roads.intersects(BUFFER_POLY)].reset_index(drop=True)
roads["last_edit"] = pd.to_datetime(roads["last_edit"], utc=True)
roads["in_shanghai"] = roads.intersects(CITY_POLY)
print(f"{len(roads):,} ways in buffer, {roads['in_shanghai'].sum():,} touching Shanghai")

roads.to_parquet(OUT / f"highways_buffer{BUFFER_KM}km_{SNAPSHOT}.parquet")
if SAVE_GPKG:
    roads.assign(last_edit=roads["last_edit"].astype(str)).to_file(
        OUT / f"highways_buffer{BUFFER_KM}km_{SNAPSHOT}.gpkg", layer="highways", driver="GPKG")


sh = gpd.clip(roads[roads["in_shanghai"]], city).explode(index_parts=False)
sh = sh[sh.geom_type == "LineString"].copy()
sh["km"] = sh.to_crs(METRIC_CRS).length / 1000

CLASS_ORDER = ["motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link",
               "secondary", "secondary_link", "tertiary", "tertiary_link", "unclassified",
               "residential", "living_street", "service", "road", "track", "cycleway",
               "footway", "path", "pedestrian", "steps", "bridleway", "corridor",
               "busway", "construction", "proposed"]
MAIN = ["trunk", "primary", "secondary", "tertiary"]                   # the roads that matter most for safety
MINOR = ["unclassified", "residential", "living_street"]
sh["base"] = sh["highway"].str.replace("_link", "", regex=False)
sh["group"] = np.select([sh["base"].isin(["motorway"]), sh["base"].isin(MAIN), sh["base"].isin(MINOR),
                         sh["base"].eq("service")], ["motorway", "main", "minor", "service"], "other")

def parse_speed(v):
    # returns (km/h or NaN, kind); kind: numeric / implicit / other / missing
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return np.nan, "missing"
    s = str(v).strip()
    if re.match(r"^[A-Z]{2}:", s):
        return np.nan, "implicit"          # e.g. CN:urban
    nums = re.findall(r"\d+(?:\.\d+)?", s)
    if not nums:
        return np.nan, "other"             # none, walk, signals ...
    x = max(float(n) for n in nums)        # "60;80" -> 80
    if "mph" in s:
        x *= 1.609
    return x, "numeric"

speed_src = sh["maxspeed"].fillna(sh["maxspeed:forward"]).fillna(sh["maxspeed:backward"])
parsed = speed_src.map(parse_speed)
sh["speed_kmh"] = [p[0] for p in parsed]
sh["speed_kind"] = [p[1] for p in parsed]

def parse_lanes(row):
    for k in ["lanes"]:
        m = re.match(r"^\s*(\d+)", str(row[k])) if row[k] is not None else None
        if m:
            return int(m.group(1))
    f, b = row["lanes:forward"], row["lanes:backward"]
    if f is not None and b is not None and str(f).isdigit() and str(b).isdigit():
        return int(f) + int(b)
    return np.nan
sh["lanes_n"] = sh.apply(parse_lanes, axis=1)
sh["edit_year"] = sh["last_edit"].dt.year
print(f"{len(sh):,} segments, {sh['km'].sum():,.0f} km inside Shanghai")


def wshare(df, col):
    return (df.loc[df[col], "km"].sum() / df["km"].sum() * 100) if len(df) else np.nan

sh["has_speed"] = sh["speed_kind"].ne("missing")
sh["has_speed_num"] = sh["speed_kind"].eq("numeric")
sh["has_lanes"] = sh["lanes_n"].notna()
sh["has_name"] = sh["name"].notna()
sh["has_oneway"] = sh["oneway"].notna()
sh["has_surface"] = sh["surface"].notna()

t_class = (sh.groupby("highway")
             .apply(lambda d: pd.Series({
                 "segments": len(d), "km": d["km"].sum(),
                 "maxspeed_%": wshare(d, "has_speed"), "maxspeed_numeric_%": wshare(d, "has_speed_num"),
                 "lanes_%": wshare(d, "has_lanes"), "name_%": wshare(d, "has_name"),
                 "oneway_%": wshare(d, "has_oneway"), "surface_%": wshare(d, "has_surface"),
                 "median_edit_year": d["edit_year"].median()}), include_groups=False))
t_class["km_share_%"] = t_class["km"] / t_class["km"].sum() * 100
order = [c for c in CLASS_ORDER if c in t_class.index] + sorted(set(t_class.index) - set(CLASS_ORDER))
t_class = t_class.loc[order].round(1)
t_class.to_csv(OUT / "tables/01_class_completeness.csv", encoding="utf-8-sig")
t_class


t_group = (sh.groupby("group")
             .apply(lambda d: pd.Series({"km": d["km"].sum(), "maxspeed_%": wshare(d, "has_speed"),
                                         "lanes_%": wshare(d, "has_lanes"), "name_%": wshare(d, "has_name")}),
                    include_groups=False).round(1))
t_group.to_csv(OUT / "tables/02_group_completeness.csv", encoding="utf-8-sig")
t_group


road_cls = [c for c in CLASS_ORDER[:14] if c in sh["highway"].unique()]
sub = sh[sh["highway"].isin(road_cls) & sh["has_speed_num"]]
t_speed = (sub.pivot_table(index="highway", columns="speed_kmh", values="km", aggfunc="sum", fill_value=0)
              .reindex(road_cls).dropna(how="all").round(1))
t_speed.columns = [f"{int(c)}" for c in t_speed.columns]
t_speed.to_csv(OUT / "tables/03_speed_values_km.csv", encoding="utf-8-sig")

other_vals = sh.loc[sh["speed_kind"].isin(["implicit", "other"]), ["highway", "maxspeed", "km"]]
print("Non-numeric maxspeed values (km):")
display(other_vals.groupby(["highway", "maxspeed"])["km"].sum().round(1).sort_values(ascending=False).head(20))
t_speed


sub = sh[sh["highway"].isin(road_cls) & sh["has_lanes"]]
t_lanes = (sub.pivot_table(index="highway", columns="lanes_n", values="km", aggfunc="sum", fill_value=0)
              .reindex(road_cls).dropna(how="all").round(1))
t_lanes.columns = [f"{int(c)}" for c in t_lanes.columns]
t_lanes.to_csv(OUT / "tables/04_lane_values_km.csv", encoding="utf-8-sig")
t_lanes


PLAUSIBLE = {"motorway": (60, 120), "trunk": (40, 100), "primary": (30, 80), "secondary": (30, 70),
             "tertiary": (20, 60), "unclassified": (5, 50), "residential": (5, 40),
             "living_street": (5, 20), "service": (5, 30)}
num = sh[sh["has_speed_num"] & sh["base"].isin(PLAUSIBLE)].copy()
num["lo"] = num["base"].map(lambda c: PLAUSIBLE[c][0])
num["hi"] = num["base"].map(lambda c: PLAUSIBLE[c][1])
num["implausible"] = (num["speed_kmh"] < num["lo"]) | (num["speed_kmh"] > num["hi"])
t_implaus = (num.groupby("base")
                .apply(lambda d: pd.Series({"tagged_km": d["km"].sum(),
                                            "implausible_km": d.loc[d["implausible"], "km"].sum()}),
                       include_groups=False))
t_implaus["implausible_%"] = (t_implaus["implausible_km"] / t_implaus["tagged_km"] * 100).round(1)
t_implaus.round(1).to_csv(OUT / "tables/05_speed_implausible.csv", encoding="utf-8-sig")
num.loc[num["implausible"], ["osm_id", "highway", "name", "maxspeed", "km"]].sort_values("km", ascending=False) \
   .to_csv(OUT / "tables/05b_speed_implausible_ways.csv", index=False, encoding="utf-8-sig")
t_implaus.round(1)


mid = sh.to_crs(METRIC_CRS)
mid["geometry"] = mid.geometry.interpolate(0.5, normalized=True)
mid = gpd.sjoin(mid, districts[["district", "geometry"]].to_crs(METRIC_CRS), how="left", predicate="within")
cx, cy = gpd.GeoSeries([Point(CENTRE)], crs=4326).to_crs(METRIC_CRS).iloc[0].coords[0]
mid["dist_km"] = np.hypot(mid.geometry.x - cx, mid.geometry.y - cy) / 1000
mid["band"] = pd.cut(mid["dist_km"], [0, 2, 5, 10, 20, 40, 200],
                     labels=["0-2", "2-5", "5-10", "10-20", "20-40", "40+"])

def completeness(d):
    m = d[d["base"].isin(MAIN)]
    n = d[d["base"].isin(MINOR)]
    return pd.Series({"main_km": m["km"].sum(), "main_maxspeed_%": wshare(m, "has_speed"),
                      "main_lanes_%": wshare(m, "has_lanes"),
                      "minor_km": n["km"].sum(), "minor_maxspeed_%": wshare(n, "has_speed")})

t_district = mid.groupby("district").apply(completeness, include_groups=False).round(1) \
                .sort_values("main_maxspeed_%")
t_band = mid.groupby("band", observed=True).apply(completeness, include_groups=False).round(1)
t_district.to_csv(OUT / "tables/06_completeness_by_district.csv", encoding="utf-8-sig")
t_band.to_csv(OUT / "tables/07_completeness_by_distance.csv", encoding="utf-8-sig")
display(t_band)
t_district


named = sh[sh["base"].isin(MAIN + ["motorway"] + MINOR) & sh["has_name"]]
by_name = named.pivot_table(index="name", columns="base", values="km", aggfunc="sum", fill_value=0)
by_name["total_km"] = by_name.sum(axis=1)
by_name["dominant_class"] = by_name.drop(columns="total_km").idxmax(axis=1)
by_name["dominant_%"] = (by_name.drop(columns=["total_km", "dominant_class"]).max(axis=1)
                         / by_name["total_km"] * 100).round(1)
mixed = by_name[(by_name["total_km"] >= 2) & (by_name["dominant_%"] < 80)].sort_values("total_km", ascending=False)
share_mixed = mixed["total_km"].sum() / by_name.loc[by_name["total_km"] >= 2, "total_km"].sum() * 100
print(f"Named roads >= 2 km: {(by_name['total_km'] >= 2).sum():,}; "
      f"with < 80% of length in one class: {len(mixed):,} ({share_mixed:.1f}% of their length)")
mixed.round(2).to_csv(OUT / "tables/08_named_roads_mixed_class.csv", encoding="utf-8-sig")

unclear = pd.Series({
    "highway=road km": sh.loc[sh["highway"] == "road", "km"].sum(),
    "main roads km": sh.loc[sh["base"].isin(MAIN), "km"].sum(),
    "unnamed main roads km": sh.loc[sh["base"].isin(MAIN) & ~sh["has_name"], "km"].sum(),
}).round(1)
display(unclear)
mixed.head(20).round(1)


layer = pd.to_numeric(sh["layer"], errors="coerce").fillna(0)
sh["elevated"] = sh["bridge"].notna() & sh["bridge"].ne("no") | (layer >= 1)
t_elev = (sh[sh["base"].isin(["motorway", "trunk", "primary", "secondary"])]
            .groupby(["base", "elevated"])["km"].sum().unstack(fill_value=0).round(1))
t_elev.to_csv(OUT / "tables/09_elevated_km.csv", encoding="utf-8-sig")
print("motorroad=yes km:", sh.loc[sh["motorroad"] == "yes", "km"].sum().round(1))
t_elev


road_like = sh[sh["base"].isin(["motorway", "trunk", "primary", "secondary", "tertiary",
                                "unclassified", "residential", "living_street"])]
fig, axes = plt.subplots(1, 2, figsize=(16, 9))
colors = {"motorway": "#7b3294", "trunk": "#c2a5cf", "primary": "#d7191c", "secondary": "#fdae61",
          "tertiary": "#2c7bb6", "unclassified": "#999999", "residential": "#cccccc", "living_street": "#cccccc"}
for c in reversed(list(colors)):
    d = road_like[road_like["base"] == c]
    if len(d):
        d.plot(ax=axes[0], color=colors[c], linewidth=0.3 if c in MINOR else 0.7, label=c)
axes[0].legend(loc="lower right", fontsize=8); axes[0].set_title("Road class")

main = sh[sh["base"].isin(["motorway"] + MAIN)]
main[~main["has_speed_num"]].plot(ax=axes[1], color="#dddddd", linewidth=0.5)
main[main["has_speed_num"]].plot(ax=axes[1], column="speed_kmh", cmap="viridis_r", linewidth=0.8,
                                 legend=True, legend_kwds={"label": "maxspeed (km/h)", "shrink": 0.6})
axes[1].set_title("Main roads: maxspeed (grey = not tagged)")
for ax in axes:
    districts.boundary.plot(ax=ax, color="black", linewidth=0.3)
    ax.set_axis_off()
plt.tight_layout()
fig.savefig(OUT / "figures/class_and_maxspeed.png", dpi=200)


def km_share(mask_df, col):
    return round(wshare(mask_df, col), 1)

m = sh[sh["base"].isin(MAIN)]
summary = {
    "snapshot": SNAPSHOT,
    "source_timestamps": stamps,
    "source": {p: f"{GEOFABRIK}/{p}-latest.osm.pbf" for p in PROVINCES},
    "buffer_km": BUFFER_KM,
    "boundary": BOUNDARY_URL,
    "ways_in_buffer": int(len(roads)),
    "km_in_shanghai": round(sh["km"].sum(), 0),
    "main_roads_km": round(m["km"].sum(), 0),
    "main_maxspeed_%": km_share(m, "has_speed"),
    "main_lanes_%": km_share(m, "has_lanes"),
    "minor_maxspeed_%": km_share(sh[sh["base"].isin(MINOR)], "has_speed"),
    "named_roads_mixed_class_%": round(share_mixed, 1),
    "created": dt.datetime.now().isoformat(timespec="seconds"),
}
(OUT / "metadata.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
(OUT / "README.md").write_text(f'''# Shanghai OSM snapshot {SNAPSHOT}

Source: Geofabrik extracts {", ".join(PROVINCES)} (timestamps in metadata.json), clipped to Shanghai + {BUFFER_KM} km.
Raw provincial files: {RAW_DIR.resolve()}

- highways_buffer{BUFFER_KM}km_{SNAPSHOT}.parquet / .gpkg: every highway=* way in the buffer; key tags as columns, all tags in tags_json; in_shanghai flag.
- shanghai_buffer{BUFFER_KM}km_{SNAPSHOT}.osm.pbf: all OSM data in the buffer (only if osmium-tool was installed).
- tables/: tag completeness and value diagnostics, length-weighted, inside the municipal boundary.
- boundary and buffer GeoJSON.

OSM data (c) OpenStreetMap contributors, ODbL.
''', encoding="utf-8")
pd.Series(summary).drop(["source_timestamps", "source"])
print(json.dumps(summary, ensure_ascii=False, indent=2))
if os.environ.get("GITHUB_OUTPUT"):
    with open(os.environ["GITHUB_OUTPUT"], "a") as f:
        f.write(f"snapshot={SNAPSHOT}\nout={OUT}\n")

