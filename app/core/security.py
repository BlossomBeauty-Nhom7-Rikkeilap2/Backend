from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Dict, Tuple
import re
import bcrypt
import jwt
from jwt.exceptions import PyJWTError
from app.config import settings

def validate_password_complexity(password: str) -> Tuple[bool, str]:
    """
    Kiểm tra độ phức tạp của mật khẩu theo FR-03 (ERR-02, BR-01/BR-02):
    - Tối thiểu 8 ký tự
    - Có ít nhất 1 chữ cái viết hoa (A-Z)
    - Có ít nhất 1 chữ cái viết thường (a-z)
    - Có ít nhất 1 chữ số (0-9)
    """
    if not password or len(password) < 8:
        return False, "Mật khẩu phải có tối thiểu 8 ký tự (gồm chữ hoa, chữ thường và chữ số)"
    if not re.search(r"[A-Z]", password):
        return False, "Mật khẩu thiếu chữ hoa (phải có tối thiểu 8 ký tự, gồm chữ hoa, chữ thường và chữ số)"
    if not re.search(r"[a-z]", password):
        return False, "Mật khẩu thiếu chữ thường (phải có tối thiểu 8 ký tự, gồm chữ hoa, chữ thường và chữ số)"
    if not re.search(r"[0-9]", password):
        return False, "Mật khẩu thiếu chữ số (phải có tối thiểu 8 ký tự, gồm chữ hoa, chữ thường và chữ số)"
    return True, "Hợp lệ"

def hash_password(password: str) -> str:
    """Mã hóa mật khẩu bằng thuật toán Bcrypt (theo NFR-02 SDD)."""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Đối chiếu mật khẩu gốc với chuỗi băm Bcrypt."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Sinh JWT Token với payload và thời gian hết hạn (theo FR-01 SDD: 60 phút).
    """
    to_encode = data.copy()
    # RFC 7519: sub (Subject) claim bắt buộc phải là dạng chuỗi (string)
    if "sub" in to_encode:
        to_encode["sub"] = str(to_encode["sub"])

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Giải mã và xác thực chữ ký JWT Token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except PyJWTError:
        return None
