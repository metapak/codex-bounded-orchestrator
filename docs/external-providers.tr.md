[English](external-providers.md) | [Türkçe](external-providers.tr.md)

# İsteğe bağlı haricî API öneri sağlayıcıları

Codex bütün yerel rollerde OpenAI GPT modellerini kullanır. Installer varsayılan olarak haricî sağlayıcı seçmez. Anthropic ve DeepSeek, sınırlı uygulama önerileri döndüren isteğe bağlı API destekli MCP araçlarıdır; yerel Codex alt agent'ları değildir.

## Yönlendirmeli kurulum

Etkileşimli installer üç açık seçenek gösterir:

1. Yok (varsayılan)
2. Anthropic Claude önerisi
3. DeepSeek önerisi

Son kontrol ekranında sağlayıcı, model, efor ve yalnız öneri sınırı gösterilir. Sağlayıcı seçmek API anahtarını kaydetmez.

## Anthropic

Anahtarı yalnız Codex'i başlatan ortamda tanımla:

```bash
export ANTHROPIC_API_KEY="anahtarın"
python3 scripts/install.py /projenin/yolu \
  --preset balanced \
  --external-provider anthropic \
  --external-model claude-sonnet-5 \
  --external-effort high
```

Hazır seçenekler `claude-sonnet-5` ve `claude-opus-5` modelleridir. Anthropic eforları `low`, `medium`, `high`, `xhigh` ve `max` değerleridir. Özel bir `claude-*` model kimliği girilebilir; erişim ve efor desteği kullanıcının hesabına ve güncel Anthropic belgelerine bağlıdır.

## DeepSeek

Anahtarı yalnız Codex'i başlatan ortamda tanımla:

```bash
export DEEPSEEK_API_KEY="anahtarın"
python3 scripts/install.py /projenin/yolu \
  --preset balanced \
  --external-provider deepseek \
  --external-model deepseek-flash \
  --external-effort high
```

Hazır seçenek `deepseek-flash` modelidir. DeepSeek'in 10 Eylül 2026 tarihli [V4.1 Flash duyurusu](https://deepseek.com/en/news/deepseek-v4-1-flash/) güncel API modeli için bu adı verir ve eski V4 Flash adlarının geçici olarak bu modele yönlendirildiğini belirtir. Köprüdeki efor seçenekleri DeepSeek Responses API biçimini izler: `none`, `minimal`, `low`, `medium`, `high`, `xhigh` ve `max`. Özel bir `deepseek-*` model kimliği girilebilir; erişim güncel sağlayıcı belgeleri ve kullanıcının hesabıyla kontrol edilmelidir.

## Sınır ve veri kullanımı

Her köprü görev, açıkça verilen bağlam, kısıtlar ve boş olmayan repo içi dosya yolu listesi alır. Çalışma alanı yolu almaz, dosya okumaz ve değişiklik uygulamaz. Yerel GPT implementer tek writer olarak kalır ve öneriyi uygulamadan önce incelemelidir.

Verilen bağlama kimlik bilgisi, kişisel veri, kapsam dışı özel kaynak veya ilgisiz dosya koyma. Seçilen bağlam sağlayıcıya gönderilir. API kullanımı sağlayıcının erişim, kota, veri ve ücretlendirme koşullarına bağlıdır.

Installer seçilen sağlayıcının köprüsünü ve MCP kaydını ekler. Etkin config güncellenebildiğinde, sağlayıcı değiştirilirse veya `none` seçilirse artık seçili olmayan değiştirilmemiş installer köprüsü kaldırılır. Kullanıcının değiştirdiği `.codex/config.toml` manuel birleştirme için korunursa bu etkin config'in hâlâ referans verdiği installer köprüleri de korunur. Sonuç ekranı istenen sağlayıcı ile etkin sağlayıcıyı ayrı gösterir ve üretilen örnek dosya yolunu belirtir. `--force-config` açık yedekle ve değiştir seçeneği olarak kalır.

Test paketi her yerel MCP el sıkışmasını ve taklit edilmiş HTTP isteğini çalıştırır. Canlı ücretli API çağrısı yapmaz ve belgelenen istek biçiminin ötesinde canlı sağlayıcı uyumluluğu iddia etmez.
