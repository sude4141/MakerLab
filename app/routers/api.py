"""JSON API uç noktaları ve yüklenen dosya indirme route'u."""

import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.auth import get_current_user
from app.config import UPLOAD_FOLDER
from app.database import get_cursor

router = APIRouter()


@router.get("/api/cihazlar")
async def api_cihazlar(user: dict = Depends(get_current_user)):
    """Tüm cihazları JSON olarak döndürür (giriş yapmış kullanıcılar)."""
    if not user:
        raise HTTPException(status_code=401, detail="Yetkisiz erişim!")

    try:
        with get_cursor() as cursor:
            cursor.execute("SELECT id, marka_model, durum, eklenme_tarihi FROM Cihazlar")
            return [
                {
                    "id": row[0],
                    "marka_model": row[1],
                    "durum": row[2],
                    "eklenme_tarihi": row[3].isoformat() if row[3] else None,
                }
                for row in cursor.fetchall()
            ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/talepler")
async def api_talepler(user: dict = Depends(get_current_user)):
    """Tüm talepleri JSON olarak döndürür (yalnızca yönetici/teknisyen)."""
    if not user or user.get("rol") not in ["Yönetici", "Teknisyen"]:
        raise HTTPException(status_code=403, detail="Bu veriyi görme yetkiniz yok!")

    try:
        with get_cursor() as cursor:
            cursor.execute(
                """
                SELECT t.id, k.ad_soyad, t.durum, t.talep_tarihi, t.baski_kalitesi
                FROM Is_Talepleri t
                JOIN Kullanicilar k ON t.kullanici_id = k.id
                ORDER BY t.talep_tarihi DESC
                """
            )
            return [
                {
                    "id": row[0],
                    "ogrenci": row[1],
                    "durum": row[2],
                    "tarih": row[3].isoformat() if row[3] else None,
                    "kalite": row[4],
                }
                for row in cursor.fetchall()
            ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/stok")
async def api_stok(user: dict = Depends(get_current_user)):
    """Stok bilgilerini JSON olarak döndürür (giriş yapmış kullanıcılar)."""
    if not user:
        raise HTTPException(status_code=401, detail="Önce giriş yapmalısınız!")

    try:
        with get_cursor() as cursor:
            cursor.execute(
                """
                SELECT sm.id, sm.malzeme_adi, sk.kategori_adi, sm.stok_miktari, sm.birim
                FROM Stok_Malzemeleri sm
                JOIN Stok_Kategorileri sk ON sm.kategori_id = sk.id
                """
            )
            return [
                {
                    "id": row[0],
                    "malzeme": row[1],
                    "kategori": row[2],
                    "miktar": row[3],
                    "birim": row[4],
                }
                for row in cursor.fetchall()
            ]
    except Exception as e:
        print(f"API Hatası: {e}")
        raise HTTPException(
            status_code=500, detail="Veritabanı sorgusu sırasında bir hata oluştu."
        )


@router.get("/indir/{dosya_adi}")
async def dosya_indir(dosya_adi: str, user: dict = Depends(get_current_user)):
    """Yüklenmiş dosyayı yalnızca teknisyen/yöneticiye indirtir."""
    if not user or user.get("rol") not in ["Teknisyen", "Yönetici"]:
        raise HTTPException(status_code=403, detail="Yetkiniz yok")

    dosya_yolu = os.path.join(UPLOAD_FOLDER, dosya_adi)
    if os.path.exists(dosya_yolu):
        return FileResponse(path=dosya_yolu, filename=dosya_adi)
    raise HTTPException(status_code=404, detail="Dosya bulunamadı")
