import {randomBytes,createHash,timingSafeEqual} from 'node:crypto';
const random=()=>randomBytes(32).toString('base64url');
export class Sessions{
 constructor(origin,now=Date.now){this.origin=origin;this.now=now;this.logins=new Map();this.sessions=new Map();}
 prune(){for(const map of [this.logins,this.sessions])for(const [k,v] of map)if(v.expires<this.now())map.delete(k);}
 beginLogin(){this.prune();if(this.logins.size>=500)throw Error('登录请求过多');const v={state:random(),verifier:random(),expires:this.now()+600e3};this.logins.set(v.state,v);return {...v,challenge:createHash('sha256').update(v.verifier).digest('base64url')};}
 consumeLogin(state){const v=this.logins.get(state);this.logins.delete(state);if(!v||v.expires<this.now())throw Error('登录已失效');return v;}
 create(user,token){this.prune();if(this.sessions.size>=500)throw Error('会话数量已达上限');const v={id:random(),csrf:random(),user,token,expires:this.now()+8*3600e3};this.sessions.set(v.id,v);return v;}
 requireUser(req){this.prune();const id=String(req.headers.cookie||'').split(';').map(s=>s.trim()).find(s=>s.startsWith('wb_session='))?.slice(11);const v=this.sessions.get(id);if(!v)throw Error('请先登录 GitHub');return v;}
 verifyCsrf(req,s){const x=Buffer.from(String(req.headers['x-csrf-token']||'')),y=Buffer.from(s.csrf);if(req.headers.origin!==this.origin||x.length!==y.length||!timingSafeEqual(x,y))throw Error('请求来源校验失败');}
}
