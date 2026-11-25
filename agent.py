"""ZlpApps AutoPublisher V2.3 — paired prepared posts."""
import argparse
import datetime
import json
import os
import shutil
import sys
import unicodedata
from pathlib import Path
from zoneinfo import ZoneInfo

PAGE = '974029112458288'
TZ = ZoneInfo('Europe/Istanbul')
ROOT = Path(__file__).resolve().parent


def log(message):
    print(message, flush=True)


def norm(text):
    return ' '.join(unicodedata.normalize('NFC', text or '').split())


def variants(message):
    # Accept the full caption or the exact original caption before store links.
    original = '\n'.join(line for line in message.splitlines()
                         if not line.startswith(('📲 Google Play (Android):', '🍎 App Store (iOS):')))
    return {norm(message), norm(original)} - {''}


def validate(queue, root):
    if not isinstance(queue, list) or not queue:
        raise RuntimeError('Katalog boş veya hatalı')
    topics, ids, captions = {}, set(), {}
    for item in queue:
        if not all(isinstance(item.get(k), str) and item[k].strip() for k in
                   ('id', 'topic', 'language', 'title', 'message', 'image')):
            raise RuntimeError('Katalog alanı eksik')
        lang = item['language'].lower()
        if lang not in ('tr', 'en') or item['id'] in ids:
            raise RuntimeError('Geçersiz dil veya yinelenen ID')
        ids.add(item['id'])
        pair = topics.setdefault(item['topic'], {})
        if lang in pair:
            raise RuntimeError('Aynı konuda yinelenen dil')
        pair[lang] = item
        path = (root / item['image']).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise RuntimeError('Görsel eksik veya geçersiz dosya yolu: ' + item['id'])
        if not all(link in item['message'] for link in ('https://play.google.com/store/apps/details?id=com.lszlp.choronometre', 'https://apps.apple.com/app/industrial-chronometer/id1613303230')):
            raise RuntimeError('Mağaza bağlantısı eksik: ' + item['id'])
        for caption in variants(item['message']):
            if caption in captions and captions[caption] != item['id']:
                raise RuntimeError('Katalogda aynı metin birden çok gönderiye ait')
            captions[caption] = item['id']
    if any(set(pair) != {'tr', 'en'} for pair in topics.values()):
        raise RuntimeError('Her konuda tam bir TR ve EN çifti olmalı')
    return topics, captions


def history(graph, captions, today):
    dates = {}
    after = None
    cursors = set()
    for _ in range(500):
        params = {'fields': 'id,message,created_time', 'limit': 100}
        if after:
            params['after'] = after
        batch = graph('GET', PAGE + '/posts', params=params)
        if not isinstance(batch.get('data'), list):
            raise RuntimeError('Gönderi geçmişi okunamadı')
        for post in batch['data']:
            item_id = captions.get(norm(post.get('message')))
            if item_id:
                stamp = datetime.datetime.fromisoformat(post['created_time'])
                if stamp.tzinfo is None:
                    raise RuntimeError('Gönderi tarihi saat dilimi eksik')
                day = stamp.astimezone(TZ).date()
                dates.setdefault(item_id, set()).add(day)
                log(f'[HISTORY] {item_id}: {day} | {post.get("id", "?")}')
        paging = batch.get('paging', {})
        if not paging.get('next'):
            return dates
        after = paging.get('cursors', {}).get('after')
        if not after or after in cursors:
            raise RuntimeError('Geçmiş sayfalama hatası; yayın durduruldu')
        cursors.add(after)
    raise RuntimeError('Geçmiş sınırı aşıldı; yayın durduruldu')


def plan(topics, dates, today):
    active = [topic for topic, pair in topics.items() if any(today in dates.get(item['id'], set()) for item in pair.values())]
    if len(active) > 1:
        raise RuntimeError('Bugün birden fazla konu tespit edildi; yayın durduruldu')
    if active:
        topic = active[0]
    else:
        # A topic is finished if both language versions have ever been posted.
        # A partially published older topic is restarted as a same-day pair.
        topic = next((t for t, pair in topics.items() if not all(dates.get(i['id']) for i in pair.values())), None)
    if topic is None:
        return None, []
    return topic, [(lang, topics[topic][lang], today in dates.get(topics[topic][lang]['id'], set())) for lang in ('tr', 'en')]


def main():
    import requests
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env')
    parser = argparse.ArgumentParser()
    parser.add_argument('--list-models', action='store_true')
    parser.add_argument('--publish', action='store_true')
    parser.add_argument('--preview-image', action='store_true')
    args = parser.parse_args()
    if args.list_models:
        from google import genai
        client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])
        for model in client.models.list():
            if 'pro' in model.name.lower(): log(model.name)
        return
    log('ZLPAPPS AUTOPUBLISHER V2.3')
    if args.preview_image and args.publish:
        raise RuntimeError('Önizleme ve yayın birlikte kullanılamaz')
    now = datetime.datetime.now(TZ)
    if args.publish:
        if os.getenv('AUTO_PUBLISH', 'false').lower() != 'true':
            raise RuntimeError('AUTO_PUBLISH kapalı')
        if now.weekday() not in (0, 2, 4):
            raise RuntimeError('Yayın günü değil')
    if os.getenv('CONTENT_MODE', 'prepared').lower() != 'prepared':
        raise RuntimeError('V2.3 yalnızca CONTENT_MODE=prepared destekler')
    topics, captions = validate(json.loads((ROOT / 'prepared_posts.json').read_text(encoding='utf-8')), ROOT)
    token = os.environ['FACEBOOK_PAGE_ACCESS_TOKEN'].strip()
    if not token: raise RuntimeError('Page Token boş')
    base = 'https://graph.facebook.com/v27.0/'
    headers = {'Authorization': 'Bearer ' + token}

    def graph(method, path, **kwargs):
        r = requests.request(method, base + path, headers=headers, timeout=45, **kwargs)
        try: data = r.json()
        except ValueError: raise RuntimeError(f'Meta HTTP {r.status_code}; JSON yanıt yok') from None
        if not r.ok or 'error' in data:
            error = data.get('error', {})
            raise RuntimeError(f'Meta HTTP {r.status_code}; code={error.get("code")}; subcode={error.get("error_subcode")}')
        return data

    identity = graph('GET', 'me', params={'fields': 'id,name'})
    if identity.get('id') != PAGE: raise RuntimeError('Yanlış sayfa tokenı')
    log(f'Sayfa doğrulandı: {PAGE} | {now.isoformat()}')
    dates = history(graph, captions, now.date())
    topic, items = plan(topics, dates, now.date())
    if topic is None:
        log('Hazır kampanya tamamlandı. Yayın yok.')
        return
    log(f'Konu: {topic}')
    counts = {'published': 0, 'skipped': 0, 'failed': 0, 'preview': 0}
    for lang, item, already_today in items:
        prefix = '[' + lang.upper() + ']'
        if already_today:
            log(f'{prefix} ATLANDI: bugün zaten yayınlandı ({item["id"]})')
            counts['skipped'] += 1
            continue
        if dates.get(item['id']):
            log(f'{prefix} Önceki tarihte yayın var; aynı gün dil çiftini tamamlamak için yeniden paylaşılacak.')
        path = ROOT / item['image']
        if not args.publish:
            log(f'{prefix} ÖNİZLEME: {item["id"]}\n{item["message"]}')
            if args.preview_image:
                dest = Path(f'preview-{lang}.jpg')
                shutil.copyfile(path, dest)
                log(f'{prefix} Görsel: {dest}')
            counts['preview'] += 1
            continue
        log(f'{prefix} Yayın başlatıldı: {item["id"]}')
        try:
            with path.open('rb') as f:
                result = graph('POST', PAGE + '/photos', data={'caption': item['message'], 'published': 'true'}, files={'source': (path.name, f, 'image/jpeg')})
            post_id = result.get('post_id') or result.get('id')
            if not post_id: raise RuntimeError('Meta yanıtında gönderi ID yok')
            log(f'{prefix} Published: {item["id"]} {post_id}')
            counts['published'] += 1
        except Exception as e:
            # No automatic POST retries: a timeout might hide a successful publication.
            log(f'{prefix} HATA: {type(e).__name__}' + (f' | {e}' if isinstance(e, RuntimeError) else ''))
            counts['failed'] += 1
    log(f'ÖZET: yeni yayın={counts["published"]}, bugün mevcut={counts["skipped"]}, hata={counts["failed"]}, önizleme={counts["preview"]}')
    if not args.publish: log('DRY RUN: yayın yapılmadı.')
    if counts['failed']: raise RuntimeError('En az bir dil başarısız; tekrar çalıştırmadan önce Facebook geçmişini kontrol edin.')


if __name__ == '__main__':
    try: main()
    except Exception as e:
        print('İşlem başarısız:', type(e).__name__, file=sys.stderr)
        if isinstance(e, RuntimeError): print(str(e), file=sys.stderr)
        sys.exit(1)
