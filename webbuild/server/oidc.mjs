import {createPublicKey,verify as verifySignature} from 'node:crypto';
const issuer='https://token.actions.githubusercontent.com';
export class OIDCVerifier{
 constructor(settings,fetcher=fetch){this.s=settings;this.fetcher=fetcher;this.keys=[];this.until=0;}
 async verify(token){
  if(typeof token!=='string'||token.length>16000)throw Error('构建身份无效');
  const parts=token.split('.');if(parts.length!==3||parts.some(p=>!/^[A-Za-z0-9_-]+$/.test(p)))throw Error('构建身份无效');
  const head=JSON.parse(Buffer.from(parts[0],'base64url'));if(head.alg!=='RS256'||typeof head.kid!=='string')throw Error('构建签名算法无效');
  if(Date.now()>this.until){const r=await this.fetcher(`${issuer}/.well-known/jwks`,{redirect:'error',signal:AbortSignal.timeout(10000)});if(!r.ok)throw Error('身份公钥暂不可用');this.keys=(await r.json()).keys;this.until=Date.now()+300e3;}
  const jwk=this.keys.find(k=>k.kid===head.kid&&k.kty==='RSA'&&k.use==='sig'&&k.alg==='RS256');if(!jwk||!verifySignature('RSA-SHA256',Buffer.from(parts.slice(0,2).join('.')),createPublicKey({key:jwk,format:'jwk'}),Buffer.from(parts[2],'base64url')))throw Error('构建签名无效');
  const c=JSON.parse(Buffer.from(parts[1],'base64url')),now=Math.floor(Date.now()/1000),s=this.s,ref=`refs/heads/${s.branch}`;
  if(!Number.isInteger(c.exp)||!Number.isInteger(c.iat)||c.exp<=now||c.iat>now+30||c.iat<now-600||c.exp-c.iat>900||(c.nbf!==undefined&&(!Number.isInteger(c.nbf)||c.nbf>now+30)))throw Error('构建身份已过期');
  const subjects=[`repo:${s.repo}:ref:${ref}`,`repo:${s.repo.split('/')[0]}@${s.ownerId}/${s.repo.split('/')[1]}@${s.repoId}:ref:${ref}`];
  if(c.iss!==issuer||c.aud!==s.origin||!subjects.includes(c.sub)||c.repository!==s.repo||String(c.repository_id)!==s.repoId||String(c.repository_owner_id)!==s.ownerId||c.ref!==ref||c.workflow_ref!==`${s.repo}/.github/workflows/${s.workflow}@${ref}`||c.workflow_sha!==s.expectedSha||c.sha!==s.expectedSha||c.event_name!=='workflow_dispatch'||!/^\d+$/.test(c.run_id)||String(c.run_attempt)!=='1')throw Error('构建身份与部署配置不匹配');
  return c;
 }
}
