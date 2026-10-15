"""Inspect the shipped SquashFS, not only the generic build manifest."""
import io
import hashlib
import json
import pathlib
import re
import sys
import tarfile


def installed_packages(data):
    packages = {}
    for block in data.decode().split('\n\n'):
        fields = dict(re.findall(r'^([PV]):(.*)$', block, re.M))
        if 'P' in fields:
            packages[fields['P']] = fields.get('V', '')
    return packages


def require_aarch64(data, name):
    if len(data) < 20 or data[:6] != b'\x7fELF\x02\x01' or int.from_bytes(data[18:20], 'little') != 183:
        raise ValueError(f'{name}: expected aarch64 ELF64 little-endian backend')


def validate_argon_assets(files, baseline):
    mismatches = [name for name, digest in baseline.items()
                  if name not in files or hashlib.sha256(files[name]).hexdigest() != digest]
    if mismatches:
        raise ValueError('Original Argon assets differ: ' + ', '.join(mismatches))


def main(root, output):
    from dissect.squashfs import SquashFS
    from passlib.hash import sha512_crypt
    image = next(output.glob('*.bin'))
    with tarfile.open(image) as archive:
        data = next(archive.extractfile(m).read() for m in archive.getmembers() if m.name.endswith('/root'))
    fs = SquashFS(io.BytesIO(data))
    paths, files = set(), {}
    def walk(node, prefix=''):
        for entry in node.iterdir():
            name = prefix + entry.name
            paths.add(name)
            if entry.is_dir():
                walk(entry, name + '/')
            elif entry.is_file() and (name.startswith(('etc/uci-defaults/', 'usr/libexec/h5000m', 'usr/share/luci/menu.d/', 'www/luci-static/argon/', 'usr/share/ucode/luci/template/themes/argon/')) or name in (
                'lib/apk/db/installed', 'usr/bin/at-webserver-rust', 'usr/sbin/fm350d', 'etc/shadow',
                'etc/config/argon',
                'usr/share/ucode/luci/template/themes/argon/header.ut')):
                files[name] = entry.open().read()
    walk(fs.root)
    packages = installed_packages(files['lib/apk/db/installed'])
    required = {'qmodem', 'luci-app-mt5700', 'luci-app-qmodem-generic', 'luci-app-fm350',
                'luci-app-store', 'luci-app-quickstart', 'quickstart', 'docker', 'dockerd',
                'luci-app-dockerman', 'kmod-mt7996e', 'kmod-mt7992-23-firmware', 'wireless-regdb'}
    missing = required - packages.keys()
    forbidden = {'nlbwmon', 'luci-app-nlbwmon', 'luci-app-mt5700m', 'luci-app-qmodem', 'luci-app-qmodem-next', 'luci-app-qmodem-ttl'} & packages.keys()
    if missing or forbidden:
        raise ValueError(f'Actual image package mismatch: missing={sorted(missing)}, forbidden={sorted(forbidden)}')
    require_aarch64(files['usr/bin/at-webserver-rust'], 'at-webserver-rust')
    require_aarch64(files['usr/sbin/fm350d'], 'fm350d')
    for name in ('etc/rc.d/S99h5000m-defaults', 'etc/rc.d/S77h5000m-modem'):
        if name not in paths:
            raise ValueError(f'Missing boot service link: {name}')
    if not any(p.endswith('/mt7996e.ko') for p in paths):
        raise ValueError('Actual wireless driver missing')
    if not any('mt7992_wm' in p for p in paths):
        raise ValueError('Actual MT7992 firmware missing')
    helper = files['usr/libexec/h5000m-firstboot'].decode()
    for value in ("ssid='A5kM'", "ssid='A5kM+'", "htmode='EHT20'", "htmode='EHT160'", 'country=AU', 'key=password', 'encryption=psk2'):
        if value not in helper:
            raise ValueError(f'Firstboot setting absent: {value}')
    password_ok = sha512_crypt.verify('password', files['etc/shadow'].decode().splitlines()[0].split(':')[1])
    if not password_ok:
        raise ValueError('Root password does not match requested default')
    header = files.get('usr/share/ucode/luci/template/themes/argon/header.ut', b'')
    if b'Hiveton H5000M' not in header:
        raise ValueError('Requested sidebar brand absent')
    baseline = json.loads((pathlib.Path(__file__).resolve().parents[1]/'baseline/argon-original-assets.json').read_text(encoding='utf-8'))
    validate_argon_assets(files, baseline['sha256'])
    menu = json.loads(files['usr/share/luci/menu.d/zz-h5000m-overview.json'])
    if menu['admin/status/overview']['action'] != {'type':'template', 'path':'quickstart/home'}:
        raise ValueError('QuickStart overview route absent')
    (output/'ACTUAL-PACKAGES.tsv').write_text('Package\tVersion\n' + '\n'.join(f'{p}\t{v}' for p,v in sorted(packages.items())), encoding='utf-8')
    (output/'STATIC-ACCEPTANCE.json').write_text(json.dumps({
        'status':'passed', 'actual_package_count':len(packages), 'rust_backends':'aarch64',
        'root_password_verified':password_ok, 'brand':'Hiveton H5000M',
        'argon_theme':'original 2.4.7; original assets verified by SHA256',
        'wifi':['AU EHT20 A5kM', 'AU EHT160 A5kM+'],
        'modem_managers':'A1/B1/C1; exclusive ownership; MT5700 default',
        'runtime_hardware_test':'required', 'uboot_acceptance':'not tested by CI'}, indent=2), encoding='utf-8')
    print(f'Actual SquashFS acceptance passed: {len(packages)} packages, A1/B1/C1, iStore, Docker, BE defaults')


if __name__ == '__main__':
    main(pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]))
