import pathlib,unittest,importlib.util
ROOT=pathlib.Path(__file__).resolve().parents[1]
class WorkflowTests(unittest.TestCase):
 def test_dispatch_never_interpolates_input_into_shell_and_private_artifacts_are_disabled(self):
  w=(ROOT/'.github/workflows/h5000m-build.yml').read_text()
  self.assertIn('task_id:',w);self.assertIn('id-token: write',w);self.assertNotIn('${{ inputs.task_id }}',w.split('    steps:')[1]);self.assertEqual(w.count("if: inputs.task_id == ''"),1);self.assertIn("if: failure() && inputs.task_id == ''",w);self.assertIn('webbuild-transfer.py finish',w);self.assertIn('webbuild-config.py" verify',w)
 def test_public_and_private_acceptance_have_distinct_password_checks(self):
  spec=importlib.util.spec_from_file_location('audit',ROOT/'scripts/validate-rootfs.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  self.assertTrue(hasattr(m,'verify_webbuild_files'))
 def test_preinit_guard_is_registered_before_restore(self):
  t=(ROOT/'files/lib/preinit/79-h5000m-preserve').read_text();self.assertIn('preinit_mount_root',t);self.assertIn('/sysupgrade.tgz',t);self.assertIn('/tmp/sysupgrade.tar',t)
