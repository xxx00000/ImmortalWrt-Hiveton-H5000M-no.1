import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "files/usr/libexec/at-webserver-auth"


class AuthBootstrapTests(unittest.TestCase):
    def run_bootstrap(self, initial="", fail_commit=False, firmware_path=False):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            state = root / "key"
            state.write_text(initial)
            uci = root / "uci"
            uci.write_text('''#!/bin/sh
[ "$1" = '-q' ] && shift
case "$1" in
get) /bin/cat "$TEST_KEY" ;;
set) printf '%s' "${2#*=}" > "$TEST_KEY" ;;
commit) [ "$TEST_FAIL_COMMIT" != '1' ] ;;
*) exit 1 ;;
esac
''')
            uci.chmod(0o755)
            (root / "python3").symlink_to(sys.executable)
            (root / "tr").symlink_to("/usr/bin/tr")
            env = dict(os.environ, PATH=str(root) if firmware_path else f"{root}:{os.environ['PATH']}",
                       TEST_KEY=str(state), TEST_FAIL_COMMIT=str(int(fail_commit)))
            result = subprocess.run(["/bin/sh", str(SCRIPT)], env=env, capture_output=True, text=True)
            return result, state.read_text()

    def test_generates_key_without_printing_it(self):
        result, key = self.run_bootstrap()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(key, r"^[0-9a-f]{64}$")
        self.assertNotIn(key, result.stdout + result.stderr)

    def test_preserves_existing_key(self):
        result, key = self.run_bootstrap("existing-user-key")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(key, "existing-user-key")

    def test_commit_failure_blocks_startup(self):
        result, _ = self.run_bootstrap(fail_commit=True)
        self.assertEqual(result.returncode, 1)

    def test_generates_key_with_firmware_commands_without_od(self):
        result, key = self.run_bootstrap(firmware_path=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(key, r"^[0-9a-f]{64}$")
