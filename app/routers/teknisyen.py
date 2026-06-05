"""Teknisyen paneli route'ları."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.auth import get_current_user
from app.config import CIHAZ_SELECT, VARSAYILAN_CIHAZ_ACIKLAMA
from app.database import get_cursor
from app.helpers import dosya_adi, hata_yaniti, map_cihaz_row
from app.templating import templates

router = APIRouter(prefix="/teknisyen")


@router.get("", response_class=HTMLResponse)
async def teknisyen_dashboard(request: Request, user: dict = Depends(get_current_user)):
    """Teknisyen ana sayfası: bekleyen işler, müsait cihazlar ve aktif baskı özetleri."""
    if not user or user.get("rol") != "Teknisyen":
        return RedirectResponse(url="/", status_code=302)

    try:
        with get_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM Is_Talepleri WHERE durum = 'Beklemede'")
            bekleyen_talepler = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM Is_Atamalari WHERE bitis_tarihi IS NULL")
            aktif_baskilar = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM Cihazlar WHERE durum = 'Müsait'")
            musait_cihazlar = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM Stok_Malzemeleri WHERE stok_miktari < 20")
            dusuk_stok = cursor.fetchone()[0]

            cursor.execute(
                """
                SELECT t.id, k.ad_soyad, t.dosya_yolu, t.baski_kalitesi,
                       t.doluluk_orani, t.tahmini_sure_dakika, t.talep_tarihi
                FROM Is_Talepleri t
                JOIN Kullanicilar k ON t.kullanici_id = k.id
                WHERE t.durum = 'Beklemede'
                ORDER BY t.talep_tarihi ASC
                """
            )
            bekleyen_talep_listesi = [
                {
                    "id": row[0],
                    "ogrenci_adi": row[1],
                    "dosya_adi": dosya_adi(row[2]),
                    "baski_kalitesi": row[3],
                    "doluluk_orani": row[4],
                    "tahmini_sure_dakika": row[5],
                    "talep_tarihi": row[6].strftime("%d.%m.%Y %H:%M"),
                }
                for row in cursor.fetchall()
            ]

            cursor.execute(
                "SELECT id, marka_model, kisa_aciklama FROM Cihazlar WHERE durum = 'Müsait'"
            )
            musait_cihaz_listesi = [
                {
                    "id": row[0],
                    "marka_model": row[1],
                    "kisa_aciklama": row[2] if row[2] else VARSAYILAN_CIHAZ_ACIKLAMA,
                }
                for row in cursor.fetchall()
            ]

            cursor.execute(
                """
                SELECT a.id, c.marka_model, t.dosya_yolu, k.ad_soyad, a.baslangic_tarihi
                FROM Is_Atamalari a
                JOIN Cihazlar c ON a.cihaz_id = c.id
                JOIN Is_Talepleri t ON a.talep_id = t.id
                JOIN Kullanicilar k ON t.kullanici_id = k.id
                WHERE a.bitis_tarihi IS NULL
                """
            )
            aktif_baski_listesi = [
                {
                    "id": row[0],
                    "cihaz_adi": row[1],
                    "dosya_adi": dosya_adi(row[2]),
                    "ogrenci_adi": row[3],
                    "baslangic_tarihi": row[4].strftime("%d.%m.%Y %H:%M"),
                }
                for row in cursor.fetchall()
            ]

            cursor.execute(CIHAZ_SELECT)
            cihazlar = [map_cihaz_row(row) for row in cursor.fetchall()]

        return templates.TemplateResponse(
            request=request,
            name="technician_dashboard.html",
            context={
                "kullanici": user,
                "bekleyen_talepler": bekleyen_talepler,
                "aktif_baskilar": aktif_baskilar,
                "musait_cihazlar": musait_cihazlar,
                "dusuk_stok": dusuk_stok,
                "bekleyen_talep_listesi": bekleyen_talep_listesi,
                "musait_cihaz_listesi": musait_cihaz_listesi,
                "aktif_baski_listesi": aktif_baski_listesi,
                "cihazlar": cihazlar,
            },
        )
    except Exception as e:
        return hata_yaniti(str(e))


@router.post("/talep/onayla/{talep_id}")
async def talep_onayla(
    talep_id: int,
    cihaz_id: int = Form(...),
    user: dict = Depends(get_current_user),
):
    """Talebi onaylar ve seçili cihaza atar (cihaz müsait ve stok uygun olmalı)."""
    if not user or user.get("rol") != "Teknisyen":
        return RedirectResponse(url="/", status_code=302)

    try:
        with get_cursor(commit=True) as cursor:
            # Kural 1: Cihaz müsait mi?
            cursor.execute("SELECT durum FROM Cihazlar WHERE id = ?", (cihaz_id,))
            cihaz = cursor.fetchone()
            if not cihaz or cihaz[0] != "Müsait":
                return hata_yaniti("Cihaz müsait değil!", status_code=400)

            # Kural 3: Stok yeterli mi? (Basitleştirilmiş kontrol)
            cursor.execute("SELECT doluluk_orani FROM Is_Talepleri WHERE id = ?", (talep_id,))
            cursor.fetchone()

            cursor.execute("SELECT stok_miktari FROM Stok_Malzemeleri WHERE id = 1")
            stok_verisi = cursor.fetchone()
            if not stok_verisi or stok_verisi[0] <= 0:
                return hata_yaniti(
                    "Stok yetersiz olduğu için bu iş 'Onaylandı' statüsüne geçemez!",
                    status_code=400,
                )

            cursor.execute(
                "UPDATE Is_Talepleri SET durum = 'Onaylandı' WHERE id = ?", (talep_id,)
            )
            cursor.execute(
                """
                INSERT INTO Is_Atamalari (talep_id, cihaz_id, teknisyen_id, baslangic_tarihi)
                VALUES (?, ?, ?, GETDATE())
                """,
                (talep_id, cihaz_id, user.get("id")),
            )
            cursor.execute(
                "UPDATE Cihazlar SET durum = 'Meşgul' WHERE id = ?", (cihaz_id,)
            )
            cursor.execute(
                """
                INSERT INTO Sistem_Loglari (kullanici_id, islem_tipi, detay, islem_tarihi)
                VALUES (?, 'Talep Onayı', ?, GETDATE())
                """,
                (user.get("id"), f"Talep #{talep_id} onaylandı (Stok ve Cihaz doğrulandı)"),
            )

        return RedirectResponse(url="/teknisyen", status_code=302)
    except Exception as e:
        return hata_yaniti(str(e))


@router.post("/talep/reddet/{talep_id}")
async def talep_reddet(talep_id: int, user: dict = Depends(get_current_user)):
    """Bir talebi reddeder ve işlemi loglar."""
    if not user or user.get("rol") != "Teknisyen":
        return RedirectResponse(url="/", status_code=302)

    try:
        with get_cursor(commit=True) as cursor:
            cursor.execute(
                "UPDATE Is_Talepleri SET durum = 'Reddedildi' WHERE id = ?", (talep_id,)
            )
            cursor.execute(
                """
                INSERT INTO Sistem_Loglari (kullanici_id, islem_tipi, detay, islem_tarihi)
                VALUES (?, 'Talep Reddi', ?, GETDATE())
                """,
                (user.get("id"), f"Talep #{talep_id} teknisyen tarafından reddedildi"),
            )

        return RedirectResponse(url="/teknisyen", status_code=302)
    except Exception as e:
        return hata_yaniti(str(e))


@router.post("/baski/tamamla/{atama_id}")
async def baski_tamamla(atama_id: int, user: dict = Depends(get_current_user)):
    """Baskıyı tamamlar: talebi 'Tamamlandı' yapar ve cihazı tekrar 'Müsait' duruma çeker."""
    if not user or user.get("rol") != "Teknisyen":
        return RedirectResponse(url="/", status_code=302)

    try:
        with get_cursor(commit=True) as cursor:
            cursor.execute(
                "SELECT talep_id, cihaz_id FROM Is_Atamalari WHERE id = ?", (atama_id,)
            )
            atama = cursor.fetchone()

            if atama:
                cursor.execute(
                    "UPDATE Is_Atamalari SET bitis_tarihi = GETDATE() WHERE id = ?", (atama_id,)
                )
                cursor.execute(
                    "UPDATE Is_Talepleri SET durum = 'Tamamlandı' WHERE id = ?", (atama[0],)
                )
                cursor.execute(
                    "UPDATE Cihazlar SET durum = 'Müsait' WHERE id = ?", (atama[1],)
                )
                cursor.execute(
                    """
                    INSERT INTO Sistem_Loglari (kullanici_id, islem_tipi, detay, islem_tarihi)
                    VALUES (?, 'Baskı Tamamlama', ?, GETDATE())
                    """,
                    (user.get("id"), f"Atama #{atama_id} başarıyla tamamlandı."),
                )

        return RedirectResponse(url="/teknisyen", status_code=302)
    except Exception as e:
        return hata_yaniti(str(e))


@router.post("/cihaz/durum/{cihaz_id}")
async def cihaz_durum_guncelle(
    cihaz_id: int,
    yeni_durum: str = Form(...),
    user: dict = Depends(get_current_user),
):
    """Cihazın durumunu manuel günceller ve değişikliği loglar."""
    if not user or user.get("rol") != "Teknisyen":
        return RedirectResponse(url="/", status_code=303)

    try:
        with get_cursor(commit=True) as cursor:
            cursor.execute(
                "UPDATE Cihazlar SET durum = ? WHERE id = ?", (yeni_durum, cihaz_id)
            )
            cursor.execute(
                """
                INSERT INTO Sistem_Loglari (kullanici_id, islem_tipi, detay, islem_tarihi)
                VALUES (?, 'Cihaz Durum Güncelleme', ?, GETDATE())
                """,
                (user.get("id"), f"Cihaz #{cihaz_id} durumu '{yeni_durum}' olarak güncellendi."),
            )

        return RedirectResponse(url="/teknisyen", status_code=303)
    except Exception as e:
        return hata_yaniti(str(e))


@router.get("/talepler", response_class=HTMLResponse)
async def teknisyen_tum_talepler(request: Request, user: dict = Depends(get_current_user)):
    """Tüm talepleri teknisyen için listeler."""
    if not user or user.get("rol") != "Teknisyen":
        return RedirectResponse(url="/", status_code=302)

    try:
        with get_cursor() as cursor:
            cursor.execute(
                """
                SELECT t.id, k.ad_soyad, t.dosya_yolu, t.baski_kalitesi, t.durum, t.talep_tarihi
                FROM Is_Talepleri t
                JOIN Kullanicilar k ON t.kullanici_id = k.id
                ORDER BY t.talep_tarihi DESC
                """
            )
            talepler = [
                {
                    "id": row[0],
                    "ogrenci_adi": row[1],
                    "dosya_adi": dosya_adi(row[2]),
                    "baski_kalitesi": row[3],
                    "durum": row[4],
                    "talep_tarihi": row[5].strftime("%d.%m.%Y %H:%M") if row[5] else "-",
                }
                for row in cursor.fetchall()
            ]

        return templates.TemplateResponse(
            request=request,
            name="technician_requests_list.html",
            context={"kullanici": user, "talepler": talepler},
        )
    except Exception as e:
        return hata_yaniti(str(e))


@router.get("/cihazlar", response_class=HTMLResponse)
async def teknisyen_cihaz_listesi(request: Request, user: dict = Depends(get_current_user)):
    """Cihaz listesini teknisyen için gösterir."""
    if not user or user.get("rol") != "Teknisyen":
        return RedirectResponse(url="/", status_code=302)

    try:
        with get_cursor() as cursor:
            cursor.execute(CIHAZ_SELECT)
            cihazlar = [map_cihaz_row(row) for row in cursor.fetchall()]

        return templates.TemplateResponse(
            request=request,
            name="technician_devices_list.html",
            context={"kullanici": user, "cihazlar": cihazlar},
        )
    except Exception as e:
        return hata_yaniti(str(e))


@router.get("/stok", response_class=HTMLResponse)
async def teknisyen_stok_listesi(request: Request, user: dict = Depends(get_current_user)):
    """Stok takip sayfasını teknisyen için gösterir."""
    if not user or user.get("rol") != "Teknisyen":
        return RedirectResponse(url="/", status_code=302)

    try:
        with get_cursor() as cursor:
            cursor.execute(
                """
                SELECT sm.id, sm.malzeme_adi, sk.kategori_adi, sm.stok_miktari, sm.birim
                FROM Stok_Malzemeleri sm
                JOIN Stok_Kategorileri sk ON sm.kategori_id = sk.id
                ORDER BY sm.malzeme_adi ASC
                """
            )
            stoklar = [
                {
                    "id": row[0],
                    "malzeme_adi": row[1],
                    "kategori": row[2],
                    "stok_miktari": row[3],
                    "birim": row[4],
                }
                for row in cursor.fetchall()
            ]

        return templates.TemplateResponse(
            request=request,
            name="technician_stok_list.html",
            context={"kullanici": user, "stoklar": stoklar},
        )
    except Exception as e:
        return hata_yaniti(str(e))
