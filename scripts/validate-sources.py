"""Reject feed packages that shadow the pinned and customized sources."""
import json
import pathlib
import re
import sys

CUSTOM_PACKAGES = (
    'luci-app-mt5700', 'luci-app-fm350', 'luci-app-qmodem-generic',
    'luci-app-h5000m-fancontrol', 'luci-app-h5000m-netmode',
    'luci-app-diskman', 'luci-theme-argon', 'luci-app-argon-config',
    'luci-app-openclash', 'luci-app-quickstart', 'quickstart',
)


def validate_sources(metadata, packages=CUSTOM_PACKAGES):
    origins = {}
    for block in metadata.split('Source-Makefile: ')[1:]:
        source = block.splitlines()[0].strip()
        for name in re.findall(r'^Package: (.+)$', block, re.M):
            origins.setdefault(name.strip(), set()).add(source)
    result = {}
    for name in packages:
        expected = 'package/' + name + '/Makefile'
        actual = origins.get(name, set())
        if actual != {expected}:
            raise ValueError(f'{name}: expected only {expected}, got {sorted(actual)}')
        result[name] = expected
    return result


if __name__ == '__main__':
    result = validate_sources(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'))
    pathlib.Path(sys.argv[2]).write_text(json.dumps(result, indent=2), encoding='utf-8')
    print('Pinned source provenance verified for ' + ', '.join(result))
