# MakerLab Yönetim Sistemi — Yapılan İyileştirmeler ve Geliştirmeler Raporu

## 1. Giriş

Bu rapor, MakerLab 3D Baskı ve Elektronik Atölyesi Yönetim Sistemi üzerinde
gerçekleştirilen iyileştirme ve geliştirme çalışmalarını kapsamaktadır.
Çalışmalar üç ana başlıkta toplanmıştır: (1) kullanıcı deneyimini artıran yeni
özellikler, (2) uygulamadaki hataların giderilmesi ve (3) projenin profesyonel
bir yazılım standardına ve sürüm kontrol sistemine (GitHub) hazır hale
getirilmesi. Tüm çalışmalar süresince uygulamanın mevcut işlevselliği korunmuş;
yalnızca kod kalitesi, bakım kolaylığı ve kullanıcı deneyimi iyileştirilmiştir.

## 2. Eklenen Yeni Özellikler

### 2.1. Cihaz/Ürün Bilgilendirme Açıklamaları

Atölyede üretilen ürünleri (örneğin bir anahtarlık) talep eden kullanıcıların,
ürün veya cihaz hakkında güvenlik ve kullanım bilgisine erişebilmesi için kısa
açıklama alanı eklenmiştir.

- Veritabanındaki `Cihazlar` tablosuna `kisa_aciklama` sütunu eklenmiştir. Bu
  işlem, uygulama her başladığında otomatik çalışan bir şema kontrol fonksiyonu
  (`ensure_schema`) ile yapılır; böylece mevcut veritabanı bozulmadan güncellenir.
- Yönetici panelinde cihaz eklerken açıklama girilebilir ve mevcut cihazların
  açıklaması satır içi düzenleme formuyla güncellenebilir.
- Açıklamalar; yönetici, teknisyen ve öğrenci panellerinde cihaz kartlarında ve
  listelerinde görüntülenir. Teknisyen panelinde cihaz seçim menüsünde açıklama,
  fareyle üzerine gelindiğinde ipucu (tooltip) olarak da gösterilir.
- Öğrenciler için cihazların durumu ve açıklamalarını listeleyen ayrı bir
  "Cihazlar" sayfası oluşturulmuştur.

### 2.2. Bekleyen Talep Limitinde Akıllı Bilgilendirme

Önceki sürümde bir öğrenci en fazla 3 bekleyen talebe ulaştığında genel bir hata
mesajı alıyordu. Bu deneyim iyileştirilerek tahmini tamamlanma süresi hesaplaması
eklenmiştir.

- Sistem, öğrencinin bekleyen taleplerinin tahmini baskı sürelerini sıraya göre
  toplayarak her talebin tahmini bitiş tarih/saatini hesaplar.
- Öğrenci limite ulaştığında, hata yerine talep haklarından birinin ne zaman
  boşalacağı bilgisi gösterilir.
- "Son Taleplerim" tablosuna "Tahmini Bitiş" sütunu eklenerek bekleyen talepler
  için bu bilgi görsel olarak sunulur.

## 3. Hata Düzeltmeleri

Uygulamada tespit edilen ve giderilen başlıca hatalar:

- **Veritabanı bağlantı sızıntıları:** `try/except/finally` bloklarında
  bağlantının her durumda güvenli kapatılmaması sorunu, `get_cursor()` adında bir
  bağlam yöneticisi (context manager) yazılarak çözüldü. Bağlantı her durumda
  otomatik açılıp kapatılır; hata olursa geri alma (rollback), başarılıysa
  kaydetme (commit) yapılır.
- **Eskimiş (deprecated) API kullanımı:** Artık önerilmeyen
  `@app.on_event("startup")` ve `datetime.utcnow()` kullanımları, modern FastAPI
  `lifespan` mekanizmasına ve `datetime.now(timezone.utc)` kullanımına taşındı.
- **Boş tarih (None) hatası:** API yanıtlarında boş tarih alanında `isoformat()`
  çağrısının hata vermesi, koruyucu kontroller eklenerek giderildi.
- **Şablon hatası:** `student_request.html` içinde tekrar eden bir seçenek
  (option) öğesi kaldırıldı.
- **Tutarsız hata sayfaları:** Ham HTML ile döndürülen düzensiz hata mesajları,
  standart bir `hata_yaniti` yardımcı fonksiyonu ile tek tip hale getirildi.

## 4. Kod Yeniden Düzenlemesi (Refactoring)

Proje, tek ve çok büyük bir `main.py` dosyasından (monolitik yapı, 1600+ satır)
modüler bir paket yapısına dönüştürülmüştür. Bu, "ilgilerin ayrılması"
(separation of concerns) ilkesine dayanır:

- `app/config.py` — Tüm ayarlar, sabitler ve yapılandırma tek yerde toplandı.
- `app/database.py` — Veritabanı bağlantısı, güvenli `get_cursor` yöneticisi ve
  şema kontrolü.
- `app/auth.py` — Parola karması (hash), JWT token üretimi ve oturum doğrulama.
- `app/templating.py` — Jinja2 şablon motorunun merkezi tanımı.
- `app/helpers.py` — Tekrar kullanılan yardımcı fonksiyonlar.
- `app/routers/` — Uç noktalar (endpoint) rollerine göre ayrı dosyalara bölündü:
  `auth.py`, `admin.py`, `ogrenci.py`, `teknisyen.py`, `api.py`. Her biri FastAPI
  `APIRouter` ile modüler hale getirildi.
- `run.py` — Uygulamayı başlatan tek giriş noktası.

Bu yapı sayesinde kodun okunabilirliği, test edilebilirliği ve birden fazla
kişiyle geliştirilmeye uygunluğu önemli ölçüde artmıştır.

## 5. Gereksiz Kodların Temizlenmesi

- Kullanılmayan içe aktarmalar (import) ve ölü kod blokları kaldırıldı.
- Tekrar eden SQL sorguları ve satır eşleme işlemleri ortak yardımcı
  fonksiyonlarda toplandı (örneğin `map_cihaz_row` fonksiyonu ve `CIHAZ_SELECT`
  sabiti).
- Geçici/deneme amaçlı eklenmiş ve kullanılmayan yapılar projeden çıkarıldı.

## 6. Açıklayıcı Yorum Satırları ve Kod Standartları

- Modüllerin başına ve karmaşık fonksiyonlara, "ne yaptığını" değil "neden
  yapıldığını" açıklayan yorumlar eklendi.
- PEP 8 Python kod stiline uyum sağlandı: tutarlı isimlendirme, import düzeni ve
  girinti.
- Sabitler büyük harfle, fonksiyon ve değişkenler anlamlı adlarla
  standartlaştırıldı.

## 7. Proje Klasör Yapısının Düzenlenmesi ve GitHub Hazırlığı

Proje, sürüm kontrolüne hazır profesyonel bir klasör düzenine kavuşturuldu:

```
MakerLab/
├── run.py                 # Giriş noktası
├── requirements.txt       # Bağımlılıklar (sürümleriyle)
├── README.md              # Kurulum, kullanım ve ekran görüntüleri
├── .gitignore             # Sürüm kontrolüne gönderilmeyecek dosyalar
├── app/                   # Uygulama kaynak kodu (modüler)
│   └── routers/           # Role göre uç noktalar
├── templates/             # HTML şablonları
├── static/                # CSS ve statik dosyalar
├── uploads/               # Kullanıcı yüklemeleri (içeriği git'e gönderilmez)
├── screenshots/           # Belgeleme görselleri
└── docs/                  # Ek belgeler
```

Ayrıca:

- `.gitignore` ile sanal ortam, önbellek dosyaları, gizli ayarlar (`.env`) ve
  kullanıcı yüklemeleri sürüm kontrolünden hariç tutuldu.
- `requirements.txt` ile tüm bağımlılıklar sabit sürümleriyle listelendi (kolay
  kurulum sağlandı).
- `README.md`; proje tanımı, kullanılan teknolojiler, kurulum/çalıştırma adımları,
  özellikler, ekran görüntüleri ve klasör yapısını içerecek şekilde hazırlandı.

## 8. Kullanılan Teknolojiler

- **FastAPI** — Web çatısı (backend ve API)
- **Jinja2** — Sunucu tarafı HTML şablonlama
- **pyodbc** — Microsoft SQL Server bağlantısı
- **JWT (JSON Web Token)** — Kimlik doğrulama ve oturum yönetimi
- **Passlib** — Güvenli parola karması
- **Uvicorn** — ASGI sunucusu

## 9. Sonuç

Yapılan çalışmalar sonucunda MakerLab Yönetim Sistemi; daha kullanıcı dostu,
hatalardan arındırılmış, bakımı kolay ve profesyonel standartlarda bir uygulamaya
dönüştürülmüştür. Modüler mimari sayesinde projenin ileride yeni özelliklerle
genişletilmesi ve birden fazla geliştirici tarafından yürütülmesi kolaylaşmıştır.
Proje, GitHub üzerinden paylaşıma ve sürdürülebilir geliştirmeye tam anlamıyla
hazırdır.
