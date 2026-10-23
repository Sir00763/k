"""Local audio transcription; progress is emitted as JSON lines."""
import json, os, re, sys, threading
from pathlib import Path

def emit(**event):
 print(json.dumps(event,ensure_ascii=False),flush=True)

def run(data):
 from faster_whisper import WhisperModel
 from yt_dlp import YoutubeDL
 runtime=Path(__file__).resolve().parents[1]/'.runtime'
 runtime.mkdir(exist_ok=True)
 job_id=data['jobId']
 if not re.fullmatch(r'[a-f0-9-]{36}',job_id): raise ValueError('无效的任务编号。')
 folder=runtime/job_id
 folder.mkdir(exist_ok=True)
 title=data.get('title','音频转写')
 video_id=data.get('videoId')
 if video_id:
  if not re.fullmatch(r'[\w-]{11}',video_id): raise ValueError('视频编号无效。')
  cache=runtime/f'{video_id}.json'
  if cache.exists():
   emit(status='done',result=json.loads(cache.read_text()));return
  emit(status='checking_subtitles',message='正在检查视频字幕；没有可用字幕时将自动识别语音…')
  try:
   from youtube_transcript_api import YouTubeTranscriptApi
   from requests import Session
   class TimedSession(Session):
    def request(self,*args,**kwargs):
     kwargs.setdefault('timeout',12)
     return super().request(*args,**kwargs)
   with TimedSession() as session:
    tracks=list(YouTubeTranscriptApi(http_client=session).list(video_id))
    preferred=['zh','zh-CN','zh-Hans','zh-Hant','en']
    tracks.sort(key=lambda t:(preferred.index(t.language_code) if t.language_code in preferred else len(preferred),t.is_generated))
    transcript=tracks[0].fetch()
    snippets=[{'start':round(t.start,2),'text':t.text.strip()} for t in transcript if t.text.strip()]
    if snippets:
     payload={'title':'视频文稿 · '+video_id,'videoId':video_id,'language':transcript.language_code,'segments':snippets,'source':'subtitles'}
     try:
      r=session.get('https://www.youtube.com/oembed',params={'url':'https://www.youtube.com/watch?v='+video_id,'format':'json'},timeout=8)
      if r.ok:payload['title']=r.json().get('title') or payload['title']
     except Exception:pass
     cache.write_text(json.dumps(payload,ensure_ascii=False));emit(status='done',result=payload);return
  except Exception:pass
  emit(status='downloading',message='未读到可用字幕，正在自动读取音轨并识别语音…')
  class QuietLogger:
   def debug(self,msg): pass
   def warning(self,msg): pass
   def error(self,msg): pass
  def length_filter(info,*,incomplete):
   if (info.get('duration') or 0)>7200:return '目前仅支持 2 小时以内的视频。'
   if info.get('is_live'):return '暂不支持正在直播的视频。'
  media=runtime/'media'/video_id;media.mkdir(parents=True,exist_ok=True)
  known=[p for p in media.glob('audio.*') if p.suffix not in ('.part','.ytdl')]
  options={'format':'bestaudio[ext=m4a]/bestaudio/best','outtmpl':str(media/'audio.%(ext)s'),'noplaylist':True,'quiet':True,'no_warnings':True,'logger':QuietLogger(),'socket_timeout':20,'retries':1,'extractor_retries':1,'match_filter':length_filter,'js_runtimes':{'node':{'path':os.environ.get('FRAME_NODE','node')}}}
  if known:
   audio=known[0]
   if (media/'title.json').exists():title=json.loads((media/'title.json').read_text())
  else:
   with YoutubeDL(options) as ydl:
    info=ydl.extract_info('https://www.youtube.com/watch?v='+video_id,download=True)
    title=info.get('title') or title
    audio=Path(ydl.prepare_filename(info))
    (media/'title.json').write_text(json.dumps(title,ensure_ascii=False))
  if not audio.exists():raise ValueError('无法下载音轨，请上传音频文件识别。')
 else:
  audio=folder/'upload.audio'
  if not audio.is_file():raise ValueError('未找到上传的音频文件。')
 emit(status='loading_model',message='正在加载本地语音模型，首次使用会下载模型文件…')
 stop=threading.Event()
 def model_progress():
  while not stop.wait(5):
   downloaded=sum(p.stat().st_size for p in (runtime/'models').rglob('*') if p.is_file() and not p.is_symlink())
   emit(status='loading_model',message=f'正在准备本地模型 · 已缓存 {downloaded//1048576} MB，首次使用需要下载…')
 reporter=threading.Thread(target=model_progress,daemon=True);reporter.start()
 try:
  model_name=os.environ.get('FRAME_WHISPER_MODEL','base')
  snapshots=runtime/'models'/('models--Systran--faster-whisper-'+model_name)/'snapshots'
  cached=[p for p in snapshots.glob('*') if (p/'model.bin').exists() and (p/'config.json').exists()]
  model=WhisperModel(str(cached[0]) if cached else model_name,device='cpu',compute_type='int8',cpu_threads=4,download_root=str(runtime/'models'))
 finally:stop.set()
 segments,info=model.transcribe(str(audio),beam_size=3,vad_filter=True)
 if info.duration>7200:raise ValueError('目前仅支持 2 小时以内的音频。')
 emit(status='transcribing',message='正在语音识别，请保持页面开启…',progress=0)
 result=[];last_progress=-5
 for segment in segments:
  if segment.text.strip():result.append({'start':round(segment.start,2),'text':segment.text.strip()})
  progress=min(99,int(segment.end/max(info.duration,1)*100))
  if progress>=last_progress+5:
   emit(status='transcribing',message=f'正在语音识别 · {progress}%',progress=progress);last_progress=progress
 if not result:raise ValueError('没有识别出语音，请检查音频是否包含清晰的人声。')
 payload={'title':title,'videoId':video_id,'language':info.language,'segments':result,'source':'speech-recognition'}
 if video_id:cache.write_text(json.dumps(payload,ensure_ascii=False))
 emit(status='done',result=payload)
 audio.unlink(missing_ok=True)

if __name__=='__main__':
 try:run(json.loads(sys.stdin.readline()))
 except ImportError:emit(status='error',code='DEPENDENCY_MISSING',message='语音识别依赖未安装，请按运行说明安装 requirements.txt。');sys.exit(1)
 except Exception as error:
  name=type(error).__name__
  if name in ('DownloadError','ExtractorError'):text='YouTube 音轨下载失败或访问受限。请使用「音频识别」上传本地音频文件。'
  elif isinstance(error,ValueError):text=str(error)
  else:text='本地语音识别失败，请检查网络和模型下载，重试或更换音频文件。'
  emit(status='error',code=name,message=text);sys.exit(1)
