#!/bin/bash
# Build, sign and upload a released version to the Ubuntu PPA.
#
#   scripts/ppa-release.sh 0.1.2              # all series, PPA revision 1
#   PPA_REV=2 scripts/ppa-release.sh 0.1.2    # re-upload after a packaging fix
#   NO_UPLOAD=1 scripts/ppa-release.sh 0.1.2  # build and sign only
#
# Needs Docker, gpg with the signing key, and the vX.Y.Z tag on GitHub.
# Built files go to dist/ppa/<version>/.
set -euo pipefail

SERIES=("noble:24.04" "resolute:26.04")
PPA_TARGET="~vakaobr/ubuntu/prime-lc-lcd/"

if [ "${1:-}" = --inside ]; then
    # Runs in an ubuntu:<num> container with /out mounted.
    v=$2 series=$3 num=$4 rev=$5 orig_flag=$6
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq >/dev/null
    apt-get install -y -qq --no-install-recommends \
        build-essential debhelper dh-python python3 python3-pytest devscripts >/dev/null 2>&1
    mkdir -p /w && cd /w
    cp "/out/prime-lc-lcd_$v.orig.tar.gz" .
    tar -xzf "prime-lc-lcd_$v.orig.tar.gz"
    cd "prime-lc-lcd-$v"
    export DEBFULLNAME="Anderson Leite" DEBEMAIL="andersonleite@outlook.com"
    dch -b -v "$v-1~ppa$rev~ubuntu$num.1" -D "$series" "PPA build for Ubuntu $num ($series)." 2>/dev/null
    dpkg-buildpackage -S "$orig_flag" -us -uc -d >/tmp/src.log 2>&1 || { tail -30 /tmp/src.log; exit 1; }
    cp ../prime-lc-lcd_"$v"-1~ppa"$rev"~ubuntu"$num".1* /out/
    exit 0
fi

if [ "${1:-}" = --upload ]; then
    # Runs in an ubuntu container with /out mounted read-only.
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq >/dev/null
    apt-get install -y -qq --no-install-recommends dput ca-certificates >/dev/null 2>&1
    printf '[ppa]\nfqdn = ppa.launchpad.net\nmethod = ftp\nincoming = %s\nlogin = anonymous\nallow_unsigned_uploads = 0\n' \
        "$PPA_TARGET" >/root/.dput.cf
    shift
    for c in "$@"; do
        dput -u ppa "/out/$c" 2>&1 | grep -v "Could not write" || true
    done
    exit 0
fi

v=${1:?usage: scripts/ppa-release.sh VERSION}
rev=${PPA_REV:-1}
repo=$(cd "$(dirname "$0")/.." && pwd)
out="$repo/dist/ppa/$v"
mkdir -p "$out"

orig="$out/prime-lc-lcd_$v.orig.tar.gz"
if [ ! -f "$orig" ]; then
    curl -fsSL -o "$orig" "https://github.com/vakaobr/prime-lc-lcd/archive/refs/tags/v$v.tar.gz"
fi

changes=()
flag=-sa # the orig tarball goes up with the first upload only
[ "$rev" != 1 ] && flag=-sd
for s in "${SERIES[@]}"; do
    series=${s%%:*} num=${s##*:}
    echo "== building $v-1~ppa$rev~ubuntu$num.1 for $series"
    docker run --rm -v "$out":/out -v "$repo/scripts/ppa-release.sh":/ppa-release.sh:ro "ubuntu:$num" \
        bash /ppa-release.sh --inside "$v" "$series" "$num" "$rev" "$flag"
    changes+=("prime-lc-lcd_$v-1~ppa$rev~ubuntu$num.1_source.changes")
    flag=-sd
done

(cd "$out" && python3 "$repo/scripts/sign-changes.py" "${changes[@]}")

if [ -n "${NO_UPLOAD:-}" ]; then
    echo "signed uploads in $out (not uploaded)"
    exit 0
fi
docker run --rm -v "$out":/out:ro -v "$repo/scripts/ppa-release.sh":/ppa-release.sh:ro ubuntu:24.04 \
    bash /ppa-release.sh --upload "${changes[@]}"
echo "uploaded; follow the builds at https://launchpad.net/~vakaobr/+archive/ubuntu/prime-lc-lcd/+packages"
