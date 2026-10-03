import ctypes
import logging
import threading
from ctypes import wintypes

from speak.interrupts.background import BackgroundInterrupts, EdgeTrigger, StopRequest
from speak.interrupts.hotkey import Hotkey
from speak.settings import Settings

WM_HOTKEY = 0x0312
MOD_NOREPEAT = 0x4000
MODIFIERS = {"alt": 0x1, "ctrl": 0x2, "shift": 0x4, "super": 0x8}
NAMED_KEYS = {"escape": 0x1B, "space": 0x20, "return": 0x0D, "tab": 0x09, "delete": 0x2E, "period": 0xBE}
PM_REMOVE = 0x1
POLL_SECONDS = 0.05
MIC_POLL_SECONDS = 0.3
MICROPHONE_CONSENT = r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone"

log = logging.getLogger(__name__)


def virtual_key(key: str) -> int:
    if key in NAMED_KEYS:
        return NAMED_KEYS[key]
    if key.startswith("f") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        return 0x70 + int(key[1:]) - 1
    if len(key) == 1 and key.isalnum():
        return ord(key.upper())
    raise ValueError(f"unsupported key {key!r}")


class WindowsHotkey:
    name = "windows-hotkey"

    def run(self, settings: Settings, request_stop: StopRequest, stopped: threading.Event) -> None:
        user32 = ctypes.windll.user32
        hotkey = Hotkey.parse(settings.hotkey)
        modifiers = sum(MODIFIERS[modifier] for modifier in hotkey.modifiers) | MOD_NOREPEAT
        if not user32.RegisterHotKey(None, 1, modifiers, virtual_key(hotkey.key)):
            log.warning("could not register hotkey %s (already taken?)", settings.hotkey)
            return
        log.info("hotkey %s registered", settings.hotkey)
        message = wintypes.MSG()
        try:
            while not stopped.wait(POLL_SECONDS):
                while user32.PeekMessageW(ctypes.byref(message), None, 0, 0, PM_REMOVE):
                    if message.message == WM_HOTKEY:
                        request_stop("hotkey")
        finally:
            user32.UnregisterHotKey(None, 1)


class WindowsMicrophone:
    name = "windows-microphone"

    def run(self, settings: Settings, request_stop: StopRequest, stopped: threading.Event) -> None:
        if not settings.stop_on_mic:
            return
        trigger = EdgeTrigger()
        log.info("watching microphone")
        while not stopped.wait(MIC_POLL_SECONDS):
            if trigger.update(microphone_in_use()):
                request_stop("mic")


def microphone_in_use() -> bool:
    import winreg

    def any_active(path: str) -> bool:
        try:
            parent = winreg.OpenKey(winreg.HKEY_CURRENT_USER, path)
        except OSError:
            return False
        with parent:
            index = 0
            while True:
                try:
                    name = winreg.EnumKey(parent, index)
                except OSError:
                    return False
                index += 1
                if name == "NonPackaged":
                    continue
                try:
                    with winreg.OpenKey(parent, name) as app:
                        started, _ = winreg.QueryValueEx(app, "LastUsedTimeStart")
                        stopped, _ = winreg.QueryValueEx(app, "LastUsedTimeStop")
                except OSError:
                    continue
                if started and not stopped:
                    return True

    return any_active(MICROPHONE_CONSENT) or any_active(MICROPHONE_CONSENT + r"\NonPackaged")


def windows_interrupts() -> BackgroundInterrupts:
    return BackgroundInterrupts([WindowsHotkey(), WindowsMicrophone()])
