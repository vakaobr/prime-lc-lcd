# Changelog

## 0.1.0 - 2026-10-01

First release.

- Live CPU and GPU temperature, load and clock on the ASUS PRIME LC ARGB LCD screen (USB 0b05:1bbe).
- NVIDIA GPUs via NVML, AMD GPUs via amdgpu sysfs; AMD and Intel CPU temperature sensors.
- Unprivileged, hardened systemd service with a udev rule; reconnects after unplug.
- `--list`, `--readings` and `--switch-theme` commands.
- Debian package and `make install` for other distributions.
