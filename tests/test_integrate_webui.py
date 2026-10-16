import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = REPO / 'scripts/integrate-webui.py'

class WebMenuIntegrationTests(unittest.TestCase):
    def test_new_web_first_inside_modem_without_legacy_package(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            package = root / 'package/luci-app-at-webserver'
            menu = package / 'root/usr/share/luci/menu.d/luci-app-at-webserver.json'
            menu.parent.mkdir(parents=True)
            menu.write_text('{"admin/services/at-webserver": {"title": "AT WebServer"}}')
            views = package / 'htdocs/luci-static/resources/view/at-webserver'
            views.mkdir(parents=True)
            for name in ['config','logs','debug']:
                (views / (name+'.js')).write_text(f"return {{ source: '{name}' }};")
            html = root / 'package/at-webserver/files/www/5700/index.html'
            html.parent.mkdir(parents=True)
            html.write_text('<script src="/scripts/loading.js"></script>')
            result=subprocess.run([sys.executable,str(SCRIPT),str(root)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            added=json.loads(menu.read_text())
            entry=added['admin/modem/mt5700m']
            self.assertEqual(entry['title'],'模组界面')
            self.assertLess(entry['order'],10)  # pinned QModem sibling order
            self.assertNotIn('admin/modem',added)  # do not move/rename parent group
            self.assertNotIn('admin/services/at-webserver',added)
            self.assertEqual(added['admin/modem/mt5700m/status']['action']['path'],'at-webserver-h5000m-v3/web')
            self.assertEqual((views.parent/'at-webserver-h5000m-v3/logs.js').read_text(),"return { source: 'logs' };")
            self.assertIn('/5700/scripts/loading.js',html.read_text())
            self.assertFalse(views.exists())
