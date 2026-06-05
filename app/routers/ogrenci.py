"""Öğrenci (müşteri) paneli route'ları."""

import os
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import Optional

from app.auth import get_current_user
from app.config import (
    CIHAZ_SELECT,
    MAKS_BEKLEYEN_TALEP,
    UPLOAD_FOLDER,
)
from app.database import get_cursor
from app.helpers import dosya_adi, hata_yaniti, map_cihaz_row, ogrenci_son_talepler
from app.templating import templates

router = APIRouter(prefix="/ogrenci")


@router.get("", response_class=HTMLResponse)
async def ogrenci_ana_sayfa(request: Request, user: dict = Depends(get_current_user)):
    """Öğrenciyi yeni talep sayfasına yönlendirir."""
    if not user or user.get("rol") != "Öğrenci":
        return RedirectResponse(url="/", status_code=302)
    return RedirectResponse(url="/ogrenci/yeni-talep", status_code=302)


@router.get("/cihazlar", response_class=HTMLResponse)
async def ogrenci_cihaz_listesi(request: Request, user: dict = Depends(get_current_user)):
    """Atölyedeki cihazları durum ve kısa açıklamalarıyla öğrenciye gösterir."""
    if not user or user.get("rol") != "Öğrenci":
        return RedirectResponse(url="/", status_code=302)

    try:
        with get_cursor() as cursor:
            cursor.execute(CIHAZ_SELECT + " ORDER BY eklenme_tarihi DESC")
            cihazlar = [map_cihaz_row(row) for row in cursor.fetchall()]

        return templates.TemplateResponse(
            request=request,
            name="student_devices_list.html",
            context={"kullanici": user, "cihazlar": cihazlar},
        )
    except Exception as e:
        return hata_yaniti(str(e))


@router.get("/yeni-talep", response_class=HTMLResponse)
async def yeni_talep_sayfasi(request: Request, user: dict = Depends(get_current_user)):
    """Yeni baskı talebi formu; son talepleri ve tahmini bitiş tarihlerini de gösterir."""
    if not user or user.get("rol") != "Öğrenci":
        return RedirectResponse(url="/", status_code=302)

    try:
        with get_cursor() as cursor:
            son_talepler, _ = ogrenci_son_talepler(cursor, user.get("id"))

        return templates.TemplateResponse(
            request=request,
            name="student_request.html",
            context={"kullanici": user, "son_talepler": son_talepler},
        )
    except Exception as e:
        return hata_yaniti(str(e))


@router.post("/yeni-talep")
async def talep_olustur(
    request: Request,
    dosya: UploadFile = File(...),
    baski_kalitesi: str = Form(...),
    doluluk_orani: int = Form(...),
    tahmini_sure: Optional[int] = Form(None),
    user: dict = Depends(get_current_user),
):
    """Yeni baskı talebi kaydeder. Aynı anda en fazla MAKS_BEKLEYEN_TALEP beklemede talep olabilir."""
    if not user or user.get("rol") != "Öğrenci":
        return RedirectResponse(url="/", status_code=302)

    try:
        with get_cursor(commit=True) as cursor:
            # Beklemede talep sayısı üst sınırı aşıyor mu?
            cursor.execute(
                "SELECT COUNT(*) FROM Is_Talepleri WHERE kullanici_id = ? AND durum = 'Beklemede'",
                (user.get("id"),),
            )
            aktif_talep_sayisi = cursor.fetchone()[0]

            if aktif_talep_sayisi >= MAKS_BEKLEYEN_TALEP:
                mevcut_talepler, en_erken_bos = ogrenci_son_talepler(cursor, user.get("id"))
                if en_erken_bos:
                    tarih_str = en_erken_bos.strftime("%d.%m.%Y %H:%M")
                    limit_bilgi = (
                        f"Şu anda {MAKS_BEKLEYEN_TALEP} beklemede talebiniz var (üst sınır). "
                        f"Mevcut talepleriniz sırayla işleniyor; en erken {tarih_str} tarihinde "
                        f"bir talebiniz tamamlanacak. Yeni talebinizi o tarihten itibaren oluşturabilirsiniz."
                    )
                else:
                    limit_bilgi = (
                        f"Aynı anda en fazla {MAKS_BEKLEYEN_TALEP} beklemede talep oluşturabilirsiniz."
                    )
                return templates.TemplateResponse(
                    request=request,
                    name="student_request.html",
                    context={
                        "kullanici": user,
                        "limit_bilgi": limit_bilgi,
                        "son_talepler": mevcut_talepler,
                    },
                )

            # Yüklenen dosyayı benzersiz adla kaydet.
            kayit_adi = f"{user.get('id')}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{dosya.filename}"
            dosya_yolu = os.path.join(UPLOAD_FOLDER, kayit_adi)
            with open(dosya_yolu, "wb") as f:
                f.write(await dosya.read())

            cursor.execute(
                """
                INSERT INTO Is_Talepleri
                    (kullanici_id, dosya_yolu, durum, talep_tarihi, doluluk_orani, baski_kalitesi, tahmini_sure_dakika)
                VALUES (?, ?, 'Beklemede', GETDATE(), ?, ?, ?)
                """,
                (user.get("id"), dosya_yolu, doluluk_orani, baski_kalitesi, tahmini_sure or 0),
            )

        return RedirectResponse(url="/ogrenci/yeni-talep", status_code=303)

    except Exception as e:
        # Hata olsa bile öğrenciye son taleplerini göstermeye çalış.
        try:
            with get_cursor() as cursor:
                mevcutlar, _ = ogrenci_son_talepler(cursor, user.get("id"))
        except Exception:
            mevcutlar = []
        return templates.TemplateResponse(
            request=request,
            name="student_request.html",
            context={"kullanici": user, "error": str(e), "son_talepler": mevcutlar},
        )


@router.get("/taleplerim", response_class=HTMLResponse)
async def ogrenci_tum_talepler(request: Request, user: dict = Depends(get_current_user)):
    """Öğrencinin tüm taleplerini tarih sırasıyla listeler."""
    if not user or user.get("rol") != "Öğrenci":
        return RedirectResponse(url="/", status_code=302)

    try:
        with get_cursor() as cursor:
            cursor.execute(
                """
                SELECT id, dosya_yolu, baski_kalitesi, durum, talep_tarihi
                FROM Is_Talepleri
                WHERE kullanici_id = ?
                ORDER BY talep_tarihi DESC
                """,
                (user.get("id"),),
            )
            talepler = [
                {
                    "id": row[0],
                    "dosya_adi": dosya_adi(row[1]),
                    "baski_kalitesi": row[2],
                    "durum": row[3],
                    "talep_tarihi": row[4].strftime("%d.%m.%Y"),
                }
                for row in cursor.fetchall()
            ]

        return templates.TemplateResponse(
            request=request,
            name="student_requests_list.html",
            context={"kullanici": user, "talepler": talepler},
        )
    except Exception as e:
        return hata_yaniti(str(e))


@router.get("/rezervasyon", response_class=HTMLResponse)
async def ogrenci_rezervasyon_sayfasi(request: Request, user: dict = Depends(get_current_user)):
    """Malzeme rezervasyon formu: stokta olan malzemeleri listeler."""
    if not user or user.get("rol") != "Öğrenci":
        return RedirectResponse(url="/", status_code=302)

    try:
        with get_cursor() as cursor:
            cursor.execute(
                """
                SELECT sm.id, sm.malzeme_adi, sk.kategori_adi, sm.stok_miktari, sm.birim
                FROM Stok_Malzemeleri sm
                JOIN Stok_Kategorileri sk ON sm.kategori_id = sk.id
                WHERE sm.stok_miktari > 0
                """
            )
            malzemeler = [
                {
                    "id": row[0],
                    "malzeme_adi": row[1],
                    "kategori": row[2],
                    "stok": row[3],
                    "birim": row[4],
                }
                for row in cursor.fetchall()
            ]

        return templates.TemplateResponse(
            request=request,
            name="student_reserve_material.html",
            context={"kullanici": user, "malzemeler": malzemeler},
        )
    except Exception as e:
        return hata_yaniti(str(e))


@router.post("/malzeme-rezerve")
async def malzeme_rezerve_et(
    request: Request,
    malzeme_id: int = Form(...),
    miktar: int = Form(...),
    user: dict = Depends(get_current_user),
):
    """Seçilen malzemeyi stoktan düşerek rezerve eder (stok yetersizse hata verir)."""
    if not user or user.get("rol") != "Öğrenci":
        return RedirectResponse(url="/", status_code=302)

    try:
        with get_cursor(commit=True) as cursor:
            cursor.execute(
                "SELECT malzeme_adi, stok_miktari, birim FROM Stok_Malzemeleri WHERE id = ?",
                (malzeme_id,),
            )
            res = cursor.fetchone()

            if not res:
                return hata_yaniti("Malzeme bulunamadı!", status_code=404)
            if miktar <= 0:
                return hata_yaniti("Miktar 0'dan büyük olmalıdır!", status_code=400)
            if miktar > res[1]:
                return hata_yaniti("Yetersiz stok!", status_code=400)

            malzeme_adi = res[0]
            birim = res[2] if res[2] else "adet"

            # Rezervasyonu iş talebi olarak kaydet.
            cursor.execute(
                """
                INSERT INTO Is_Talepleri (kullanici_id, dosya_yolu, durum, talep_tarihi)
                VALUES (?, ?, 'Beklemede', GETDATE())
                """,
                (user.get("id"), f"STOK_TALEBI | {miktar} {birim} {malzeme_adi}"),
            )

            # Stoğu düş.
            cursor.execute(
                "UPDATE Stok_Malzemeleri SET stok_miktari = stok_miktari - ? WHERE id = ?",
                (miktar, malzeme_id),
            )

            cursor.execute(
                """
                INSERT INTO Sistem_Loglari (kullanici_id, islem_tipi, detay, islem_tarihi)
                VALUES (?, 'Malzeme Rezervasyonu', ?, GETDATE())
                """,
                (user.get("id"), f"{miktar} adet {malzeme_adi} rezerve edildi"),
            )
    except Exception as e:
        return hata_yaniti(f"İşlem Başarısız: {e}")

    return RedirectResponse(url="/ogrenci", status_code=303)


@router.post("/talep/sil/{talep_id}")
async def talep_sil(talep_id: int, user: dict = Depends(get_current_user)):
    """Yalnızca 'Beklemede' durumundaki ve kullanıcıya ait talebin silinmesine izin verir."""
    if not user or user.get("rol") != "Öğrenci":
        return RedirectResponse(url="/", status_code=302)

    try:
        with get_cursor(commit=True) as cursor:
            # Talep gerçekten bu öğrenciye mi ait ve 'Beklemede' mi?
            cursor.execute(
                "SELECT durum FROM Is_Talepleri WHERE id = ? AND kullanici_id = ?",
                (talep_id, user.get("id")),
            )
            talep = cursor.fetchone()
            if talep and talep[0] == "Beklemede":
                cursor.execute("DELETE FROM Is_Talepleri WHERE id = ?", (talep_id,))

        return RedirectResponse(url="/ogrenci/yeni-talep", status_code=303)
    except Exception as e:
        return hata_yaniti(str(e))


@router.post("/talep/duzenle/{talep_id}")
async def talep_duzenle(
    talep_id: int,
    baski_kalitesi: str = Form(...),
    doluluk_orani: int = Form(...),
    tahmini_sure: Optional[int] = Form(None),
    renk: str = Form("Farketmez"),
    aciklama: str = Form(None),
    user: dict = Depends(get_current_user),
):
    """Yalnızca 'Beklemede' durumundaki kendi talebinin tüm alanlarını günceller."""
    if not user or user.get("rol") != "Öğrenci":
        return RedirectResponse(url="/", status_code=302)

    try:
        with get_cursor(commit=True) as cursor:
            cursor.execute(
                """
                UPDATE Is_Talepleri
                SET baski_kalitesi = ?,
                    doluluk_orani = ?,
                    tahmini_sure_dakika = ?,
                    filament_rengi = ?,
                    aciklama = ?
                WHERE id = ? AND kullanici_id = ? AND durum = 'Beklemede'
                """,
                (baski_kalitesi, doluluk_orani, tahmini_sure or 0, renk, aciklama, talep_id, user.get("id")),
            )

        return RedirectResponse(url="/ogrenci/yeni-talep", status_code=303)
    except Exception as e:
        return hata_yaniti(str(e))
