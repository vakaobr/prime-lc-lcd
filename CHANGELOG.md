# Changelog

## 0.1.1 - 2026-10-01

Packaging release; no change to what the screen shows.

- Proper Debian source package (`debian/`), built and tested on Debian unstable, Ubuntu 24.04 and 26.04, ready for a PPA and for Debian.
- The service user is now created by systemd-sysusers.
- Manual page `prime-lc-lcd(1)`.
- A bare `make` no longer installs anything.

## 0.1.0 - 2026-10-01

First release.

- Live CPU and GPU temperature, load and clock on the ASUS PRIME LC ARGB LCD screen (USB 0b05:1bbe).
- NVIDIA GPUs via NVML, AMD GPUs via amdgpu sysfs; AMD and Intel CPU temperature sensors.
- Unprivileged, hardened systemd service with a udev rule; reconnects after unplug.
- `--list`, `--readings` and `--switch-theme` commands.
- Debian package and `make install` for other distributions.
