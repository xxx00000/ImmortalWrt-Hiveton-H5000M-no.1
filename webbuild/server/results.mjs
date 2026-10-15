import {mkdirSync,createWriteStream,renameSync,rmSync,existsSync,statSync} from 'node:fs';import {join} from 'node:path';import {pipeline} from 'node:stream/promises';import {Transform} from 'node:stream';
export class Results{
 constructor(store,maxBytes=1024**3){this.store=store;this.maxBytes=maxBytes;this.busy=new Set();}
 path(id,name){if(!/^[a-f0-9-]{36}$/.test(id)||!['firmware.tar.gz','diagnostics.tar.gz'].includes(name))throw Error('文件不存在');return join(this.store.dir,id,name);}
 async upload(id,name,source){const path=this.path(id,name),t=this.store.get(id);if(this.busy.has(id)||t.files.includes(name))throw Error('结果已存在或正在上传');this.busy.add(id);mkdirSync(join(this.store.dir,id),{mode:0o700,recursive:true});let size=0;const limit=new Transform({transform:(chunk,enc,cb)=>{size+=chunk.length;cb(size>this.maxBytes?Error('上传文件过大'):null,chunk);}});try{await pipeline(source,limit,createWriteStream(path+'.tmp',{flags:'wx',mode:0o600}));if(size<1)throw Error('文件为空');renameSync(path+'.tmp',path);this.store.update(id,{files:[...new Set([...t.files,name])]});}catch(e){rmSync(path+'.tmp',{force:true});throw e;}finally{this.busy.delete(id);}}
 download(owner,id,name){const t=this.store.readTask(owner,id),path=this.path(id,name);if(!t.files.includes(name)||!existsSync(path))throw Error('文件不存在或已过期');return {path,size:statSync(path).size};}
}
