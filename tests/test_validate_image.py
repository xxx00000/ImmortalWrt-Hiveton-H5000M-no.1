import contextlib
import io
import pathlib
import runpy
import sys
import tarfile
import tempfile
import unittest
from unittest import mock


SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "validate-image.py"


class ValidateImageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name) / "wrt"
        self.target = self.root / "bin/targets/mediatek/filogic"
        self.target.mkdir(parents=True)
        self.image = self.target / "immortalwrt-mediatek-filogic-hiveton_h5000m-squashfs-sysupgrade.bin"
        self.fwtool = self.root / "staging_dir/host/bin/fwtool"
        self.fwtool.parent.mkdir(parents=True)
        self.fwtool.write_text("test placeholder", encoding="utf-8")
        with tarfile.open(self.image, "w") as archive:
            for name, contents in (("CONTROL", b"control"), ("kernel", b"kernel"), ("root", b"rootfs")):
                data = pathlib.Path(self.temp.name) / name
                data.write_bytes(contents)
                archive.add(data, arcname=f"sysupgrade-hiveton,h5000m/{name}")
        self.output = pathlib.Path(self.temp.name) / "output"

    def tearDown(self):
        self.temp.cleanup()

    def run_validator(self, supported_device):
        def write_metadata(args, check):
            pathlib.Path(args[3]).write_text(
                '{"supported_devices": ["' + supported_device + '"]}', encoding="utf-8"
            )

        old_argv = sys.argv
        sys.argv = [str(SCRIPT), str(self.root), str(self.output)]
        try:
            with mock.patch("subprocess.run", side_effect=write_metadata), contextlib.redirect_stdout(io.StringIO()):
                runpy.run_path(str(SCRIPT), run_name="__main__")
        finally:
            sys.argv = old_argv

    def test_exports_only_complete_supported_h5000m_image(self):
        self.run_validator("hiveton,h5000m")
        image = self.output / "immortalwrt-25.12.2-hiveton_h5000m-AU-full.bin"
        self.assertTrue(image.is_file())
        self.assertEqual((self.output / "SHA256SUMS").read_text(encoding="utf-8").split()[1], image.name)
        self.assertTrue((self.output / "IMAGE-METADATA.json").is_file())

    def test_rejects_metadata_for_another_device(self):
        with self.assertRaises(SystemExit):
            self.run_validator("some,other-device")
        self.assertFalse((self.output / "immortalwrt-25.12.2-hiveton_h5000m-AU-full.bin").exists())

    def test_rejects_container_without_root_filesystem(self):
        with tarfile.open(self.image, "w") as archive:
            data = pathlib.Path(self.temp.name) / "only-kernel"
            data.write_bytes(b"kernel")
            archive.add(data, arcname="kernel")
        with self.assertRaises(SystemExit):
            self.run_validator("hiveton,h5000m")


if __name__ == "__main__":
    unittest.main()
