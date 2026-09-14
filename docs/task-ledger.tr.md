[English](task-ledger.md) | [Türkçe](task-ledger.tr.md)

# Yerel görev ledger'ı

v0.3.0 ledger'ı, owner'ın bir orkestrasyon çalışması için tanımladığı işleri küçük ve yerel bir kayıtta tutar. Review ve tamamlama öncesinde hâlâ bekleyen, devam eden, bloklanan veya gerekçesiz atlanan zorunlu görevleri görmeye yardımcı olur.

Yalnız metadata saklar: kısa çalışma ve görev kimlikleri, kısa etiketler, bağımlılıklar, zorunlu/isteğe bağlı işaretleri, durumlar, kısa nedenler ve zaman bilgileri. Etiketlere veya nedenlere prompt, kaynak kod, diff, log, kişisel veri, kullanıcı bilgisi ya da secret yazma.

## Temel akış

Komutları hedef Git reposunda çalıştır:

```bash
python3 .codex/tools/ledger.py start fatura-idempotency --title "Fatura idempotency"

python3 .codex/tools/ledger.py add haritala --title "Request ve kayıt akışını haritala"
python3 .codex/tools/ledger.py add uygula --title "Sınırlı değişikliği uygula" --depends-on haritala
python3 .codex/tools/ledger.py add dogrula --title "Bağımsız doğrulama çalıştır" --depends-on uygula

python3 .codex/tools/ledger.py begin haritala
python3 .codex/tools/ledger.py complete haritala
python3 .codex/tools/ledger.py status
```

Durumları `begin` ve `complete` ile ilerlet. Kanıt belirli bir engel gösterdiğinde `block GÖREV --reason "kısa neden"` kullan. Bir görev ancak atlama kararı gerekçeliyse `skip GÖREV --reason "kısa owner kararı"` ile atlanmalıdır. Çalışmayı engellememesi gereken bir görev eklemek için `add` komutuna `--optional` ekle.

Adayı dondurmadan önce:

```bash
python3 .codex/tools/ledger.py ready-for-review
```

Sınırlı akışın tüm tamamlama kontrolleri geçtikten sonra:

```bash
python3 .codex/tools/ledger.py complete-run
```

Makinece okunabilir çıktı için `status --json` kullan. Mevcut çalışma dışında bir kaydı hedeflemek için `--run ÇALIŞMA_KİMLİĞİ` ekle. `clear --run ÇALIŞMA_KİMLİĞİ` yalnız o çalışmanın yerel ledger metadata'sını siler.

## Geçerli geçişler

| Komut | Önce | Sonra |
|---|---|---|
| `begin` | `pending`, `blocked` | `in_progress` |
| `complete` | `in_progress` | `complete` |
| `block` | `pending`, `in_progress` | `blocked` |
| `skip` | `pending`, `blocked` | `skipped` |

Bir görev ancak bağımlılıkları tamamlandıktan veya kayıtlı bir atlama nedeni aldıktan sonra başlayabilir. `pending`, `in_progress` veya `blocked` durumundaki zorunlu görevler review hazırlığını ve tamamlamayı engeller. Atlanmış zorunlu görev de bir nedeni yoksa engel olur. Çözülmemiş isteğe bağlı görevler görünür kalır ama kontrolü engellemez.

## Saklama ve sınırlar

Çalışma verisi `.codex/.bounded-orchestrator/runs/` altında atomik biçimde yazılır. Installer, aracı kurmadan önce üst çalışma dizinine tam bir `.gitignore` yerleştirir. POSIX izinlerini destekleyen sistemlerde dizinler geçerli kullanıcıyla sınırlandırılır ve JSON dosyaları `0600` modunu kullanır.

Ledger bir çalışma yardımcısıdır; scheduler veya güvenlik sınırı değildir. Tanımlanmış kimlikleri, bağımlılıkları, durum geçişlerini ve tamamlanma koşullarını doğrular. Hiç tanımlanmayan bir görevi keşfedemez, durum güncellemesinin doğru olduğunu onaylayamaz, kod doğruluğunu kanıtlayamaz ve test veya review'ın yerini alamaz.

## Denemeler, kesintiler ve yerel değerlendirme

Şema 2 mevcut çalışma/görev kimliklerini, sabit deneme kimliklerini, yalnız sona eklenen geçiş olaylarını, sorumlu rolü ve geri yönlendirme bilgisini korur. Şema-1 dosyaları bellekte güncellenir ve sonraki değişiklikte şema 2 olarak yazılır. Gerçek geçişlerde `interrupt`, `wait-user` ve `needs-repair` kullanılır. `retry GOREV --evidence "yeni kısa kanıt"` yalnız bir sınırlı yeniden denemeye izin verir; dış işlemlerin yinelenmez olduğunu iddia etmez.
`wait-user` sonrasında `resume GOREV --evidence "yanıt alındı"` kullanılır. Başlamadan bekleyen görev beklemeye döner; aktif görev aynı denemeyi sürdürür. Bağımlılık kontrolleri devam eder.

`require-eval --label ETIKET`, açıkça çalıştırılmış yerel değerlendirmeyi inceleme kapısına ekler. Eşleşen ve Git tarafından yok sayılan özet `pass` göstermelidir.
