import framebuf2 as framebuf
import uasyncio as asyncio
import time


class Display:
    _byte = bytearray(1)
    _word = bytearray(2)

    def __init__(self, i2c, address=0x3C, width=128, height=64, target_refresh_rate=30):
        self._i2c = i2c
        self._address = address
        self.width = width
        self.height = height
        pages = height // 8
        self._refresh_rate = 1000 // target_refresh_rate
        self._trig = asyncio.Event()

        self._command = bytearray(b"\x21\x00\x7f\x22\x00\x0f")
        self._command[2] = width - 1
        if width == 64:
            self._command[1] += 32
            self._command[2] += 32
        self._command[5] = pages - 1
        self._i2c.writeto_mem(
            self._address,
            0x00,
            b"\xae\x20\x00\x40\x00\xa1"
            b"\xc8\xd3\x00\xd5\x80\xd9\xf1\xdb\x30\x8d\x14"
            b"\x81\xff\xa4\xa6",
        )
        self._word[0] = 0xA8
        self._word[1] = height - 1
        self._i2c.writeto_mem(self._address, 0x00, self._word)
        self._word[0] = 0xDA
        self._word[1] = 0x02 if height == 32 else 0x12
        self._i2c.writeto_mem(self._address, 0x00, self._word)
        self.active(True)

        buffer = bytearray(width * pages)
        self._buffer1 = buffer
        self._buffer2 = buffer
        self.fb = framebuf.FrameBuffer(buffer, width, height, framebuf.MONO_VLSB)
        self.fb2 = framebuf.FrameBuffer(buffer, width, height, framebuf.MONO_VLSB)

        self._current_buffer = 1

    def active(self, val):
        self._i2c.writeto_mem(self._address, 0x00, b"\xaf" if val else b"\xae")

    def inverse(self, val):
        self._i2c.writeto_mem(self._address, 0x00, b"\xa7" if val else b"\xa6")

    def vscroll(self, dy):
        self._byte[0] = 0x40 | dy & 0x3F
        self._i2c.writeto_mem(self._address, 0x00, self._byte)

    def flip(self, val):
        self._i2c.writeto_mem(self._address, 0x00, b"\xc0" if val else b"\xc8")

    def mirror(self, val):
        self._i2c.writeto_mem(self._address, 0x00, b"\xa0" if val else b"\xa1")

    def contrast(self, val):
        self._word[0] = 0x81
        self._word[1] = val & 0xFF
        self._i2c.writeto_mem(self._address, 0x00, self._word)

    async def ready(self):
        """Return a ready function for the display."""
        await self._trig.wait()
        self._trig.clear()
        return True

    def setup_auto_update(self):
        """Start the auto update loop."""
        asyncio.create_task(self._auto_update())

    def update(self) -> int:
        """Update the display with the current buffer."""
        start_time = time.ticks_ms()

        self._i2c.writeto_mem(self._address, 0x00, self._command)
        self._i2c.writeto_mem(self._address, 0x40, self._buffer1)

        # Swap buffers after updating the display
        self._swap_buffers()

        end_time = time.ticks_ms()

        # miliseconds resulution is fine, because the display is slow (>30ms)
        delay = max(0, self._refresh_rate - (end_time - start_time))
        return delay

    def _swap_buffers(self):
        """Swap between the two buffers."""
        if self._current_buffer == 1:
            self._current_buffer = 2
            self._buffer1 = self._buffer2
            self.fb = self.fb2
        else:
            self._current_buffer = 1
            self._buffer2 = self._buffer1
            self.fb2 = self.fb

        self._trig.set()

    async def _auto_update(self):
        """Auto update loop."""
        while True:
            delay = self.update()
            await asyncio.sleep_ms(delay)
