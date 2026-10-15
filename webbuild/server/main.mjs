import {readFileSync} from 'node:fs';import {loadSettings} from './settings.mjs';import {Store} from './store.mjs';import {Sessions} from './session.mjs';import {GitHubClient} from './github.mjs';import {OIDCVerifier} from './oidc.mjs';import {Tasks} from './tasks.mjs';import {Results} from './results.mjs';import {createServer} from './http.mjs';
const settings=loadSettings(),policy=JSON.parse(readFileSync(new URL('../policy.json',import.meta.url))),deps={settings,policy};
let cleanup;
if(!settings.preview){const store=new Store(settings.dataDir,settings.key),github=new GitHubClient(settings);Object.assign(deps,{store,github,sessions:new Sessions(settings.origin),oidc:new OIDCVerifier(settings),tasks:new Tasks(settings,store,github),results:new Results(store,settings.maxResultBytes)});store.expire();cleanup=setInterval(()=>{try{store.expire();}catch{console.error('任务清理失败，请检查数据卷');}},60000);cleanup.unref();}
const server=createServer(deps);server.requestTimeout=30*60e3;server.headersTimeout=30000;server.keepAliveTimeout=5000;
server.listen(settings.port,settings.host,()=>console.log(`H5000M WebBuild ${settings.preview?'本地预览':'服务'}：${settings.preview?settings.origin:settings.origin}`));
for(const signal of ['SIGINT','SIGTERM'])process.on(signal,()=>{clearInterval(cleanup);server.close(()=>process.exit(0));setTimeout(()=>process.exit(0),10000).unref();});
