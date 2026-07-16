---
name: milvus-array-operators
description: Use when a Milvus filter expression needs to check contents or length of an ARRAY field. Covers ARRAY_CONTAINS, ARRAY_CONTAINS_ALL, ARRAY_CONTAINS_ANY, ARRAY_LENGTH.
---

# Milvus ARRAY Operators

All elements in an ARRAY field share one type; nested structures are treated as plain strings, so keep arrays flat.

## ARRAY_CONTAINS(identifier, expr)
True if the specific element exists in the array.
```python
filter = 'ARRAY_CONTAINS(history_temperatures, 23)'
```

## ARRAY_CONTAINS_ALL(identifier, expr)
True only if every listed value is present.
```python
filter = 'ARRAY_CONTAINS_ALL(history_temperatures, [23, 24])'
```

## ARRAY_CONTAINS_ANY(identifier, expr)
True if at least one listed value is present.
```python
filter = 'ARRAY_CONTAINS_ANY(history_temperatures, [23, 24])'
```

## ARRAY_LENGTH(identifier)
Returns element count; combine with comparison operators.
```python
filter = 'ARRAY_LENGTH(history_temperatures) < 10'
```

## Null handling for ARRAY fields
Field is null if the whole array is `None` or missing. Arrays cannot contain partial nulls (all elements share one type).
```python
filter = 'tags IS NULL'
filter = 'tags IS NOT NULL'
```

## Directly indexing an element
```python
filter = 'history_temperatures[0] > 30'
```
