# Shanghai OSM snapshot 20261014

Source: Geofabrik extracts shanghai, jiangsu, zhejiang (timestamps in metadata.json), clipped to Shanghai + 20 km.
Raw provincial files: /home/runner/work/_temp/osm_shanghai/raw

Release assets (https://github.com/zhengpei-xu/shanghai-gis-data/releases/tag/osm-20261014):
- shanghai_osm_highways.parquet / .gpkg: every highway=* way in the buffer; key tags as columns, all tags in tags_json; in_shanghai flag.
- shanghai_osm.osm.pbf: all OSM data in the buffer.
- tables/: tag completeness and value diagnostics, length-weighted, inside the municipal boundary.
- boundary and buffer GeoJSON.

OSM data (c) OpenStreetMap contributors, ODbL.
