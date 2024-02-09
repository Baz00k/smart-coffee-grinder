import uasyncio as asyncio
from helpers.async_helpers import launch
from time import ticks_ms


class Pushbutton:
    def __init__(self, pin, debounce_ms=50, long_press_ms=500, sense=None):
        self._pin = pin  # Initialise for input
        self._pressedFunc = False  # Pressed function
        self._releasedFunc = False  # Released function
        self._clickedFunc = False  # Click function
        self._longFunc = False  # Long press function
        self._timer = False  # Current pressed duration

        self.debounce_ms = debounce_ms
        self.long_press_ms = long_press_ms

        # Convert from electrical to logical value
        self._sense = pin.value() if sense is None else sense
        self._state = self.rawstate()  # Initial state
        self._run = asyncio.create_task(self._go())  # Thread runs forever

    async def _go(self):
        while True:
            self._check(self.rawstate())
            # Ignore state changes until switch has settled. Also avoid hogging CPU.
            # See https://github.com/peterhinch/micropython-async/issues/69
            await asyncio.sleep_ms(self.debounce_ms)

    def _check(self, state):
        if state == self._state:
            return

        # State has changed
        self._state = state
        if state:
            self._pressed()
        else:
            self._released()

    def _pressed(self):
        self._timer = ticks_ms()
        if self._pressedFunc:
            launch(*self._pressedFunc)

    def _released(self):
        duration = ticks_ms() - self._timer
        if duration >= self.long_press_ms:
            if self._longFunc:
                launch(*self._longFunc)
        elif self._clickedFunc:
            launch(*self._clickedFunc)
        if self._releasedFunc:
            launch(*self._releasedFunc)

    # ****** API ******
    def press_func(self, func=False, args=()):
        """Run imidiately when button is pressed"""
        if func is None:
            self.press = asyncio.Event()
            func = self.press.set
        if func:
            self._pressedFunc = (func, args)
        else:
            self._pressedFunc = False

    def click_func(self, func=False, args=()):
        """Run when button is clicked (pressed then released withing long_press_ms)"""
        if func is None:
            self.click = asyncio.Event()
            func = self.click.set
        if func:
            self._clickedFunc = (func, args)
        else:
            self._clickedFunc = False

    def release_func(self, func=False, args=()):
        """Run imidiately when button is released"""
        if func is None:
            self.release = asyncio.Event()
            func = self.release.set
        if func:
            self._releasedFunc = (func, args)
        else:
            self._releasedFunc = False

    def long_func(self, func=False, args=()):
        """Run when button is pressed for at least long_press_ms"""
        if func is None:
            self.long = asyncio.Event()
            func = self.long.set
        if func:
            self._longFunc = (func, args)
        else:
            self._longFunc = False

    def rawstate(self) -> bool:
        """Current non-debounced logical button state: True == pressed"""
        return bool(self._pin() ^ self._sense)

    def __call__(self) -> bool:
        """Current debounced state of button (True == pressed)"""
        return self._state

    def deinit(self):
        self._run.cancel()
