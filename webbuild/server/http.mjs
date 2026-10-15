import {isIP} from 'node:net';
import {createServer as httpServer} from 'node:http';import {readFileSync,createReadStream} from 'node:fs';import {pipeline} from 'node:stream/promises';import {spawnSync} from 'node:child_process';import {createHmac} from 'node:crypto';import {validateConfig,toTemplate} from '../shared/config.mjs';
const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const json=(res,status,value)=>{res.writeHead(status,{'Content-Type':'application/json; charset=utf-8'});res.end(JSON.stringify(value));};
const reject=(status,message)=>Object.assign(new Error(message),{status});
async function body(req){let size=0;const chunks=[];for await(const c of req){size+=c.length;if(size>16384)throw reject(413,'请求过大');chunks.push(c);}try{return JSON.parse(Buffer.concat(chunks));}catch{throw reject(400,'JSON 格式不正确');}}
export function hashPassword(password,salt){const result=spawnSync('openssl',['passwd','-6','-stdin','-salt',salt],{input:password+'\n',encoding:'utf8',timeout:10000,maxBuffer:4096});const hash=result.stdout?.trim();if(result.status!==0||!/^\$6\$[a-zA-Z0-9./]{1,16}\$[a-zA-Z0-9./]{86}$/.test(hash))throw reject(500,'密码哈希服务不可用');return hash;}
export function createServer({settings:s,policy,sessions,github,store,tasks,oidc,results}){
 const staticFiles=new Map([['/','../public/index.html'],['/app.mjs','../public/app.mjs'],['/style.css','../public/style.css'],['/shared/config.mjs','../shared/config.mjs'],['/shared/templates.mjs','../shared/templates.mjs']]);
 const rates=new Map();
 return httpServer(async(req,res)=>{
  res.setHeader('Cache-Control','no-store');res.setHeader('X-Content-Type-Options','nosniff');res.setHeader('Referrer-Policy','no-referrer');res.setHeader('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'");
  if(!s.preview)res.setHeader('Strict-Transport-Security','max-age=31536000');
  let u;try{u=new URL(req.url,s.origin);if(req.url.length>2048)throw reject(414,'地址过长');const forwarded=req.headers['x-webbuild-client-ip'],ip=s.trustProxy&&typeof forwarded==='string'&&isIP(forwarded)?forwarded:req.socket.remoteAddress;
   let identity;try{identity=sessions?.requireUser(req).user.id;}catch{}
   const namespace=u.pathname.startsWith('/internal/')?'internal':identity?'user':'public';
   const key=`${namespace}:${namespace==='user'?identity:ip}`,now=Date.now();
   if(rates.size>=10000){for(const [k,v] of rates)if(v.until<now)rates.delete(k);if(rates.size>=10000&&!rates.has(key))throw reject(429,'请求过于频繁');}
   const r=rates.get(key)||{n:0,until:now+60000};if(r.until<now){r.n=0;r.until=now+60000;}rates.set(key,r);
   if(++r.n>(namespace==='public'?600:300))throw reject(429,'请求过于频繁');
   if(u.pathname==='/healthz'&&req.method==='GET')return json(res,200,{ok:true});
   if(staticFiles.has(u.pathname)&&req.method==='GET'){const type=u.pathname.endsWith('.mjs')?'text/javascript':u.pathname.endsWith('.css')?'text/css':'text/html';const data=readFileSync(new URL(staticFiles.get(u.pathname),import.meta.url));res.writeHead(200,{'Content-Type':`${type}; charset=utf-8`});return res.end(data);}
   if(u.pathname==='/api/policy'&&req.method==='GET')return json(res,200,policy);
   if(u.pathname==='/api/session'&&req.method==='GET'){if(s.preview)return json(res,200,{preview:true,user:null,csrf:null});let a;try{a=sessions.requireUser(req);}catch{return json(res,200,{preview:false,user:null,csrf:null});}const user=await github.authorize(a.token);return json(res,200,{preview:false,user,csrf:a.csrf});}
   if(s.preview&&(u.pathname.startsWith('/api/')||u.pathname.startsWith('/auth/')||u.pathname.startsWith('/internal/')))throw reject(503,'本地预览未连接 GitHub；部署后才能编译');
   if(u.pathname==='/auth/login'&&req.method==='GET'){const state=sessions.beginLogin();const target=new URL('https://github.com/login/oauth/authorize');for(const [k,v] of Object.entries({client_id:s.clientId,redirect_uri:`${s.origin}/auth/callback`,state:state.state,code_challenge:state.challenge,code_challenge_method:'S256'}))target.searchParams.set(k,v);res.writeHead(302,{Location:target.href,'Set-Cookie':`wb_login=${state.state}; HttpOnly; Secure; SameSite=Lax; Path=/auth/callback; Max-Age=600`});return res.end();}
   if(u.pathname==='/auth/callback'&&req.method==='GET'){const state=u.searchParams.get('state'),loginCookie=String(req.headers.cookie||'').split(';').map(v=>v.trim()).find(v=>v.startsWith('wb_login='))?.slice(9);if(!state||state!==loginCookie||!u.searchParams.get('code'))throw reject(403,'登录来源不匹配');const login=sessions.consumeLogin(state),token=await github.exchange(u.searchParams.get('code'),login.verifier),user=await github.authorize(token),session=sessions.create(user,token);res.writeHead(302,{Location:'/', 'Set-Cookie':[`wb_session=${session.id}; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=28800`,'wb_login=; HttpOnly; Secure; SameSite=Lax; Path=/auth/callback; Max-Age=0']});return res.end();}
   const internal=u.pathname.match(/^\/internal\/tasks\/([^/]+)\/(claim|finish|firmware.tar.gz|diagnostics.tar.gz)$/);
   if(internal){const [,id,action]=internal;if(!UUID.test(id))throw reject(404,'任务不存在');const token=String(req.headers.authorization||'').match(/^Bearer (.+)$/)?.[1];let claims;try{claims=await oidc.verify(token);}catch{throw reject(403,'构建身份校验失败');}
    if(action==='claim'&&req.method==='POST')return json(res,200,await tasks.claim(id,claims));
    if(action==='finish'&&req.method==='POST'){const v=await body(req);await tasks.finish(id,claims,v.status);return json(res,200,{ok:true});}
    if(['firmware.tar.gz','diagnostics.tar.gz'].includes(action)&&req.method==='PUT'){await tasks.identity(id,claims);if(Number(req.headers['content-length'])>s.maxResultBytes)throw reject(413,'结果过大');await results.upload(id,action,req);return json(res,200,{ok:true});}
    throw reject(405,'请求方法不支持');
   }
   if(u.pathname.startsWith('/api/')){
    let a;try{a=sessions.requireUser(req);}catch{throw reject(401,'请先登录 GitHub');}
    let user;try{user=await github.authorize(a.token);if(user.id!==a.user.id)throw Error();}catch{throw reject(403,'当前用户没有仓库写入权限');}
    if(!['GET','HEAD'].includes(req.method))try{sessions.verifyCsrf(req,a);}catch{throw reject(403,'请求来源校验失败');}
    if(u.pathname==='/api/logout'&&req.method==='POST'){sessions.sessions.delete(a.id);res.setHeader('Set-Cookie','wb_session=; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=0');return json(res,200,{ok:true});}
    if(u.pathname==='/api/tasks'&&req.method==='GET')return json(res,200,store.list(user.id).map(t=>tasks.summary(t)));
    if(u.pathname==='/api/tasks'&&req.method==='POST'){
     const input=await body(req),key=String(req.headers['idempotency-key']||'');if(!/^[a-zA-Z0-9-]{16,80}$/.test(key))throw reject(400,'提交编号不合法');let config;try{config=validateConfig(input,policy);}catch(e){throw reject(400,e.message);}
     const salt=createHmac('sha256',s.key).update(`${user.id}:${key}`).digest('hex').slice(0,16);config.rootHash=hashPassword(config.rootPassword,salt);delete config.rootPassword;
     // Store normalized config only; derived netmask is needed by the build generator.
     const t=store.createTask(user.id,config,key);await tasks.dispatch(t);return json(res,202,tasks.summary(t));
    }
    const taskRoute=u.pathname.match(/^\/api\/tasks\/([^/]+)(?:\/files\/(firmware.tar.gz|diagnostics.tar.gz))?$/);
    if(taskRoute&&req.method==='GET'){const [,id,name]=taskRoute;if(!UUID.test(id))throw reject(404,'任务不存在');const t=store.readTask(user.id,id);if(name){const f=results.download(user.id,id,name);res.writeHead(200,{'Content-Type':'application/gzip','Content-Length':f.size,'Content-Disposition':`attachment; filename="H5000M-${id}-${name}"`});await pipeline(createReadStream(f.path),res);return;}
     try{await tasks.refresh(t);}catch{return json(res,200,{...tasks.summary(t),statusUnavailable:true});}return json(res,200,tasks.summary(t));}
   }
   throw reject(404,'页面不存在');
  }catch(e){if(res.headersSent){res.destroy();return;}const status=e.status||400;json(res,status,{error:e.status?e.message:'操作失败：配置无效、任务不存在或服务暂不可用'});}
 });
}
