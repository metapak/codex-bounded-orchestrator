[English](release-v0.5.0.md) | [Türkçe](release-v0.5.0.tr.md)

# v0.5.0 sürüm notları

Codex Bounded Orchestrator artık bütün yerel rolleri OpenAI GPT modellerinde tutar. Hazır profillerin amacı değişmedi; özel yerel model kimlikleri ileriye uyumlu `gpt-*` ailesinden olmalıdır. Diğer markalar açıkça seçilen, isteğe bağlı API öneri araçlarıdır.

Haricî sağlayıcı varsayılanı yoktur; seçim ekranı artık Anthropic Claude veya DeepSeek sunar. Standart kütüphane kullanan yeni DeepSeek köprüsü güncel V4.1 Flash adı `deepseek-flash` ile hazırlanmıştır, yalnız sınırlı verilen bağlamı alır ve çalışma alanını okuyamaz veya yazamaz. Yerel GPT implementer tek writer olarak kalır.

Terminal kurulumu yerel profil, isteğe bağlı haricî API ve son kontrolü üç açık bölümde gösterir. macOS ve Windows başlatıcıları işlem ve çakışma davranışını seçimden önce açıklar; Linux aynı yönlendirmeli Python akışını `scripts/install.sh /proje/yolu --interactive` ile kullanır. Çıktı renk gerektirmez ve kısıtlı konsol kodlamalarında okunabilir kalır.

Doğrulama canlı ve ücretli sağlayıcı çağrısı yapmaz. Sağlayıcı biçimi taklit edilmiş istek testleriyle kontrol edilir; model erişimi yine kullanıcının kendi hesabında doğrulanmalıdır.

Sağlayıcı değişimi etkin config'i dikkate alır. Kullanıcının değiştirdiği etkin config korunmak zorundaysa installer bu config'in hâlâ referans verdiği sahip olunan köprüleri de korur. Sonuç ekranı istenen ve etkin sağlayıcıyı ayrı bildirir, bekleyen manuel birleştirme örneğinin yolunu gösterir.
