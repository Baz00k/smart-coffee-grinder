import uasyncio as asyncio
from micropython import const
from machine import SoftI2C, Pin
from primitives.encoder_async import Encoder
from primitives.button_async import Pushbutton
from primitives.display import Display
from time import ticks_ms

_PIN_BUTTON = const(4)
_PIN_ENCODER_A = const(9)
_PIN_ENCODER_B = const(10)
_PIN_SDA = const(5)
_PIN_SCL = const(6)
_PIN_TRANSISTOR = const(7)
MIN_GRIND_TIME = const(1)
MAX_GRIND_TIME = const(25)
SCREEN_WIDTH = const(128)
SCREEN_HEIGHT = const(64)
DISPLAY_SCALE = const(3)  # Default font is 8x8 so we need to scale it up
TARGET_REFRESH_RATE_HZ = const(25)
TARGET_REFRESH_RATE = const(1000 // TARGET_REFRESH_RATE_HZ)


grinder_running = False


def display_float(seconds: float, display: Display) -> float:
    """Display the time on the screen and return the time it took to display"""
    start_time = ticks_ms()
    display.fb.fill(0)
    str_seconds = f"{seconds:.1f}"
    length = len(str_seconds)
    display.fb.large_text(
        str_seconds,
        (SCREEN_WIDTH - length * 8 * DISPLAY_SCALE) // 2,
        (SCREEN_HEIGHT - 8 * DISPLAY_SCALE) // 2,
        DISPLAY_SCALE,
    )
    end_time = ticks_ms()
    return end_time - start_time


async def toggle_grinder(time_getter, transistor: Pin, display: Display):
    global grinder_running

    if grinder_running:
        grinder_running = False
        return

    grinder_running = True
    seconds = time_getter()

    transistor.on()
    start_time = ticks_ms()

    while grinder_running:
        current_time = (ticks_ms() - start_time) / 1000
        update_time = display_float(current_time, display)
        sleep_time = max(0, int(TARGET_REFRESH_RATE - update_time))

        # Do not run next loop if the time is close to the target
        if abs(seconds - current_time) <= sleep_time / 1000 or current_time > seconds:
            break

        await asyncio.sleep_ms(sleep_time)

    transistor.off()
    grinder_running = False

    asyncio.create_task(store_grinding_time(seconds))


async def store_grinding_time(seconds: float):
    with open("grinding_txt", "w") as f:
        f.write(str(seconds))


async def read_grinding_time():
    try:
        with open("grinding_txt", "r") as f:
            return float(f.read())
    except Exception:
        return 10.0


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

    target_time = await asyncio.create_task(read_grinding_time())
    rotation_raw = 0
    rotation_prev = 0

    def get_target_time() -> float:
        return target_time

    button.press_func(toggle_grinder, args=(get_target_time, transistor, display))  # type: ignore

    while True:
        rotation_prev = rotation_raw
        rotation_raw = encoder.value()

        # Do not change target time while grinding
        if grinder_running:
            await asyncio.sleep_ms(100)
            continue

        diff = rotation_raw - rotation_prev

        # value should be between min and max with increments of 0.5
        target_time = max(MIN_GRIND_TIME, min(target_time + diff / 2, MAX_GRIND_TIME))

        update_time = display_float(target_time, display)
        await asyncio.sleep_ms(max(0, int(TARGET_REFRESH_RATE - update_time)))


try:
    asyncio.run(main())
finally:
    asyncio.new_event_loop()
