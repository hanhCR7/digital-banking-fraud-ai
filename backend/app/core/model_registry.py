import importlib
import os
import pathlib

from backend.app.core.logging import get_logger

logger = get_logger()

# Hàm phát hiện toàn bộ các file models.py trong dự án
def discover_models() -> list[str]:
    models_modules = []
    root_path = pathlib.Path(__file__).parent.parent

    logger.debug(f"Searching for models in the root path: {root_path}")
    # Duyệt qua all các folder để tìm file models.py
    for root, _, files in os.walk(root_path):
        # Bỏ qua các thư mục không liên quan như môi trường ảo và cache
        if any(
            excluded in root for excluded in ["venv", "__pycache__", ".pytest_cache"]
        ):
            continue
        # Khi phát hiện file models.py, chuyển đường dẫn thư mục sang module Python
        if "models.py" in files:
            rel_path = os.path.relpath(root, root_path)
            module_path = rel_path.replace(os.path.sep, ".")
            # Xây dựng đường dẫn import đầy đủ cho module
            if module_path == ".":
                full_module_path = "backend.app.models"
            else:
                full_module_path = f"backend.app.{module_path}.models"

            logger.debug(f"Discovered models file in: {full_module_path}")

            models_modules.append(full_module_path)
    return models_modules

# Import toàn bộ các module model đã được phát hiện
def load_models() -> None:
    modules = discover_models()
    for module_path in modules:
        try:
            importlib.import_module(module_path)
            logger.debug(f"Imported module {module_path}")
        except ImportError as e:
            logger.error(f"Failed to import module {module_path}: {e}")