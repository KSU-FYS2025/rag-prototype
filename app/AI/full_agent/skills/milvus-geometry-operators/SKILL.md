---
name: milvus-geometry-operators
description: Use when a Milvus filter expression needs spatial filtering on a GEOMETRY field. Covers ST_EQUALS, ST_CONTAINS, ST_CROSSES, ST_INTERSECTS, and related spatial operators using WKT geometry literals.
---

# Milvus Geometry Operators

Operators take two arguments: the GEOMETRY field name and a target geometry in Well-Known Text (WKT) format. Operator names must be all-uppercase or all-lowercase (don't mix case).

```
<operator>(geometry_field, '<WKT literal>')
```

## Common operators
- `ST_EQUALS(field, wkt)` — TRUE if the two geometries are spatially identical (same points/dimension).
```python
filter = "ST_EQUALS(geo_field, 'POINT(10 20)')"
```

- `ST_CONTAINS(field, wkt)` — TRUE if the stored geometry completely contains the target geometry. Useful for "points within a polygon."

- `ST_CROSSES(field, wkt)` — TRUE if the intersection produces a lower-dimension geometry than the inputs (e.g. a line crossing a polygon or another line).
```python
filter = "ST_CROSSES(geo_field, 'LINESTRING(5 0, 5 10)')"
```

- `ST_INTERSECTS(field, wkt)` — TRUE if the two geometries share any boundary/interior point. General-purpose spatial overlap check.

Combine with standard logical operators (see `milvus-boolean-filter`) to mix spatial and scalar conditions.
