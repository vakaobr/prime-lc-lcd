#!/usr/bin/env bash
# Build dist/prime-lc-lcd_<version>_all.deb with plain dpkg-deb (no debhelper).
set -euo pipefail
cd "$(dirname "$0")/.."

version=$(python3 -c 'import re,sys; print(re.search(r"__version__ = \"(.+)\"", open("src/prime_lc_lcd/__init__.py").read())[1])')
pkg="prime-lc-lcd_${version}_all"
root=$(mktemp -d)
trap 'rm -rf -- "$root"' EXIT
chmod 0755 "$root"  # mktemp makes it 0700; this becomes the package's ./ entry

install -Dm0644 -t "$root/usr/lib/python3/dist-packages/prime_lc_lcd" src/prime_lc_lcd/*.py
install -Dm0755 packaging/prime-lc-lcd.bin "$root/usr/bin/prime-lc-lcd"
install -Dm0644 packaging/systemd/prime-lc-lcd.service "$root/usr/lib/systemd/system/prime-lc-lcd.service"
install -Dm0644 packaging/udev/70-prime-lc-lcd.rules "$root/usr/lib/udev/rules.d/70-prime-lc-lcd.rules"
install -Dm0644 packaging/default/prime-lc-lcd "$root/etc/default/prime-lc-lcd"
install -Dm0644 README.md "$root/usr/share/doc/prime-lc-lcd/README.md"
install -Dm0644 docs/protocol.md "$root/usr/share/doc/prime-lc-lcd/protocol.md"
install -Dm0644 LICENSE "$root/usr/share/doc/prime-lc-lcd/copyright"

install -d "$root/DEBIAN"
install -m0755 packaging/debian/postinst packaging/debian/prerm packaging/debian/postrm "$root/DEBIAN/"
echo /etc/default/prime-lc-lcd > "$root/DEBIAN/conffiles"
size=$(du -sk --exclude=DEBIAN "$root" | cut -f1)
sed -e "s/@VERSION@/$version/" -e "s/@SIZE@/$size/" packaging/debian/control > "$root/DEBIAN/control"

mkdir -p dist
dpkg-deb --root-owner-group -Zxz --build "$root" "dist/$pkg.deb" >/dev/null
echo "dist/$pkg.deb"
