---
name: milvus-json-operators
description: Use when a Milvus filter expression needs to check contents of a JSON field (not just look up a single key). Covers JSON_CONTAINS, JSON_CONTAINS_ALL, JSON_CONTAINS_ANY.
---

# Milvus JSON Operators

JSON fields are flat key-value/array structures; avoid deep nesting for performance.

## JSON_CONTAINS(identifier, expr)
True if the given element/subarray exists in the JSON field.
```python
# {"tags": ["electronics", "sale", "new"]}
filter = 'json_contains(product["tags"], "sale")'
```

## JSON_CONTAINS_ALL(identifier, expr)
True only if every element in the list is present.
```python
# {"tags": ["electronics", "sale", "new", "discount"]}
filter = 'json_contains_all(product["tags"], ["electronics", "sale", "new"])'
```

## JSON_CONTAINS_ANY(identifier, expr)
True if at least one element in the list is present.
```python
# {"tags": ["electronics", "sale", "new"]}
filter = 'json_contains_any(tags, ["electronics", "new", "clearance"])'
```

## Null handling for JSON fields
- Field treated as null if the whole JSON object is `None` or the field is missing entirely.
- A null value on an individual key (e.g. `{"category": None, "price": 99.99}`) does NOT make the field null.
```python
filter = 'metadata IS NULL'
filter = 'metadata IS NOT NULL'
```
