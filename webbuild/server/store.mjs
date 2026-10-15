import {mkdirSync,readFileSync,writeFileSync,renameSync,existsSync,rmSync,chmodSync} from 'node:fs';import {join} from 'node:path';import {randomBytes,randomUUID,createCipheriv,createDecipheriv,createHmac} from 'node:crypto';
const day=86400e3;
export class Store{
 constructor(dir,key){this.dir=dir;this.key=key;mkdirSync(dir,{recursive:true,mode:0o700});chmodSync(dir,0o700);this.file=join(dir,'state.enc');this.tasks={};if(existsSync(this.file)){const b=readFileSync(this.file);const d=createDecipheriv('aes-256-gcm',key,b.subarray(0,12));d.setAuthTag(b.subarray(12,28));this.tasks=JSON.parse(Buffer.concat([d.update(b.subarray(28)),d.final()]));}}
 save(){const iv=randomBytes(12),c=createCipheriv('aes-256-gcm',this.key,iv);const b=Buffer.concat([c.update(JSON.stringify(this.tasks)),c.final()]);writeFileSync(this.file+'.tmp',Buffer.concat([iv,c.getAuthTag(),b]),{mode:0o600});renameSync(this.file+'.tmp',this.file);}
 createTask(ownerId,config,idempotencyKey){this.expire();if(!/^[a-zA-Z0-9-]{16,80}$/.test(idempotencyKey))throw Error('提交编号不合法');const digest=createHmac('sha256',this.key).update(JSON.stringify(config)).digest('hex');const previous=Object.values(this.tasks).find(t=>t.ownerId===ownerId&&t.idempotencyKey===idempotencyKey);if(previous){if(previous.digest!==digest)throw Error('相同提交编号对应不同配置');return previous;}
 if(Object.values(this.tasks).filter(t=>t.ownerId===ownerId&&!['completed','failed','dispatch_failed','expired'].includes(t.state)).length>=3||Object.keys(this.tasks).length>=200)throw Error('任务数量已达上限');
 const t={id:randomUUID(),ownerId,config,digest,idempotencyKey,createdAt:Date.now(),state:'created',runId:null,headSha:null,files:[]};this.tasks[t.id]=t;this.save();return t;}
 get(id){const t=this.tasks[id];if(!t||t.state==='expired')throw Error('任务不存在或已过期');return t;}
 readTask(owner,id){const t=this.get(id);if(t.ownerId!==owner)throw Error('任务不存在或已过期');return t;}
 list(owner){return Object.values(this.tasks).filter(t=>t.ownerId===owner&&t.state!=='expired').sort((a,b)=>b.createdAt-a.createdAt);}
 update(id,changes){Object.assign(this.get(id),changes);this.save();return this.get(id);}
 expire(now=Date.now()){let changed=false;for(const [id,t] of Object.entries(this.tasks)){if(t.config&&now-t.createdAt>day){delete t.config;if(!['completed','failed'].includes(t.state))t.state='expired';changed=true;}if(now-t.createdAt>7*day){rmSync(join(this.dir,id),{recursive:true,force:true});delete this.tasks[id];changed=true;}}if(changed)this.save();}
}
