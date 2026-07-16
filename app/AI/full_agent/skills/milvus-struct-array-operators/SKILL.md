---
name: milvus-struct-array-operators
description: Use when a Milvus filter expression needs to filter on a scalar sub-field inside a StructArray field (an array of struct elements, e.g. document chunks). Covers element_filter and the MATCH_ANY/ALL/LEAST/MOST/EXACT family. Milvus 3.0.x+.
---

# Milvus StructArray Operators

A StructArray field stores an ordered array of struct elements that all share one schema (multiple sub-fields, possibly including vectors). Reference a sub-field with `$[subField]`.

## element_filter(identifier, predicate)
True if at least one element in the array matches the predicate. Build the predicate with the standard comparison/range/arithmetic/logical operators (see `milvus-boolean-filter`).
```python
element_filter(chunks, $[text] LIKE "Red%")
```

**Important ordering rule:** when combining an entity-level predicate with an element_filter, put the element_filter LAST.
```python
# correct
id > 0 && element_filter(chunks, $[x] > 1)

# incorrect — will error
element_filter(chunks, $[x] > 1) && id > 0
```

## Match-family operators (quantitative)
Instead of "does at least one element match," these control how many/what proportion must match.

- `MATCH_ANY(identifier, predicate)` — at least 1 matches (same as element_filter)
- `MATCH_ALL(identifier, predicate)` — every element matches
- `MATCH_LEAST(identifier, predicate, k)` — count(matches) >= k
- `MATCH_MOST(identifier, predicate, k)` — count(matches) <= k
- `MATCH_EXACT(identifier, predicate, k)` — count(matches) == k

```python
MATCH_ANY(chunks, $[text] LIKE 'Red%')
MATCH_ALL(chunks, $[text] LIKE 'Red%')
MATCH_LEAST(chunks, $[text] LIKE 'Red%', 3)
MATCH_MOST(chunks, $[text] LIKE 'Red%', 3)   # useful for noise reduction
MATCH_EXACT(chunks, $[text] LIKE 'Red%', 3)
```

Index the sub-field used in `$[subField]` predicates for large datasets — these operators iterate array elements per candidate entity.
