import importlib.util,os,pathlib,tarfile,tempfile,unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
class TransferTests(unittest.TestCase):
 def test_private_archive_includes_checksum_and_excludes_secrets_and_symlinks(self):
  spec=importlib.util.spec_from_file_location('transfer',ROOT/'scripts/webbuild-transfer.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);(root/'temp').mkdir();output=root/'output';output.mkdir();(output/'firmware.bin').write_bytes(b'firmware');(output/'SHA256SUMS').write_text('checksum');(output/'IMAGE-INFO.txt').write_text('metadata');(output/'config.conf').write_text('SECRET');(output/'secret.txt').symlink_to(output/'config.conf');(output/'nested').mkdir();(output/'nested/secret.bin').write_text('SECRET')
   calls=[]
   def transfer(action,payload=None,file=None):
    if file:
     with tarfile.open(file) as tar:calls.extend(tar.getnames())
    return {'ok':True}
   with patch.dict(os.environ,{'RUNNER_TEMP':str(root/'temp'),'GITHUB_WORKSPACE':str(root),'BUILD_STATUS':'success'}),patch.object(m,'transfer',transfer):m.main('finish')
   self.assertIn('firmware.bin',calls);self.assertIn('SHA256SUMS',calls);self.assertIn('IMAGE-INFO.txt',calls);self.assertNotIn('config.conf',calls);self.assertNotIn('secret.txt',calls);self.assertNotIn('nested/secret.bin',calls)
