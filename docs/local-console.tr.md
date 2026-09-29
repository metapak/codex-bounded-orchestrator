[English](local-console.md) | [Türkçe](local-console.tr.md)

# Yerel konsol

Python 3.11 veya yenisi ile, açılmış installer deposundan çalıştırın:

```sh
python3 scripts/dashboard.py /hedef/depo
# Windows: py -3 scripts/dashboard.py C:\hedef\depo
```

Tarayıcı varsayılan olarak açılır. `--no-browser` açmayı kapatır; `--port 8765` yerel portu seçer (`0` boş port ister). Yazdırılan `http://127.0.0.1:PORT` adresini kullanın ve terminali açık bırakın. Ctrl+C sunucuyu durdurur. npm veya üçüncü taraf Python paketi gerekmez. Başlatıcı ve HTML/CSS/JS kaynak, macOS ve Windows paketlerine dahildir. Konsol installer deposundan çalışır ve hedef projeye kopyalanmaz. Kurulmuş salt okunur kullanım aracı `python .codex/tools/usage_report.py --json` ile çalışmaya devam eder.

**Tercihler**, **Kullanım**, **Çalışmalar** sekmeleri vardır. Türkçe / English seçimi sayfayı yenilemeden dili değiştirir ve bu tarayıcıda seçimi hatırlar. Ana ekranda sade çalışma biçimleri ile şu anki ve kaydedilecek tercih özeti görünür. Modeller, tam dosya değişiklikleri ve seçili oturum klasörü İleri ayarlar veya Ayrıntıları göster altında bulunur. Ayarlar seçilen projeye uygulanır; kullanıcı geneli kurulumu desteklenmez. Mevcut rol modeli/eforu ve eşzamanlılık proje dosyalarından okunur. Yeni hedefte `focused` başlar; mevcut hedefin seçimi korunur. Profiller yönlendirme niyetidir; hesap yeteneği keşfi yapılmaz. GPT model kimliklerini ve modele bağlı reasoning erişimini yeni Codex oturumunda doğrulayın. Eşzamanlılık 1–10 aralığındadır; çalışma zamanı/hesap sınırı önceliklidir.

**Önizleme** seçilen alanları doğrular; tam ayar satırı farklarını ve yönetilen dosya işlemlerini gösterir. İlgisiz gizli alanların görünmemesi için diff bağlamı sıfırdır. **Kaydet** yalnız seçilen hedefe yazar; installer ile önceki yapılandırmayı yedekler, sahiplik/hash kaydını günceller, ilgisiz TOML alanlarını ve AGENTS metnini korur. Installer sahipliğindeki değişmemiş dosyalar güncellenebilir. Değişmiş veya sahip olunmayan rol/araç/skill çakışmaları kaydetmeyi engeller; önce CLI installer ile açıkça uzlaştırın. Symlink hedefleri reddedilir. Bozuk TOML hatadır; sessizce yenisiyle değiştirilmez. Önizleme sonrası dosya değişirse yeni önizleme gerekir.

**Geri yükle**, hemen önceki konsol değişikliğinin dosya içeriklerini ve installer manifestini geri getirir. Kaydet sonrası değişmiş dosya varsa işlemi reddeder. Snapshot/yedekler Git tarafından yok sayılan `.codex/.bounded-orchestrator` altında yerel kalır; önceki yapılandırmanızı içerebilir ve API'de gösterilmez. İlk kurulumu geri yüklemek yeni yönetilen dosyaları kaldırır; installer yedekleri kaldığında runtime ignore dosyası korunur, böylece önceki yapılandırma içerikleri Git tarafından eklenmez. CLI uninstall mevcut sahiplik/çakışma kurallarını kullanır; konsol başlatıcısı yalnız installer deposundadır, yerel snapshot/yedekler yok sayılan runtime verisi olarak kalır.

Sunucu yalnız `127.0.0.1` dinler. Yazma isteğinde rastgele CSRF tokenı, eşleşen Origin/Host, JSON türü ve sınırlı gövde gerekir. Web girdisi shell komutuna girmez. Tarayıcı yalnız seçilen ayar değerlerini ve kullanım metadatasını alır; kimlik bilgileri veya konuşma metni almaz.

Kullanım, `token_usage_record.payload.usage` alanını istek kullanımı olarak toplar; `thread_token_usage` ile delta hesaplamaz. 29.268 ve 32.426 istekleri 61.694 toplam verir. Eski `event_msg/token_count.info.total_token_usage` kümülatif sayaçlarında delta ve reset algılaması vardır. İki biçim bir thread içinde bulunursa istek kayıtları önceliklidir. Zaman/istek kimliği olan tekrarlar atlanır; kimliksiz eşit istekler ayrı gerçek istek olabileceği için korunur. Eksik metadata `unknown` olur. Tarih/proje/thread filtreleri yalnız bulunan metadataya dayanır; tarih filtresinde zamanı bilinmeyen kayıtlar dışlanır. Önbellek girişe, reasoning çıkışa zaten dahildir. Kota yüzdesi, ölçülmemiş tasarruf veya fiyat çıkarılmaz. Güvenilir fiyat metadatası olmadığında maliyet kullanılamaz. Karışık biçimler, resetler ve eksik kayıtlar kapsamı sınırlar.

Kullanım grafikleri aynı gözlenen toplam tokenı modele ve çalışma biçimine göre ayırır; önbellekteki giriş ikinci kez eklenmez. Model, varsa `turn_context` olayından okunur; bilinmeyen kullanım ayrı gösterilir. Codex oturum kaydı seçilen konsol çalışma biçimini içermez. Konsol Kaydet/Geri yükle zamanlarını, seçilen biçimi ve model ayarlarını hedefin Git tarafından yok sayılan `.codex/.bounded-orchestrator/console-style-history.json` dosyasında tutar. Biçim grafiği her turu ancak `turn_id` ile zamanlı `turn_context`, kullanım ve `task_complete`/`turn_aborted` eşleşiyorsa, proje aynıysa, tur Kaydet sonrasında başlayıp sonraki Kaydet/Geri yükle öncesinde bitiyorsa tahminle eşler. Eski veya bitmemiş turlar, eksik kimlik/zaman, ayar değişikliğini aşan turlar ve diğer projeler bilinmeyen kalır. Tek oturumda farklı biçimlere bağlanan turlar bulunabilir. Elle yapılan ayar değişiklikleri görülemediğinden bu bir tahmindir; fatura veya karşılaştırmalı tasarruf ölçüsü değildir. Demo verisi iki uydurma tur, model ve biçim içerir; örnek etiketi görünür.

Görev ayrıntıları thread grupları ve zamanlı token kayıtlarını gösterir; token olaylarından görev tamamlanması veya araç kullanımı çıkarılmaz. Bağlam/rapor rehberi **yumuşak tercihtir**, sert token sınırı değildir: varsayılan bir uzman, destekleniyorsa kısa görev özeti ve temiz bağlam, temiz reviewer bağlamı, ilgili ajanı yeniden kullanma, gerekçeli paralellik, sınırlı bekleme ve kısa kanıt raporu. Aday dondurma, tek yazar, bağımsız kontrol ve sonlu yeniden deneme korunur.

Gerçek konuşma içermeyen demo:

```sh
python3 scripts/dashboard.py /gecici/hedef --sessions tests/fixtures/usage-sanitized --no-browser --port 0
```

Güncel başvuru: [resmî Codex yapılandırması](https://learn.chatgpt.com/docs/config-file/config-reference). Yapılandırma niyeti gösterir; istemcinin gerçekten uyguladığını canlı smoke testi doğrular.


İleri ayarlardaki model listesi mümkünse yerel Codex CLI `model/list` yanıtından gelir. Resmî belgede bulunan diğer modeller **erişim doğrulanmadı** etiketiyle ayrılır. Bağlantısız kullanım için paketlenen `scripts/model_catalog.json` kaynak ve inceleme tarihini içerir. **Güncel modelleri yenile**, sınırlı yerel keşfi tekrarlar; kayıtlı ayarları değiştirmez. Yerel CLI listesi başka bir Codex istemcisi veya çalışma alanından farklı olabilir. Listede olmayan kayıtlı model korunur; konsolda listede olmayan yeni model kimliği girilemez veya kaydedilemez. Kaydetme önizlemesi tam eski/yeni model ve inceleme düzeyini gösterir. Kaynak: [Codex app-server model/list](https://learn.chatgpt.com/docs/app-server#models) ve [Codex modelleri](https://learn.chatgpt.com/docs/models).
