import sys
import time
from tqdm import tqdm


class ProgressTask:
    def __init__(self, reporter, description, total=None, initial=0, unit="项"):
        self.reporter, self.description = reporter, description
        self.total, self.current, self.unit = total, initial, unit
        self.postfix, self.closed = {}, False
        self.started = reporter.clock()
        self.dynamic = reporter.enabled and bool(getattr(reporter.stream, "isatty", lambda: False)())
        self.bar = tqdm(total=total, initial=initial, desc=description, unit=unit,
                        file=reporter.stream, dynamic_ncols=True, leave=True) if self.dynamic else None
        if not self.dynamic and not reporter.silent:
            reporter.write("开始: {}".format(description))

    def update(self, amount=1, **postfix):
        self.current += amount
        self.postfix.update(postfix)
        if self.bar is not None:
            self.bar.update(amount)
            if postfix:
                self.bar.set_postfix(postfix, refresh=False)

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.bar is not None:
            self.bar.close()
        elif not self.reporter.silent:
            elapsed = self.reporter.clock() - self.started
            count = "{}/{}".format(self.current, self.total) if self.total is not None else str(self.current)
            self.reporter.write("完成: {} {} {}，耗时 {:.1f}s".format(self.description, count, self.unit, elapsed))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False


class ProgressReporter:
    def __init__(self, stream=None, enabled=True, clock=None, silent=False):
        self.stream = stream or sys.stderr
        self.enabled = enabled
        self.clock = clock or time.monotonic
        self.silent = silent

    def task(self, description, total=None, initial=0, unit="项"):
        return ProgressTask(self, description, total, initial, unit)

    def write(self, message):
        self.stream.write(message + "\n")
        self.stream.flush()


NULL_PROGRESS = ProgressReporter(enabled=False, silent=True)
