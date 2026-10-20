"""Avoid Python ownership cycles between a page and its containing Qt window."""

from collections.abc import Callable
from types import MethodType
from typing import cast
from weakref import WeakMethod


def weak_callback[**P, T](callback: Callable[P, T]) -> Callable[P, T]:
    if getattr(callback, "__self__", None) is None:
        return callback
    reference = WeakMethod(cast(MethodType, callback))

    def invoke(*args: P.args, **kwargs: P.kwargs) -> T:
        method = reference()
        if method is None:
            raise RuntimeError("The containing workspace was closed.")
        return cast(Callable[P, T], method)(*args, **kwargs)

    return invoke
