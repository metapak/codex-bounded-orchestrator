# X Autopilot Phase 2

Tek hesap için Luna-only araştırma, taslak üretimi ve insan onaylı X yayını. Codex geliştirme ajanları ile sunucudaki model çağrıları ayrıdır: runtime yalnız `gpt-5.6-luna` kullanır; Sol ve Astra kapalıdır.

## Kurulum

Python 3.14 önerilir. Yerel SQLite için Phase 1 verileri korunur; cloud için PostgreSQL zorunludur.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# Yalnız config henüz yoksa kopyalayın; var olan kişisel ayarları koruyun.
cp config/x-autopilot.example.toml config/x-autopilot.toml
python3 -m x_autopilot init-db
python3 -m x_autopilot review
```

Windows'ta sanal ortam Python'u `.venv\Scripts\python.exe` altındadır. `.env.example` yalnız isimleri açıklar; uygulama `.env` dosyalarını otomatik yüklemez. Gerçek anahtarları ortam/secrets içinde tutun.

`review` yalnız paneli açar. `serve` panelle beraber sürekli scheduler başlatır; yayın kontrolü araştırma ve model çağrılarından bağımsız bir döngüde çalışır. `worker` yalnız scheduler çalıştırır. `scheduler-tick` tek kontrol yapıp çıkar; `research`, `generate`, `run` elle tetikleme komutlarıdır. Elle `generate/run` günlük scheduler kotasından bağımsızdır; tekrar çağırmak ek API maliyeti yaratır.

## Luna ve içerik güvenilirliği

En fazla 4 aday için toplu üretim ve toplu kanıt incelemesi yapılır; model ve provider arayüzleri korunur. Sıfır otomatik model tekrarı, kısıtlı kaynak metinleri ve token sınırları maliyeti kontrol eder. Üretim limiti kabul edilenlere değil toplam adaylara uygulanır.

Kalıcı prompt günlük, doğal Türkçe; kısa cümleler, gözlem, hafif mizah, SaaS/app/AI/developer fikirleri ister. Emoji, kurumsal dil, yapay clickbait, zorunlu soru/hook ve kullanıcı taklidi yoktur. Örnekler kopyalanmaz. Kullanıcı adına gerçekleşmiş kişisel deneyim uydurulamaz. `app.verified_user_context` yalnız hesap sahibinin gerçekten doğruladığı proje/deneyim bilgileri içindir; boş liste varsayılandır.

Model çıktısı güvenilir talimat sayılmaz. Sayısal/olgusal iddialar, kaynak sahipliği, eksik veya uydurma claim/evidence referansları ve kişisel deneyim sinyalleri kontrollerden geçer. Kanıtı geçmeyen taslak onaylanamaz; edit edilip yeniden doğrulanır. Doğal dil kontrolleri kusursuz bir doğruluk kanıtı değildir. Son editoryal sorumluluk insan onayındadır.

## Review ve yayın

`pending → approved → scheduled → publishing → published`

Onaylanan bir taslak ayrıca **Şimdi yayınla** ile doğrudan gönderilebilir. Kaydetmek ya da tekrar doğrulamak önceki onay ve zamanlamayı geçersizleştirir. Her değişiklik revizyonu artırır; eski sayfadan gönderilen işlemler reddedilir. Kaynaklar, evidence, model ve maliyet kayıtları panelde görünür.

`X_PUBLISH_ENABLED=false` varsayılandır. `true` yalnız gönderme özelliğini açar; içerikleri kendi kendine onaylamaz. Scheduler sadece onaylanıp zamanı gelmiş taslaklara bakar. Pending/rejected taslaklar hiçbir yayın yolundan geçemez.

X API `POST /2/tweets` sunucu tarafında idempotency anahtarı sunmadığından ağ kesilmesinde tam exactly-once teslim garantisi verilemez. Veritabanındaki atomik claim ve kalıcı gönderim kaydı aynı taslağa ikinci gönderim denemesini engeller. Timeout, bozuk yanıt veya gönderim sırasında süreç çökmesi otomatik tekrar edilmez; `publish_unknown` veya `publishing` panelde görünür. X hesabındaki paylaşım geçmişi kontrol edilmeden aynı metni yeni taslak olarak göndermeyin. `publish_failed` kesin hata durumudur. Bu ilk sürümde hata durumları için otomatik retry/requeue yoktur.

Otomatik reply, DM, takip, like, repost, görsel/video ve çoklu hesap yoktur.

## X hesabı

Resmî OAuth 1.0a user context kullanılır. X Developer App'in yazma izni bulunmalıdır. Tek hesap için uygulama panelinden o hesaba ait access token/secret alınır; izin değiştiyse token yeniden oluşturulur.

Ortam değişkenleri: `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_TOKEN_SECRET`. Tokenlar DB veya repoya yazılmaz. Yönlendirme ve otomatik POST retry kapalıdır. Başarılı gönderimde X post ID ve UTC zaman damgası saklanır.

Gerçek test tweeti için hesap sahibinden içerik ve paylaşım konusunda açık onay alınmalıdır. Mock testler gerçek X'e gitmez.

## Scheduler

Örnek config İstanbul saatini (`Europe/Istanbul`), 6 saatlik kaynak taramasını, her gün 09:00 sonrası bir kez en fazla 4 aday üretimini ve 60 saniyelik yayın kontrolünü ayarlar. `scheduler` bölümünden saat, gün aralığı, araştırma/yayın periyodu ve kontrol sıklığı değişir. `SCHEDULER_ENABLED=false` bütün periyodik işleri durdurur.

İş aralıkları PostgreSQL/SQLite içinde benzersiz kayıtlarla claim edilir. Yeniden başlatma veya ikinci süreç aynı günlük üretimi tekrarlamaz. Başarısız ya da çökmüş üretim aralığı tekrar denenmez; maliyetli tekrar yerine sonraki plan beklenir. Uzun süre kapalı kalan servis geçmiş günleri topluca üretmez. UI onay/zamanlamaları kalıcıdır. Birden çok süreçte cloud PostgreSQL kullanılır; Railway varsayılanı tek replica'dır.

## Railway

Dockerfile, `railway.json` ve `config/x-autopilot.cloud.toml` hazırdır. Docker imajı yalnız uygulama ve cloud config'i alır; yerel DB, kişisel config ve secrets dışlanır. Ayrı bir PostgreSQL servisi ekleyin, uygulamada `DATABASE_URL` değişkenini `${{Postgres.DATABASE_URL}}` referansına bağlayın. Cloud modunda SQLite fallback yoktur. Başlangıç migration'ları uygulanır; kısa DB başlangıç gecikmelerinde sınırlı tekrar vardır.

Uygulama başlangıcı:

```sh
python -m x_autopilot --config config/x-autopilot.cloud.toml serve
```

Gerekli değişkenler:

| Ad | Değer / kullanım |
| --- | --- |
| `DATABASE_URL` | PostgreSQL servis referansı |
| `OPENAI_API_KEY` | Luna Responses erişimi; secret |
| `PUBLIC_URL` | Railway HTTPS origin, ör. `https://your-service.up.railway.app` |
| `REVIEW_USERNAME` | Tek inceleyici kullanıcı adı |
| `REVIEW_PASSWORD` | En az 20 karakter, benzersiz secret |
| `X_PUBLISH_ENABLED` | İlk kurulum `false` |
| `SCHEDULER_ENABLED` | Normal servis `true` |
| `PORT` | Railway tarafından sağlanır |

X secrets yalnız yayınlama açılacağı zaman gerekir. Kimlik doğrulama HTTP Basic üzerinden, yalnız HTTPS dış erişimle yapılır. Uzak bind kimlik bilgisi veya HTTPS origin olmadan açılmaz. Local loopback panel geliştirme için parolasız kalabilir. `/health` ve `/ready` gizli veri içermez; `/ready` DB ve birleşik servis scheduler sağlığını denetler. Railway healthcheck deploy anındaki kontroldür; sürekli dış izleme yerine geçmez.

Railway hesabında CLI oturumu veya uygun proje tokenı gerekir. `railway link` ile doğru projeyi doğrulayın, app ve Postgres servislerini seçin, secretları Railway Variables ekranından tanımlayın ve uygulamayı `railway up` ile yükleyin. Bu bir hazır kurulum tarifidir; dosyaların varlığı başarılı canlı deploy kanıtı değildir. Yeni servisin URL'sinde auth, `/ready`, worker kayıtları ve DB kalıcılığı ayrıca doğrulanmalıdır.

## SQLite verisini PostgreSQL'e taşıma

`DATABASE_URL` boş bir PostgreSQL hedefine işaret ederken `python -m x_autopilot import-sqlite /absolute/path/source.sqlite3` çalıştırılabilir. Komut kaynağı salt okunur ve tutarlı bir transaction içinde okur; kimlikleri/ilişkileri korur, PostgreSQL sequence değerlerini günceller. Hedefte herhangi bir uygulama verisi varsa kopyalamayı reddeder; hata halinde kopyalama tamamen geri alınır. Kaynak SQLite değiştirilmez. Aktarımdan sonra cloud panelinde kayıt sayıları ve durumları kontrol edilmeden yayınlamayı açmayın.

## Test ve maliyet

```sh
python scripts/validate.py
python -m unittest discover -s tests -v
```

PostgreSQL entegrasyon testleri yalnız ayrılmış test DB'sinde çalıştırılır; `XAP_TEST_DATABASE_URL` bağlantı değişkenini kullanın. Gerçek X/OpenAI credential'ı testler için gerekmez. Model çağrılarında giriş/çıkış, cache tokenları ve fiyat kaynağına bağlı tahmini USD kayıtları tutulur; çıkış içindeki reasoning tokenları ikinci kez eklenmez.

11 Eylül 2026 Luna deneyinde tek çağrıyla 15 ham adayın üretimi yaklaşık **0.00199205 USD**, aday başına **0.00013280333 USD** idi. Bu geçmiş deneydir; Phase 2'nin toplu kontrolü ve onaylanan/yayınlanan tweet başı gerçek maliyeti değildir. X API, Railway/Postgres ve Codex geliştirme giderleri dahil değildir.

## Resmî kaynaklar

- [X post entegrasyonu](https://docs.x.com/x-api/posts/manage-tweets/integrate)
- [OAuth 1.0a kullanıcı tokenları](https://docs.x.com/fundamentals/authentication/oauth-1-0a/obtaining-user-access-tokens)
- [Railway Dockerfiles](https://docs.railway.com/builds/dockerfiles)
- [Railway healthchecks](https://docs.railway.com/deployments/healthchecks)
- [Railway PostgreSQL](https://docs.railway.com/databases/postgresql)
- [Luna modeli ve fiyatları](https://developers.openai.com/api/docs/models/gpt-5.6-luna)
