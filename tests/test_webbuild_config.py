import importlib.util,json,pathlib,tempfile,unittest,subprocess,os
ROOT=pathlib.Path(__file__).resolve().parents[1]
def module():
 s=importlib.util.spec_from_file_location('webbuild_config',ROOT/'scripts/webbuild-config.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class WebBuildTests(unittest.TestCase):
 def config(self):
  return {'schemaVersion':1,'author':'用户','notes':'定制','hostname':'Hiveton-H5000M','timezone':'Asia/Shanghai','lan':{'address':'10.0.0.1','prefix':24,'netmask':'255.255.255.0','start':100,'limit':150},'wifi2g':{'ssid':"A3KM'$(touch /tmp/not-created)",'enabled':True,'encryption':'psk2','password':"pa'ssword"},'wifi5g':{'ssid':'A3KM+','enabled':False,'encryption':'psk2','password':'password'},'theme':'argon','extraPackages':[],'rootHash':'$6$abcdefghijklmnop$'+'A'*86}
 def test_shell_values_are_literals_and_shadow_uses_hash(self):
  m=module()
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);(root/'files/etc').mkdir(parents=True);(root/'files/etc/shadow').write_text('root:old:0:0:99999:7:::\nother:x:0:0:1:1:::\n');(root/'.config').write_text((ROOT/'config/h5000m.config').read_text())
   c=self.config();m.apply(root,c,json.loads((ROOT/'webbuild/policy.json').read_text()))
   conf=root/'files/etc/h5000m-webbuild.conf';out=subprocess.check_output(['sh','-c','. "$1"; printf "%s" "$wb_2g_ssid"','sh',str(conf)],text=True)
   self.assertEqual(out,c['wifi2g']['ssid']);self.assertIn(c['rootHash'],(root/'files/etc/shadow').read_text());self.assertNotIn('rootPassword',conf.read_text());self.assertEqual(conf.stat().st_mode&0o777,0o600)
 def test_generator_rejects_untrusted_configuration(self):
  m=module();p=json.loads((ROOT/'webbuild/policy.json').read_text())
  for mutate in [lambda c:c.update(extraPackages=['nano; id']),lambda c:c.update(extraPackages=['unknown']),lambda c:c.update(removePackages=['qmodem']),lambda c:c.update(rootHash='$(id)'),lambda c:c['lan'].update(address='10.0.0.255'),lambda c:c['wifi2g'].update(password='short')]:
   c=self.config();mutate(c)
   with self.assertRaises(ValueError):m.validate(c,p)
 def test_defconfig_must_keep_baseline_and_extra(self):
  m=module();p=json.loads((ROOT/'webbuild/policy.json').read_text());c=self.config();c['extraPackages']=['nano'];text=(ROOT/'config/h5000m.config').read_text()
  with self.assertRaises(ValueError):m.verify_selections(text,c,p)
  m.verify_selections(text+'\nCONFIG_PACKAGE_nano=y\n',c,p)
 def test_firstboot_identifies_reordered_bands_and_keeps_other_ap(self):
  with tempfile.TemporaryDirectory() as d:
   path=pathlib.Path(d);db=path/'db.json';calls=path/'calls';done=path/'done';conf=path/'config'
   state={'wireless.z':'wifi-device','wireless.z.band':'5g','wireless.a':'wifi-device','wireless.a.hwmode':'11g','wireless.guest':'wifi-iface','wireless.guest.device':'z','wireless.guest.mode':'ap','wireless.guest.network':'guest','wireless.guest.ssid':'KEEP','wireless.lan5':'wifi-iface','wireless.lan5.device':'z','wireless.lan5.mode':'ap','wireless.lan5.network':'lan'};db.write_text(json.dumps(state))
   (path/'uci').write_text('''#!/usr/bin/env python3
import json,os,sys
p=os.environ['MOCK_DB'];d=json.load(open(p));a=sys.argv[1:]
if a[0]=='-q':a=a[1:]
if a[0]=='get':
 if a[1] not in d:sys.exit(1)
 print(d[a[1]])
elif a[0]=='show':
 for k,v in d.items():
  if k.startswith(a[1]+'.'):print(k+'='+v)
elif a[0]=='set':
 k,v=a[1].split('=',1);d[k]=v
elif a[0]=='add':
 k='new'+str(len(d));d[a[1]+'.'+k]=a[2];print(k)
json.dump(d,open(p,'w'))
''');(path/'uci').chmod(0o755)
   for name in ['wifi','logger','sleep']:(path/name).write_text('#!/bin/sh\nexit 0\n');(path/name).chmod(0o755)
   conf.write_text("wb_2g_ssid='A3KM'\nwb_5g_ssid='A3KM+'\nwb_2g_password='password'\nwb_5g_password='password'\nwb_2g_disabled='0'\nwb_5g_disabled='1'\n")
   env={**os.environ,'PATH':str(path)+':'+os.environ['PATH'],'MOCK_DB':str(db),'H5000M_CONFIG':str(conf),'H5000M_DONE':str(done),'H5000M_BACKUP_LIST':str(path/'backup-list'),'H5000M_RESTORE_GUARD':str(path/'preserve')}
   subprocess.run(['sh',str(ROOT/'files/usr/libexec/h5000m-firstboot')],env=env,check=True,timeout=5)
   result=json.loads(db.read_text());self.assertEqual(result['wireless.lan5.ssid'],'A3KM+');self.assertEqual(result['wireless.z.disabled'],'1');self.assertEqual(result['wireless.guest.ssid'],'KEEP');self.assertTrue(done.exists());self.assertIn('A3KM',result.values())
   done.unlink();(path/'preserve').touch();before=db.read_text();subprocess.run(['sh',str(ROOT/'files/usr/libexec/h5000m-firstboot')],env=env,check=True,timeout=5);self.assertEqual(db.read_text(),before)
   self.assertTrue(done.exists(),'restored boot must leave a persistent guard')
   (path/'preserve').unlink();subprocess.run(['sh',str(ROOT/'files/usr/libexec/h5000m-firstboot')],env=env,check=True,timeout=5);self.assertEqual(db.read_text(),before,'second reboot must preserve restored wireless')
