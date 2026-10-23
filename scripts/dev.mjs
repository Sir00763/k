import http from 'node:http';
import {spawn} from 'node:child_process';
import {randomUUID,createHash,timingSafeEqual} from 'node:crypto';
import {mkdir,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import worker,{videoId} from '../worker/index.js';
const root=fileURLToPath(new URL('../',import.meta.url));
const publicOrigin=process.env.PUBLIC_ORIGIN?new URL(process.env.PUBLIC_ORIGIN).origin:null;
const accessPassword=process.env.ACCESS_PASSWORD;
if(publicOrigin&&(!accessPassword||accessPassword.length<16))throw new Error('PUBLIC_ORIGIN requires ACCESS_PASSWORD with at least 16 characters.');
function authorized(req){if(!accessPassword)return true;const header=req.headers.authorization||'';if(!header.startsWith('Basic '))return false;const credentials=Buffer.from(header.slice(6),'base64').toString();const colon=credentials.indexOf(':');if(colon<0||credentials.slice(0,colon)!=='viewer')return false;const hash=s=>createHash('sha256').update(s).digest();return timingSafeEqual(hash(credentials.slice(colon+1)),hash(accessPassword))}
const jobs=new Map();const children=new Map();
const active=()=>[...jobs.values()].some(j=>!['done','error'].includes(j.status));
function respond(res,data,status=200){res.writeHead(status,{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'});res.end(JSON.stringify(data))}
async function readBody(req,limit){const parts=[];let size=0;for await(const chunk of req){size+=chunk.length;if(size>limit){const e=new Error('文件或请求超过允许大小。');e.status=413;throw e}parts.push(chunk)}return Buffer.concat(parts)}
function startJob(data,id=randomUUID()){
 if(jobs.size>=30){for(const [key,j]of jobs){if(['done','error'].includes(j.status)){jobs.delete(key);break}}}
 const job={id,videoId:data.videoId,status:'starting',message:'正在准备语音识别…',progress:0};jobs.set(id,job);
 const child=spawn(process.env.FRAME_PYTHON||'python3',[root+'scripts/transcribe.py'],{cwd:root,env:{...process.env,FRAME_NODE:process.execPath,HF_HOME:root+'.runtime/huggingface',XDG_CACHE_HOME:root+'.runtime/cache',HF_HUB_DISABLE_XET:'1'},stdio:['pipe','pipe','pipe']});
 children.set(id,child);
 let pending='';child.stdout.on('data',chunk=>{pending+=chunk;let pos;while((pos=pending.indexOf('\n'))>=0){const line=pending.slice(0,pos);pending=pending.slice(pos+1);try{Object.assign(job,JSON.parse(line))}catch{}}});
 child.stderr.on('data',()=>{});
 child.on('error',()=>Object.assign(job,{status:'error',message:'未能启动 Python。请设置 FRAME_PYTHON，详见运行说明。'}));
 const timer=setTimeout(()=>child.kill(),60*60*1000);
 child.on('close',()=>{children.delete(id);clearTimeout(timer);if(!['done','error'].includes(job.status))Object.assign(job,{status:'error',message:'语音识别进程已停止，请重试。'})});
 child.stdin.on('error',()=>{});child.stdin.end(JSON.stringify({...data,jobId:id})+'\n');return job;
}
let creating=false;
const server=http.createServer(async(req,res)=>{try{
 const url=new URL(req.url,'http://127.0.0.1');const origin=req.headers.origin;
 if(url.pathname==='/healthz'&&req.method==='GET')return respond(res,{status:'ok'});
 if(!authorized(req)){res.writeHead(401,{'WWW-Authenticate':'Basic realm="Frame Notes", charset="UTF-8"','Content-Type':'text/plain; charset=utf-8'});return res.end('需要访问密码。用户名：viewer')}
 const expectedOrigin=publicOrigin||`http://${req.headers.host}`;
 if(req.method==='POST'&&origin&&origin!==expectedOrigin)return respond(res,{error:'仅允许从本地页面发起请求。'},403);
 if(url.pathname==='/api/capabilities')return respond(res,{asr:true});
 if(url.pathname.startsWith('/api/jobs/')&&req.method==='GET'){const j=jobs.get(url.pathname.split('/').pop());return respond(res,j||{error:'任务不存在，请重新开始。'},j?200:404)}
 if(['/api/transcription','/api/transcribe-audio'].includes(url.pathname)&&req.method==='POST'){
  if(active()||creating)return respond(res,{error:'已有语音识别任务在运行，请等待完成。'},409);
  creating=true;try{
   if(url.pathname==='/api/transcription'){
    const body=JSON.parse((await readBody(req,4096)).toString());const id=videoId(body.url);
    if(!id)return respond(res,{error:'YouTube 链接无效。'},400);
    return respond(res,startJob({videoId:id}),202);
   }
   const id=randomUUID();const data=await readBody(req,200*1024*1024);
   if(!data.length)return respond(res,{error:'文件为空。'},400);
   await mkdir(root+'.runtime/'+id,{recursive:true});await writeFile(root+'.runtime/'+id+'/upload.audio',data);
   return respond(res,startJob({title:(url.searchParams.get('name')||'音频转写').slice(0,200)},id),202);
  }finally{creating=false}
 }
 const body=await readBody(req,4096);const response=await worker.fetch(new Request('http://127.0.0.1'+req.url,{method:req.method,headers:req.headers,...(!['GET','HEAD'].includes(req.method)?{body}:{})}));
 res.writeHead(response.status,Object.fromEntries(response.headers));res.end(Buffer.from(await response.arrayBuffer()));
}catch(e){respond(res,{error:e.status?e.message:'请求处理失败，请检查输入并重试。'},e.status||400)}});
const port=Number(process.env.PORT||8787);server.listen(port,process.env.HOST||'127.0.0.1',()=>console.log('Local: http://127.0.0.1:'+port));

process.on('SIGTERM',()=>{for(const child of children.values())child.kill();server.close(()=>process.exit(0));setTimeout(()=>process.exit(0),1000).unref()});
