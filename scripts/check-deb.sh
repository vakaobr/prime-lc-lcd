#!/bin/bash
# Build, lint and install-test the Debian package inside a throwaway container.
#
#   scripts/check-deb.sh [image] [outdir]      e.g. scripts/check-deb.sh ubuntu:24.04 dist
#
# The repository is mounted read-only; built files are copied to outdir if given.
set -euo pipefail

if [ "${1:-}" != --inside ]; then
    image=${1:-debian:unstable}
    out=${2:-}
    repo=$(cd "$(dirname "$0")/.." && pwd)
    args=(--rm -v "$repo":/src:ro -e CHECK_DEB_OUT="${out:+/out}")
    if [ -n "$out" ]; then
        mkdir -p "$out"
        args+=(-v "$(cd "$out" && pwd)":/out)
    fi
    exec docker run "${args[@]}" "$image" bash /src/scripts/check-deb.sh --inside
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq >/dev/null
apt-get install -y -qq --no-install-recommends \
    build-essential debhelper dh-python python3 python3-pytest lintian git ca-certificates >/dev/null 2>&1

version=$(sed -n '1s/.*(\(.*\)-[^-]*).*/\1/p' /src/debian/changelog)
tree=/build/prime-lc-lcd-$version
mkdir -p "$tree"
git config --global --add safe.directory /src
git -C /src ls-files -co --exclude-standard | grep -v '^debian/' | tar -C /src -cf - -T - | tar -xf - -C "$tree"
tar -C /build -czf "/build/prime-lc-lcd_$version.orig.tar.gz" "prime-lc-lcd-$version"
cp -R /src/debian "$tree/"

echo "== build ($(. /etc/os-release && echo "$PRETTY_NAME"))"
(cd "$tree" && dpkg-buildpackage -us -uc) >/tmp/build.log 2>&1 || { tail -40 /tmp/build.log; exit 1; }
grep -E "^[0-9]+ passed" /tmp/build.log

echo "== lintian"
# Ubuntu's lintian rejects the Debian distribution name; that is expected.
lintian --display-info --tag-display-limit 0 --suppress-tags bad-distribution-in-changes-file /build/*.changes || true

deb=$(ls /build/*.deb)
echo "== install"
apt-get install -y -qq "$deb" >/dev/null 2>&1
getent passwd prime-lc-lcd >/dev/null
test -f /etc/default/prime-lc-lcd
test -f /usr/lib/systemd/system/prime-lc-lcd.service
test -f /usr/lib/udev/rules.d/70-prime-lc-lcd.rules
prime-lc-lcd --version
prime-lc-lcd --readings --gpu none
rc=0
prime-lc-lcd --list || rc=$?
test "$rc" -le 1

echo "== purge"
apt-get purge -y -qq prime-lc-lcd >/dev/null 2>&1
test ! -e /etc/default/prime-lc-lcd
for f in /usr/bin/prime-lc-lcd /usr/share/prime-lc-lcd /usr/lib/systemd/system/prime-lc-lcd.service; do
    if [ -e "$f" ]; then
        echo "purge left $f behind"
        exit 1
    fi
done

if [ -n "${CHECK_DEB_OUT:-}" ]; then
    cp /build/*.deb "$CHECK_DEB_OUT/"
fi
echo "== ok"
