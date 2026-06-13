"""Image processing utilities using Pillow.

This module provides simple image manipulation functions such as
resizing, grayscale conversion, and merging multiple images.  The
optional dependency `Pillow` is required to use these functions.
"""

from __future__ import annotations

from typing import Iterable, Tuple
from pathlib import Path

try:
    from PIL import Image  # type: ignore
except ImportError as exc:  # pragma: no cover - optional dependency
    Image = None  # type: ignore
    _pil_import_error = exc
else:
    _pil_import_error = None


def resize_image(image_path: str | Path, output_path: str | Path, size: Tuple[int, int]) -> None:
    """Resize an image to the given dimensions.

    Parameters
    ----------
    image_path:
        Path to the input image.
    output_path:
        Path to the resized image.
    size:
        A tuple (width, height) specifying the new size.
    """
    if Image is None:
        raise ImportError(
            "Pillow is required for image processing but is not installed"
        ) from _pil_import_error
    img = Image.open(image_path)
    resized = img.resize(size)
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    resized.save(out_path)


def convert_to_grayscale(image_path: str | Path, output_path: str | Path) -> None:
    """Convert an image to grayscale.

    Parameters
    ----------
    image_path:
        Path to the input image.
    output_path:
        Path to the grayscale image.
    """
    if Image is None:
        raise ImportError(
            "Pillow is required for image processing but is not installed"
        ) from _pil_import_error
    img = Image.open(image_path)
    gray = img.convert('L')
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    gray.save(out_path)


def merge_images(image_paths: Iterable[str | Path], output_path: str | Path, *, direction: str = 'horizontal') -> None:
    """Merge multiple images into a single image.

    Parameters
    ----------
    image_paths:
        Iterable of image file paths to merge.
    output_path:
        Path of the merged image to create.
    direction:
        'horizontal' to place images side-by-side, 'vertical' to stack them.
    """
    if Image is None:
        raise ImportError(
            "Pillow is required for image processing but is not installed"
        ) from _pil_import_error
    images = [Image.open(p) for p in image_paths]
    if not images:
        raise ValueError("No images provided to merge")
    widths, heights = zip(*(img.size for img in images))
    if direction == 'vertical':
        total_height = sum(heights)
        max_width = max(widths)
        merged = Image.new('RGB', (max_width, total_height))
        y_offset = 0
        for img in images:
            merged.paste(img, (0, y_offset))
            y_offset += img.height
    else:
        # horizontal
        total_width = sum(widths)
        max_height = max(heights)
        merged = Image.new('RGB', (total_width, max_height))
        x_offset = 0
        for img in images:
            merged.paste(img, (x_offset, 0))
            x_offset += img.width
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    merged.save(out_path)