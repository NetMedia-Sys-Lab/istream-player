import asyncio
import functools
import traceback
from asyncio.exceptions import CancelledError
from typing import Generic, TypeVar


def critical_task(ignore_exc: list[type[BaseException]] = [CancelledError]):
    def wrapper(func):
        @functools.wraps(func)
        async def wrapped(*args):
            try:
                return await func(*args)
            except Exception as e:  # noqa
                if e.__class__ not in ignore_exc:
                    traceback.print_exc()
                    exit(1)

        return wrapped

    return wrapper


T = TypeVar("T")


class AsyncResource(Generic[T]):
    def __init__(self, default: T) -> None:
        self._value: T = default
        self.event_non_none = asyncio.Event()
        if default is not None:
            self.event_non_none.set()

    @property
    def value(self) -> T:
        return self._value

    @value.setter
    def value(self, val: T):
        self._value = val
        if val is not None and not self.event_non_none.is_set():
            self.event_non_none.set()
        elif val is None and self.event_non_none.is_set():
            self.event_non_none.clear()

    async def value_non_none(self):
        await self.event_non_none.wait()
        return self._value
