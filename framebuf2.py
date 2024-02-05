# this code is distributed under the MIT licence.

"""
frambuf2 v209: micropython framebuffer extensions
(c) 2022-2023 Peter Lumb (peter-l5)

acknowledgement
the methods: circle() and triangle() are based on the
adafruit micropython gfx library:
See repository: https://github.com/adafruit/micropython-adafruit-gfx
that library was: 
Port of Adafruit GFX Arduino library to MicroPython
Based on: https://github.com/adafruit/Adafruit-GFX-Library
Author: Tony DiCola (original GFX author Phil Burgess)
License: MIT License (https://opensource.org/licenses/MIT)
"""

__version__ = "v209"
__repo__ = "https://github.com/peter-l5/framebuf2"

import framebuf

# constants available in MicroPython 1.19.1
MONO_VLSB = framebuf.MONO_VLSB
MONO_HLSB = framebuf.MONO_HLSB
MONO_HMSB = framebuf.MONO_HMSB
RGB565 = framebuf.RGB565
GS2_HMSB = framebuf.GS2_HMSB
GS4_HMSB = framebuf.GS4_HMSB
GS8 = framebuf.GS8


class FrameBuffer(framebuf.FrameBuffer):
    def _reverse(self, s: str) -> str:
        t = ""
        for i in range(0, len(s)):
            t += s[len(s) - 1 - i]
        return t

    def large_text(self, s, x, y, m, c: int = 1, r: int = 0, t=None):
        """
        large text drawing function uses the standard framebuffer font (8x8 pixel characters)
        writes text, s,
        to co-cordinates x, y
        size multiple, m (integer, eg: 1,2,3,4. a value of 2 produces 16x16 pixel characters)
        colour, c [optional parameter, default value c=1]
        optional parameter, r is rotation of the text: 0, 90, 180, or 270 degrees
        optional parameter, t is rotation of each character within the text: 0, 90, 180, or 270 degrees
        """
        colour = c
        smallbuffer = bytearray(8)
        letter = framebuf.FrameBuffer(smallbuffer, 8, 8, framebuf.MONO_HMSB)
        r = r % 360 // 90
        dx = 8 * m if r in (0, 2) else 0
        dy = 8 * m if r in (1, 3) else 0
        if r in (2, 3):
            s = self._reverse(s)
        t = r if t is None else t % 360 // 90
        a, b, c, d = 1, 0, 0, 1
        for i in range(0, t):
            a, b, c, d = c, d, -a, -b
        x0 = 0 if a + c > 0 else 7
        y0 = 0 if b + d > 0 else 7
        for character in s:
            letter.fill(0)
            letter.text(character, 0, 0, 1)
            for i in range(0, 8):
                for j in range(0, 8):
                    if letter.pixel(i, j) == 1:
                        p = x0 + a * i + c * j
                        q = y0 + b * i + d * j
                        if m == 1:
                            self.pixel(x + p, y + q, colour)
                        else:
                            self.fill_rect(x + p * m, y + q * m, m, m, colour)
            x += dx
            y += dy
