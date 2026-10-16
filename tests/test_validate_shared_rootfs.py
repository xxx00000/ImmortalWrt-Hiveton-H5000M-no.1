import json
import os
import pathlib
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest


SCRIPT = pathlib.Path(__file__).resolve().parents[1] / 'scripts/validate-shared-rootfs.py'


class SharedRootfsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = pathlib.Path(self.temp.name)
        self.wrt = self.base / 'wrt'
        self.output = self.base / 'output'
        self.output.mkdir()
        self.root = self.base / 'fixture'
        files = {
            'usr/bin/ubus-at-daemon': '', 'usr/bin/tom_modem': '',
            'usr/bin/at-server.py': '# shared AT transport',
            'usr/libexec/at-webserver-auth': 'secrets.token_hex(32)',
            'usr/libexec/qmodem-shared-sms': '',
            'usr/lib/at-webserver/shared_at.py': '',
            'usr/lib/at-webserver/shared_sms.py': '',
            'usr/lib/at-webserver/qmodem_control.py': '',
            'usr/lib/python3.12/secrets.py': '', 'www/5700/index.html': '',
            'etc/uci-defaults/98-h5000m-shared-at': '',
            'usr/share/luci/menu.d/luci-app-at-webserver.json': json.dumps({
                'admin/modem/mt5700m': {'title': '模组界面', 'order': 0}}),
        }
        for name, content in files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        (self.root / 'etc/rc.d').mkdir()
        for name in ('S70ubus-at-daemon', 'S99at-webserver'):
            (self.root / 'etc/rc.d' / name).symlink_to('../init.d/' + name[3:])
        self.manifest = self.output / 'BUILT-PACKAGES.manifest'
        self.manifest.write_text(''.join(p + ' - 1\n' for p in (
            'qmodem', 'ubus-at-daemon', 'tom_modem', 'at-webserver',
            'luci-app-at-webserver', 'python3')))
        self.squashfs = self.base / 'root.squashfs'
        self.squashfs.write_bytes(b'fixture')
        self.pack()
        self.tools = self.base / 'tools'
        self.tools.mkdir()
        # Model the external extractor only; run all real rootfs assertions.
        self.extractor = self.tools / 'unsquashfs'
        self.extractor.write_text(
            '#!' + sys.executable + '\nimport os, shutil, sys\n'
            'shutil.copytree(os.environ["ROOTFS_FIXTURE"], '
            'sys.argv[sys.argv.index("-d") + 1], symlinks=True)\n')
        self.extractor.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.tools), ROOTFS_FIXTURE=str(self.root))

    def pack(self):
        with tarfile.open(self.output / 'test-full.bin', 'w') as archive:
            archive.add(self.squashfs, arcname='sysupgrade-hiveton,h5000m/root')

    def validate(self, env=None):
        return subprocess.run([sys.executable, str(SCRIPT), str(self.wrt), str(self.output)],
                              env=env or self.env, capture_output=True, text=True)

    def test_system_extractor_works_without_old_hardcoded_host_path(self):
        result = self.validate()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.output / 'SHARED-AT-VALIDATION.txt').is_file())

    def test_pinned_host_extractor_uses_unsquashfs4_name(self):
        host = self.wrt / 'staging_dir/host/bin/unsquashfs4'
        host.parent.mkdir(parents=True)
        self.extractor.rename(host)
        result = self.validate()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_tool_fails_during_preflight(self):
        self.extractor.unlink()
        result = subprocess.run([sys.executable, str(SCRIPT), '--check-tools'],
                                cwd=self.base, env=self.env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('squashfs-tools', result.stderr)
        self.assertFalse((self.output / 'SHARED-AT-VALIDATION.txt').exists())

    def test_missing_runtime_still_blocks_acceptance(self):
        (self.root / 'usr/lib/at-webserver/shared_at.py').unlink()
        result = self.validate()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Missing rootfs file', result.stderr)
        self.assertFalse((self.output / 'SHARED-AT-VALIDATION.txt').exists())

    @unittest.skipUnless(shutil.which('mksquashfs') and shutil.which('unsquashfs'),
                         'real squashfs-tools roundtrip runs in Linux CI')
    def test_real_xz_image_extraction_and_runtime_acceptance(self):
        self.squashfs.unlink()
        subprocess.run(['mksquashfs', str(self.root), str(self.squashfs),
                        '-noappend', '-comp', 'xz', '-no-xattrs', '-processors', '1'],
                       check=True, stdout=subprocess.DEVNULL)
        self.pack()
        result = self.validate(os.environ.copy())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.output / 'SHARED-AT-VALIDATION.txt').is_file())


if __name__ == '__main__':
    unittest.main()
