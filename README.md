# prime-lc-lcd

Live CPU and GPU readings on the screen of the **ASUS PRIME LC ARGB LCD**
all-in-one cooler, on GNU/Linux.

ASUS only ships a Windows utility for this cooler, and without it the screen
shows nothing useful. `prime-lc-lcd` replaces it with a small, unprivileged
systemd service:

- shows the temperature, load and clock speed of the CPU and the GPU, switching
  between them every few seconds (or showing just one)
- reads NVIDIA GPUs through NVML (part of the NVIDIA driver) and AMD GPUs
  through the `amdgpu` sysfs interface
- reads AMD (`k10temp`, `zenpower`) and Intel (`coretemp`) CPU temperatures
- recovers by itself if the cooler is unplugged or the system resumes
- pure Python standard library, no dependencies, about 20 MB of memory

Not affiliated with or endorsed by ASUS.

## Supported hardware

| Cooler | USB ID | Status |
|---|---|---|
| ASUS PRIME LC 360 ARGB LCD | `0b05:1bbe` | tested |
| ASUS PRIME LC 240/280 ARGB LCD | `0b05:1bbe` (expected) | untested, reports welcome |

Check yours with `lsusb | grep 0b05:1bbe`. Other ASUS LCD coolers (ROG Ryujin,
TUF/TX Gaming LC) use different protocols and are not supported.

## Install

### Debian, Ubuntu and derivatives

Download the `.deb` from the
[latest release](https://github.com/vakaobr/prime-lc-lcd/releases/latest) and:

```bash
sudo apt install ./prime-lc-lcd_*_all.deb
```

The package creates the `prime-lc-lcd` system user, installs the udev rule
that gives that user access to the cooler, and starts the service.

### Other distributions

You need Python 3.9 or newer, systemd and udev.

```bash
git clone https://github.com/vakaobr/prime-lc-lcd.git
cd prime-lc-lcd
sudo make install       # installs under /usr/local and starts the service
sudo make uninstall     # removes it again
```

## Configure

Edit `/etc/default/prime-lc-lcd`, then `sudo systemctl restart prime-lc-lcd`.

| Setting | Values | Default |
|---|---|---|
| `PRIME_LC_LCD_SHOW` | `alternate`, `cpu`, `gpu` | `alternate` |
| `PRIME_LC_LCD_INTERVAL` | seconds per source when alternating | `5` |
| `PRIME_LC_LCD_GPU` | `auto` (NVIDIA, then AMD), `nvidia`, `amd`, `none` | `auto` |
| `PRIME_LC_LCD_DEVICE` | a `/dev/hidrawN` path, empty to autodetect | empty |

The screen's layout comes from the cooler's built-in themes. To move to the
next theme (it cycles, so repeat until you like it):

```bash
sudo -u prime-lc-lcd prime-lc-lcd --switch-theme
```

## Command line

```text
prime-lc-lcd                    run the service loop (what systemd starts)
prime-lc-lcd --list             list connected coolers
prime-lc-lcd --readings         print what would be shown, without sending it
prime-lc-lcd --switch-theme     advance the screen to its next theme
prime-lc-lcd --show gpu --gpu amd -v
```

## Troubleshooting

- `journalctl -u prime-lc-lcd` shows what the service is doing.
- **Permission denied** on `/dev/hidrawN`: the udev rule did not apply. Run
  `sudo udevadm trigger --subsystem-match=hidraw --action=change` or replug the
  cooler's USB cable, then check `ls -l /dev/hidraw*` shows group `prime-lc-lcd`.
- **No GPU readings**: for NVIDIA, the proprietary driver must be installed
  (`nvidia-smi` works). For AMD, the card must use the `amdgpu` driver. Set
  `PRIME_LC_LCD_GPU=none` to show only the CPU.
- **CPU temperature shows 0**: no supported sensor was found. Load `k10temp`
  (AMD) or `coretemp` (Intel) and check `sensors`.

## How it works

The cooler renders its own dashboard. Once a second the service sends one
64-byte HID report with the readings, and the cooler answers with an
acknowledgement. [docs/protocol.md](docs/protocol.md) describes the format.

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install pytest ruff
.venv/bin/python -m pytest -q
.venv/bin/ruff check . && .venv/bin/ruff format --check .
scripts/build-deb.sh            # needs dpkg-deb
```

## License

MIT, see [LICENSE](LICENSE). ASUS and PRIME are trademarks of ASUSTeK Computer Inc.
