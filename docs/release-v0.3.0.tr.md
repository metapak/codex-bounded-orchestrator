[English](release-v0.3.0.md) | [Türkçe](release-v0.3.0.tr.md)

# v0.3.0 sürüm notları

v0.3.0, v0.2.0 yetki modelini korurken tanımlanmış işleri görünür kılar ve isteğe bağlı iki uzmanlık bakışı ekler.

Yeni `.codex/tools/ledger.py`; kısa ve yerel görev metadata'sı kaydeder, bağımlılıkları ve durum geçişlerini doğrular, insan tarafından veya makinece okunabilen durum çıktısı verir ve tanımlanmış zorunlu işler çözülmeden review/tamamlamayı engeller. Dosyalar ignore edilen çalışma dizininde atomik biçimde ve desteklenen sistemlerde kısıtlı izinlerle yazılır. Windows uyumluluğu için geçici dosya tanımlayıcıları değiştirme işleminden önce açıkça kapatılır. Ledger prompt, kaynak, diff, log, kişisel veri, kullanıcı bilgisi veya secret içeriğine ihtiyaç duymaz.

UI tasarımı ve güvenlik review paketleri ayrı ve isteğe bağlı skill'ler olarak kurulur. Tek owner, kapsam başına tek writer, bağımsız doğrulama, dondurulmuş aday review'ı, sonlu döngüler ve dış eylemler için açık yetki kurallarını koruyarak odaklanmış sorular ve kontroller ekler.

Installer ve uninstaller yeni dosyaları mevcut çakışma korumalı sahiplik manifest'i ile izler. Statik doğrulama ve sürüm arşivleri artık bunları zorunlu tutar. Testlerdeki paket sürümü beklentileri `VERSION` dosyasından alınır.

Bilinen sınır: Ledger yalnız tanımlanmış görevler arasındaki çözülmemiş işleri bulabilir. Eksiksizliği veya doğruluğu kanıtlamaz. Uzmanlık paketleri talimattır; enforcement veya izin eklemez.
