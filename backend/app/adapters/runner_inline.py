from collections.abc import Callable


class InlineRunner:
    """Starter TaskRunner: executes synchronously in-request. Swap for a
    DB-backed job queue later; services only know submit()."""

    def submit(self, fn: Callable[[], None]) -> None:
        fn()
