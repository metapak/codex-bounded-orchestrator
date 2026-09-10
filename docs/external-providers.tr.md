[English](external-providers.md) | [Türkçe](external-providers.tr.md)

# İsteğe bağlı Anthropic API köprüsü

Codex MCP araçlarını desteklediği için bu proje, Anthropic Messages API'yi isteğe bağlı yerel bir stdio MCP aracı olarak sunabilir. Bu, API üzerinden çalışan bir araç bağlantısıdır; Codex'in içine yerleşmiş doğal bir Claude alt agent'ı değildir.

## Kurulum

Anahtarı yalnız Codex'i başlatan ortamda tanımla:

```bash
export ANTHROPIC_API_KEY="anahtarın"
python3 scripts/install.py /projenin/yolu \
  --preset balanced \
  --external-provider anthropic \
  --external-model claude-sonnet-5 \
  --external-effort high
```

Installer yalnız seçildiğinde `.codex/tools/anthropic_mcp.py` dosyasını ve `anthropic_claude` MCP kaydını ekler. Mevcut `.codex/config.toml`, hâlâ değiştirilmemiş installer dosyası değilse veya `--force-config` verilmediyse korunur. Çakışmada oluşturulan örnek dosyayı elle birleştirmen gerekir.

## Sınır

Araç görev, açıkça verilen bağlam, kısıtlar ve boş olmayan repo içi dosya yolu listesi alır. Bunları Anthropic'e göndererek unified diff biçiminde öneri ister. Çalışma alanı yolu almaz, dosya okumaz ve değişiklik uygulamaz. Tek writer yerel implementer olarak kalır; öneriyi uygulamadan önce incelemelidir.

Verilen bağlama kimlik bilgisi, kişisel veri, kapsam dışı özel kaynak veya ilgisiz dosya koyma. API kullanımı kullanıcının Anthropic hesabına, model erişimine, kotasına ve ücretlendirmesine tabidir.

## Modeller ve efor

2026-09-10 tarihinde doğrulandığı üzere hazır seçenekler güncel sabit Claude API kimlikleri `claude-sonnet-5` ve `claude-opus-5` kullanır. Anthropic'in [efor belgesi](https://platform.claude.com/docs/en/build-with-claude/effort), iki modelin de `low`, `medium`, `high`, `xhigh` ve `max` değerlerini desteklediğini belirtir; köprü seçilen değeri `output_config.effort` alanında gönderir. Özel model kimliği girilebilir; erişim ve efor desteği Anthropic'in güncel [model özeti](https://platform.claude.com/docs/en/about-claude/models/overview), [Messages API referansı](https://platform.claude.com/docs/en/api/messages/create) ve kullanıcının hesabıyla doğrulanmalıdır.

Repo testleri yerel MCP el sıkışmasını ve taklit edilmiş Messages API HTTP isteğini uçtan uca çalıştırır. CI içinde ücretli canlı API çağrısı yapıldığı iddia edilmez.
