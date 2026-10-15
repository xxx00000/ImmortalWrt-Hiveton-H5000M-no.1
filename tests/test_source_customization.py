import importlib.util
import pathlib
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / 'scripts/prepare-custom.py'

class SourceCustomizationTests(unittest.TestCase):
    def load(self):
        spec = importlib.util.spec_from_file_location('prepare_custom', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_guard_handles_upstream_function_spacing_and_is_idempotent(self):
        m = self.load()
        with tempfile.TemporaryDirectory() as directory:
            p = pathlib.Path(directory) / 'init'
            p.write_text('#!/bin/sh\nstart_service(){\n echo start\n}\n')
            m.guard_service(p, 'quectel')
            once = p.read_text()
            m.guard_service(p, 'quectel')
            self.assertEqual(once, p.read_text())
            self.assertIn('h5000m-modem-owner', once)
            self.assertIn('!= quectel', once)

    def test_guard_fails_when_upstream_entrypoint_changes(self):
        m = self.load()
        with tempfile.TemporaryDirectory() as directory:
            p = pathlib.Path(directory) / 'init'
            p.write_text('unknown_entrypoint() { :; }\n')
            with self.assertRaises(ValueError):
                m.guard_service(p, 'fm350')

    def test_branding_changes_brand_anchors_without_changing_hostname(self):
        m = self.load()
        text = '<title>{{ hostname }}</title><a class="brand" href="/">{{ hostname }}</a>'
        out = m.brand_header(text)
        self.assertIn('<title>{{ hostname }}</title>', out)
        self.assertIn('>Hiveton H5000M</a>', out)

    def test_hotplug_is_guarded_before_any_scan(self):
        m = self.load()
        with tempfile.TemporaryDirectory() as directory:
            p = pathlib.Path(directory) / 'hook'
            p.write_text('#!/bin/sh\nmodem_scan add\n')
            m.guard_hook(p, 'quectel')
            text = p.read_text()
            self.assertLess(text.index('h5000m-modem-owner'), text.index('modem_scan add'))

if __name__ == '__main__':
    unittest.main()
