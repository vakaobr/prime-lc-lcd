# Packaging and releases

Maintainer notes: cutting a release, publishing it to the Ubuntu PPA, and
getting the package into Debian (and from there into Ubuntu).

`debian/` is a regular Debian source package (3.0 quilt, debhelper 13). It
installs the pure-Python module to `/usr/share/prime-lc-lcd`, creates the
service user through `systemd-sysusers`, and lets debhelper enable the
systemd unit. `scripts/check-deb.sh <image>` builds it, runs the tests and
lintian, then installs and purges it in a throwaway container; CI runs that on
Debian unstable, Debian 13 and Ubuntu 24.04/26.04.

## Cutting a release

1. Bump the version in `src/prime_lc_lcd/__init__.py` and in the header of
   `packaging/prime-lc-lcd.1`.
2. Add a `## X.Y.Z - YYYY-MM-DD` section to `CHANGELOG.md`.
3. Add a `debian/changelog` entry (`dch -v X.Y.Z-1`, distribution
   `unstable`). `tests/test_versions.py` fails if any of these disagree.
4. Merge, then push a signed tag: `git tag -s vX.Y.Z -m "prime-lc-lcd X.Y.Z" && git push origin vX.Y.Z`.
   The Release workflow publishes the `.deb`, the wheel, the sdist and
   `SHA256SUMS` on GitHub.

The upstream tarball for Debian and the PPA is GitHub's tag archive
(`https://github.com/vakaobr/prime-lc-lcd/archive/refs/tags/vX.Y.Z.tar.gz`),
which `debian/watch` also points at.

## Building a signed source package

Launchpad and Debian both take *source* uploads signed with your GPG key.
On a Debian or Ubuntu machine (or container) with `devscripts`, `debhelper`,
`dh-python` and `python3-pytest`:

```bash
v=0.1.1
curl -fsSL -o prime-lc-lcd_$v.orig.tar.gz https://github.com/vakaobr/prime-lc-lcd/archive/refs/tags/v$v.tar.gz
tar -xzf prime-lc-lcd_$v.orig.tar.gz && cd prime-lc-lcd-$v
dpkg-buildpackage -S -sa -k<KEYID>     # writes ../prime-lc-lcd_$v-1_source.changes
```

`-sa` includes the orig tarball, which the first upload of every upstream
version needs.

## Ubuntu PPA

One-time setup:

1. Create a Launchpad account at https://launchpad.net and set your username.
2. Upload your GPG public key (Launchpad > your profile > OpenPGP keys) and
   confirm the encrypted email Launchpad sends.
3. Create a PPA named `prime-lc-lcd` (Launchpad > your profile > Create a new PPA).
4. Install `dput` and add to `~/.dput.cf`:

   ```ini
   [prime-lc-lcd]
   fqdn = ppa.launchpad.net
   method = ftp
   incoming = ~<launchpad-user>/ubuntu/prime-lc-lcd/
   login = anonymous
   allow_unsigned_uploads = 0
   ```

Each release, upload once per Ubuntu series, changing only the changelog
entry. PPA versions sort below the eventual archive version:

```bash
cp debian/changelog ../changelog.debian
orig=-sa                               # send the orig tarball with the first upload only
for series in noble:24.04 resolute:26.04; do
    name=${series%%:*} num=${series##*:}
    cp ../changelog.debian debian/changelog
    dch -b -v "$v-1~ppa1~ubuntu$num.1" -D "$name" "PPA build for Ubuntu $num."
    dpkg-buildpackage -S $orig -k<KEYID>
    dput prime-lc-lcd "../prime-lc-lcd_$v-1~ppa1~ubuntu$num.1_source.changes"
    orig=-sd
done
cp ../changelog.debian debian/changelog
```

Launchpad builds the binaries; users then run:

```bash
sudo add-apt-repository ppa:<launchpad-user>/prime-lc-lcd
sudo apt install prime-lc-lcd
```

## Debian (and Ubuntu's main archive)

New packages reach Ubuntu by entering Debian unstable first; Ubuntu imports
them automatically for its next release. Uploading to Debian needs a Debian
Developer to sponsor (check and upload) the package:

1. **ITP.** File an "Intent To Package" bug against `wnpp` (template below,
   or `reportbug wnpp`). Note the bug number, then change the
   `debian/changelog` entry to `* Initial release. (Closes: #NNNNNNN)`. This
   clears the last lintian warning (`initial-upload-closes-no-bugs`).
2. **mentors.debian.net.** Create an account, upload your GPG key, and
   upload the signed source package:
   `dput mentors ../prime-lc-lcd_$v-1_source.changes`
   (mentors' dput configuration is shown on its "Uploading" help page).
3. **RFS.** File a "Request For Sponsorship" bug against `sponsorship-requests`
   (mentors generates the template on the package page). Answer review
   feedback until a sponsor uploads it.
4. Once accepted it migrates to Debian testing, then into the next Ubuntu
   development release.

Optional but welcome by sponsors: keeping the packaging on
https://salsa.debian.org and joining a team (for example the Debian Python
Team) so others can help maintain it.

### ITP template

Send to `submit@bugs.debian.org`:

```text
Subject: ITP: prime-lc-lcd -- show CPU/GPU readings on the ASUS PRIME LC ARGB LCD cooler screen

Package: wnpp
Severity: wishlist
Owner: Anderson Leite <andersonleite@outlook.com>
X-Debbugs-Cc: debian-devel@lists.debian.org

* Package name    : prime-lc-lcd
  Version         : 0.1.1
  Upstream Author : Anderson Leite <andersonleite@outlook.com>
* URL             : https://github.com/vakaobr/prime-lc-lcd
* License         : Expat
  Programming Lang: Python
  Description     : show CPU/GPU readings on the ASUS PRIME LC ARGB LCD cooler screen

The ASUS PRIME LC ARGB LCD all-in-one CPU cooler has a small LCD on its
pump that only shows useful content while ASUS's Windows utility runs.
prime-lc-lcd replaces it on Linux: a small unprivileged daemon sends the CPU
and GPU temperature, load and clock to the screen once per second. NVIDIA
GPUs are read through NVML and AMD GPUs through amdgpu sysfs; the device is
accessed through hidraw with a udev rule and a dedicated system user.

No similar package exists in Debian: liquidctl does not support this device,
and other LCD-cooler tools target different models and protocols.

I use the package myself and will maintain it as upstream author. I need a
sponsor.
```
