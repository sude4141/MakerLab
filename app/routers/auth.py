"""Kimlik doğrulama route'ları: giriş sayfası, login ve logout."""

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.auth import create_access_token, verify_password
from app.database import get_cursor
from app.templating import templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    """Giriş (login) sayfasını gösterir."""
    return templates.TemplateResponse(request=request, name="login.html")


@router.post("/login")
async def login(request: Request, email: str = Form(...), password: str = Form(...)):
    """E-posta/şifre doğrular; başarılıysa role göre yönlendirir ve token cookie'si yazar."""
    try:
        with get_cursor() as cursor:
            cursor.execute(
                """
                SELECT k.id, k.ad_soyad, k.email, k.sifre_hash, r.rol_adi
                FROM Kullanicilar k
                JOIN Kullanici_Rolleri kr ON k.id = kr.kullanici_id
                JOIN Roller r ON kr.rol_id = r.id
                WHERE k.email = ?
                """,
                (email,),
            )
            user = cursor.fetchone()

        if user and verify_password(password, user[3]):
            # JWT içeriğini hazırla (email, id, ad soyad, rol).
            token_data = {
                "sub": user[2],
                "id": user[0],
                "ad_soyad": user[1],
                "rol": user[4],
            }
            access_token = create_access_token(data=token_data)

            # Role göre hedef paneli belirle.
            if user[4] == "Yönetici":
                target_url = "/admin"
            elif user[4] == "Teknisyen":
                target_url = "/teknisyen"
            else:
                target_url = "/ogrenci"

            response = RedirectResponse(url=target_url, status_code=302)
            # httponly=True, token'ın JavaScript ile okunmasını engeller.
            response.set_cookie(
                key="access_token",
                value=f"Bearer {access_token}",
                httponly=True,
                max_age=1800,
            )
            return response

        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": "Geçersiz e-posta veya şifre"},
        )
    except Exception:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": "Giriş işlemi sırasında bir hata oluştu"},
        )


@router.post("/logout")
async def logout():
    """Oturumu kapatır: access token cookie'sini siler."""
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("access_token")
    return response
