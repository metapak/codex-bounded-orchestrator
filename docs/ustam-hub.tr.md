# Ustam yerel merkezi

Ustam’ı indir → Aç → Uygulamaları seç → Projeleri ekle.

Sürüm dosyalarından işletim sisteminiz ve işlemciniz için yerel ZIP paketini indirin, tamamını çıkarın; macOS’ta Ustam.app, Windows’ta Ustam.exe, Linux’ta Ustam dosyasını açın. Yerel indirme Python çalışma ortamını içerir. Windows/Linux çalıştırılabilir dosyasını çıkarılan diğer dosyalarla birlikte tutun. Mac uygulaması worker ve varlıklarını içerir; önce paket veya proje klasörü seçtirmeden merkezi doğrudan açar.

Codex, Claude Code, OpenCode veya birkaçını birlikte seçin. Proje klasörlerini yerel tarayıcı sayfasında ekleyin. Projeleri seçin, önerilen değişiklikleri inceleyin ve ardından uygulayın. Sağlayıcıların komut satırı araçları, giriş ve model erişimi ayrıca gereklidir. Ustam bu araçları veya hesapları sağlamaz. API modelleri kendi kimlik bilgilerini gerektirebilir; gerçekten kullanıldığında ücret oluşturabilir. Çevrimdışı kurulum ve önizleme ücretli model çağrısı gerektirmez.

Merkez tercihleri ve kayıtlı projeleri kullanıcının yerel durum klasöründe saklar. Projelere yalnızca açıkça uyguladığınızda yapılandırma yazılır. Her sağlayıcı kendi paketlenmiş, sabitlenmiş motoruyla çalışır; motor manifesti tam dosya kümesini ve SHA-256 özetlerini doğrular. Kullanım, yerelde kaydedilmiş geçmişi gösterir; fatura bakiyesi değildir.

Bu derlemeler imzasızdır ve notarize edilmemiştir: imzalama kimlik bilgileri mevcut değildir. macOS Gatekeeper indirilen uygulamayı engelleyebilir; bu paketi imzalı veya notarize edilmiş bir sürüm olarak değerlendirmeyin. İmzasız derlemeyi kullanmadan önce sürümün yayımlanmış özetini ve kaynağını kontrol edin. Güvenmeye karar verdiğiniz yazılımlar için macOS güvenlik ayarlarını izleyin. Yönetilen bilgisayarlarda yönetici onayı gerekebilir. Yerel testlerin geçmesi indirilen uygulamanın Gatekeeper’dan geçeceğini kanıtlamaz.

İleri düzey kaynak kullanımı Python 3.11+ gerektirir: `python -m ustam` çalıştırın. Önceki sağlayıcıya özel konsollar ve terminal kurucuları uyumluluk için korunur. Yerel uygulama indirmeleri ek sürüm dosyalarıdır; kaynak CLI dağıtımlarının yerini almaz.

Yerel derleme için ayrı bir Python ortamına PyInstaller kurun; sabitlenmiş kardeş depolar mevcutken `python scripts/build_ustam_engines.py`, ardından `python scripts/build_ustam_app.py` çalıştırın. CI, depoya eklenmiş değişmez motor kümesini doğrulamak ve paketlemek için `--skip-engine-build` kullanır. Her hedef işletim sistemi/işlemci için orada derleme yapın. Pencereli başlatıcı ayrı konsol worker’ını açar; adaptörler JSON stdio bağlantısını koruyarak aynı worker’ı `--adapter` ile yeniden başlatır. Windows alt süreçleri gizlenir.

Yerel uygulama sürümü `ustam/VERSION` dosyasında tutulur; sabitlenmiş sağlayıcı motorlarının sürümleri ve önceki kaynak CLI sürümü ayrıdır. Bu beta pakette yalnızca Mac arm64 gerçek yerel çalışma testi yapılmıştır. Windows, Linux ve Mac Intel derlemeleri CI tarafından üretilip doğrulanmalıdır.

İmzalı dağıtım için haricî ön koşullar: Developer ID Application kimliği, güvenli secret olarak saklanan dışa aktarılmış P12 sertifikası ve parolası; notarizasyon için Apple hesabı, uygulamaya özel parola ve takım kimliği. Mevcut CI bu bilgileri istemez veya kullanmaz ve imzasız paket üretir. Sertifika ya da kimlik bilgilerini depoya eklemeyin.

macOS beta.1 paketinde uygulama oluşturulduktan sonra Info.plist değiştirildiği için bütünlük imzası geçersizdi; “hasar görmüş” uyarısı bu paketleme hatasından kaynaklanıyordu. beta.2 uygulama birleştirildikten sonra ad-hoc bütünlük mührünü yeniler ve ZIP’ten çıkarılan uygulamayı doğrular. beta.1 uygulama dosyasını beta.2 ile değiştirin; proje veya sağlayıcı ayarlarını yeniden kurmanız gerekmez. Ad-hoc mühür Apple Developer ID imzası veya notarizasyon değildir; Gatekeeper güven değerlendirmesi ayrı kalır ve uygulamayı yine engelleyebilir.
