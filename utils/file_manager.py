# utils/file_manager.py
import os
import json
from config.settings import DATA_DIR


def _ensure_directory(directory: str):
    """Ensures that a directory exists."""
    os.makedirs(directory, exist_ok=True)


def save_content_file(content: str | bytes, filename: str, directory: str, binary_mode: bool = False) -> str:
    """
    Saves content (text or binary) to a file.
    Returns the full path to the saved file.
    """
    full_directory_path = os.path.join(DATA_DIR, directory)
    _ensure_directory(full_directory_path)
    filepath = os.path.join(full_directory_path, filename)

    mode = "wb" if binary_mode else "w"
    encoding = None if binary_mode else "utf-8"

    with open(filepath, mode, encoding=encoding) as f:
        f.write(content)
    return filepath


def load_content_file(filepath: str, binary_mode: bool = False) -> str | bytes:
    """
    Loads content (text or binary) from a file.
    """
    mode = "rb" if binary_mode else "r"
    encoding = None if binary_mode else "utf-8"

    with open(filepath, mode, encoding=encoding) as f:
        return f.read()


def save_json(data: dict, filename: str, directory: str) -> str:
    """
    Saves a dictionary as a JSON file.
    Returns the full path to the saved file.
    """
    full_directory_path = os.path.join(DATA_DIR, directory)
    _ensure_directory(full_directory_path)
    filepath = os.path.join(full_directory_path, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    return filepath


def load_json(filepath: str) -> dict:
    """
    Loads a JSON file into a dictionary.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)
