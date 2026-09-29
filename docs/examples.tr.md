[English](examples.md) | [Türkçe](examples.tr.md)

# Örnekler

Kurulumdan sonra hedef projede `$bounded-orchestrator` çağrısını kullan. Hedefi ve sınırları yaz; şef her yürütme adımını sınırları belli bir uzmana verir.

## Birden fazla dosyaya yayılan özellik

```text
$bounded-orchestrator

API ve persistence katmanlarında invoice oluşturmaya idempotency ekle.
Public API'yi koru. Önce yolu haritala, implementasyonu tek writer'a ver,
tekrarlanan istekleri doğrula ve tek dondurulmuş adayı review et. Deploy yapma.
```

## Bileşenler arası bug

```text
$bounded-orchestrator

Kaydedilen bildirim tercihinin girişten sonra neden sıfırlandığını bul ve düzelt.
Repair kapsamını seçmeden önce client, API ve storage state'ini izle.
Hatayı yeniden üret ve düzeltmeyi doğrula. Schema'yı değiştirme.
```

## Yüksek riskli karar

```text
$bounded-orchestrator

Payment capture için en güvenli retry sınırını değerlendir.
Advisor'ı yalnız tanımlanan mimari karar için kullan. Kanıtları, seçenekleri
ve öneriyi döndür; kodu veya dış sistemleri değiştirme.
```

Küçük, yerel düzenlemeler de tek bir uygun uzmana verilir. Şef kullanıcıyla konuşur ve koordinasyon yapar; ek uzman ancak bağımsız çalışması değer katarsa kullanılır.
