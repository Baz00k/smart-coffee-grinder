import uasyncio as asyncio
from micropython import const
from machine import SoftI2C, Pin
from encoder_async import Encoder
from button import Pushbutton
from display import Display
import time

_PIN_BUTTON = const(4)
_PIN_ENCODER_A = const(9)
_PIN_ENCODER_B = const(10)
_PIN_SCL = const(7)
_PIN_SDA = const(6)
_PIN_TRANSISTOR = const(5)
SCREEN_WIDTH = const(128)
SCREEN_HEIGHT = const(64)
DISPLAY_SCALE = const(3)  # Default font is 8x8 so we need to scale it up
TARGET_REFRESH_RATE_HZ = const(20)
TARGET_REFRESH_RATE = const(1000 // TARGET_REFRESH_RATE_HZ)


grinder_running = False


async def grind(seconds: float, transistor: Pin):
    # Grind for `seconds` seconds
    transistor.on()
    await asyncio.sleep(seconds)
    transistor.off()


def display_float(seconds: float, display: Display) -> float:
    """Display the time on the screen and return the time it took to display"""
    start_time = time.ticks_ms()
    display.fb.fill(0)
    str_seconds = f"{seconds:.1f}"
    length = len(str_seconds)
    display.fb.large_text(
        str_seconds,
        (SCREEN_WIDTH - length * 8 * DISPLAY_SCALE) // 2,
        (SCREEN_HEIGHT - 8 * DISPLAY_SCALE) // 2,
        DISPLAY_SCALE,
    )
    end_time = time.ticks_ms()
    return end_time - start_time


async def start_grind(time_getter, transistor: Pin, display: Display):
    global grinder_running
    seconds = time_getter()

    if grinder_running:
        return
    grinder_running = True

    asyncio.create_task(grind(seconds, transistor))

    current_time = 0.0
    while current_time < seconds:
        update_time = display_float(current_time, display)
        current_time += update_time / 100  # Convert to seconds
        sleep_time = max(0, int(TARGET_REFRESH_RATE - update_time))
        await asyncio.sleep_ms(sleep_time)

    grinder_running = False


async def main():
    global grinder_running

    i2c = SoftI2C(
        scl=Pin(_PIN_SCL),
        sda=Pin(_PIN_SDA),
        freq=400_000,  # 400kHz (fast mode)
    )
    display = Display(
        i2c,
        width=SCREEN_WIDTH,
        height=SCREEN_HEIGHT,
        target_refresh_rate=TARGET_REFRESH_RATE_HZ,
    )
    display.setup_auto_update()
    encoder = Encoder(
        Pin(_PIN_ENCODER_A, Pin.IN, Pin.PULL_UP),
        Pin(_PIN_ENCODER_B, Pin.IN, Pin.PULL_UP),
        div=4,  # Native resolution of the encoder (4 steps per detent)
    )
    transistor = Pin(_PIN_TRANSISTOR, Pin.OUT)
    button = Pushbutton(Pin(_PIN_BUTTON, Pin.IN, Pin.PULL_UP))

    target_time = 10.0
    rotation_raw = 0
    rotation_prev = 0

    def get_target_time() -> float:
        return target_time

    button.press_func(start_grind, args=(get_target_time, transistor, display))  # type: ignore

    while True:
        # Do not change target time while grinding
        if grinder_running:
            await asyncio.sleep_ms(500)
            continue

        rotation_prev = rotation_raw
        rotation_raw = encoder.value()
        diff = rotation_raw - rotation_prev

        # value should be between 1 and 25 with increments of 0.5
        target_time = max(1, min(target_time + diff / 2, 25))

        update_time = display_float(target_time, display)
        await asyncio.sleep_ms(max(0, int(TARGET_REFRESH_RATE - update_time)))


try:
    asyncio.run(main())
finally:
    asyncio.new_event_loop()
