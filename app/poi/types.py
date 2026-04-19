from typing import TypeVar

T = TypeVar("T")

OneOrMore = T | list[T]
"""
This is just a helper type to make types that are either one or more of itself
easier to declare
"""