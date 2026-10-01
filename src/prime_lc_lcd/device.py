"""Talk to the cooler through the kernel's hidraw interface (no libusb needed)."""

from __future__ import annotations

import glob
import os
import select

from . import protocol

_HID_ID = f"HID_ID=0003:{protocol.VENDOR_ID:08X}:{protocol.PRODUCT_ID:08X}"


def find_devices(sysfs: str = "/sys") -> list[str]:
    """``/dev/hidrawN`` paths of every connected PRIME LC LCD, sorted."""
    found = []
    for uevent in glob.glob(os.path.join(sysfs, "class/hidraw/hidraw*/device/uevent")):
        try:
            with open(uevent) as f:
                if _HID_ID in f.read().splitlines():
                    found.append("/dev/" + uevent.split(os.sep)[-3])
        except OSError:
            continue
    return sorted(found, key=lambda p: int(p.rsplit("hidraw", 1)[1]))


class DeviceNotFound(OSError):
    pass


class Cooler:
    """One cooler screen. Opens lazily and reopens after an unplug."""

    def __init__(self, path: str | None = None, reply_timeout: float = 1.0) -> None:
        self.path = path
        self.reply_timeout = reply_timeout
        self._fd: int | None = None
        self._opened: str | None = None

    @property
    def opened_path(self) -> str | None:
        return self._opened if self._fd is not None else None

    def _open(self) -> int:
        if self._fd is None:
            path = self.path
            if path is None:
                devices = find_devices()
                if not devices:
                    raise DeviceNotFound("no ASUS PRIME LC LCD (0b05:1bbe) found")
                path = devices[0]
            self._fd = os.open(path, os.O_RDWR | os.O_CLOEXEC)
            self._opened = path
            self._drain()
        return self._fd

    def _drain(self) -> None:
        while self._fd is not None and select.select([self._fd], [], [], 0)[0]:
            os.read(self._fd, protocol.REPORT_LEN)

    def close(self) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None

    def send(self, report: bytes) -> protocol.Reply | None:
        """Send one report and wait briefly for the cooler's answer."""
        try:
            fd = self._open()
            # hidraw: the first byte is the report ID; 0 means "unnumbered".
            os.write(fd, b"\x00" + report)
            if select.select([fd], [], [], self.reply_timeout)[0]:
                return protocol.parse_reply(os.read(fd, protocol.REPORT_LEN))
            return None
        except OSError:
            self.close()
            raise

    def __enter__(self) -> Cooler:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
