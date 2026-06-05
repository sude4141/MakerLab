"""MakerLab - 3D Baskı ve Elektronik Atölyesi Yönetim Sistemi.

FastAPI uygulamasının oluşturulduğu, statik dosyaların bağlandığı ve
router'ların eklendiği merkez modül.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import STATIC_DIR
from app.database import ensure_schema
from app.routers import admin, api, auth, ogrenci, teknisyen


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Uygulama açılırken veritabanı şemasını (eksik kolonları) tamamlar."""
    try:
        ensure_schema()
    except Exception as e:
        print(f"Şema kontrolü başarısız: {e}")
    yield


app = FastAPI(
    title="MakerLab",
    description="3D Baskı ve Elektronik Atölyesi Yönetim Sistemi",
    lifespan=lifespan,
)

# Statik dosyalar (CSS, görseller).
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Route modüllerini ekle.
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(ogrenci.router)
app.include_router(teknisyen.router)
app.include_router(api.router)
