[English](release-v0.4.0.md) | [Türkçe](release-v0.4.0.tr.md)

# v0.4.0 sürüm notları

v0.4.0, Türkçe anlaşılır tek tıklamalı profil seçimi ve isteğe bağlı Anthropic API öneri rolü ekler.

- Kurulumda `balanced`, `quality`, `economy` veya `custom` seçilir.
- `custom` seçeneğinde her rolün modeli ve eforu ayrı belirlenir.
- Aynı seçimler `--preset`, `--role-model` ve `--role-effort` ile otomatikleştirilebilir.
- İstenirse bağımlılıksız yerel MCP köprüsü Claude'dan yama önerisi alır.
- `ANTHROPIC_API_KEY` yalnız ortamda kalır; config veya manifest içine kopyalanmaz.
- Yerel tek writer kuralı korunur: köprü çalışma alanını okuyamaz veya yazamaz.
- Uninstall manifest'indeki sabit yönetilen dosya listesi dışındaki yollar reddedilir.

Haricî köprü yerel MCP el sıkışması ve taklit edilmiş Anthropic Messages API HTTP isteğiyle test edildi. Repo doğrulamasında ücretli canlı API çağrısı yapılmadı.
