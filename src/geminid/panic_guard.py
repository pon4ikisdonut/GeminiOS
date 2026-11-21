#!/usr/bin/env python3
"""
GeminiOS Keyboard Panic Guard (`panic_guard.py`)
Monitors Linux evdev keyboard input globally (TTY, SDDM, Wayland, X11).
If any forbidden sequence is typed:
  - "67"
  - "six seven"
  - "сик севен"
  - "сек севен"
  - "я люблю microsoft"
  - "я люблю майкрософт"
it immediately triggers a real Linux kernel panic via /proc/sysrq-trigger.
"""

import glob
import os
import select
import struct
import sys
import time
from collections import deque
from pathlib import Path
from typing import Dict, List, Sequence

# Linux input_event struct on 64-bit: timeval (16B) + type (H) + code (H) + value (i) = 24 bytes
EVENT_FMT = "llHHi"
EVENT_SIZE = struct.calcsize(EVENT_FMT)
EV_KEY = 0x01
KEY_PRESS = 1

# Standard Linux input-event-codes.h keycodes
KEY_1 = 2
KEY_6 = 7
KEY_7 = 8
KEY_BACKSPACE = 14
KEY_Q = 16
KEY_W = 17
KEY_E = 18
KEY_R = 19
KEY_T = 20
KEY_Y = 21
KEY_U = 22
KEY_I = 23
KEY_O = 24
KEY_P = 25
KEY_A = 30
KEY_S = 31
KEY_D = 32
KEY_F = 33
KEY_G = 34
KEY_H = 35
KEY_J = 36
KEY_K = 37
KEY_L = 38
KEY_Z = 44
KEY_X = 45
KEY_C = 46
KEY_V = 47
KEY_B = 48
KEY_N = 49
KEY_M = 50
KEY_COMMA = 51
KEY_DOT = 52
KEY_SPACE = 57
KEY_KP7 = 71
KEY_KP6 = 77

# Normalize numpad digits to top-row digits
KEY_ALIAS: Dict[int, int] = {
    KEY_KP6: KEY_6,
    KEY_KP7: KEY_7,
}

# Physical QWERTY keycode -> Latin & Russian JCUKEN characters
LATIN_CHAR_TO_KEY: Dict[str, int] = {
    "6": KEY_6, "7": KEY_7, " ": KEY_SPACE,
    "a": KEY_A, "b": KEY_B, "c": KEY_C, "d": KEY_D, "e": KEY_E,
    "f": KEY_F, "g": KEY_G, "h": KEY_H, "i": KEY_I, "j": KEY_J,
    "k": KEY_K, "l": KEY_L, "m": KEY_M, "n": KEY_N, "o": KEY_O,
    "p": KEY_P, "q": KEY_Q, "r": KEY_R, "s": KEY_S, "t": KEY_T,
    "u": KEY_U, "v": KEY_V, "w": KEY_W, "x": KEY_X, "y": KEY_Y, "z": KEY_Z,
}

CYRILLIC_JCUKEN_TO_KEY: Dict[str, int] = {
    "й": KEY_Q, "ц": KEY_W, "у": KEY_E, "к": KEY_R, "е": KEY_T, "н": KEY_Y,
    "г": KEY_U, "ш": KEY_I, "щ": KEY_O, "з": KEY_P,
    "ф": KEY_A, "ы": KEY_S, "в": KEY_D, "а": KEY_F, "п": KEY_G, "р": KEY_H,
    "о": KEY_J, "л": KEY_K, "д": KEY_L,
    "я": KEY_Z, "ч": KEY_X, "с": KEY_C, "м": KEY_V, "и": KEY_B, "т": KEY_N,
    "ь": KEY_M, "б": KEY_COMMA, "ю": KEY_DOT,
    " ": KEY_SPACE, "6": KEY_6, "7": KEY_7,
}

FORBIDDEN_PHRASES: List[str] = [
    "67",
    "six seven",
    "сик севен",
    "сек севен",
    "я люблю microsoft",
    "я люблю майкрософт",
]


def phrase_to_keycodes(phrase: str) -> List[int]:
    codes: List[int] = []
    for ch in phrase.lower():
        if ch in LATIN_CHAR_TO_KEY:
            codes.append(LATIN_CHAR_TO_KEY[ch])
        elif ch in CYRILLIC_JCUKEN_TO_KEY:
            codes.append(CYRILLIC_JCUKEN_TO_KEY[ch])
    return codes


class PanicSequenceDetector:
    def __init__(self, phrases: Sequence[str] = FORBIDDEN_PHRASES):
        self.triggers = [(p, phrase_to_keycodes(p)) for p in phrases]
        max_len = max((len(seq) for _, seq in self.triggers), default=32)
        self.buffer: deque = deque(maxlen=max_len + 8)

    def feed(self, keycode: int) -> str | None:
        if keycode == KEY_BACKSPACE:
            if self.buffer:
                self.buffer.pop()
            return None
        code = KEY_ALIAS.get(keycode, keycode)
        # Ignore modifier keys (Shift, Ctrl, Alt, Super, CapsLock) so Shift+letter or layout switch doesn't break sequences
        if code in (29, 42, 54, 56, 58, 97, 100, 125, 126):
            return None
        self.buffer.append(code)
        buf_list = list(self.buffer)
        for phrase, seq in self.triggers:
            n = len(seq)
            if n > 0 and len(buf_list) >= n and buf_list[-n:] == seq:
                return phrase
        return None


def trigger_kernel_panic(matched_phrase: str) -> None:
    """
    Triggers an authentic, highly visible Linux Kernel Panic.
    1. Unmutes kernel console printk (loglevel 8) and configures panic halt behavior.
    2. Terminates graphical display servers (KWin, Xorg, SDDM) to immediately release DRM master.
    3. Forces VT1 console into KD_TEXT mode.
    4. Renders a high-visibility ANSI Kernel Panic screen directly to /dev/tty1 and /dev/console.
    5. Dispatches emergency <0> alert to /dev/kmsg.
    6. Rapidly blinks all keyboard LEDs (Caps/Scroll/Num Lock) and sounds hardware bell.
    7. Triggers real kernel panic via /proc/sysrq-trigger 'c', locking CPU in panic state.
    """
    import subprocess

    # 1. Unmute printk and configure kernel panic
    try:
        Path("/proc/sys/kernel/printk").write_text("8 8 8 8\n", encoding="utf-8")
    except Exception:
        pass
    try:
        Path("/proc/sys/kernel/sysrq").write_text("1\n", encoding="utf-8")
    except Exception:
        pass
    try:
        # 0 means panic halts forever on screen with blinking LEDs, does not reboot
        Path("/proc/sys/kernel/panic").write_text("0\n", encoding="utf-8")
    except Exception:
        pass

    # 2. Kill graphical display servers immediately so DRM drops to VT console
    try:
        subprocess.run(["systemctl", "stop", "sddm", "sddm.service", "display-manager.service", "--no-block"], check=False)
        subprocess.run(["systemctl", "kill", "-s", "SIGKILL", "sddm.service"], check=False)
        subprocess.run(["pkill", "-9", "-f", "kwin_wayland|kwin_x11|Xorg|sddm|startplasma|plasma"], check=False)
        subprocess.run(["chvt", "1"], check=False)
    except Exception:
        pass

    # 3. Force KD_TEXT mode on VT1 / console via ioctl
    if sys.platform != "win32":
        try:
            import fcntl
            KDSETMODE = 0x4B3A
            KD_TEXT = 0x00
            VT_ACTIVATE = 0x5606
            VT_WAITACTIVE = 0x5607

            for dev in ("/dev/tty1", "/dev/console", "/dev/tty0"):
                try:
                    with open(dev, "wb") as f:
                        fcntl.ioctl(f.fileno(), VT_ACTIVATE, 1)
                        fcntl.ioctl(f.fileno(), KDSETMODE, KD_TEXT)
                except Exception:
                    pass
        except Exception:
            pass

    # 4. Format authentic, dramatic Kernel Panic screen
    pid = os.getpid()
    panic_screen = (
        "\033[2J\033[H\033[?25l"
        "\033[41;37;1m================================================================================\033[0m\r\n"
        "\033[41;37;1m                   !!! CRITICAL GEMINIOS KERNEL PANIC !!!                       \033[0m\r\n"
        "\033[41;37;1m================================================================================\033[0m\r\n\r\n"
        f"\033[1;31m[   13.370420] Kernel panic - not syncing: GeminiOS Panic Guard: Forbidden sequence detected: '{matched_phrase}'\033[0m\r\n"
        f"[   13.370425] CPU: 0 PID: {pid} Comm: panic_guard.py Tainted: G        W  OE      7.3.5-geminios #1\r\n"
        "[   13.370430] Hardware name: GeminiOS Secure Workstation / UEFI Platform\r\n"
        "[   13.370435] Call Trace:\r\n"
        " <TASK>\r\n"
        " dump_stack_lvl+0x5d/0x80\r\n"
        " panic+0x31b/0x360\r\n"
        " geminios_panic_guard_detector_feed+0x42/0x50 [panic_guard]\r\n"
        " panic_guard_evdev_loop+0x180/0x240 [panic_guard]\r\n"
        " input_handle_event+0x9e/0x450\r\n"
        " input_event+0x5b/0x80\r\n"
        " atkbd_interrupt+0x42f/0x5c0\r\n"
        " __handle_irq_event_percpu+0x4f/0x1a0\r\n"
        " handle_irq_event+0x38/0x80\r\n"
        " handle_edge_irq+0x93/0x240\r\n"
        " __common_interrupt+0x43/0xa0\r\n"
        " common_interrupt+0x7b/0xa0\r\n"
        " asm_common_interrupt+0x27/0x40\r\n"
        " </TASK>\r\n"
        "[   13.370515] Kernel Offset: disabled\r\n"
        f"\033[1;31m[   13.370520] ---[ end Kernel panic - not syncing: GeminiOS Panic Guard: Forbidden sequence detected: '{matched_phrase}' ]---\033[0m\r\n\r\n"
        "\033[1;33m********************************************************************************\r\n"
        "SYSTEM HALTED TO PROTECT COGNITIVE INTEGRITY.\r\n"
        f"REASON: FORBIDDEN SEQUENCE DETECTED IN RAW HARDWARE INPUT STREAM: '{matched_phrase}'.\r\n"
        "ACTION: HARD POWER CYCLE (POWER OFF / REBOOT) REQUIRED.\r\n"
        "********************************************************************************\033[0m\r\n\a"
    )

    for dev in ("/dev/tty1", "/dev/console", "/dev/tty0", "/dev/tty"):
        try:
            with open(dev, "w", encoding="utf-8", errors="ignore") as tty:
                tty.write(panic_screen)
                tty.flush()
        except Exception:
            pass

    try:
        with open("/dev/kmsg", "w", encoding="utf-8") as kmsg:
            kmsg.write(f"<0>Kernel panic - not syncing: GeminiOS Panic Guard: Forbidden sequence detected: '{matched_phrase}'\n")
            kmsg.flush()
    except Exception:
        pass

    # 5. Blink keyboard LEDs (Caps Lock / Scroll Lock / Num Lock) and beep
    led_files = glob.glob("/sys/class/leds/*lock/brightness")
    for _ in range(6):
        for led in led_files:
            try:
                Path(led).write_text("1\n", encoding="utf-8")
            except Exception:
                pass
        time.sleep(0.12)
        for led in led_files:
            try:
                Path(led).write_text("0\n", encoding="utf-8")
            except Exception:
                pass
        time.sleep(0.12)

    # 6. Trigger real hardware kernel panic via SysRq (sync -> unmount-ro -> crash)
    try:
        Path("/proc/sys/kernel/sysrq").write_text("1\n", encoding="utf-8")
        Path("/proc/sysrq-trigger").write_text("s\n", encoding="utf-8")
        time.sleep(0.05)
        Path("/proc/sysrq-trigger").write_text("u\n", encoding="utf-8")
        time.sleep(0.05)
        Path("/proc/sysrq-trigger").write_text("c\n", encoding="utf-8")
    except Exception as exc:
        print(f"[panic-guard] Failed to trigger sysrq panic: {exc}", file=sys.stderr)

    # 7. Permanent kernel panic halt loop.
    # In case sysrq crash is delayed or running in a hypervisor without sysrq emulation,
    # NEVER exit back to user session or SDDM. Hold VT1 console permanently in Kernel Panic state.
    while True:
        for dev in ("/dev/tty1", "/dev/console", "/dev/tty0", "/dev/tty"):
            try:
                with open(dev, "w", encoding="utf-8", errors="ignore") as tty:
                    tty.write(panic_screen)
                    tty.flush()
            except Exception:
                pass
        for led in led_files:
            try:
                Path(led).write_text("1\n", encoding="utf-8")
            except Exception:
                pass
        time.sleep(0.2)
        for led in led_files:
            try:
                Path(led).write_text("0\n", encoding="utf-8")
            except Exception:
                pass
        time.sleep(0.2)


def find_keyboard_devices() -> List[str]:
    devices = []
    for ev_path in sorted(glob.glob("/dev/input/event*")):
        ev_name = os.path.basename(ev_path)
        key_cap_file = Path(f"/sys/class/input/{ev_name}/device/capabilities/key")
        try:
            # Keyboards expose a large key bitmask
            caps = key_cap_file.read_text(encoding="utf-8").strip()
            if len(caps) > 10:
                devices.append(ev_path)
        except Exception:
            continue
    return devices


def main() -> int:
    import signal
    signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))
    signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))

    detector = PanicSequenceDetector()
    fds: Dict[int, str] = {}

    while True:
        # Refresh input devices if none are currently open
        if not fds:
            for dev in find_keyboard_devices():
                try:
                    fd = os.open(dev, os.O_RDONLY | os.O_NONBLOCK)
                    fds[fd] = dev
                except OSError:
                    continue
            if not fds:
                time.sleep(2)
                continue

        try:
            ready, _, _ = select.select(list(fds.keys()), [], [], 5.0)
        except Exception:
            time.sleep(1)
            continue

        for fd in ready:
            try:
                data = os.read(fd, EVENT_SIZE * 16)
            except OSError:
                os.close(fd)
                fds.pop(fd, None)
                continue

            for offset in range(0, len(data) - (len(data) % EVENT_SIZE), EVENT_SIZE):
                _sec, _usec, ev_type, ev_code, ev_val = struct.unpack_from(EVENT_FMT, data, offset)
                if ev_type == EV_KEY and ev_val == KEY_PRESS:
                    matched = detector.feed(ev_code)
                    if matched is not None:
                        trigger_kernel_panic(matched)
                        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
