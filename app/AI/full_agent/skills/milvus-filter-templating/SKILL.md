---
name: milvus-filter-templating
description: Use when a Milvus filter expression contains many literal values, large arrays, or non-ASCII (e.g. CJK) values — use placeholders plus a filter_params dict instead of embedding values directly, for better parse performance.
---

# Milvus Filter Expression Templating

Instead of embedding values directly in the filter string, use `{placeholder}` syntax with a separate `filter_params` dict. Reduces parsing overhead, especially for large arrays or non-ASCII values.

```python
filter = "age > {age} AND city IN {city}"
filter_params = {"age": 25, "city": ["北京", "上海"]}
```

## Search
```python
res = client.search(
    "collection_name",
    vectors[:nq],
    filter=filter,
    filter_params=filter_params,
    limit=10,
    output_fields=["age", "city"],
)
```

## Query
```python
res = client.query(
    "collection_name",
    filter=filter,
    filter_params=filter_params,
    output_fields=["age", "city"],
)
```

## Delete
```python
res = client.delete(
    "collection_name",
    filter=filter,
    filter_params=filter_params,
)
```

Use this whenever the filter you're constructing would otherwise embed a long literal array or CJK/non-ASCII string values directly.
