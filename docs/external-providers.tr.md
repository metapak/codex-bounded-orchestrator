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
  --external-model claude-sonnet-5-5 \
  --external-effort high
```

Tarayıcı konsolu ve rehberli kurulum `claude-fable-5-1`, `claude-opus-5-5`, `claude-sonnet-5-5` ve `claude-haiku-4-5-20251001` seçeneklerini sunar. İlk üçü `low`, `medium`, `high`, `xhigh` veya `max` eforunu kullanır. Haiku 4.5 için ayrı efor ayarı yoktur; `auto` seçildiğinde köprü isteğe `output_config` eklemez. Kimlikler ve efor sınırı [Anthropic model listesine](https://platform.claude.com/docs/en/models/overview) ve [efor rehberine](https://platform.claude.com/docs/en/build-with-claude/effort) dayanır. Hesap erişimi burada doğrulanmaz. CLI özel bir `claude-*` kimliğini kabul eder; erişim ve efor desteği sağlayıcının güncel belgelerinden ayrıca kontrol edilmelidir.

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

Tarayıcıdaki model `deepseek-flash` seçeneğidir; adı DeepSeek'in [V4.1 Flash duyurusunda](https://deepseek.com/en/news/deepseek-v4-1-flash/) yer alır. Tarayıcı, Responses API'deki ayrı inceleme düzeyleri olan `none`, `low`, `high` ve `max` değerlerini gösterir. API bazı diğer CLI köprüsü değerlerini eşanlamlı kabul eder; ayrıntı [Responses API belgesindedir](https://api-docs.deepseek.com/api/create-response/). CLI özel bir `deepseek-*` kimliğini kabul eder, ancak erişim sağlayıcı ve hesap üzerinden ayrıca doğrulanmalıdır.

## Sınır ve veri kullanımı

Her köprü görev, açıkça verilen bağlam, kısıtlar ve boş olmayan repo içi dosya yolu listesi alır. Çalışma alanı yolu almaz, dosya okumaz ve değişiklik uygulamaz. Yerel GPT implementer tek writer olarak kalır ve öneriyi uygulamadan önce incelemelidir.

Verilen bağlama kimlik bilgisi, kişisel veri, kapsam dışı özel kaynak veya ilgisiz dosya koyma. Seçilen bağlam sağlayıcıya gönderilir. API kullanımı sağlayıcının erişim, kota, veri ve ücretlendirme koşullarına bağlıdır.

Installer seçilen sağlayıcının köprüsünü ve MCP kaydını ekler. Etkin config güncellenebildiğinde, sağlayıcı değiştirilirse veya `none` seçilirse artık seçili olmayan değiştirilmemiş installer köprüsü kaldırılır. Kullanıcının değiştirdiği `.codex/config.toml` manuel birleştirme için korunursa bu etkin config'in hâlâ referans verdiği installer köprüleri de korunur. Sonuç ekranı istenen sağlayıcı ile etkin sağlayıcıyı ayrı gösterir ve üretilen örnek dosya yolunu belirtir. `--force-config` açık yedekle ve değiştir seçeneği olarak kalır.

Test paketi her yerel MCP el sıkışmasını ve taklit edilmiş HTTP isteğini çalıştırır. Canlı ücretli API çağrısı yapmaz ve belgelenen istek biçiminin ötesinde canlı sağlayıcı uyumluluğu iddia etmez.
