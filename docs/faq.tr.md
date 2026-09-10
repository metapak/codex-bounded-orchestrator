[English](faq.md) | [Türkçe](faq.tr.md)

# SSS ve sorun giderme

## Her modelin ve sandbox'ın kullanılacağını garanti eder mi?

Hayır. Repo hedeflenen proje config'ini ve rol talimatlarını sunar. İstemci sürümü, ürün yüzeyi, trust durumu, plan erişimi ve parent izinleri gerçek davranışı etkileyebilir. [Runtime smoke testini](runtime-smoke-test.md) çalıştır ve gözlemlenemeyen metadata'yı bilinmiyor say.

## Kurulum neden config example oluşturdu?

Mevcut `.codex/config.toml` varsayılan olarak korunur. Installer, inceleyip manuel birleştirmen için `.codex/bounded-orchestrator.config.example.toml` yazar. `--force-config` seçeneğini yalnız root config'i yedekleyip değiştirmek istediğinde kullan.

## Bir agent veya tool dosyası neden atlandı?

Hedefteki dosya sunulan dosyadan farklıdır. Önce farkı incele. `--force`, çakışan yönetilen rol, skill ve tool dosyalarını yedekleyip değiştirir; ayrıca `--force-config` verilmedikçe root config'i değiştirmez.

## Candidate freeze değişiklikleri engeller mi?

Hayır. Hash'leri ve Git kimliğini kaydeder; `verify` daha sonra dondurulmuş adayın değişip değişmediğini tespit eder. Dosyaları kilitlemez, doğruluğu kanıtlamaz, test ve review'ın yerine geçmez.

## Görev ledger'ı hiçbir işin unutulmadığını kanıtlayabilir mi?

Hayır. Tanımlanmış zorunlu görevler arasındaki çözülmemiş işleri gösterir. Owner yine de doğru işleri tanımlamalı, sonucu incelemeli, testleri çalıştırmalı ve bağımsız review'ı tamamlamalıdır. Ledger etiketlerine ve nedenlerine prompt, kaynak, log, kişisel veri, kullanıcı bilgisi veya secret yazma.

## Uzmanlık paketleri ek izin verir mi?

Hayır. Bunlar isteğe bağlı talimat kümeleridir. Agent oluşturmaz, sandbox değiştirmez, kullanıcı bilgisi sağlamaz veya dış eylemleri yetkilendirmez.

## Uninstall bir dosyayı neden tuttu?

Uninstall yalnız installer-owned olarak kaydedilen ve kurulumdan sonra değişmemiş dosyaları kaldırır. Kullanıcı işini silmemek için önceden var olan veya değiştirilmiş dosyaları korur. `AGENTS.md` içinden de yalnız işaretli bounded-orchestrator bloğunu kaldırır.

## Sol-owner profili ne zaman kullanılmalı?

Sunulan Astra root-owner modeli kullanılamıyorsa veya root olarak açıkça Sol high tercih ediyorsan `--profile sol` kullan. Sunulan diğer rol yönlendirmeleri korunur. Gerçek model erişimini Codex plan veya workspace'inde doğrula.
