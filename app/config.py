"""Uygulama genelinde kullanılan ayarlar ve sabitler.

Gizli/makineye özel değerler (DB bağlantısı, SECRET_KEY) burada toplanır.
Ortam değişkeni tanımlıysa o kullanılır, yoksa buradaki varsayılana düşülür.
"""

import os
from pathlib import Path

# Proje kök dizini (bu dosya app/ altında olduğu için iki seviye yukarısı).
# Template ve static klasörleri çalışma dizininden bağımsız bulunabilsin diye kullanılır.
BASE_DIR = Path(__file__).resolve().parent.parent

TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# Yüklenen STL/3D dosyalarının saklandığı klasör.
UPLOAD_FOLDER = str(BASE_DIR / "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ==================== Veritabanı ====================
# SQL Server bağlantı dizesi. Farklı bir makinede çalıştırmak için
# MAKERLAB_DB_CONNECTION ortam değişkeni tanımlanabilir.
DB_CONNECTION_STRING = os.getenv(
    "MAKERLAB_DB_CONNECTION",
    r"DRIVER={SQL Server};"
    r"SERVER=LAPTOP-F17T2ILF\SQLEXPRESS;"
    r"DATABASE=MakerLabDB;"
    r"Trusted_Connection=yes;",
)

# ==================== Kimlik Doğrulama (JWT) ====================
SECRET_KEY = os.getenv("MAKERLAB_SECRET_KEY", "MakerLab_Cok_Gizli_Anahtar_123")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# ==================== İş Kuralları / Varsayılanlar ====================
# Bir öğrencinin aynı anda sahip olabileceği en fazla "Beklemede" talep sayısı.
MAKS_BEKLEYEN_TALEP = 3

# Tahmini süre girilmemiş bir baskı için varsayılan süre (dakika).
VARSAYILAN_BASKI_DAKIKA = 120

# Cihaz için müşteriyi bilgilendiren varsayılan kısa açıklama.
VARSAYILAN_CIHAZ_ACIKLAMA = (
    "3D baskı cihazı. Sıcak nozul ve hareketli eksenler vardır; "
    "baskı sırasında yetkisiz müdahale etmeyin, çocukların yaklaşmaması önerilir."
)

# Cihaz listelerinde tekrar eden temel SELECT.
CIHAZ_SELECT = "SELECT id, marka_model, durum, eklenme_tarihi, kisa_aciklama FROM Cihazlar"
