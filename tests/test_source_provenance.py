import importlib.util
import pathlib
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / 'scripts/validate-sources.py'


class SourceProvenanceTests(unittest.TestCase):
    def load(self):
        spec = importlib.util.spec_from_file_location('validate_sources', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_rejects_feed_shadowing_customized_package(self):
        metadata = ('Source-Makefile: package/feeds/luci/luci-theme-argon/Makefile\n'
                    '\nPackage: luci-theme-argon\nVersion: 1\n')
        with self.assertRaisesRegex(ValueError, 'luci-theme-argon'):
            self.load().validate_sources(metadata, ['luci-theme-argon'])

    def test_accepts_custom_source_and_checks_each_subpackage(self):
        metadata = ('Source-Makefile: package/luci-theme-argon/Makefile\n'
                    '\nPackage: luci-theme-argon\nVersion: 1\n'
                    '\nPackage: luci-i18n-argon-zh-cn\nVersion: 1\n')
        self.load().validate_sources(metadata, ['luci-theme-argon'])

    def test_rejects_missing_selected_custom_source(self):
        with self.assertRaisesRegex(ValueError, 'luci-app-openclash'):
            self.load().validate_sources('', ['luci-app-openclash'])


if __name__ == '__main__':
    unittest.main()
