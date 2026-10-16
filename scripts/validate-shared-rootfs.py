#!/usr/bin/env python3
"""Inspect the actual built rootfs, not just package selection symbols."""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tarfile
import tempfile

check_tools = sys.argv[1:] == ['--check-tools']
if not check_tools and len(sys.argv) != 3:
    raise SystemExit('Usage: validate-shared-rootfs.py WRT OUTPUT | --check-tools')
wrt = pathlib.Path('.') if check_tools else pathlib.Path(sys.argv[1])
# The pinned ImmortalWrt source installs this tool with a "4" suffix.
host_tool = wrt / 'staging_dir/host/bin/unsquashfs4'
unsquashfs = str(host_tool.resolve()) if host_tool.is_file() and os.access(host_tool, os.X_OK) else shutil.which('unsquashfs')
if not unsquashfs:
    raise SystemExit('Missing SquashFS extractor: install squashfs-tools before building')
print(f'Rootfs extractor: {unsquashfs}', flush=True)
if check_tools:
    version = subprocess.run([unsquashfs, '-version'], capture_output=True, text=True)
    report = version.stdout + version.stderr
    # Ubuntu 24.04's unsquashfs 4.6.1 returns 1 for a successful version query.
    if version.returncode not in (0, 1) or not report.startswith('unsquashfs version '):
        raise SystemExit(f'SquashFS extractor cannot run: {report}')
    print(report, end='')
    raise SystemExit(0)
output = pathlib.Path(sys.argv[2])
manifest = (output/'BUILT-PACKAGES.manifest').read_text()
installed = {line.split(' - ')[0] for line in manifest.splitlines()}
for old in ('luci-app-mt5700m','mt5700m-transport','sms-tool_q'):
    assert old not in installed, f'Legacy component is still installed: {old}'
assert not any(x.startswith('luci-i18n-mt5700m-') for x in installed)
for required in ('qmodem','ubus-at-daemon','tom_modem','at-webserver','luci-app-at-webserver','python3'):
    assert required in installed, f'Missing shared AT runtime: {required}'
image=next(output.glob('*full.bin'))
with tempfile.TemporaryDirectory() as directory:
    directory=pathlib.Path(directory)
    with tarfile.open(image) as archive:
        member=next(x for x in archive.getmembers() if pathlib.PurePosixPath(x.name).name=='root')
        with archive.extractfile(member) as source:
            (directory/'root.squashfs').write_bytes(source.read())
    root=directory/'root'
    subprocess.run([unsquashfs,'-no-progress','-d',str(root),str(directory/'root.squashfs')],check=True,stdout=subprocess.DEVNULL)
    for name in ('usr/bin/ubus-at-daemon','usr/bin/tom_modem','usr/bin/at-server.py','usr/libexec/at-webserver-auth','usr/libexec/qmodem-shared-sms','usr/lib/at-webserver/shared_at.py','usr/lib/at-webserver/shared_sms.py','usr/lib/at-webserver/qmodem_control.py','www/5700/index.html','etc/uci-defaults/98-h5000m-shared-at'):
        assert (root/name).is_file(), f'Missing rootfs file {name}'
    for name in ('usr/sbin/mt5700m-transport','etc/init.d/mt5700m-manager','etc/init.d/mt5700m-traffic','usr/libexec/rpcd/mt5700m'):
        assert not (root/name).exists(), f'Old service survives in rootfs: {name}'
    auth=(root/'usr/libexec/at-webserver-auth').read_text()
    assert 'secrets.token_hex(32)' in auth and 'od -' not in auth
    assert list((root/'usr/lib').glob('python*/secrets.py*')), 'Missing secrets runtime'
    menu=json.loads((root/'usr/share/luci/menu.d/luci-app-at-webserver.json').read_text())
    assert menu['admin/modem/mt5700m']['title']=='模组界面'
    assert menu['admin/modem/mt5700m']['order']<10
    assert (root/'etc/rc.d/S70ubus-at-daemon').is_symlink()
    assert (root/'etc/rc.d/S99at-webserver').is_symlink()
    assert 'serial.Serial(' not in (root/'usr/bin/at-server.py').read_text()
    for page in (root/'www/5700').rglob('*.html'):
        assert 'src="/scripts/loading.js"' not in page.read_text()
(output/'SHARED-AT-VALIDATION.txt').write_text('PASS: actual rootfs contains shared AT service, new Web, device key runtime, startup links and replacement menu; old MT5700M components absent.\nHardware acceptance remains required.\n')
print('Actual rootfs shared AT acceptance passed')
