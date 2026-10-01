"""prime-lc-lcd: live CPU/GPU readings on the ASUS PRIME LC ARGB LCD screen."""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import time

from . import __version__, protocol
from .device import Cooler, find_devices
from .sensors import Cpu, GpuUnavailable, Reading, open_gpu

log = logging.getLogger("prime-lc-lcd")


def _env(name: str, default: str) -> str:
    return os.environ.get(f"PRIME_LC_LCD_{name}", default)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="prime-lc-lcd", description=__doc__.split(": ", 1)[1])
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    ap.add_argument(
        "--show",
        choices=("alternate", "cpu", "gpu"),
        default=_env("SHOW", "alternate"),
        help="what the screen shows (default: alternate between CPU and GPU)",
    )
    ap.add_argument(
        "--interval",
        type=int,
        default=int(_env("INTERVAL", "5")),
        help="seconds per source when alternating (default: 5)",
    )
    ap.add_argument(
        "--gpu",
        choices=("auto", "nvidia", "amd", "none"),
        default=_env("GPU", "auto"),
        help="GPU to read (default: auto, NVIDIA first, then AMD)",
    )
    ap.add_argument("--device", default=_env("DEVICE", "") or None, help="hidraw node (default: autodetect)")
    action = ap.add_mutually_exclusive_group()
    action.add_argument("--list", action="store_true", help="list connected coolers and exit")
    action.add_argument("--readings", action="store_true", help="print current readings without sending them")
    action.add_argument("--switch-theme", action="store_true", help="advance the screen to its next theme and exit")
    ap.add_argument("-v", "--verbose", action="store_true")
    return ap.parse_args(argv)


def run(cooler: Cooler, cpu: Cpu, gpu, show: str, interval: int) -> None:
    stopping = False

    def stop(*_: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    healthy = None
    started = time.monotonic()
    while not stopping:
        tick = time.monotonic()
        cpu_reading = cpu.read()  # sample every second so the load window stays 1 s wide
        use_gpu = gpu is not None and (
            show == "gpu" or (show == "alternate" and int((tick - started) // interval) % 2 == 1)
        )
        try:
            if use_gpu:
                report = protocol.metrics(protocol.SOURCE_GPU, *_fields(gpu.read()))
            else:
                report = protocol.metrics(protocol.SOURCE_CPU, *_fields(cpu_reading))
            reply = cooler.send(report)
            if healthy is not True:
                log.info("sending to %s", cooler.opened_path)
                healthy = True
            if reply is not None and not reply.ok:
                log.warning("cooler rejected a frame (status %#04x)", reply.status)
        except (OSError, GpuUnavailable) as e:
            if healthy is not False:
                log.warning("%s; retrying every 5 s", e)
                healthy = False
            time.sleep(4)
        time.sleep(max(0.0, 1.0 - (time.monotonic() - tick)))


def _fields(r: Reading) -> tuple[float, float, int]:
    return r.temperature_c, r.load_pct, r.clock_mhz


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
        stream=sys.stderr,
    )

    if args.list:
        devices = find_devices()
        print("\n".join(devices) if devices else "no ASUS PRIME LC LCD (0b05:1bbe) found")
        return 0 if devices else 1

    if args.switch_theme:
        with Cooler(args.device) as cooler:
            reply = cooler.send(protocol.switch_theme())
        print("theme switched" if reply and reply.ok else f"unexpected reply: {reply}")
        return 0 if reply and reply.ok else 1

    cpu = Cpu()
    gpu = None
    if args.show != "cpu":
        try:
            gpu = open_gpu(args.gpu)
        except GpuUnavailable as e:
            if args.show == "gpu":
                log.error("no GPU: %s", e)
                return 1
            log.warning("no GPU readings (%s); showing the CPU only", e)

    if args.readings:
        time.sleep(1)
        for name, reading in (("CPU", cpu.read()), ("GPU", gpu.read() if gpu else None)):
            if reading:
                print(f"{name}  {reading.temperature_c:5.1f} C  {reading.load_pct:5.1f} %  {reading.clock_mhz:5d} MHz")
        return 0

    if cpu.temp_path is None:
        log.warning("no CPU temperature sensor found; the screen will show 0")
    with Cooler(args.device) as cooler:
        run(cooler, cpu, gpu, args.show, max(1, args.interval))
    return 0
