"""Wire format of the ASUS PRIME LC ARGB LCD screen (USB 0b05:1bbe).

The cooler draws its own dashboard; the host only sends numbers. Every message
is one 64-byte HID output report without a report ID:

    2C <cmd> 01 <len> <payload...> <checksum> 00...

The checksum is the sum of all preceding bytes, modulo 256. The cooler answers
each message with a 64-byte input report echoing the command, where byte 4 is
the status (01 = ok). See docs/protocol.md.
"""

from __future__ import annotations

from dataclasses import dataclass

VENDOR_ID = 0x0B05
PRODUCT_ID = 0x1BBE
REPORT_LEN = 64

PREFIX = 0x2C
CMD_THEME = 0x10
CMD_METRICS = 0x20
STATUS_OK = 0x01

SOURCE_CPU = 0
SOURCE_GPU = 1


def checksum(data: bytes | list[int]) -> int:
    return sum(data) & 0xFF


def message(cmd: int, payload: list[int]) -> bytes:
    """A complete 64-byte report for ``cmd`` carrying ``payload``."""
    body = [PREFIX, cmd, 0x01, len(payload), *payload]
    body.append(checksum(body))
    if len(body) > REPORT_LEN:
        raise ValueError("payload too long")
    return bytes(body) + bytes(REPORT_LEN - len(body))


def _whole_and_tenths(value: float, upper: float) -> tuple[int, int]:
    tenths = round(min(max(value, 0.0), upper) * 10)
    return tenths // 10, tenths % 10


def metrics(source: int, temperature_c: float, load_pct: float, clock_mhz: int) -> bytes:
    """Readings shown on the screen. ``source`` picks the CPU or GPU label."""
    if source not in (SOURCE_CPU, SOURCE_GPU):
        raise ValueError(f"unknown source {source}")
    temp = _whole_and_tenths(temperature_c, 255.9)
    load = _whole_and_tenths(load_pct, 100.0)
    clock = min(max(int(clock_mhz), 0), 0xFFFF)
    return message(CMD_METRICS, [source, *temp, *load, clock >> 8, clock & 0xFF])


def switch_theme() -> bytes:
    """Advance the screen to its next built-in theme (it cycles; there is no 'set')."""
    return message(CMD_THEME, [0x01, 0x01, 0x00])


@dataclass(frozen=True)
class Reply:
    cmd: int
    status: int

    @property
    def ok(self) -> bool:
        return self.status == STATUS_OK


def parse_reply(data: bytes) -> Reply | None:
    if len(data) < 6 or data[0] != PREFIX:
        return None
    length = data[3]
    if len(data) < 5 + length or checksum(data[: 4 + length]) != data[4 + length]:
        return None
    return Reply(cmd=data[1], status=data[4] if length else 0)
