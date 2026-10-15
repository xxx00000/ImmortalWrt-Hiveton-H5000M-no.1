#!/usr/bin/env python3
import hashlib
import pathlib
import subprocess
import sys
import tarfile

root = pathlib.Path(sys.argv[1])
output = pathlib.Path(sys.argv[2])
images = list(root.glob("bin/targets/mediatek/filogic/*hiveton_h5000m*squashfs-sysupgrade.bin"))
if len(images) != 1:
    raise SystemExit(f"expected exactly one H5000M squashfs-sysupgrade.bin, found {len(images)}")

image = images[0]
with tarfile.open(image, "r:*") as archive:
    names = {pathlib.PurePosixPath(member.name).name for member in archive.getmembers()}
    missing = {"CONTROL", "kernel", "root"} - names
    if missing:
        raise SystemExit(f"not a complete H5000M sysupgrade container; missing: {sorted(missing)}")

fwtool = root / "staging_dir/host/bin/fwtool"
if not fwtool.is_file():
    raise SystemExit(f"cannot validate device metadata; fwtool is missing at {fwtool}")

output.mkdir(parents=True, exist_ok=True)
metadata = output / "IMAGE-METADATA.json"
subprocess.run([str(fwtool), "-q", "-i", str(metadata), str(image)], check=True)
metadata_text = metadata.read_text(encoding="utf-8")
if "hiveton,h5000m" not in metadata_text:
    raise SystemExit("firmware metadata does not list hiveton,h5000m as a supported device")

destination = output / "immortalwrt-25.12.2-hiveton_h5000m-AU-full.bin"
destination.write_bytes(image.read_bytes())
digest = hashlib.sha256(destination.read_bytes()).hexdigest()
(output / "SHA256SUMS").write_text(f"{digest}  {destination.name}\n", encoding="utf-8")
(output / "IMAGE-INFO.txt").write_text(
    "Device: Hiveton H5000M (mediatek/filogic)\n"
    "Source: ImmortalWrt v25.12.2\n"
    "Image: single full-system .bin containing the complete kernel and root filesystem; container layout matches the uploaded reference image\n"
    "Bootloader: U-Boot acceptance was confirmed for the reference image; verify this file's size against the device upload limit before flashing\n"
    f"Size: {destination.stat().st_size} bytes\n"
    f"SHA256: {digest}\n"
    "Wi-Fi: country AU; 2.4GHz A5KM EHT40; 5GHz A5KM+ EHT160; WPA2-PSK; hardware/client validation is still required\n",
    encoding="utf-8",
)
print(f"Validated {destination.name} ({destination.stat().st_size} bytes, SHA256 {digest})")
