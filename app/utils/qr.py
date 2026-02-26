import io
import qrcode
from aiogram.types import BufferedInputFile


async def generate_qr_code(data: str) -> BufferedInputFile:
    """
    Генерирует QR-код и возвращает объект BufferedInputFile.
    """

    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    bio = io.BytesIO()
    img.save(bio, format='PNG')
    bio.seek(0)

    return BufferedInputFile(bio.read(), filename="qr.png")
