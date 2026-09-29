[English](usage-and-local-eval.md) | [Türkçe](usage-and-local-eval.tr.md)

# Kullanım raporu ve isteğe bağlı yerel değerlendirme

```bash
python3 .codex/tools/usage_report.py
python3 .codex/tools/usage_report.py --json
```

Rapor aracı `~/.codex/sessions` klasörünü salt okunur tarar ve gözlenen `token_usage_record.usage` istek sayaçlarını toplar; eski kümülatif `token_count` sayaçlarında zaman sıralı fark kullanır. İstem veya kaynak içeriklerini yazdırmaz. Model, rol ve görev bilgisi token/oturum metadatasında varsa gösterilir (thread için dosya adı yedek kaynaktır). Bu sayılar yerel gözlemdir; kota yüzdesi, fatura veya maliyet tahmini değildir.

Yerel değerlendirme kendiliğinden çalışmaz. Örnek dosyayı proje içinde kopyalayıp açık `argv` listesini düzenleyin:

```bash
python3 .codex/tools/local_eval.py .codex/local-eval.json
python3 .codex/tools/ledger.py require-eval --label focused-tests
python3 .codex/tools/ledger.py ready-for-review
```

Araç kabuk kullanmaz, proje kökünde ve süre sınırıyla çalışır, sonucu Git tarafından yok sayılan kısa bir özete yazar. Varsayılan özet komut çıktısı yerine özet değerini saklar. Bu kontrol evrensel kalite ölçümü değildir. Bir görev çalışmasında seçilirse inceleme öncesinde başarılı olması gerekir.
Başarılı sonuç, HEAD ile ilgili izlenen ve yeni çalışma dosyalarının gizlilik koruyan parmak izine bağlanır. Sonraki bir değişiklik sonucu geçersiz kılar; sonuç dosyasının kendisi parmak izinden çıkarılır.

Ledger artık sabit deneme ve olay kimlikleri tutar. `interrupt`, `wait-user` ve `needs-repair` kısa kanıtı korur; `retry --evidence ...` tek sınırlı yeniden denemeye izin verir ve işi kayıtlı sorumlu role geri yollar.


[İstek hesaplama, filtreler ve yerel konsol](local-console.tr.md). `payload.usage` istek bazlıdır; yalnız eski `token_count.info.total_token_usage` kümülatif delta kullanır.
