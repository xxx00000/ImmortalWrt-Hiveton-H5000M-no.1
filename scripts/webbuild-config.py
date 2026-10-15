"""Strict, shell-safe customization of the existing pinned H5000M build."""
import ipaddress,json,pathlib,re,shlex,sys

def validate(c,p):
    expected={'schemaVersion','author','notes','hostname','timezone','lan','wifi2g','wifi5g','theme','extraPackages','rootHash'}
    if not isinstance(c,dict) or set(c)!=expected or c['schemaVersion']!=1: raise ValueError('Configuration schema mismatch')
    def text(v,max_bytes,min_len=0):
        if not isinstance(v,str) or len(v)<min_len or len(v.encode())>max_bytes or re.search(r'[\x00-\x1f\x7f]',v): raise ValueError('Invalid text')
    text(c['author'],80);text(c['notes'],160)
    if not isinstance(c['hostname'],str) or not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?',c['hostname']):raise ValueError('Invalid hostname')
    if c['timezone'] not in p['timezones'] or c['theme'] not in p['themes']:raise ValueError('Unknown timezone/theme')
    lan=c['lan']
    if set(lan)!={'address','prefix','netmask','start','limit'} or type(lan['prefix']) is not int or not 8<=lan['prefix']<=30:raise ValueError('Invalid LAN')
    ip=ipaddress.IPv4Address(lan['address']);net=ipaddress.IPv4Network(str(ip)+'/'+str(lan['prefix']),strict=False)
    if ip.is_loopback or ip.is_multicast or int(str(ip).split('.')[0]) in (0,255) or ip in (net.network_address,net.broadcast_address) or str(net.netmask)!=lan['netmask']:raise ValueError('Invalid LAN host/mask')
    start,limit=lan['start'],lan['limit'];host=int(ip)-int(net.network_address)
    if type(start) is not int or type(limit) is not int or start<1 or limit<1 or start+limit-1>=net.num_addresses-1 or start<=host<start+limit:raise ValueError('Invalid DHCP pool')
    for name in ('wifi2g','wifi5g'):
        w=c[name]
        if set(w)!={'ssid','enabled','encryption','password'} or type(w['enabled']) is not bool or w['encryption']!='psk2':raise ValueError('Invalid wireless fields')
        text(w['ssid'],32,1)
        if not isinstance(w['password'],str) or not re.fullmatch(r'[\x20-\x7e]{8,63}',w['password']):raise ValueError('Invalid PSK')
    if not isinstance(c['rootHash'],str) or not re.fullmatch(r'\$6\$[a-zA-Z0-9./]{1,16}\$[a-zA-Z0-9./]{86}',c['rootHash']):raise ValueError('Invalid password hash')
    if not isinstance(c['extraPackages'],list) or len(c['extraPackages'])>30 or any(not isinstance(x,str) or not re.fullmatch(r'[-a-zA-Z0-9+_.]+',x) or x not in p['additions'] for x in c['extraPackages']) or len(set(c['extraPackages']))!=len(c['extraPackages']):raise ValueError('Package is not allowlisted')
    return c

def selected(c):
    return set(c['extraPackages'])|{'luci-theme-'+c['theme']}

def verify_selections(text,c,p):
    enabled=set(re.findall(r'^CONFIG_PACKAGE_(.+)=y$',text,re.M))
    if (set(p['protectedPackages'])|selected(c))-enabled:raise ValueError('Required baseline or extra package not selected')

def shell_config(c,p):
    fields={'wb_lan_address':c['lan']['address'],'wb_lan_netmask':c['lan']['netmask'],'wb_dhcp_start':c['lan']['start'],'wb_dhcp_limit':c['lan']['limit'],'wb_hostname':c['hostname'],'wb_zonename':c['timezone'],'wb_timezone':p['timezones'][c['timezone']],'wb_theme':p['themes'][c['theme']]}
    for band,name in [('2g','wifi2g'),('5g','wifi5g')]:
        fields.update({f'wb_{band}_ssid':c[name]['ssid'],f'wb_{band}_password':c[name]['password'],f'wb_{band}_disabled':'0' if c[name]['enabled'] else '1'})
    return '# Generated from validated data; never log or publish this file.\n'+''.join(k+'='+shlex.quote(str(v))+'\n' for k,v in fields.items())

def apply(root,c,p):
    validate(c,p)
    config=root/'.config';text=config.read_text()
    # Refuse malformed baseline rather than silently replacing it.
    missing=set(p['protectedPackages'])-set(re.findall(r'^CONFIG_PACKAGE_(.+)=y$',text,re.M))
    if missing:raise ValueError('Protected package baseline changed')
    for package in sorted(selected(c)):
        text=re.sub(r'^(?:CONFIG_PACKAGE_'+re.escape(package)+r'=.*|# CONFIG_PACKAGE_'+re.escape(package)+r' is not set)\n?','',text,flags=re.M)
        text+='\nCONFIG_PACKAGE_'+package+'=y\n'
    config.write_text(text)
    etc=root/'files/etc';etc.mkdir(parents=True,exist_ok=True)
    conf=etc/'h5000m-webbuild.conf';conf.write_text(shell_config(c,p));conf.chmod(0o600)
    shadow=etc/'shadow'
    if not shadow.exists():shadow.write_bytes((root/'package/base-files/files/etc/shadow').read_bytes())
    text,count=re.subn(r'^root:[^:]*:',lambda m:'root:'+c['rootHash']+':',shadow.read_text(),count=1,flags=re.M)
    if count!=1:raise ValueError('Root shadow entry missing')
    shadow.write_text(text);shadow.chmod(0o600)
    (etc/'h5000m-build-info.json').write_text(json.dumps({'author':c['author'],'notes':c['notes'],'schemaVersion':1},ensure_ascii=False)+'\n')

if __name__=='__main__':
    try:
        mode,root_path,config_path=sys.argv[1:4];root=pathlib.Path(root_path);c=json.loads(pathlib.Path(config_path).read_text());p=json.loads((pathlib.Path(__file__).resolve().parents[1]/'webbuild/policy.json').read_text());validate(c,p)
        if mode=='apply':apply(root,c,p)
        elif mode=='verify':verify_selections((root/'.config').read_text(),c,p)
        else:raise ValueError('Invalid mode')
    except Exception:
        print('WebBuild configuration rejected; sensitive values withheld',file=sys.stderr);sys.exit(1)
