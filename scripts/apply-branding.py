#!/usr/bin/env python3
"""Change display text only; preserve the existing Argon markup and assets."""
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
header = root / "feeds/luci/themes/luci-theme-argon/ucode/template/themes/argon/header.ut"
original = header.read_text(encoding="utf-8")
old = '<a class="brand" href="#">{{ hostname }}</a>'
new = '<a class="brand" href="#">Hiveton H5000M</a>'
if original.count(old) != 2:
    raise SystemExit("Unexpected Argon header: expected exactly two original brand labels")
branded = original.replace(old, new)
assert branded.replace(new, old) == original
# Rootfs overlay wins over package installation without changing theme selection.
target = root / "files/usr/share/ucode/luci/template/themes/argon/header.ut"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(branded, encoding="utf-8")

# Only human-readable descriptions change; release/ABI/repository versions stay intact.
replacements = {
    "package/base-files/files/etc/openwrt_release": {
        "DISTRIB_DESCRIPTION='%D %V %C'": "DISTRIB_DESCRIPTION='%D %V %C by xxxbug'",
    },
    "package/base-files/files/usr/lib/os-release": {
        'PRETTY_NAME="%D %V"': 'PRETTY_NAME="%D %V by xxxbug"',
        'OPENWRT_RELEASE="%D %V %C"': 'OPENWRT_RELEASE="%D %V %C by xxxbug"',
    },
}
for name, pairs in replacements.items():
    path = root / name
    content = path.read_text(encoding="utf-8")
    for before, after in pairs.items():
        if content.count(before) != 1:
            raise SystemExit("Unexpected version template: " + name)
        content = content.replace(before, after)
    path.write_text(content, encoding="utf-8")
print("Brand: Hiveton H5000M; firmware signature: by xxxbug; Argon styles unchanged")
