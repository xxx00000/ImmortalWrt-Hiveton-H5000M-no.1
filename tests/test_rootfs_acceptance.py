import importlib.util
import pathlib
import unittest
import hashlib

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / 'scripts/validate-rootfs.py'

class RootfsAcceptanceTests(unittest.TestCase):
    def load(self):
        spec = importlib.util.spec_from_file_location('validate_rootfs', SCRIPT)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    def test_rejects_host_binary_in_rust_backend(self):
        m = self.load()
        blob = bytearray(64)
        blob[:6] = b'\x7fELF\x02\x01'
        blob[18:20] = (62).to_bytes(2, 'little')
        with self.assertRaisesRegex(ValueError, 'aarch64'):
            m.require_aarch64(bytes(blob), 'fm350d')

    def test_accepts_target_aarch64_backend(self):
        m = self.load()
        blob = bytearray(64)
        blob[:6] = b'\x7fELF\x02\x01'
        blob[18:20] = (183).to_bytes(2, 'little')
        m.require_aarch64(bytes(blob), 'at-webserver-rust')

    def test_reads_actual_apk_database_not_generic_build_manifest(self):
        m = self.load()
        db = b'P:qmodem\nV:3.3.0-r1\n\nP:kmod-mt7996e\nV:6.12-r1\n\n'
        self.assertEqual(m.installed_packages(db), {'qmodem':'3.3.0-r1', 'kmod-mt7996e':'6.12-r1'})

    def test_original_theme_gate_rejects_a_different_font_stylesheet(self):
        baseline = {'www/luci-static/argon/css/cascade.css': hashlib.sha256(b'original font').hexdigest()}
        with self.assertRaisesRegex(ValueError, 'Original Argon'):
            self.load().validate_argon_assets({'www/luci-static/argon/css/cascade.css': b'changed font'}, baseline)

    def test_original_theme_gate_accepts_identical_assets(self):
        files = {'www/luci-static/argon/css/cascade.css': b'original font'}
        baseline = {p: hashlib.sha256(data).hexdigest() for p, data in files.items()}
        self.load().validate_argon_assets(files, baseline)

if __name__ == '__main__':
    unittest.main()
