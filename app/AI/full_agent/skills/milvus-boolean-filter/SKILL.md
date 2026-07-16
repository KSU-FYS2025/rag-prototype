---
name: milvus-boolean-filter
description: Use whenever constructing a Milvus boolean filter expression (the `filter`/`expr` argument passed to a Milvus search, query, or delete call). Covers core grammar, comparison/logical/arithmetic operators, IN, LIKE, IS NULL, and operator precedence. Load this first for any Milvus filter task; load the json/array/struct-array/geometry/random-sampling/templating skills only if the query needs those specific features.
---

# Milvus Filter Expression: Core Syntax

A filter expression is a string that evaluates to TRUE or FALSE per entity. Milvus scans entities and keeps the ones where the expression is TRUE.

## Comparison operators
`==` `!=` `>` `<` `>=` `<=`

```python
filter = 'status == "active"'
filter = 'age > 30'
filter = '0 < age < 60'          # chained comparisons are valid
```

## Logical operators
`&&` / `and`, `||` / `or`, `not` (unary)

```python
filter = '(age > 18 && age < 65) or status == "vip"'
filter = 'not (status == "banned")'
```

## Arithmetic operators
`+` `-` `*` `/` `%` `**` — usable inside comparisons.

```python
filter = 'price ** 2 > 1000'
filter = 'id % 2 == 0'
```

## Range / membership: IN
```python
filter = 'color in ["red", "green", "blue"]'
filter = 'id not in [1, 2, 3]'
```

## Pattern matching: LIKE
`%` is the wildcard. Prefix match is fastest; infix/suffix are slower.

```python
filter = 'name LIKE "Prod%"'      # prefix (fast)
filter = 'name LIKE "%XYZ"'       # suffix
filter = 'name LIKE "%Pro%"'      # infix (slowest)
```

## NULL checks
Case-insensitive. `""` is NOT null for VARCHAR.

```python
filter = 'description IS NULL'
filter = 'description IS NOT NULL AND price > 10'
```

## Referencing JSON/ARRAY element keys directly
```python
filter = 'product["price"] > 1000'      # JSON key
filter = 'history_temperatures[0] > 30' # array index
```

## Operator precedence (highest to lowest)
1. unary `+` `-`
2. `not`
3. `**`
4. `*` `/` `%`
5. binary `+` `-`
6. `<` `<=` `>` `>=`
7. `==` `!=`
8. `like`
9. `json_contains` / `array_contains`
10. `json_contains_all` / `array_contains_all`
11. `json_contains_any` / `array_contains_any`
12. `array_length`
13. `&&` / `and`
14. `||` / `or`

Same-precedence operators evaluate left to right. Use parentheses to force order, e.g. `30 / (2 + 8)`.

## When to load other skills
- Filtering on JSON field contents (not just a key lookup) → load `milvus-json-operators`
- Filtering on ARRAY contents/length beyond a simple index → load `milvus-array-operators`
- Filtering on a StructArray (array of structs) sub-field → load `milvus-struct-array-operators`
- Filtering on a GEOMETRY field → load `milvus-geometry-operators`
- Sampling a random subset of results → load `milvus-random-sampling`
- Expression has many/large literal values or non-ASCII (e.g. CJK) values → load `milvus-filter-templating`
