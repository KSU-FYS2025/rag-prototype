---
name: milvus-random-sampling
description: Use when the user wants a random subset/sample of results rather than (or in addition to) a precise filter — e.g. "sample 1% of the collection," "give me a random subset for testing." Covers the RANDOM_SAMPLE filter expression.
---

# Milvus Random Sampling

`RANDOM_SAMPLE(sampling_factor)` returns an approximately random subset of matching entities. `sampling_factor` is a float in (0, 1) representing the fraction to sample.

## Sample the whole collection
```python
filter = "RANDOM_SAMPLE(0.01)"   # ~1% of the collection
```

## Combine with a filter — filter first, then sample
```python
filter = 'color == "red" AND RANDOM_SAMPLE(0.001)'
# Processing order: find all red items -> sample 0.1% of those red items
```

**Do not** OR a sample with a filter — it's logically meaningless ("either red items OR a random sample of everything"):
```python
# invalid logic, avoid
filter = 'color == "red" OR RANDOM_SAMPLE(0.001)'
```

Use `AND` to chain `RANDOM_SAMPLE` after any other predicate built with the standard operators (see `milvus-boolean-filter`).
