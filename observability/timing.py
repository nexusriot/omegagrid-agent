import time

class Timer:
    def __init__(self):
        self._start = time.perf_counter()
        self._last = self._start
        self._marks = {}

    def mark(self, name: str):
        now = time.perf_counter()
        self._marks[name] = round(now - self._last, 6)
        self._last = now

    def as_dict(self) -> dict:
        total = round(time.perf_counter() - self._start, 6)
        return {**self._marks, "total_s": total}
