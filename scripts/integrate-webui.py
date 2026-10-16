#!/usr/bin/env python3
"""Install the replacement Web entry inside the existing Modem group."""
import json
import pathlib
import shutil
import sys

NAMESPACE = 'at-webserver-h5000m-v3'
ROOT = pathlib.Path(__file__).resolve().parents[1]


def integrate(wrt):
    package = wrt / 'package/luci-app-at-webserver'
    prefix = 'admin/modem/mt5700m'
    menu = {prefix: {
        'title': '模组界面', 'order': 0,
        'action': {'type': 'firstchild'},
        'depends': {'acl': ['luci-app-at-webserver']},
    }}
    for name, title, view, order in [
        ('status', '模组界面', 'web', 10),
        ('config', '连接设置', 'config', 20),
        ('logs', '通知日志', 'logs', 30),
        ('debug', 'AT 调试', 'debug', 40),
    ]:
        menu[prefix + '/' + name] = {
            'title': title, 'order': order,
            'action': {'type': 'view', 'path': NAMESPACE + '/' + view},
        }
    menu_path = package / 'root/usr/share/luci/menu.d/luci-app-at-webserver.json'
    menu_path.write_text(json.dumps(menu, ensure_ascii=False, indent=2) + '\n')
    views = package / 'htdocs/luci-static/resources/view'
    destination = views / NAMESPACE
    destination.mkdir(parents=True, exist_ok=True)
    for name in ['config', 'logs', 'debug']:
        source = (views / 'at-webserver' / (name + '.js')).read_text()
        (destination / (name + '.js')).write_text(source.replace('admin/services/at-webserver', prefix))
    shutil.copyfile(ROOT / 'webui/mt5700m.js', destination / 'web.js')
    shutil.rmtree(views / 'at-webserver')
    # The pinned frontend is mounted at /5700/, including its loading asset.
    for page in (wrt / 'package/at-webserver/files/www/5700').rglob('*.html'):
        content = page.read_text()
        page.write_text(content.replace('src="/scripts/loading.js"', 'src="/5700/scripts/loading.js"'))


if __name__ == '__main__':
    integrate(pathlib.Path(sys.argv[1]))
