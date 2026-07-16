---
name: poi-json-schema
description: Use whenever reading, importing, transforming, or writing code against a "POI export" JSON file (building/floor point-of-interest data exported from the Unity scene, e.g. UpdatedFloorsAndFireinteraction_POIs.json). Describes the file's schema, field meanings, enum values, and known data quirks — without embedding the actual POI records. Load this before writing an import/ETL script or a query/filter against this data source.
---

# POI Export JSON Schema

This file format is exported from a Unity scene and describes points of interest
(rooms, exits, safety equipment, etc.) placed in a building model. It is NOT meant
to be read in full by an LLM — it's typically hundreds of records with verbose
per-record transform data. Use this schema to write deterministic import/query
code instead.

## Top-level structure

```json
{
  "sceneName": "string",
  "exportTimestamp": "YYYY-MM-DD HH:MM:SS",
  "pois": [ /* array of POI objects, schema below */ ]
}
```

## POI object fields

| Field | Type | Notes |
|---|---|---|
| `name` | string | Primary identifier. In practice identical to `title` and `poiName` — treat as one field, don't triple-store. |
| `title` | string | Duplicate of `name`. |
| `poiName` | string | Duplicate of `name`. |
| `identification` | int | Unique numeric ID. Good candidate for a primary key. |
| `description` | string | Free text. **Frequently empty (`""`)** — mostly for `type`s whose name is self-explanatory (Toilet, Elevator, Staircase, Exit, VendingMachine). `Room` descriptions are free-form and inconsistent: sometimes `"size: X sq ft, purpose: Y"`, sometimes a full sentence with room number, capacity, and square footage. Watch for the typo variant `"sq tf"` alongside `"sq ft"`. |
| `type` | enum string | One of: <!--AUTO:type_values-->`Elevator`, `Exit`, `Room`, `Safety`, `Staircase`, `Toilet`, `VendingMachine`<!--/AUTO--> Treat as a scalar/filterable field, not free text. |
| `position` | `{x,y,z: float}` | World-space coordinates (Unity units). |
| `rotation` | `{x,y,z: float}` | World-space Euler rotation in degrees. |
| `localPosition` | `{x,y,z: float}` | Same shape as `position`, relative to `parentName`'s transform. |
| `localRotation` | `{x,y,z: float}` | Same shape as `rotation`, relative to `parentName`'s transform. |
| `parentName` | string | One of: <!--AUTO:parent_name_values-->`1st Floor`, `2nd Floor`, `3rd Floor`, `None`, `POIs`<!--/AUTO--> (`POIs` = ungrouped fixtures not attached to a floor; `None` is a **literal string**, not JSON null — seen on at least one record). Good candidate for a filterable "floor" field. |

## Example records (representative, not exhaustive)

```json
{
  "name": "Room 1215",
  "title": "Room 1215",
  "identification": 31,
  "poiName": "Room 1215",
  "description": "Classroom(1215/J-109), Capacity 32 students, and 32 available seats, used for lectures. Approximately 749 sq ft.",
  "type": "Room",
  "position": {"x": -0.149, "y": -8.757, "z": -28.670},
  "rotation": {"x": 0.0, "y": 108.933, "z": 0.0},
  "localPosition": {"x": -2.060, "y": -8.757, "z": -28.670},
  "localRotation": {"x": 0.0, "y": 108.933, "z": 0.0},
  "parentName": "1st Floor"
}
```

```json
{
  "name": "Fire Extinguisher",
  "title": "EmergencySafety",
  "identification": 300,
  "poiName": "Fire extinguisher",
  "description": "This is a fire extinguisher used on fire (Type added soon)",
  "type": "Safety",
  "position": {"x": -0.657, "y": -4.986, "z": -22.979},
  "rotation": {"x": 0.870, "y": 295.856, "z": 0.0},
  "localPosition": {"x": -0.657, "y": -4.986, "z": -22.979},
  "localRotation": {"x": 0.870, "y": 295.856, "z": 0.0},
  "parentName": "None"
}
```

## Recommended field mapping for downstream storage (e.g. Milvus)

- `identification` → primary key
- `name` (dedupe `title`/`poiName`) → scalar field
- `type` → scalar field, indexed, used for filtering (`type == "Safety"`)
- `parentName` → scalar field, indexed, used for filtering by floor (`parentName == "3rd Floor"`)
- `description` → text field; embed for semantic search (skip/empty-string embedding is fine for the ~10% of records with no description)
- `position` / `rotation` / `localPosition` / `localRotation` → store as a single JSON metadata field; not typically filtered or embedded, just retrieved for rendering/navigation

## Do not

- Don't load the whole `pois` array into an LLM prompt/context — write a script that reads and transforms it instead.
- Don't assume `description` is always populated — handle the empty-string case explicitly in any embedding or NLP step.
- Don't treat `parentName: "None"` as JSON null — it's the string `"None"`.
