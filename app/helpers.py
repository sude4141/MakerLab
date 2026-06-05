"""Router'ların paylaştığı yardımcı fonksiyonlar (veri dönüştürme, hesaplama)."""

import os
from datetime import datetime, timedelta

from fastapi.responses import HTMLResponse

from app.config import (
    VARSAYILAN_BASKI_DAKIKA,
    VARSAYILAN_CIHAZ_ACIKLAMA,
)


def hata_yaniti(mesaj: str, status_code: int = 500) -> HTMLResponse:
    """Beklenmeyen hatalar için tek tip, basit bir hata sayfası döndürür.

    Hata ayrıca konsola yazılır; böylece geliştirme sırasında kök neden takip edilebilir.
    """
    print(f"[MakerLab] Hata: {mesaj}")
    govde = (
        "<div style='font-family:sans-serif;max-width:600px;margin:80px auto;text-align:center;'>"
        "<h1 style='color:#c0392b;'>Bir hata oluştu</h1>"
        f"<p style='color:#555;'>{mesaj}</p>"
        "<a href='/' style='color:#1e88e5;'>Ana sayfaya dön</a>"
        "</div>"
    )
    return HTMLResponse(content=govde, status_code=status_code)


def dosya_adi(yol) -> str:
    """Tam dosya yolundan yalnızca dosya adını döndürür (yol boşsa 'Dosya yok')."""
    return os.path.basename(yol) if yol else "Dosya yok"


def map_cihaz_row(row) -> dict:
    """CIHAZ_SELECT sonucundaki bir satırı şablonların beklediği sözlüğe çevirir."""
    eklenme = row[3].strftime("%d.%m.%Y") if row[3] else "-"
    kisa = row[4] if len(row) > 4 and row[4] else VARSAYILAN_CIHAZ_ACIKLAMA
    return {
        "id": row[0],
        "marka_model": row[1],
        "durum": row[2],
        "eklenme_tarihi": eklenme,
        "kisa_aciklama": kisa,
    }


def hesapla_kuyruk_bitis(bekleyenler):
    """Sıralı baskı kuyruğu varsayımıyla her bekleyen talebin tahmini bitiş zamanını hesaplar.

    bekleyenler: (talep_id, tahmini_sure_dakika) listesi; eskiden yeniye sıralı olmalı.
    Dönüş: {talep_id: bitis_datetime}
    """
    bitis = {}
    birikimli = datetime.now()
    for talep_id, sure in bekleyenler:
        dakika = sure if sure and sure > 0 else VARSAYILAN_BASKI_DAKIKA
        birikimli = birikimli + timedelta(minutes=dakika)
        bitis[talep_id] = birikimli
    return bitis


def ogrenci_son_talepler(cursor, kullanici_id, limit=5):
    """Öğrencinin son taleplerini, bekleyenlere tahmini bitiş tarihi ekleyerek döndürür.

    Ayrıca bir slotun en erken boşalacağı tarihi (en erken bitiş) de verir;
    bu tarih, üst sınıra ulaşıldığında yeni talebin ne zaman oluşturulabileceğini gösterir.
    """
    cursor.execute(
        f"""SELECT TOP {int(limit)} id, dosya_yolu, baski_kalitesi, durum, talep_tarihi,
                   doluluk_orani, tahmini_sure_dakika
            FROM Is_Talepleri WHERE kullanici_id = ? ORDER BY talep_tarihi DESC""",
        (kullanici_id,),
    )
    rows = cursor.fetchall()
    bekleyenler = sorted([r for r in rows if r[3] == "Beklemede"], key=lambda r: r[4])
    bitis_map = hesapla_kuyruk_bitis([(r[0], r[6]) for r in bekleyenler])

    talepler = []
    for r in rows:
        bitis_dt = bitis_map.get(r[0])
        talepler.append({
            "id": r[0],
            "dosya_adi": os.path.basename(r[1]) if r[1] else "Dosya yok",
            "baski_kalitesi": r[2],
            "durum": r[3],
            "talep_tarihi": r[4].strftime("%d.%m.%Y"),
            "doluluk_orani": r[5],
            "tahmini_sure_dakika": r[6],
            "tahmini_bitis": bitis_dt.strftime("%d.%m.%Y %H:%M") if bitis_dt else None,
        })

    en_erken_bos = min(bitis_map.values()) if bitis_map else None
    return talepler, en_erken_bos
