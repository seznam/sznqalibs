import time


class FrameState(object):
    """Abstraction and tracking of frame state"""

    def __init__(self, max_load, size, debug):
        self.start = 0
        self.pos = 0
        self.load = 0
        self.allows = None
        self.time_ok = None
        self.load_ok = None
        self.MAX_LOAD = max_load
        self.SIZE = size
        self.DEBUG_MODE = debug
        self.__reset()

    def __reset(self):
        self.start = time.time()
        self.pos = 0
        self.load = 0
        self.allows = True

    def __update(self):
        self.pos = time.time() - self.start
        self.time_ok = self.pos <= self.SIZE
        self.load_ok = self.load <= self.MAX_LOAD - 1

        if self.time_ok and self.load_ok:
            self.allows = True
        elif not self.time_ok:
            self.__reset()
        elif not self.load_ok:
            self.allows = False

    def debug(self):
        if self.DEBUG_MODE:
            print("%4d; %4d; %5s; %0.3f; %0.3f; %5s; %5s"
                  % (self.load, self.MAX_LOAD, self.load_ok,
                     self.pos, self.SIZE, self.time_ok,
                     self.allows))

    def is_closed(self):
        return not self.is_open()

    def is_open(self):
        self.__update()
        if self.allows:
            self.load += 1
        return self.allows


class Throttle(object):
    """Throttle to allow only certain amount of iteration per given time.

    Usage:

        t = bottleneck.Throttle(300)

        while True:
            call_a_load_sensitive_service()
            t.wait()        # ensures above loop will not be called more
                            # than 300 times within 1 minute

        t = bottleneck.Throttle(10, 1)

        while True:
            call_a_load_sensitive_service()
            t.wait()        # ensures above loop will not be called more
                            # than 10 times within 1 second

    Note that the class will not in any way guarantee any even distribution
    of calls in time.  If your loop takes 1ms and you throttle to 1000 loops
    per 10 minutes, all loops will happen in the first second, and the last
    call will block for 599 seconds.

    """

    def __init__(self, max_load, frame_size=60, debug=False):
        """Create new Throttle.

        Only required parameter is `max_load`, which is number of times per
        frame `Throttle.wait()` returns without blocking.  Optionally you can
        specify `frame_size` in seconds, which defaults to 60, and debug,
        which when true, causes printing of some debugging info.
        """

        self.max_load = max_load
        self.frame_size = frame_size
        self.debug = debug
        self.waiting = True
        self.frame = FrameState(max_load=self.max_load, size=self.frame_size,
                                debug=self.debug)

    def is_closed(self):
        """True if throttle is closed."""
        return self.frame.is_closed()

    def is_open(self):
        """True if throttle is open."""
        return self.frame.is_open()

    def wait(self):
        """Return now if throttle is open, otherwise block until it is."""
        self.frame.debug()
        self.waiting = self.is_closed()
        while self.waiting:
            self.waiting = self.is_closed()
