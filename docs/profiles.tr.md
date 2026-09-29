[English](profiles.md) | [Türkçe](profiles.tr.md)

# Yönlendirme profilleri

Profil adları yönlendirme amacını ve göreli kaynak kullanımını anlatır; ölçülmüş kalite, maliyet veya hız garantisi değildir. Gerçek erişim ve kullanım kullanıcının Codex planına ve çalışma alanına bağlıdır.

| Rol | balanced | quality | economy | quota-saver | custom | focused |
|---|---|---|---|---|---|---|
| owner | 6-astra medium | 6-astra high | 5.6-terra medium | 6-astra low | 6-astra medium | 6-astra medium |
| fast_lookup | 5.6-luna medium | 5.6-luna medium | 5.6-luna low | 5.6-luna minimal | 5.6-luna medium | 6-luna high |
| explorer | 5.6-terra medium | 6-astra high | 5.6-luna medium | 5.6-terra low | 5.6-terra medium | 6-luna high |
| researcher | 5.6-terra medium | 6-astra high | 5.6-terra low | 5.6-terra low | 5.6-terra medium | 6-sol medium |
| implementer | 5.6-sol high | 6-astra high | 5.6-terra medium | 5.6-sol medium | 5.6-sol high | 6-sol medium |
| verifier | 5.6-terra high | 6-astra high | 5.6-terra medium | 5.6-terra medium | 5.6-terra high | 6-sol medium |
| failure_analyst | 5.6-sol high | 6-astra high | 5.6-terra medium | 5.6-sol medium | 5.6-sol high | 6-sol medium |
| qa_operator | 5.6-sol high | 6-astra high | 5.6-terra medium | 5.6-sol medium | 5.6-sol high | 6-sol medium |
| reviewer | 6-astra medium | 6-astra xhigh | 5.6-terra high | 6-astra low | 6-astra medium | 6-sol medium |
| advisor | 6-astra xhigh | 6-astra max | 5.6-sol high | 6-astra low | 6-astra xhigh | 6-sol medium |

`custom`, Balanced ayarlarından başlar ve her rolün model kimliği ile eforunu sorar. Yerel Codex rolleri yalnız OpenAI `gpt-*` model kimliklerini kabul eder; Claude ve DeepSeek açık haricî öneri sağlayıcısı akışından seçilir. Bu önek kuralı kırılgan bir tam liste oluşturmadan gelecekteki GPT model kimliklerini kullanılabilir tutar. Otomatik kurulumda `--role-model ROLE=MODEL` ve `--role-effort ROLE=EFOR` tekrarlanabilir. Installer seçilen GPT modelinin kullanıcının hesabında açık olduğunu doğrulayamaz.


`focused`, owner için Astra medium; dar arama/inceleme için Luna high; diğer sınırlı uzmanlar için Sol medium kullanır. Yeni konsolun varsayılanıdır; mevcut CLI profilleri korunur. [Yerel konsol](local-console.tr.md)
