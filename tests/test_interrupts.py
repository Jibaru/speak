import pytest

from speak.interrupts.background import EdgeTrigger
from speak.interrupts.hotkey import Hotkey
from speak.interrupts.linux import keysym_name
from speak.interrupts.windows import virtual_key
from speak.system.lock import InstanceLock


def test_parse_hotkey_normalizes_aliases():
    assert Hotkey.parse("Option+Esc") == Hotkey(frozenset({"alt"}), "escape")
    assert Hotkey.parse("ctrl+cmd+shift+k") == Hotkey(frozenset({"ctrl", "super", "shift"}), "k")


@pytest.mark.parametrize("description", ["hyper+escape", "ctrl+", ""])
def test_invalid_hotkeys_are_rejected(description):
    with pytest.raises(ValueError):
        Hotkey.parse(description)


@pytest.mark.parametrize(("key", "code"), [("escape", 0x1B), ("space", 0x20), ("f1", 0x70), ("f12", 0x7B), ("k", ord("K")), ("7", ord("7"))])
def test_windows_virtual_keys(key, code):
    assert virtual_key(key) == code


def test_windows_rejects_unknown_keys():
    with pytest.raises(ValueError):
        virtual_key("hyper")


@pytest.mark.parametrize(("key", "name"), [("escape", "Escape"), ("space", "space"), ("f5", "F5"), ("k", "k")])
def test_x11_keysym_names(key, name):
    assert keysym_name(key) == name


def test_edge_trigger_fires_once_per_activation():
    trigger = EdgeTrigger()
    assert [trigger.update(active) for active in (False, True, True, False, True)] == [False, True, False, False, True]


def test_instance_lock_is_exclusive(tmp_path):
    first, second = InstanceLock(tmp_path / "a.lock"), InstanceLock(tmp_path / "a.lock")
    assert first.acquire()
    assert not second.acquire()
    first.release()
    assert second.acquire()
    second.release()
