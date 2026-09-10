[English](release-v0.4.1.md) | [Türkçe](release-v0.4.1.tr.md)

# v0.4.1 sürüm notları

v0.4.1, etkin kodlaması bazı Türkçe karakterleri gösteremeyen Windows konsollarındaki etkileşimli installer hatasını düzeltir.

- Installer başlarken standart çıktı ve standart hata akışının etkin terminal kodlamasını korur; yalnız desteklenmeyen karakterleri güvenli biçimde değiştirir.
- UTF-8 terminaller özgün Türkçe metni göstermeye devam eder.
- cp1252 gibi sınırlı kodlamalar `UnicodeEncodeError` verip kurulumu durdurmak yerine güvenli değiştirme karakterleri gösterir.
- Regresyon testi etkileşimli dry-run akışını katı cp1252 çıktı akışlarıyla çalıştırır.

v0.4.0 ile gelen profil seçimi, özel rol yönlendirmesi, isteğe bağlı Claude API köprüsü, anahtar koruması ve sınırlı çalışma düzeni değişmeden kalır.
