import os, json, argparse, datetime, sys, shutil, unicodedata
from zoneinfo import ZoneInfo
from pathlib import Path
import requests
from dotenv import load_dotenv
from google import genai
load_dotenv()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--list-models',action='store_true')
    parser.add_argument('--publish',action='store_true')
    parser.add_argument('--preview-image',action='store_true')
    args=parser.parse_args()
    if args.list_models:
        client=genai.Client(api_key=os.environ['GEMINI_API_KEY'])
        for m in client.models.list():
            if 'pro' in m.name.lower(): print(m.name)
        return
    page='974029112458288'
    base='https://graph.facebook.com/v27.0/'
    headers={'Authorization':'Bearer '+os.environ['FACEBOOK_PAGE_ACCESS_TOKEN']}
    def graph(method,path,**kwargs):
        r=requests.request(method,base+path,headers=headers,timeout=45,**kwargs)
        if not r.ok:
            raise RuntimeError(f'Meta HTTP {r.status_code}; code={r.json().get("error",{}).get("code")}')
        return r.json()
    identity=graph('GET','me',params={'fields':'id,name'})
    if identity['id']!=page: raise RuntimeError('Yanlış sayfa tokenı')
    now=datetime.datetime.now(ZoneInfo('Europe/Istanbul'))
    if args.preview_image and args.publish:
        raise RuntimeError('Önizleme ve yayın birlikte kullanılamaz')
    if args.publish:
        if os.getenv('AUTO_PUBLISH','false').lower()!='true': raise RuntimeError('AUTO_PUBLISH kapalı')
        if now.weekday() not in (0,2,4): raise RuntimeError('Yayın günü değil')
    if os.getenv('CONTENT_MODE','prepared').lower() != 'ai':
        directory=Path(__file__).resolve().parent
        queue=json.loads((directory/'prepared_posts.json').read_text(encoding='utf-8'))
        def norm(text):
            return ' '.join(unicodedata.normalize('NFC',text or '').split())
        seen=set(); today_topics=set(); after=None; cursors=set()
        for _ in range(500):
            params={'fields':'message,created_time','limit':100}
            if after: params['after']=after
            batch=graph('GET',page+'/posts',params=params)
            for post in batch.get('data',[]):
                msg=norm(post.get('message',''))
                for item in queue:
                    if msg.startswith(norm(item['message'].split('\n\n')[0])):
                        seen.add(item['id'])
                        if post.get('created_time') and datetime.datetime.fromisoformat(post['created_time']).astimezone(now.tzinfo).date()==now.date():
                            today_topics.add(item['topic'])
            paging=batch.get('paging',{})
            if not paging.get('next'): break
            after=paging.get('cursors',{}).get('after')
            if not after or after in cursors: raise RuntimeError('Gönderi geçmişi okunamadı; yayın durduruldu')
            cursors.add(after)
        else: raise RuntimeError('Gönderi geçmişi sınırı aşıldı; yayın durduruldu')
        if len(today_topics)>1: raise RuntimeError('Bugün birden çok kampanya konusu var; yayın durduruldu')
        topic=next(iter(today_topics),None) or next((p['topic'] for p in queue if p['id'] not in seen),None)
        pending=[p for p in queue if p['topic']==topic and p['id'] not in seen]
        if not pending:
            print('Bugünkü konu tamamlandı veya hazır gönderi kalmadı. Yayın yok.'); return
        for item in pending:
            path=directory/item['image']
            if not path.is_file(): raise RuntimeError('Hazır gönderi görseli eksik')
        for item in pending:
            path=directory/item['image']
            print('Hazır gönderi:',item['id'],item['title'])
            print(item['message'])
            if not args.publish:
                if args.preview_image:
                    dest=Path('preview-'+item['language']+'.jpg')
                    shutil.copyfile(path,dest); print('Görsel önizleme:',dest)
                continue
            with path.open('rb') as f:
                result=graph('POST',page+'/photos',data={'caption':item['message'],'published':'true'},files={'source':(path.name,f,'image/jpeg')})
            print('Published:',item['id'],result.get('post_id') or result['id'],flush=True)
        if not args.publish: print('DRY RUN: yayın yapılmadı.')
        return
    raise RuntimeError('V2.2: çift dilli hazır kampanya için CONTENT_MODE=prepared kullanın; AI modu bu sürümde devre dışı')

if __name__=='__main__':
    try: main()
    except Exception as e:
        # Do not print exception payloads that could contain credentials.
        print('İşlem başarısız:',type(e).__name__,file=sys.stderr)
        if isinstance(e,RuntimeError): print(str(e),file=sys.stderr)
        sys.exit(1)
