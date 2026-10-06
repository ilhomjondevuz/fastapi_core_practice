import re

from fastapi import HTTPException, status

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,50}$")
PHONE_RE = re.compile(r"^\+\d{10,12}$")  # modelda String(13): + va 12 tagacha raqam

# Kichik ro'yxat. Jiddiy loyihada tayyor top-10000 ro'yxatini faylga qo'yib o'qing.
COMMON_PASSWORDS = {
    "password", "password1", "password123", "12345678", "123456789", "1234567890",
    "qwerty123", "qwertyuiop", "iloveyou", "admin123", "welcome1", "letmein123",
    "abc12345", "11111111", "00000000", "parol123", "parol12345", "qwerty12345",
}


def _has_sequence(text: str, n: int = 4) -> bool:
    """abcd, 1234, 4321 kabi ketma-ketliklarni topadi."""
    text = text.lower()
    for i in range(len(text) - n + 1):
        window = text[i : i + n]
        diffs = {ord(window[j + 1]) - ord(window[j]) for j in range(n - 1)}
        if diffs == {1} or diffs == {-1}:
            return True
    return False


def validate_password(password: str, username: str, email: str) -> list[str]:
    errors: list[str] = []
    lowered = password.lower()

    if len(password) < 8:
        errors.append("Parol kamida 8 belgidan iborat bo'lishi kerak")
    if len(password.encode("utf-8")) > 72:
        errors.append("Parol juda uzun (bcrypt 72 baytdan ortig'ini qabul qilmaydi)")
    if re.search(r"\s", password):
        errors.append("Parolda bo'sh joy bo'lmasligi kerak")
    if not re.search(r"[a-z]", password):
        errors.append("Parolda kamida bitta kichik harf bo'lishi kerak")
    if not re.search(r"[A-Z]", password):
        errors.append("Parolda kamida bitta katta harf bo'lishi kerak")
    if not re.search(r"\d", password):
        errors.append("Parolda kamida bitta raqam bo'lishi kerak")
    if lowered in COMMON_PASSWORDS:
        errors.append("Bu parol juda keng tarqalgan, boshqasini tanlang")
    if re.search(r"(.)\1{3,}", password):
        errors.append("Parolda bir xil belgi 4 martadan ko'p ketma-ket kelmasligi kerak")
    if _has_sequence(password):
        errors.append("Parolda 1234 yoki abcd kabi ketma-ketliklar bo'lmasligi kerak")

    local_part = email.split("@")[0].lower()
    if len(username) >= 3 and username.lower() in lowered:
        errors.append("Parol username'ni o'z ichiga olmasligi kerak")
    if len(local_part) >= 3 and local_part in lowered:
        errors.append("Parol emailingizni o'z ichiga olmasligi kerak")

    return errors


def validate_username(username: str) -> list[str]:
    if not USERNAME_RE.match(username):
        return ["Username 3-50 belgi bo'lib, faqat lotin harflari, raqam va _ dan iborat bo'lishi kerak"]
    return []


def validate_phone(phone: str | None) -> list[str]:
    if phone and not PHONE_RE.match(phone):
        return ["Telefon raqami + bilan boshlanib, 10-12 ta raqamdan iborat bo'lishi kerak (masalan +998901234567)"]
    return []


def raise_if_errors(errors: list[str]) -> None:
    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=errors,
        )