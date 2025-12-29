import io
from typing import Tuple

from PIL import Image, UnidentifiedImageError

from backend.app.core.config import settings
from backend.app.core.logging import get_logger

logger = get_logger()


def validate_image(file_data: bytes) -> Tuple[bool, str]:
    """Kiểm tra tính hợp lệ của file ảnh upload."""
    try:
        # Kiểm tra dung lượng file ảnh (tránh upload file quá lớn)
        file_size_mb = len(file_data) / (1024 * 1024)
        if file_size_mb > settings.MAX_FILE_SIZE / (1024 * 1024):
            return (
                False,
                f"File size exceeds {settings.MAX_FILE_SIZE/1024*1024}MB limit",
            )
        # Chuyển bytes sang buffer để Pillow có thể đọc được như file
        image_buffer = io.BytesIO(file_data)
        # Mở ảnh bằng Pillow để kiểm tra định dạng và metadata
        with Image.open(image_buffer) as img:
            # Kiểm tra định dạng ảnh thực tế (không tin vào đuôi file)
            if img.format is None or img.format.lower() not in ["jpeg", "png", "jpg"]:
                return False, "Invalid image format. Only JPEG, and PNG are allowed"
            # Kiểm tra kích thước ảnh (tránh ảnh quá lớn gây tốn tài nguyên)
            width, height = img.size
            if width > settings.MAX_DIMENSION or height > settings.MAX_DIMENSION:
                return (
                    False,
                    f"Image dimensions exceed {settings.MAX_DIMENSION}px limit",
                )
            # Thử load toàn bộ ảnh để phát hiện file ảnh bị hỏng hoặc thiếu dữ liệu
            try:
                img.load()
            except Exception as e:
                return (False, f"Invalid or corrupted image file: {str(e)}")
        return True, "Image is valid"

    except UnidentifiedImageError:
        #  File không phải là ảnh hợp lệ (Pillow không nhận diện được)
        return False, "File is not a valid image"
    except Exception as e:
        logger.error(f"Image validation error: {str(e)}")
        return False, f"Invalid image file: {str(e)}"