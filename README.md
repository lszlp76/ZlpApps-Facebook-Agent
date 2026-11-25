# ZlpApps AutoPublisher V2.3

Tek Render Cron Job ile Industrial Chronometer için hazır Türkçe ve İngilizce fotoğraflı Facebook gönderileri. Her yayın gününde tek konu, iki ayrı paylaşım; her metinde Android ve iOS bağlantıları. Hazır içeriklerde Gemini çağrısı yapılmaz.

## Kurulum / güncelleme
Mevcut proje klasöründeki `agent.py` dosyasını değiştirin. Paket, V2.2 kataloğunu ve 10 görseli de içerir. Özel katalog değişiklikleriniz varsa bunları koruyun. `.env` ve `apps.json` dosyalarını koruyun. Python 3.10+ gerekir.

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m py_compile agent.py
AUTO_PUBLISH=false CONTENT_MODE=prepared python agent.py --preview-image
```
Önizleme yalnızca bugün eksik olan dil(ler) için `preview-tr.jpg` veya `preview-en.jpg` yazar. Önceki çalışmalardan kalan önizleme dosyaları otomatik silinmez. Logları esas alın. Bu işlem Facebook geçmişini okur ama gönderi oluşturmaz.

## Ortam değişkenleri
- `FACEBOOK_PAGE_ACCESS_TOKEN`: ZlpApps sayfasına ait geçerli Page Access Token (System User üzerinden elde edilebilir). Gizli tutun.
- `AUTO_PUBLISH`: yerelde `false`, Render'da gerçek yayın için `true`.
- `CONTENT_MODE`: `prepared`.
- `GEMINI_API_KEY`: yalnızca `--list-models` komutunda gerekir.

Sayfa kimliği `974029112458288`, API sürümü `v27.0`, saat dilimi `Europe/Istanbul` mevcut kodda sabittir.

## Render
Tek Cron Job, Schedule `0 9 * * 1,3,5` (Türkiye saati ile Pzt/Çar/Cum 12:00). Build: `pip install -r requirements.txt`. Command: `python agent.py --publish`. Diğer Cron Job'lar kapalı olmalıdır. GitHub'a `.env` veya token yüklemeyin.

```bash
git add agent.py README.md
git commit -m "V2.3 - paired publishing and language logs"
git pull --rebase origin main && git push origin main
```

## V2.3 yayın algoritması
1. Kataloğun her konusunda tam bir TR/EN çifti, eşsiz ID ve metin, geçerli görsel yolu ve her iki mağaza bağlantısı bulunmalıdır.
2. Facebook `/me` ile hedef sayfa doğrulanır; `/posts` üzerinden sayfalı geçmiş okunur.
3. Eski ilk paragraf karşılaştırması yerine, Unicode ve boşluk normalizasyonuyla tam metin eşleşmesi kullanılır. Mağaza linkleri eklenmeden önceki tam metin de eşleşme sayılır.
4. Bugün bir konuya ait gönderi bulunursa yalnızca o konu tamamlanır. Bugün EN varsa TR gönderilir, EN atlanır; tersi de geçerli. Daha önce başka bir tarihte yayınlanan TR/EN bugün için engel oluşturmaz.
5. Bugün kampanya yoksa iki dili de geçmişte tamamlanmamış ilk konu seçilir. Önceki gün yarım kalan konu yeni bir çift olarak paylaşılır; bu nedenle daha önce yayınlanan tek dil bir kez daha yayınlanabilir. Geçmişte iki dili de yayınlanan konular tamamlanmış kabul edilir (tarihleri farklı olsa bile). Bugün birden fazla konu tanınırsa güvenlik amacıyla durur.
6. TR sonra EN işlenir. Her dilin yayın hatası ayrı raporlanır; diğer dil denenir. Hata varsa program sıfır olmayan çıkış koduyla biter. POST otomatik tekrar denenmez.
7. Her iki dil bugün mevcutsa yayın yok. Tüm katalog bittiğinde yayın yok. Gemini ile yeni içerik üretme henüz yok.

## Bugünkü eksik TR paylaşımını tamamlama
Önce önizleme çalıştırın. `[TR] ÖNİZLEME` ve `[EN] ATLANDI` beklenir (EN metni katalogla eşleşiyorsa). Facebook'ta gerçekten yalnızca EN olduğunu doğrulayın. Render'da yeni commit dağıtıldıktan sonra, aynı yayın günü içerisinde tek kez **Trigger Run** yapabilirsiniz. Çalışma sırasında ikinci bir tetikleme yapmayın. Özetin `yeni yayın=1, bugün mevcut=1, hata=0` olması beklenir.

## Sınırlamalar
Kalıcı veritabanı yoktur. Silinen, düzenlenen, API'nin döndürmediği veya katalogla eşleşmeyen içerikler yanlışlıkla yeniden seçilebilir. Önceki iki dili farklı tarihlerde yayınlanmış konular geriye dönük eşleştirilmez. Eşzamanlı işlerde veya Facebook geçmişinin gecikmeli güncellendiği durumlarda kesin tek-sefer garantisi yoktur. Ağ zaman aşımından sonra tekrar çalıştırmadan önce Facebook sayfasını kontrol edin. Token geçersizliği, API erişim seviyesi ve kota hataları ayrıca çözülmelidir. Canlı API testi yapılmamıştır. Python derleme ve yerel seçim/katalog kontrolleri yapılmıştır.
