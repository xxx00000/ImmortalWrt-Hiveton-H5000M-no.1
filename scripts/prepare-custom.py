"""Apply the reviewed, H5000M-specific integration to pinned upstream sources."""
import pathlib
import re
import sys


def guard_service(path, owner):
    text = path.read_text(encoding='utf-8')
    if '# H5000M modem ownership' in text:
        return
    guard = ('\n\t# H5000M modem ownership\n'
             '\t[ "$(/usr/libexec/h5000m-modem-owner)" != ' + owner + ' ] && return 0\n'
             '\t/usr/libexec/h5000m-modem-prepare ' + owner + '\n')
    text, count = re.subn(r'(\nstart_service\(\)\s*\{)', lambda m: m[0] + guard, text, count=1)
    if count != 1:
        raise ValueError(f'Unknown upstream service entrypoint: {path}')
    path.write_text(text, encoding='utf-8')


def brand_header(text):
    result, count = re.subn(r'(<a\b[^>]*\bclass="brand"[^>]*>\s*)\{\{\s*hostname\s*\}\}(\s*</a>)',
                           lambda match: match[1] + 'Hiveton H5000M' + match[2], text)
    if not count:
        raise ValueError('Argon brand anchors not found')
    return result


def guard_hook(path, owner):
    text = path.read_text(encoding='utf-8')
    marker = '# H5000M modem hook ownership'
    if marker not in text:
        if not text.startswith('#!/bin/sh\n'):
            raise ValueError(f'Unknown hotplug script format: {path}')
        lines = text.split('\n', 1)
        text = lines[0] + '\n' + marker + '\n[ "$(/usr/libexec/h5000m-modem-owner)" = ' + owner + ' ] || exit 0\n' + lines[1]
        path.write_text(text, encoding='utf-8')


def main(root):
    package = root / 'package'
    header = package/'luci-theme-argon/ucode/template/themes/argon/header.ut'
    header.write_text(brand_header(header.read_text(encoding='utf-8')), encoding='utf-8')
    guard_service(package/'luci-app-mt5700/root/etc/init.d/at-webserver', 'mt5700')
    guard_service(package/'luci-app-fm350/root/etc/init.d/fm350d', 'fm350')
    guard_service(package/'luci-app-qmodem-generic/root/etc/init.d/qmodem-worker', 'quectel')
    for name in ('qmodem_init', 'qmodem_network'):
        guard_service(root/'feeds/qmodem/application/qmodem/files/etc/init.d'/name, 'quectel')
    for family, name in (('usb', '20-modem-usb'), ('net', '20-modem-net')):
        guard_hook(root/'feeds/qmodem/application/qmodem/files/etc/hotplug.d'/family/name, 'quectel')
    for family in ('usb', 'iface'):
        guard_hook(package/'luci-app-mt5700/root/etc/hotplug.d'/family/'99-at-webserver', 'mt5700')
    guard_hook(package/'luci-app-fm350/root/etc/uci-defaults/99-fm350-network', 'fm350')

    # A1 owns the currently installed MT5700. FM350 has an explicit enable switch.
    config = package/'luci-app-fm350/root/etc/config/fm350'
    text = config.read_text(encoding='utf-8')
    if "option enabled '1'" not in text:
        raise ValueError('Unknown upstream FM350 default')
    config.write_text(text.replace("option enabled '1'", "option enabled '0'", 1), encoding='utf-8')

    # Never let the generic UI's optional MT5700 helper modify A1's modem.
    fix = package/'luci-app-qmodem-generic/root/etc/init.d/qmodem-mt5700-fix'
    text = fix.read_text(encoding='utf-8')
    text, count = re.subn(r'(\nstart(?:_service)?\(\)\s*\{)',
                          r'\1\n\treturn 0 # A1 owns MT5700 in this firmware\n', text, count=1)
    if count != 1:
        raise ValueError('Unknown generic MT5700 fix service')
    fix.write_text(text, encoding='utf-8')

    # Both Rust crates carry Cargo.lock. Fail rather than silently refreshing it.
    for path in (package/'luci-app-mt5700/src/Makefile', package/'luci-app-fm350/Makefile'):
        text = path.read_text(encoding='utf-8')
        if 'cargo build ' in text:
            text = text.replace('cargo build ', 'cargo build --locked ')
        elif '$(CARGO) build ' in text:
            text = text.replace('$(CARGO) build ', '$(CARGO) build --locked ')
        else:
            raise ValueError(f'Unknown Rust build recipe: {path}')
        if path.name == 'Makefile' and path.parent.name == 'src':
            text = 'RUST_TRIPLE := aarch64-unknown-linux-musl\n' + text
        path.write_text(text, encoding='utf-8')


if __name__ == '__main__':
    main(pathlib.Path(sys.argv[1]))
