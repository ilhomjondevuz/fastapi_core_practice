# Python 3.12 ning ixcham image'i
FROM python:3.12-slim

# Python loglarini darhol chiqarish va .pyc fayllarini yaratmaslik
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Konteyner ichidagi ishchi katalog
WORKDIR /app

# Python kutubxonalari ro'yxatini ko'chirish
COPY requirements.txt .

# Kerakli kutubxonalarni o'rnatish
RUN pip install --no-cache-dir -r requirements.txt

# Loyihaning barcha kerakli fayllarini ko'chirish
COPY . .

# FastAPI porti
EXPOSE 8000

# FastAPI serverini ishga tushirish
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]