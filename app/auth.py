"""Kimlik doğrulama: şifre hashleme, JWT token üretimi ve oturum çözümleme."""

from datetime import datetime, timedelta, timezone

from fastapi import Request
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, SECRET_KEY

# Şifre hashleme bağlamı (SHA-256 tabanlı).
pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    """Düz şifreyi veritabanında saklanacak güvenli hash'e çevirir."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Girilen şifrenin saklanan hash ile eşleşip eşleşmediğini kontrol eder."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict) -> str:
    """Kullanıcı bilgilerini süreli bir JWT access token'a dönüştürür."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(request: Request):
    """Cookie'deki access token'dan giriş yapan kullanıcıyı çözer.

    Token yoksa veya geçersizse None döner. Dönen sözlük şu alanları içerir:
    {'sub': email, 'id': ..., 'ad_soyad': ..., 'rol': ...}
    """
    token = request.cookies.get("access_token")
    if not token:
        return None

    try:
        # "Bearer <token>" formatından token kısmını ayıkla ve çöz.
        token_data = token.split(" ")[1]
        return jwt.decode(token_data, SECRET_KEY, algorithms=[ALGORITHM])
    except (JWTError, IndexError, AttributeError):
        return None
