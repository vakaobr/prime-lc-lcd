"""Byte-exact checks against frames the official ASUS app sends."""

import pytest

from prime_lc_lcd import protocol


def test_metrics_matches_vendor_template():
    # The vendor app's built-in frame: CPU, 34.1 C, 96.8 %, 2000 MHz.
    report = protocol.metrics(protocol.SOURCE_CPU, 34.1, 96.8, 2000)
    assert list(report[:12]) == [0x2C, 0x20, 0x01, 0x07, 0, 34, 1, 96, 8, 0x07, 0xD0, 0xB6]
    assert len(report) == protocol.REPORT_LEN
    assert report[12:] == bytes(52)


def test_switch_theme_matches_vendor():
    assert list(protocol.switch_theme()[:8]) == [0x2C, 0x10, 0x01, 0x03, 0x01, 0x01, 0x00, 0x42]


def test_gpu_source_and_rounding():
    report = protocol.metrics(protocol.SOURCE_GPU, 67.84, 88.0, 2550)
    assert list(report[4:11]) == [1, 67, 8, 88, 0, 0x09, 0xF6]
    assert report[11] == protocol.checksum(report[:11])


@pytest.mark.parametrize(
    ("temp", "load", "clock", "expected"),
    [
        (-5.0, -1.0, -10, [0, 0, 0, 0, 0, 0]),
        (999.0, 140.0, 70000, [255, 9, 100, 0, 0xFF, 0xFF]),
        (39.96, 99.96, 1, [40, 0, 100, 0, 0, 1]),
    ],
)
def test_values_are_clamped(temp, load, clock, expected):
    assert list(protocol.metrics(protocol.SOURCE_CPU, temp, load, clock)[5:11]) == expected


def test_unknown_source_rejected():
    with pytest.raises(ValueError):
        protocol.metrics(7, 1, 1, 1)


@pytest.mark.parametrize(
    ("raw", "cmd"),
    [
        ("2c 20 01 01 01 4f", protocol.CMD_METRICS),  # seen from a real cooler
        ("2c 10 01 01 01 3f", protocol.CMD_THEME),
    ],
)
def test_parse_real_replies(raw, cmd):
    reply = protocol.parse_reply(bytes.fromhex(raw) + bytes(58))
    assert reply == protocol.Reply(cmd=cmd, status=1)
    assert reply.ok


def test_parse_rejects_garbage():
    assert protocol.parse_reply(bytes(64)) is None
    assert protocol.parse_reply(bytes.fromhex("2c 20 01 01 01 50") + bytes(58)) is None  # bad checksum
