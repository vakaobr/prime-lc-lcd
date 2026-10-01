"""CPU and GPU readings from sysfs, /proc and NVML. Standard library only."""

from __future__ import annotations

import ctypes
import glob
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Reading:
    temperature_c: float
    load_pct: float
    clock_mhz: int


def _read(path: str) -> str:
    with open(path) as f:
        return f.read().strip()


def _read_int(path: str) -> int | None:
    try:
        return int(_read(path))
    except (OSError, ValueError):
        return None


class Cpu:
    """Package temperature, total utilisation and average core clock."""

    # hwmon drivers and the label of their package sensor (None = temp1).
    _TEMP_DRIVERS = {"k10temp": "Tctl", "zenpower": "Tdie", "coretemp": "Package id 0"}

    def __init__(self, root: str = "/") -> None:
        self.root = root
        self.temp_path = self._find_temp_sensor()
        self._prev = self._times()

    def _p(self, *parts: str) -> str:
        return os.path.join(self.root, *parts)

    def _find_temp_sensor(self) -> str | None:
        for name_file in sorted(glob.glob(self._p("sys/class/hwmon/hwmon*/name"))):
            try:
                driver = _read(name_file)
            except OSError:
                continue
            if driver not in self._TEMP_DRIVERS:
                continue
            base = os.path.dirname(name_file)
            wanted = self._TEMP_DRIVERS[driver]
            for label_file in sorted(glob.glob(os.path.join(base, "temp*_label"))):
                try:
                    if _read(label_file) == wanted:
                        return label_file.replace("_label", "_input")
                except OSError:
                    continue
            if os.path.exists(os.path.join(base, "temp1_input")):
                return os.path.join(base, "temp1_input")
        for zone in sorted(glob.glob(self._p("sys/class/thermal/thermal_zone*"))):
            try:
                if _read(os.path.join(zone, "type")) in ("x86_pkg_temp", "cpu-thermal", "cpu_thermal"):
                    return os.path.join(zone, "temp")
            except OSError:
                continue
        return None

    def _times(self) -> tuple[int, int]:
        with open(self._p("proc/stat")) as f:
            fields = [int(x) for x in f.readline().split()[1:]]
        busy_and_idle = sum(fields[:8])  # guest time is already inside user/nice
        idle = fields[3] + fields[4]  # idle + iowait
        return busy_and_idle, idle

    def temperature(self) -> float:
        value = _read_int(self.temp_path) if self.temp_path else None
        return value / 1000.0 if value is not None else 0.0

    def load(self) -> float:
        """Utilisation since the previous call, in percent."""
        total, idle = self._times()
        d_total, d_idle = total - self._prev[0], idle - self._prev[1]
        self._prev = (total, idle)
        return 100.0 * (d_total - d_idle) / d_total if d_total > 0 else 0.0

    def clock(self) -> int:
        khz = [
            v
            for v in (
                _read_int(p) for p in glob.glob(self._p("sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_cur_freq"))
            )
            if v is not None
        ]
        return round(sum(khz) / len(khz) / 1000) if khz else 0

    def read(self) -> Reading:
        return Reading(self.temperature(), self.load(), self.clock())


class GpuUnavailable(RuntimeError):
    pass


class _NvmlUtilization(ctypes.Structure):
    _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]


class NvidiaGpu:
    """First NVIDIA GPU through NVML (libnvidia-ml ships with the driver)."""

    name = "nvidia"

    def __init__(self, index: int = 0) -> None:
        try:
            self._nvml = ctypes.CDLL("libnvidia-ml.so.1")
        except OSError as e:
            raise GpuUnavailable("libnvidia-ml.so.1 not found") from e
        self._check(self._nvml.nvmlInit_v2(), "init")
        self._handle = ctypes.c_void_p()
        self._check(self._nvml.nvmlDeviceGetHandleByIndex_v2(index, ctypes.byref(self._handle)), "device")

    @staticmethod
    def _check(rc: int, what: str) -> None:
        if rc != 0:
            raise GpuUnavailable(f"NVML {what} failed (error {rc})")

    def read(self) -> Reading:
        temp, clock, util = ctypes.c_uint(), ctypes.c_uint(), _NvmlUtilization()
        self._check(self._nvml.nvmlDeviceGetTemperature(self._handle, 0, ctypes.byref(temp)), "temperature")
        self._check(self._nvml.nvmlDeviceGetUtilizationRates(self._handle, ctypes.byref(util)), "utilisation")
        self._check(self._nvml.nvmlDeviceGetClockInfo(self._handle, 0, ctypes.byref(clock)), "clock")
        return Reading(float(temp.value), float(util.gpu), int(clock.value))


class AmdGpu:
    """An amdgpu card through sysfs. Prefers a discrete card over an APU's iGPU."""

    name = "amd"

    def __init__(self, root: str = "/") -> None:
        self.device = self._find(root)
        hwmon = sorted(glob.glob(os.path.join(self.device, "hwmon/hwmon*")))
        if not hwmon:
            raise GpuUnavailable("amdgpu card has no hwmon sensors")
        self.hwmon = hwmon[0]

    @staticmethod
    def _find(root: str) -> str:
        cards = []
        for dev in sorted(glob.glob(os.path.join(root, "sys/class/drm/card[0-9]*/device"))):
            if os.path.basename(os.path.dirname(dev)).count("-"):
                continue  # connector entries like card1-DP-1
            if not os.path.exists(os.path.join(dev, "gpu_busy_percent")):
                continue
            try:
                if _read(os.path.join(dev, "vendor")) != "0x1002":
                    continue
            except OSError:
                continue
            vram = _read_int(os.path.join(dev, "mem_info_vram_total")) or 0
            cards.append((vram, dev))
        if not cards:
            raise GpuUnavailable("no amdgpu card found")
        return max(cards)[1]  # most VRAM = the discrete card

    def read(self) -> Reading:
        temp = _read_int(os.path.join(self.hwmon, "temp1_input"))
        busy = _read_int(os.path.join(self.device, "gpu_busy_percent"))
        sclk_hz = _read_int(os.path.join(self.hwmon, "freq1_input"))
        return Reading(
            (temp or 0) / 1000.0,
            float(busy or 0),
            round((sclk_hz or 0) / 1_000_000),
        )


def open_gpu(kind: str = "auto") -> NvidiaGpu | AmdGpu | None:
    """The GPU to show. ``kind``: auto, nvidia, amd or none."""
    if kind == "none":
        return None
    order = {"auto": (NvidiaGpu, AmdGpu), "nvidia": (NvidiaGpu,), "amd": (AmdGpu,)}[kind]
    errors = []
    for cls in order:
        try:
            return cls()
        except GpuUnavailable as e:
            errors.append(f"{cls.name}: {e}")
    raise GpuUnavailable("; ".join(errors))
