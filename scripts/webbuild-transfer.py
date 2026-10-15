"""OIDC-only task transfer. No credentials or configuration are printed."""
import http.client,json,os,pathlib,re,ssl,sys,tarfile,urllib.parse,urllib.request
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ValueError('Redirect refused')
def url_origin():
    u=urllib.parse.urlsplit(os.environ['WEBBUILD_URL'])
    if u.scheme!='https' or not u.hostname or u.path not in ('','/') or u.query or u.fragment or u.username:raise ValueError('HTTPS origin required')
    return u

def oidc(audience):
    url=os.environ['ACTIONS_ID_TOKEN_REQUEST_URL']+'&'+urllib.parse.urlencode({'audience':audience})
    req=urllib.request.Request(url,headers={'Authorization':'Bearer '+os.environ['ACTIONS_ID_TOKEN_REQUEST_TOKEN']})
    with urllib.request.build_opener(NoRedirect).open(req,timeout=30) as r:return json.load(r)['value']

def transfer(action,payload=None,file=None):
    u=url_origin();origin=urllib.parse.urlunsplit((u.scheme,u.netloc,'','',''));task=os.environ['TASK_ID']
    if not re.fullmatch(r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}',task):raise ValueError('Invalid task UUID')
    token=oidc(origin);conn=http.client.HTTPSConnection(u.hostname,u.port or 443,timeout=900,context=ssl.create_default_context());path='/internal/tasks/'+task+'/'+action
    headers={'Authorization':'Bearer '+token,'Content-Type':'application/octet-stream' if file else 'application/json'}
    if file:
        size=file.stat().st_size;headers['Content-Length']=str(size);conn.putrequest('PUT',path)
        for k,v in headers.items():conn.putheader(k,v)
        conn.endheaders()
        with file.open('rb') as stream:
            while True:
                chunk=stream.read(1024*1024)
                if not chunk:break
                conn.send(chunk)
    else:conn.request('POST',path,body=json.dumps(payload or {}).encode(),headers=headers)
    res=conn.getresponse();data=res.read(32768)
    if res.status!=200:raise ValueError('Private transfer failed')
    conn.close();return json.loads(data)

def main(mode):
    base=pathlib.Path(os.environ['RUNNER_TEMP'])/'webbuild';base.mkdir(mode=0o700,exist_ok=True);base.chmod(0o700);config=base/'config.json'
    if mode=='claim':
        data=transfer('claim');fd=os.open(config,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(fd,'w') as f:json.dump(data,f)
    elif mode=='finish':
        success=os.environ.get('BUILD_STATUS')=='success';root=pathlib.Path(os.environ['GITHUB_WORKSPACE']);name='firmware.tar.gz' if success else 'diagnostics.tar.gz';archive=base/name
        with tarfile.open(archive,'w:gz') as tar:
            if success:
                # Only flat reviewed output files; never include wrt/files or runner secrets.
                for p in sorted((root/'output').iterdir()):
                    if p.is_file() and not p.is_symlink() and (p.suffix in ('.bin','.json','.txt','.tsv','.manifest') or p.name in ('feeds.conf.default','SHA256SUMS')):tar.add(p,arcname=p.name,recursive=False)
            else:
                for p in (pathlib.Path(os.environ['RUNNER_TEMP'])/'webbuild-private.log',root/'build.log'):
                    if p.is_file() and not p.is_symlink():tar.add(p,arcname=p.name,recursive=False)
        transfer(name,file=archive);transfer('finish',{'status':'completed' if success else 'failed'})
    else:raise ValueError('Unsupported mode')

if __name__=='__main__':
    try:main(sys.argv[1])
    except Exception:
        print('WebBuild private transfer failed; details withheld to protect credentials',file=sys.stderr);sys.exit(1)
