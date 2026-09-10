[English](expertise-packs.md) | [Türkçe](expertise-packs.tr.md)

# İsteğe bağlı uzmanlık paketleri

v0.3.0 iki isteğe bağlı skill paketi içerir. Kullanıcı bunlardan birini açıkça seçtiğinde veya ilgili uzmanlığı istediğinde temel sınırlı akışa odaklanmış bir kontrol listesi ekler.

## UI tasarımı

İstenen sonuç UI veya UX tasarımı uzmanlığı içeriyorsa `$bounded-orchestrator` ile birlikte `$bounded-orchestrator-ui-design` çağrılır.

Paket; owner'ın hedef kitleyi, temel eylemi, durumları, kısıtları ve mevcut design system öğelerini tanımlamasını ister. Etkileşim durumlarını, desteklenen ekran genişliklerini, klavye kullanımını, odağı, etiketleri, kontrastı, azaltılmış hareketi, zoom'u ve gerçekçi içeriği ele alır. Ürüne özel ve bilinçli bir yön ister; araştırma, erişilebilirlik veya uyumluluk hakkında doğrulanmamış iddiaları engeller.

## Güvenlik review

Kullanıcı güvenlik odaklı analiz veya review istediğinde `$bounded-orchestrator` ile birlikte `$bounded-orchestrator-security-review` çağrılır.

Paket ilgili varlıkları, güven sınırlarını, giriş noktalarını, aktörleri, veri hassasiyetini ve kötüye kullanım senaryolarını tanımlatır. Uygun olduğu yerlerde kimlik doğrulama, yetkilendirme, girdi kontrolü, secret'lar, kişisel veriler, log'lar, riskli çalıştırma sınırları, bağımlılıklar, tekrar oynatma, hız sınırları ve hizmet engelleme risklerine dikkat çeker. Bulgular önem derecesini şişirmeden kanıt ve güven düzeyi belirtmelidir.

## Sınır

İki paket de talimattır. Araç eklemez, agent oluşturmaz, model veya sandbox değiştirmez, kullanıcı bilgisi sağlamaz, dış sistem testine izin vermez ve davranışı teknik olarak zorlamaz. Temel kurallar geçerli kalır: tek sorumlu owner, kapsam başına tek writer, recursive delegation yasağı, bağımsız doğrulama, dondurulmuş aday review'ı, sonlu repair döngüleri ve dış etkiler için açık yetki.
