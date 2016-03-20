from __future__ import print_function, division
import threading
import sys
from collections import namedtuple


def terminal_size():
    import fcntl
    import termios
    import struct

    h, w, hp, wp = struct.unpack(
        'HHHH', fcntl.ioctl(
            0, termios.TIOCGWINSZ, struct.pack('HHHH', 0, 0, 0, 0)))

    return w, h


Event = namedtuple("Event", ["code", "data"])


class Progress(threading.Thread):
    STOP_CODE, UPDATE_CODE = range(2)

    def __init__(
            self, min_=0, max_=100, width=80, brackets="[]", out=sys.stderr,
            mapping=("#", " ")):

        super(Progress, self).__init__()
        self.daemon = True

        self._min = min_
        self._max = max_
        self._range = self._max - self._min
        assert self._range > 0

        self._width = width

        self._lbrack = brackets[:len(brackets) // 2]
        self._rbrack = brackets[len(self._lbrack):]

        assert self._width >= len(self._lbrack) + len(self._rbrack)

        self._mapping = mapping
        assert len(self._mapping) > 1

        self._out = sys.stderr

        self._event = threading.Event()
        self._lock = threading.Lock()
        self._data = None

    def __enter__(self):
        if not self.is_alive():
            self.start()

        return self

    def __exit__(self, *args):
        if self.is_alive():
            self.stop()

    def _init(self):
        self._out.write('\x1b[?25l')
        self._out.flush()

    def _term(self):
        self._out.write('\x1b[?25h')
        self._out.write('\x1b[0m')
        self._out.flush()

    def _draw(self, data):
        assert len(data) >= len(self._mapping) - 1

        w, _ = terminal_size()
        width = min((w, self._width))
        blen = len(self._rbrack) + len(self._lbrack)
        width -= blen  # make room for open/close brackets

        self._out.write(self._lbrack)

        # convert values to normalized values
        normalized = ((x - self._min) / self._range for x in data)
        converted = [int(x * width) for x in normalized]

        for x, char in zip(converted, self._mapping):
            self._out.write(char * x)

        width -= sum(converted)
        assert width >= 0

        self._out.write(self._mapping[-1] * width)
        self._out.write(self._rbrack)
        self._out.write('\r')
        self._out.flush()

    def _send(self, event):
        with self._lock:
            self._data = event
            self._event.set()

    def _receive(self):
        with self._lock:
            event = self._data
            self._data = None
            self._event.clear()
            return event

    def _stop(self):
        self._send(Event(self.STOP_CODE, None))

    def start(self):
        self._init()
        super(Progress, self).start()

    def stop(self):
        self._stop()
        self.join()
        self._term()

    def update(self, data):
        if self.is_alive():
            self._send(Event(self.UPDATE_CODE, tuple(data)))

    def run(self):
        while True:
            self._event.wait()
            event = self._receive()

            if not event:
                continue

            if event.code == self.STOP_CODE:
                break
            elif event.code == self.UPDATE_CODE:
                self._draw(event.data)


if __name__ == '__main__':
    from time import sleep
    progress = Progress(mapping=('\x1b[31m>', '\x1b[32m>', '\x1b[0m '))

    with progress:
        for i in range(25):
            progress.update((i, i * 2))
            sleep(0.05)
