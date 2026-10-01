#!/usr/bin/env python3
"""Sign Debian source uploads without devscripts (works on macOS).

For each .changes file: clear-sign the .dsc and .buildinfo it lists, refresh
their sizes and checksums in the .changes, then clear-sign the .changes. This
is what debsign does.

    scripts/sign-changes.py [--key KEYID] dist/source/*_source.changes
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess

# Public OpenPGP fingerprint of the maintainer's signing key (not a secret).
MAINTAINER_FPR = "C11708432D7816D5DF0F68EADB6DE8C654E10EA0"


def clearsign(path: str, key: str) -> None:
    with open(path, "rb") as f:
        data = f.read()
    if data.startswith(b"-----BEGIN PGP SIGNED MESSAGE-----"):
        raise SystemExit(f"{path} is already signed")
    gpg = shutil.which("gpg")  # Homebrew and distro locations differ
    if gpg is None:
        raise SystemExit("gpg not found in PATH")
    signed = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [
            gpg,
            "--batch",
            "--yes",
            "--clearsign",
            "--local-user",
            key,
            "--digest-algo",
            "SHA512",
        ],
        input=data,
        capture_output=True,
        check=True,
    ).stdout
    with open(path, "wb") as f:
        f.write(signed)


def checksums(path: str) -> dict[str, str]:
    with open(path, "rb") as f:
        data = f.read()
    return {
        "size": str(len(data)),
        "md5": hashlib.md5(data).hexdigest(),  # noqa: S324 - required by the .changes format
        "sha1": hashlib.sha1(data).hexdigest(),  # noqa: S324 - required by the .changes format
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def sign(changes: str, key: str) -> None:
    base = os.path.dirname(os.path.abspath(changes))
    with open(changes) as f:
        text = f.read()
    for name in re.findall(r"^ [0-9a-f]{32} \d+ \S+ \S+ (\S+)$", text, re.M):
        if not name.endswith((".dsc", ".buildinfo")):
            continue
        clearsign(os.path.join(base, name), key)
        s = checksums(os.path.join(base, name))
        n = re.escape(name)
        text = re.sub(rf"^ [0-9a-f]{{32}} \d+ (\S+ \S+) {n}$", rf" {s['md5']} {s['size']} \1 {name}", text, flags=re.M)
        text = re.sub(rf"^ [0-9a-f]{{40}} \d+ {n}$", f" {s['sha1']} {s['size']} {name}", text, flags=re.M)
        text = re.sub(rf"^ [0-9a-f]{{64}} \d+ {n}$", f" {s['sha256']} {s['size']} {name}", text, flags=re.M)
        print("signed", name)
    with open(changes, "w") as f:
        f.write(text)
    clearsign(changes, key)
    print("signed", os.path.basename(changes))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--key", default=os.environ.get("DEBSIGN_KEYID", MAINTAINER_FPR))
    ap.add_argument("changes", nargs="+")
    args = ap.parse_args()
    for c in args.changes:
        sign(c, args.key)


if __name__ == "__main__":
    main()
