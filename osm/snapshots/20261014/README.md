# Shanghai OSM snapshot 20261014

Source: Geofabrik extracts shanghai, jiangsu, zhejiang (timestamps in metadata.json), clipped to Shanghai + 20 km.
Raw provincial files: /home/runner/work/_temp/osm_shanghai/raw

- highways_buffer20km_20261014.parquet / .gpkg: every highway=* way in the buffer; key tags as columns, all tags in tags_json; in_shanghai flag.
- shanghai_buffer20km_20261014.osm.pbf: all OSM data in the buffer (only if osmium-tool was installed).
- tables/: tag completeness and value diagnostics, length-weighted, inside the municipal boundary.
- boundary and buffer GeoJSON.

OSM data (c) OpenStreetMap contributors, ODbL.
