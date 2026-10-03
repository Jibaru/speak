import ctypes
import ctypes.util
import logging
import os
import shutil
import subprocess
import threading

from speak.interrupts.background import BackgroundInterrupts, EdgeTrigger, StopRequest
from speak.interrupts.hotkey import Hotkey
from speak.settings import Settings

KEY_PRESS = 2
KEY_PRESS_MASK = 1
GRAB_MODE_ASYNC = 1
MODIFIERS = {"shift": 1, "ctrl": 4, "alt": 8, "super": 64}
IGNORED_LOCKS = (0, 2, 16, 18)
NAMED_KEYSYMS = {"escape": "Escape", "space": "space", "return": "Return", "tab": "Tab", "delete": "Delete", "period": "period"}
POLL_SECONDS = 0.05
MIC_POLL_SECONDS = 0.5

log = logging.getLogger(__name__)


def keysym_name(key: str) -> str:
    if key in NAMED_KEYSYMS:
        return NAMED_KEYSYMS[key]
    if key.startswith("f") and key[1:].isdigit():
        return key.upper()
    return key


class X11Hotkey:
    name = "x11-hotkey"

    def run(self, settings: Settings, request_stop: StopRequest, stopped: threading.Event) -> None:
        library = ctypes.util.find_library("X11")
        if not os.environ.get("DISPLAY") or library is None:
            log.warning("no X11 display: bind `speak stop` to a keyboard shortcut in your desktop settings")
            return
        x11 = ctypes.cdll.LoadLibrary(library)
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        x11.XDefaultRootWindow.restype = ctypes.c_ulong
        x11.XStringToKeysym.restype = ctypes.c_ulong
        x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        x11.XGrabKey.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint, ctypes.c_ulong, ctypes.c_int, ctypes.c_int, ctypes.c_int]
        x11.XPending.argtypes = [ctypes.c_void_p]
        x11.XNextEvent.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        x11.XSelectInput.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_long]

        display = x11.XOpenDisplay(None)
        if not display:
            log.warning("could not open the X11 display")
            return
        root = x11.XDefaultRootWindow(display)
        hotkey = Hotkey.parse(settings.hotkey)
        keycode = x11.XKeysymToKeycode(display, x11.XStringToKeysym(keysym_name(hotkey.key).encode()))
        modifiers = sum(MODIFIERS[modifier] for modifier in hotkey.modifiers)
        for lock in IGNORED_LOCKS:
            x11.XGrabKey(display, keycode, modifiers | lock, root, True, GRAB_MODE_ASYNC, GRAB_MODE_ASYNC)
        x11.XSelectInput(display, root, KEY_PRESS_MASK)
        if os.environ.get("WAYLAND_DISPLAY"):
            log.warning("on Wayland the hotkey only works while an X11 window has focus")
        log.info("hotkey %s registered", settings.hotkey)

        event = (ctypes.c_long * 24)()
        while not stopped.wait(POLL_SECONDS):
            while x11.XPending(display):
                x11.XNextEvent(display, event)
                if ctypes.cast(event, ctypes.POINTER(ctypes.c_int))[0] == KEY_PRESS:
                    request_stop("hotkey")


class PulseMicrophone:
    name = "pulse-microphone"

    def run(self, settings: Settings, request_stop: StopRequest, stopped: threading.Event) -> None:
        if not settings.stop_on_mic:
            return
        pactl = shutil.which("pactl")
        if pactl is None:
            log.warning("pactl not found, microphone detection disabled")
            return
        trigger = EdgeTrigger()
        log.info("watching microphone")
        while not stopped.wait(MIC_POLL_SECONDS):
            if trigger.update(_recording(pactl)):
                request_stop("mic")


def _recording(pactl: str) -> bool:
    result = subprocess.run([pactl, "list", "short", "source-outputs"], capture_output=True, text=True, timeout=2)
    return bool(result.stdout.strip())


def linux_interrupts() -> BackgroundInterrupts:
    return BackgroundInterrupts([X11Hotkey(), PulseMicrophone()])
