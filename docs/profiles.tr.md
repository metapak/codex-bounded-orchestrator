[English](profiles.md) | [Türkçe](profiles.tr.md)

# Yönlendirme profilleri

Profil adları yönlendirme amacını ve göreli kaynak kullanımını anlatır; ölçülmüş kalite, maliyet veya hız garantisi değildir. Gerçek erişim ve kullanım kullanıcının Codex planına ve çalışma alanına bağlıdır.

| Rol | Balanced | Quality | Economy |
|---|---|---|---|
| owner | Astra medium | Astra high | Terra medium |
| hızlı arama | Luna medium | Luna medium | Luna low |
| explorer | Terra medium | Astra high | Luna medium |
| researcher | Terra medium | Astra high | Terra low |
| implementer | Sol high | Astra high | Terra medium |
| verifier | Terra high | Astra high | Terra medium |
| hata analisti | Sol high | Astra high | Terra medium |
| QA operatörü | Sol high | Astra high | Terra medium |
| reviewer | Astra medium | Astra xhigh | Terra high |
| advisor | Astra xhigh | Astra max | Sol high |

`custom`, Balanced ayarlarından başlar ve her rolün model kimliği ile eforunu sorar. Otomatik kurulumda `--role-model ROL=MODEL` ve `--role-effort ROL=EFOR` tekrarlanabilir. Installer efor adlarını doğrular ve model kimliklerini TOML için güvenli biçimde yazar; seçilen modelin kullanıcının hesabında açık olduğunu doğrulayamaz.
