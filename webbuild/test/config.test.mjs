import test from 'node:test';
import assert from 'node:assert/strict';
import { defaults, validateConfig, toTemplate, preview } from '../shared/config.mjs';
import { readFileSync } from 'node:fs';
const policy=JSON.parse(readFileSync(new URL('../policy.json',import.meta.url)));
const input=()=>({...structuredClone(defaults),rootPassword:'password',wifi2g:{...defaults.wifi2g,password:'password'},wifi5g:{...defaults.wifi5g,password:'password'}});
test('defaults and normalized network',()=>{const c=validateConfig(input(),policy);assert.equal(c.lan.address,'10.0.0.1');assert.equal(c.lan.netmask,'255.255.255.0');assert.equal(c.wifi2g.ssid,'A3KM');assert.equal(c.wifi5g.ssid,'A3KM+');});
for(const [name,change] of [
 ['broadcast',c=>c.lan.address='10.0.0.255'],['network',c=>c.lan.address='10.0.0.0'],['prefix31',c=>c.lan.prefix=31],['pool overflow',c=>c.lan.limit=250],['pool includes router',c=>c.lan.start=1],
 ['injection package',c=>c.extraPackages=['htop;touch /tmp/x']],['unknown package',c=>c.extraPackages=['foo']],['unknown field',c=>c.command='id'],['unknown theme',c=>c.theme='../../x'],['unknown time',c=>c.timezone='$(id)'],['hostname',c=>c.hostname='a.b'],['SSID bytes',c=>c.wifi2g.ssid='汉'.repeat(11)],['control',c=>c.notes='a\nb'],['short password',c=>c.wifi5g.password='short'],['root newline',c=>c.rootPassword='pass\nword']])test(`rejects ${name}`,()=>{const c=input();change(c);assert.throws(()=>validateConfig(c,policy));});
test('small subnet accepted with matching pool',()=>{const c=input();c.lan={address:'10.0.0.1',prefix:30,start:2,limit:1};assert.equal(validateConfig(c,policy).lan.netmask,'255.255.255.252');});
test('templates and previews omit secrets and reject imported secrets',()=>{const c=input();assert(!JSON.stringify(toTemplate(c)).includes('password'));assert(!JSON.stringify(preview(c)).includes('password'));assert.throws(()=>validateConfig(c,policy,{secretsRequired:false}));const t=toTemplate(c);assert.equal(validateConfig(t,policy,{secretsRequired:false}).wifi2g.ssid,'A3KM');});
test('only allowlisted additions and no removal fields',()=>{const c=input();c.extraPackages=['luci-theme-bootstrap'];assert.deepEqual(validateConfig(c,policy).extraPackages,c.extraPackages);c.removePackages=['qmodem'];assert.throws(()=>validateConfig(c,policy));});
