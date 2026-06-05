"""Veritabanı bağlantısı ve şema bakımı."""

from contextlib import contextmanager

import pyodbc

from app.config import DB_CONNECTION_STRING


def get_db_connection():
    """Yeni bir SQL Server bağlantısı açar.

    Çağıran taraf bağlantıyı kapatmaktan sorumludur. Mümkünse `get_cursor`
    context manager'ı tercih edin; o, kapatmayı otomatik yapar.
    """
    return pyodbc.connect(DB_CONNECTION_STRING)


@contextmanager
def get_cursor(commit: bool = False):
    """Bağlantı/cursor yaşam döngüsünü yöneten yardımcı.

    Hata olsa bile bağlantıyı her durumda kapatır; böylece bağlantı sızıntısı
    ve `finally` içinde tanımsız değişken hatası önlenir.

    commit=True verilirse blok başarıyla bitince değişiklikler kaydedilir,
    hata olursa geri alınır (rollback).
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        yield cursor
        if commit:
            conn.commit()
    except Exception:
        if commit:
            conn.rollback()
        raise
    finally:
        conn.close()


def ensure_schema():
    """Cihazlar tablosuna kısa açıklama sütununu (yoksa) ekler."""
    with get_cursor(commit=True) as cursor:
        cursor.execute(
            """
            IF NOT EXISTS (
                SELECT 1 FROM sys.columns
                WHERE object_id = OBJECT_ID('Cihazlar') AND name = 'kisa_aciklama'
            )
            ALTER TABLE Cihazlar ADD kisa_aciklama NVARCHAR(500) NULL
            """
        )
