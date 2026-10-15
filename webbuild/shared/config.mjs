export const defaults={schemaVersion:1,author:'',notes:'',hostname:'Hiveton-H5000M',timezone:'Asia/Shanghai',lan:{address:'10.0.0.1',prefix:24,start:100,limit:150},wifi2g:{ssid:'A3KM',enabled:true,encryption:'psk2'},wifi5g:{ssid:'A3KM+',enabled:true,encryption:'psk2'},theme:'argon',extraPackages:[]};
const fail=message=>{throw new Error(message);};
function keys(v,allowed){if(!v||typeof v!=='object'||Array.isArray(v)||Object.keys(v).some(k=>!allowed.includes(k)))fail('配置字段不正确');}
function str(v,label,max=64,min=0){if(typeof v!=='string'||v.length<min||new TextEncoder().encode(v).length>max||/[\x00-\x1f\x7f]/.test(v))fail(`${label}长度或字符不合法`);return v;}
function integer(v,min,max,label){if(!Number.isInteger(v)||v<min||v>max)fail(`${label}范围不正确`);return v;}
export function validateConfig(input,policy,{secretsRequired=true}={}){
 keys(input,[...Object.keys(defaults),...(secretsRequired?['rootPassword']:[])]);
 if(input.schemaVersion!==1)fail('不支持的模板版本');
 const c=structuredClone(input);
 for(const k of Object.keys(defaults))if(!(k in c))fail('配置不完整');
 str(c.author,'编译者',80);str(c.notes,'版本备注',160);
 if(!/^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$/.test(c.hostname))fail('主机名不合法');
 if(!Object.hasOwn(policy.timezones,c.timezone))fail('时区不在白名单');
 keys(c.lan,['address','prefix','start','limit']);
 if(typeof c.lan.address!=='string'||!c.lan.address.split('.').every(s=>/^(0|[1-9][0-9]{0,2})$/.test(s)&&+s<256)||c.lan.address.split('.').length!==4)fail('LAN IPv4 地址不合法');
 const octets=c.lan.address.split('.').map(Number);if(octets[0]===0||octets[0]===127||octets[0]>=224||c.lan.address==='169.254.0.0')fail('LAN 地址不可用');
 const prefix=integer(c.lan.prefix,8,30,'网段前缀');
 const size=2**(32-prefix),n=octets.reduce((a,b)=>a*256+b,0),host=n%size;
 if(host===0||host===size-1)fail('LAN 必须是可用主机地址');
 integer(c.lan.start,1,size-2,'DHCP 起始偏移');integer(c.lan.limit,1,size-2,'DHCP 数量');
 if(c.lan.start+c.lan.limit-1>size-2||(host>=c.lan.start&&host<c.lan.start+c.lan.limit))fail('DHCP 地址池溢出或包含管理地址');
 // Derived values are not accepted on import; normalization is deliberately separate.
 const mask=(0xffffffff <<(32-prefix))>>>0;c.lan.netmask=[24,16,8,0].map(b=>(mask>>>b)&255).join('.');
 for(const name of ['wifi2g','wifi5g']){
  keys(c[name],['ssid','enabled','encryption',...(secretsRequired?['password']:[])]);str(c[name].ssid,'SSID',32,1);
  if(typeof c[name].enabled!=='boolean'||c[name].encryption!=='psk2')fail('无线选项不合法');
  if(secretsRequired){const p=str(c[name].password,'Wi-Fi 密码',63,8);if(!/^[\x20-\x7e]{8,63}$/.test(p))fail('Wi-Fi 密码请使用 8–63 位可打印 ASCII 字符');}
 }
 if(secretsRequired)str(c.rootPassword,'root 密码',128,8);
 if(!Object.hasOwn(policy.themes,c.theme))fail('主题不在白名单');
 if(!Array.isArray(c.extraPackages)||c.extraPackages.length>30||new Set(c.extraPackages).size!==c.extraPackages.length)fail('额外包列表不合法');
 for(const p of c.extraPackages)if(typeof p!=='string'||!/^[-a-zA-Z0-9+_.]+$/.test(p)||!policy.additions.includes(p))fail('额外包不在白名单');
 return c;
}
export function toTemplate(c){const t=structuredClone(c);delete t.rootPassword;delete t.rootHash;delete t.lan.netmask;for(const k of ['wifi2g','wifi5g'])delete t[k].password;return t;}
export function preview(c){return {...toTemplate(c),credentials:'密码已隐藏；模板不会保存密码'};}
