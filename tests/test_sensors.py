"""Sensor discovery against fake sysfs/proc trees."""

from pathlib import Path

import pytest

from prime_lc_lcd import device, sensors


def write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def stat_line(user, idle) -> str:
    return f"cpu  {user} 0 0 {idle} 0 0 0 0 0 0\ncpu0 1 1 1 1 1 1 1 1 1 1\n"


@pytest.fixture
def amd_cpu(tmp_path: Path) -> Path:
    write(tmp_path, "sys/class/hwmon/hwmon0/name", "nvme\n")
    write(tmp_path, "sys/class/hwmon/hwmon0/temp1_input", "31000\n")
    write(tmp_path, "sys/class/hwmon/hwmon2/name", "k10temp\n")
    write(tmp_path, "sys/class/hwmon/hwmon2/temp1_label", "Tctl\n")
    write(tmp_path, "sys/class/hwmon/hwmon2/temp1_input", "41250\n")
    write(tmp_path, "sys/class/hwmon/hwmon2/temp3_label", "Tccd1\n")
    write(tmp_path, "sys/class/hwmon/hwmon2/temp3_input", "38000\n")
    for cpu, khz in enumerate((3000000, 5000000)):
        write(tmp_path, f"sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_cur_freq", f"{khz}\n")
    write(tmp_path, "proc/stat", stat_line(100, 900))
    return tmp_path


def test_cpu_reads_k10temp_tctl_load_and_clock(amd_cpu: Path):
    cpu = sensors.Cpu(root=str(amd_cpu))
    assert cpu.temp_path.endswith("hwmon2/temp1_input")
    write(amd_cpu, "proc/stat", stat_line(400, 1600))  # +300 busy, +700 idle
    reading = cpu.read()
    assert reading == sensors.Reading(41.25, 30.0, 4000)


def test_intel_coretemp_uses_package_sensor(tmp_path: Path):
    write(tmp_path, "sys/class/hwmon/hwmon1/name", "coretemp\n")
    write(tmp_path, "sys/class/hwmon/hwmon1/temp2_label", "Core 0\n")
    write(tmp_path, "sys/class/hwmon/hwmon1/temp2_input", "50000\n")
    write(tmp_path, "sys/class/hwmon/hwmon1/temp1_label", "Package id 0\n")
    write(tmp_path, "sys/class/hwmon/hwmon1/temp1_input", "55000\n")
    write(tmp_path, "proc/stat", stat_line(1, 1))
    assert sensors.Cpu(root=str(tmp_path)).temperature() == 55.0


def test_thermal_zone_fallback_and_missing_sensor(tmp_path: Path):
    write(tmp_path, "proc/stat", stat_line(1, 1))
    assert sensors.Cpu(root=str(tmp_path)).temperature() == 0.0
    write(tmp_path, "sys/class/thermal/thermal_zone3/type", "x86_pkg_temp\n")
    write(tmp_path, "sys/class/thermal/thermal_zone3/temp", "47000\n")
    assert sensors.Cpu(root=str(tmp_path)).temperature() == 47.0


def amd_card(root: Path, card: int, vram: int, busy: int) -> None:
    base = f"sys/class/drm/card{card}/device"
    write(root, f"{base}/vendor", "0x1002\n")
    write(root, f"{base}/gpu_busy_percent", f"{busy}\n")
    write(root, f"{base}/mem_info_vram_total", f"{vram}\n")
    write(root, f"{base}/hwmon/hwmon9/temp1_input", "52000\n")
    write(root, f"{base}/hwmon/hwmon9/freq1_input", "2400000000\n")


def test_amd_prefers_discrete_card(tmp_path: Path):
    amd_card(tmp_path, 1, 512 << 20, busy=3)  # APU iGPU
    amd_card(tmp_path, 2, 16 << 30, busy=77)  # discrete
    write(tmp_path, "sys/class/drm/card2-DP-1/device/vendor", "0x1002\n")  # connector, ignored
    gpu = sensors.AmdGpu(root=str(tmp_path))
    assert gpu.device.endswith("card2/device")
    assert gpu.read() == sensors.Reading(52.0, 77.0, 2400)


def test_amd_ignores_other_vendors(tmp_path: Path):
    write(tmp_path, "sys/class/drm/card0/device/vendor", "0x10de\n")
    write(tmp_path, "sys/class/drm/card0/device/gpu_busy_percent", "0\n")
    with pytest.raises(sensors.GpuUnavailable):
        sensors.AmdGpu(root=str(tmp_path))


def test_open_gpu_none():
    assert sensors.open_gpu("none") is None


def test_find_devices_matches_only_the_cooler(tmp_path: Path):
    write(
        tmp_path,
        "class/hidraw/hidraw10/device/uevent",
        "HID_ID=0003:00000B05:00001BBE\nHID_NAME=AsusTek PRIME LC LCD\n",
    )
    write(tmp_path, "class/hidraw/hidraw2/device/uevent", "HID_ID=0003:00000B05:00001BBE\n")
    write(tmp_path, "class/hidraw/hidraw0/device/uevent", "HID_ID=0003:0000046D:0000C52B\n")
    assert device.find_devices(sysfs=str(tmp_path)) == ["/dev/hidraw2", "/dev/hidraw10"]
