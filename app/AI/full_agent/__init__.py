from . import agent

# Registers the `subquery_correctness` eval metric so adk web can offer it.
# Eval dependencies are optional, so a missing install must not break the app.
try:
    from .evals import judge  # noqa: F401
except ImportError:
    pass
