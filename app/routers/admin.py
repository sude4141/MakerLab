"""Yönetici (admin) paneli route'ları."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.auth import get_current_user, get_password_hash
from app.config import CIHAZ_SELECT, VARSAYILAN_CIHAZ_ACIKLAMA
from app.database import get_cursor
from app.helpers import dosya_adi, hata_yaniti, map_cihaz_row
from app.templating import templates

router = APIRouter(prefix="/admin")


@router.get("", response_class=HTMLResponse)
async def admin_dashboard(request: Request, user: dict = Depends(get_current_user)):
    """Yönetici ana sayfası: özet istatistikler, son talepler, cihazlar ve kritik stoklar."""
    if not user or user.get("rol") != "Yönetici":
        return RedirectResponse(url="/", status_code=302)

    try:
        with get_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM Cihazlar")
            cihaz_sayisi = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM Is_Talepleri WHERE durum = 'Beklemede'")
            bekleyen_talepler = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM Is_Talepleri WHERE durum = 'Tamamlandı'")
            tamamlanan_isler = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM Stok_Malzemeleri WHERE stok_miktari < 10")
            kritik_stok_sayisi = cursor.fetchone()[0]

            cursor.execute(
                """
                SELECT TOP 5 t.id, k.ad_soyad, t.durum, t.talep_tarihi
                FROM Is_Talepleri t
                JOIN Kullanicilar k ON t.kullanici_id = k.id
                ORDER BY t.talep_tarihi DESC
                """
            )
            son_talepler = [
                {
                    "id": row[0],
                    "ogrenci_adi": row[1],
                    "durum": row[2],
                    "talep_tarihi": row[3].strftime("%d.%m.%Y"),
                }
                for row in cursor.fetchall()
            ]

            cursor.execute(CIHAZ_SELECT + " ORDER BY eklenme_tarihi DESC")
            cihazlar = [map_cihaz_row(row) for row in cursor.fetchall()]

            cursor.execute(
                """
                SELECT sm.id, sm.malzeme_adi, sk.kategori_adi, sm.stok_miktari, sm.birim
                FROM Stok_Malzemeleri sm
                JOIN Stok_Kategorileri sk ON sm.kategori_id = sk.id
                WHERE sm.stok_miktari < 10
                """
            )
            kritik_stoklar = [
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
            name="admin_dashboard.html",
            context={
                "kullanici": user,
                "cihaz_sayisi": cihaz_sayisi,
                "bekleyen_talepler": bekleyen_talepler,
                "tamamlanan_isler": tamamlanan_isler,
                "kritik_stok": kritik_stok_sayisi,
                "son_talepler": son_talepler,
                "cihazlar": cihazlar,
                "kritik_stoklar": kritik_stoklar,
            },
        )
    except Exception as e:
        return hata_yaniti(str(e))


@router.post("/cihaz-ekle")
async def cihaz_ekle(
    marka_model: str = Form(...),
    kisa_aciklama: str = Form(""),
    user: dict = Depends(get_current_user),
):
    """Sisteme yeni cihaz ekler (varsayılan durum 'Müsait')."""
    if not user or user.get("rol") != "Yönetici":
        return RedirectResponse(url="/", status_code=302)

    aciklama = kisa_aciklama.strip() or VARSAYILAN_CIHAZ_ACIKLAMA
    with get_cursor(commit=True) as cursor:
        cursor.execute(
            "INSERT INTO Cihazlar (marka_model, durum, eklenme_tarihi, kisa_aciklama) "
            "VALUES (?, 'Müsait', GETDATE(), ?)",
            (marka_model, aciklama),
        )
    return RedirectResponse(url="/admin", status_code=303)


@router.post("/cihaz-aciklama/{cihaz_id}")
async def cihaz_aciklama_guncelle(
    cihaz_id: int,
    kisa_aciklama: str = Form(""),
    user: dict = Depends(get_current_user),
):
    """Var olan bir cihazın müşteri bilgilendirme açıklamasını günceller."""
    if not user or user.get("rol") != "Yönetici":
        return RedirectResponse(url="/", status_code=302)

    aciklama = kisa_aciklama.strip() or VARSAYILAN_CIHAZ_ACIKLAMA
    with get_cursor(commit=True) as cursor:
        cursor.execute(
            "UPDATE Cihazlar SET kisa_aciklama = ? WHERE id = ?",
            (aciklama, cihaz_id),
        )
    return RedirectResponse(url="/admin/cihazlar", status_code=303)


@router.post("/cihaz-sil/{cihaz_id}")
async def cihaz_sil(cihaz_id: int, user: dict = Depends(get_current_user)):
    """Cihazı sistemden siler."""
    if not user or user.get("rol") != "Yönetici":
        return RedirectResponse(url="/", status_code=302)

    with get_cursor(commit=True) as cursor:
        cursor.execute("DELETE FROM Cihazlar WHERE id = ?", (cihaz_id,))
    return RedirectResponse(url="/admin", status_code=303)


@router.post("/personel-ekle")
async def personel_ekle(
    ad_soyad: str = Form(...),
    email: str = Form(...),
    sifre: str = Form(...),
    user: dict = Depends(get_current_user),
):
    """Sisteme yeni teknisyen (personel) ekler ve rolünü atar."""
    if not user or user.get("rol") != "Yönetici":
        return RedirectResponse(url="/", status_code=302)

    try:
        sifre_hash = get_password_hash(sifre)
        with get_cursor(commit=True) as cursor:
            # Kullanıcıyı ekle ve yeni ID'yi al.
            cursor.execute(
                """
                INSERT INTO Kullanicilar (ad_soyad, email, sifre_hash, eklenme_tarihi)
                OUTPUT INSERTED.id
                VALUES (?, ?, ?, GETDATE())
                """,
                (ad_soyad, email, sifre_hash),
            )
            yeni_id = cursor.fetchone()[0]

            # Teknisyen rolünü (rol_id=2) ata.
            cursor.execute(
                "INSERT INTO Kullanici_Rolleri (kullanici_id, rol_id) VALUES (?, 2)",
                (yeni_id,),
            )

            cursor.execute(
                """
                INSERT INTO Sistem_Loglari (kullanici_id, islem_tipi, detay, islem_tarihi)
                VALUES (?, 'Personel Kaydı', ?, GETDATE())
                """,
                (user.get("id"), f"Yeni personel eklendi: {ad_soyad} ({email})"),
            )

        return RedirectResponse(url="/admin", status_code=303)
    except Exception as e:
        return hata_yaniti(str(e))


@router.get("/talepler", response_class=HTMLResponse)
async def admin_tum_talepler(request: Request, user: dict = Depends(get_current_user)):
    """Tüm iş taleplerini öğrenci adı, dosya ve durum bilgisiyle listeler."""
    if not user or user.get("rol") != "Yönetici":
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
                    "talep_tarihi": row[5].strftime("%d.%m.%Y") if row[5] else "-",
                }
                for row in cursor.fetchall()
            ]

        return templates.TemplateResponse(
            request=request,
            name="admin_requests_list.html",
            context={"kullanici": user, "talepler": talepler},
        )
    except Exception as e:
        return hata_yaniti(str(e))


@router.get("/cihazlar", response_class=HTMLResponse)
async def admin_cihaz_listesi(request: Request, user: dict = Depends(get_current_user)):
    """Cihaz yönetim listesini gösterir."""
    if not user or user.get("rol") != "Yönetici":
        return RedirectResponse(url="/", status_code=302)

    try:
        with get_cursor() as cursor:
            cursor.execute(CIHAZ_SELECT)
            cihazlar = [map_cihaz_row(row) for row in cursor.fetchall()]

        return templates.TemplateResponse(
            request=request,
            name="admin_devices_list.html",
            context={"kullanici": user, "cihazlar": cihazlar},
        )
    except Exception as e:
        return hata_yaniti(str(e))


@router.get("/stoklar", response_class=HTMLResponse)
async def admin_stok_listesi(request: Request, user: dict = Depends(get_current_user)):
    """Stok malzemelerini kategorileriyle birlikte listeler."""
    if not user or user.get("rol") != "Yönetici":
        return RedirectResponse(url="/", status_code=302)

    try:
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT id, kategori_adi FROM Stok_Kategorileri ORDER BY kategori_adi ASC"
            )
            kategoriler = [{"id": r[0], "kategori_adi": r[1]} for r in cursor.fetchall()]

            cursor.execute(
                """
                SELECT sm.id, sm.malzeme_adi, sk.kategori_adi, sm.stok_miktari, sm.birim
                FROM Stok_Malzemeleri sm
                JOIN Stok_Kategorileri sk ON sm.kategori_id = sk.id
                ORDER BY sm.malzeme_adi ASC
                """
            )
            stok_listesi = [
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
            name="admin_stok_yonetimi.html",
            context={
                "kullanici": user,
                "stoklar": stok_listesi,
                "kategoriler": kategoriler,
            },
        )
    except Exception as e:
        return hata_yaniti(str(e))


@router.post("/stok-ekle")
async def admin_stok_ekle(
    malzeme_adi: str = Form(...),
    kategori_id: int = Form(...),
    miktar: int = Form(...),
    birim: str = Form(...),
    user: dict = Depends(get_current_user),
):
    """Yeni stok kalemi ekler."""
    if not user or user.get("rol") != "Yönetici":
        return RedirectResponse(url="/", status_code=302)

    try:
        with get_cursor(commit=True) as cursor:
            cursor.execute(
                "INSERT INTO Stok_Malzemeleri (malzeme_adi, kategori_id, stok_miktari, birim) "
                "VALUES (?, ?, ?, ?)",
                (malzeme_adi, kategori_id, miktar, birim),
            )
    except Exception as e:
        return hata_yaniti(f"Ekleme Hatası: {e}")

    return RedirectResponse(url="/admin/stoklar", status_code=303)


@router.get("/kullanicilar", response_class=HTMLResponse)
async def admin_kullanici_listesi(request: Request, user: dict = Depends(get_current_user)):
    """Tüm kullanıcıları ve rollerini listeler."""
    if not user or user.get("rol") != "Yönetici":
        return RedirectResponse(url="/", status_code=302)

    try:
        with get_cursor() as cursor:
            cursor.execute(
                """
                SELECT k.id, k.ad_soyad, k.email, r.rol_adi
                FROM Kullanicilar k
                JOIN Kullanici_Rolleri kr ON k.id = kr.kullanici_id
                JOIN Roller r ON kr.rol_id = r.id
                """
            )
            kullanicilar_verisi = [
                {"id": row[0], "ad_soyad": row[1], "email": row[2], "rol": row[3]}
                for row in cursor.fetchall()
            ]

        return templates.TemplateResponse(
            request=request,
            name="admin_users_list.html",
            context={
                "kullanici": user,
                "kullanicilar": kullanicilar_verisi,
                "success": request.query_params.get("success"),
                "error": request.query_params.get("error"),
            },
        )
    except Exception as e:
        return hata_yaniti(str(e))


@router.post("/kullanicilar/sil/{kullanici_id}")
async def admin_kullanici_sil(kullanici_id: int, user: dict = Depends(get_current_user)):
    """Kullanıcıyı siler (kendi hesabını ve ilişkili kayıtları olanları engeller)."""
    if not user or user.get("rol") != "Yönetici":
        return RedirectResponse(url="/", status_code=302)

    # Yönetici kendi hesabını silemez.
    if kullanici_id == user.get("id"):
        return RedirectResponse(
            url="/admin/kullanicilar?error=Kendi+hesabinizi+silemezsiniz",
            status_code=303,
        )

    try:
        with get_cursor(commit=True) as cursor:
            cursor.execute(
                "SELECT id, ad_soyad FROM Kullanicilar WHERE id = ?", (kullanici_id,)
            )
            hedef = cursor.fetchone()
            if not hedef:
                return RedirectResponse(
                    url="/admin/kullanicilar?error=Kullanici+bulunamadi",
                    status_code=303,
                )

            # Veri kaybını önlemek için ilişkili kayıt kontrolü.
            cursor.execute(
                "SELECT COUNT(*) FROM Is_Talepleri WHERE kullanici_id = ?", (kullanici_id,)
            )
            talep_sayisi = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM Is_Atamalari WHERE teknisyen_id = ?", (kullanici_id,)
            )
            atama_sayisi = cursor.fetchone()[0]

            if talep_sayisi > 0 or atama_sayisi > 0:
                return RedirectResponse(
                    url="/admin/kullanicilar?error=Kullaniciya+bagli+talep+veya+atama+kayitlari+var",
                    status_code=303,
                )

            # Önce rol eşleşmelerini, sonra kullanıcıyı sil.
            cursor.execute(
                "DELETE FROM Kullanici_Rolleri WHERE kullanici_id = ?", (kullanici_id,)
            )
            cursor.execute("DELETE FROM Kullanicilar WHERE id = ?", (kullanici_id,))

            cursor.execute(
                """
                INSERT INTO Sistem_Loglari (kullanici_id, islem_tipi, detay, islem_tarihi)
                VALUES (?, 'Kullanici Silme', ?, GETDATE())
                """,
                (user.get("id"), f"Kullanici silindi: {hedef[1]} (ID: {kullanici_id})"),
            )

        return RedirectResponse(
            url="/admin/kullanicilar?success=Kullanici+basariyla+silindi",
            status_code=303,
        )
    except Exception:
        return RedirectResponse(
            url="/admin/kullanicilar?error=Silme+islemi+sirasinda+hata+olustu",
            status_code=303,
        )


@router.get("/loglar", response_class=HTMLResponse)
async def admin_sistem_loglari(request: Request, user: dict = Depends(get_current_user)):
    """Son sistem log kayıtlarını listeler."""
    if not user or user.get("rol") != "Yönetici":
        return RedirectResponse(url="/", status_code=302)

    try:
        with get_cursor() as cursor:
            cursor.execute(
                """
                SELECT TOP 200 l.id, k.ad_soyad, l.islem_tipi, l.detay, l.islem_tarihi
                FROM Sistem_Loglari l
                LEFT JOIN Kullanicilar k ON l.kullanici_id = k.id
                ORDER BY l.islem_tarihi DESC
                """
            )
            loglar = [
                {
                    "id": row[0],
                    "kullanici_adi": row[1] if row[1] else "Sistem",
                    "islem_tipi": row[2],
                    "detay": row[3] if row[3] else "-",
                    "islem_tarihi": row[4].strftime("%d.%m.%Y %H:%M") if row[4] else "-",
                }
                for row in cursor.fetchall()
            ]

        return templates.TemplateResponse(
            request=request,
            name="admin_logs_list.html",
            context={"kullanici": user, "loglar": loglar},
        )
    except Exception as e:
        return hata_yaniti(str(e))
