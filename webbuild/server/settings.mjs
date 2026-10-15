import {readFileSync} from 'node:fs';import {resolve} from 'node:path';
export function loadSettings(e=process.env){
 const preview=e.PREVIEW==='1',host=e.HOST||(preview?'127.0.0.1':'0.0.0.0'),port=Number(e.PORT||8787);
 if(!Number.isInteger(port)||port<1||port>65535)throw Error('PORT 不合法');
 if(preview){if(host!=='127.0.0.1')throw Error('预览只能绑定本机');return {preview,host,port,origin:`http://127.0.0.1:${port}`};}
 const required=['PUBLIC_ORIGIN','GITHUB_APP_ID','GITHUB_CLIENT_ID','GITHUB_CLIENT_SECRET','GITHUB_INSTALLATION_ID','GITHUB_PRIVATE_KEY_FILE','DATA_KEY','EXPECTED_SHA'];
 for(const k of required)if(!e[k])throw Error(`缺少部署设置：${k}`);
 const origin=new URL(e.PUBLIC_ORIGIN);if(origin.protocol!=='https:'||origin.origin!==e.PUBLIC_ORIGIN)throw Error('PUBLIC_ORIGIN 必须为 HTTPS origin');
 const key=Buffer.from(e.DATA_KEY,'base64');if(key.length!==32||key.toString('base64')!==e.DATA_KEY)throw Error('DATA_KEY 必须为 32 随机字节的 base64');
 if(!/^[0-9a-f]{40}$/.test(e.EXPECTED_SHA))throw Error('EXPECTED_SHA 必须固定已审核分支提交');
 const dataDir=resolve(e.DATA_DIR||'/data');if(dataDir.includes('/public')||dataDir.includes('/shared'))throw Error('数据目录不能公开');
 return {preview,host,port,trustProxy:e.TRUST_PROXY==='1',origin:origin.origin,key,dataDir,appId:e.GITHUB_APP_ID,clientId:e.GITHUB_CLIENT_ID,clientSecret:e.GITHUB_CLIENT_SECRET,installationId:e.GITHUB_INSTALLATION_ID,privateKey:readFileSync(e.GITHUB_PRIVATE_KEY_FILE,'utf8'),repo:'xxx00000/OpenWRT-CI-H5000M',repoId:'1417656071',ownerId:'94558296',branch:'Hiveton-H5000M-WebBuild',workflow:'h5000m-build.yml',expectedSha:e.EXPECTED_SHA,maxResultBytes:1024*1024*1024};
}
