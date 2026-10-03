import sys

from speak.paths import Paths


def create_sidecar(paths: Paths):
    if sys.platform == "darwin":
        from speak.interrupts.macos import MacHelper

        return MacHelper(paths)
    if sys.platform == "win32":
        from speak.interrupts.windows import windows_interrupts

        return windows_interrupts()
    from speak.interrupts.linux import linux_interrupts

    return linux_interrupts()
