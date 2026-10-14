import asyncio
from app.users.mail import send_email

asyncio.run(send_email("rahimovilhomjon25@gmail.com", "Test", "Salom"))