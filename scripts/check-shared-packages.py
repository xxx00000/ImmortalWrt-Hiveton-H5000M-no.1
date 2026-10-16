#!/usr/bin/env python3
"""Integration checks against fetched, patched package trees before firmware build."""
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

repo = pathlib.Path(__file__).resolve().parents[1]
web, qmodem = map(pathlib.Path, sys.argv[1:3])
workflow = (repo/'.github/workflows/h5000m-build.yml').read_text()
required = set(re.findall(r'\bPACKAGE_([\w-]+)', workflow))
forbidden = set(re.search(r'for legacy in (.*); do', workflow)[1].split())
assert not required & forbidden, f'Conflicting package gates: {required & forbidden}'
selection = (repo/'config/h5000m.config').read_text()
for name in forbidden:
    assert f'CONFIG_PACKAGE_{name}=y' not in selection, f'Obsolete package selected: {name}'
assert 'needs: webui-check' in workflow
backend = (web / 'at-webserver/files/usr/bin/at-server.py').read_text()
for prohibited in ('class SerialATConnection', 'class NetworkATConnection', 'serial.Serial(', 'socket.connect('):
    assert prohibited not in backend, prohibited
assert 'SharedATConnection(control=QModemControl())' in backend
assert 'await client.connect()' not in backend  # startup must not wait for a modem
for path in (qmodem / 'application/qmodem/files').rglob('*'):
    if path.is_file():
        content = path.read_text(errors='ignore')
        assert not re.search(r'^\s*[^#\n]*\bsms_tool_q\b', content, re.M), path
main = (qmodem / 'application/tom_modem/src/main.c').read_text()
assert 'TRANSPORT_UBUS' in main
assert '"close", json' not in (qmodem / 'application/modem_scan/src/modem_scand.c').read_text()
with tempfile.TemporaryDirectory() as directory:
    root = pathlib.Path(directory)
    for name in ('at-webserver','luci-app-at-webserver'):
        shutil.copytree(web/name, root/'package'/name)
    subprocess.run([sys.executable,str(repo/'scripts/integrate-webui.py'),str(root)],check=True)
    menu=json.loads((root/'package/luci-app-at-webserver/root/usr/share/luci/menu.d/luci-app-at-webserver.json').read_text())
    assert menu['admin/modem/mt5700m']['title']=='模组界面'
    assert menu['admin/modem/mt5700m']['order'] < 10
    assert 'admin/modem' not in menu
    for view in (root/'package/luci-app-at-webserver/htdocs/luci-static/resources/view').rglob('*.js'):
        assert 'admin/services/at-webserver' not in view.read_text(), view
    assets=root/'package/at-webserver/files/www/5700'
    for page in assets.rglob('*.html'):
        for reference in re.findall(r'(?:src|href)="(/[^"?#]+)',page.read_text()):
            if reference.startswith('/5700/'):
                assert (assets/reference[6:]).exists(), (page,reference)
            assert not reference.startswith('/scripts/'), (page,reference)
print('Pinned Web/QModem package integration and replacement menu checks passed')
