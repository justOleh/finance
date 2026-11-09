from io import BytesIO

import pytest
from PIL import Image, UnidentifiedImageError
from pillow_heif import register_heif_opener

from convert_image.converter import convert_to_png, is_ready_png

register_heif_opener()  # needed to *write* HEIF in the tests as well

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _encode(image: Image.Image, fmt: str, **kwargs) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format=fmt, **kwargs)
    return buffer.getvalue()


def _open(png: bytes) -> Image.Image:
    image = Image.open(BytesIO(png))
    image.load()
    return image


def test_jpeg_becomes_png():
    jpeg = _encode(Image.new("RGB", (80, 60), (200, 10, 10)), "JPEG")

    png = convert_to_png(jpeg, max_edge=2000)

    assert png.startswith(PNG_SIGNATURE)
    result = _open(png)
    assert result.format == "PNG"
    assert result.mode == "RGB"
    assert result.size == (80, 60)


def test_heic_becomes_png():
    heic = _encode(Image.new("RGB", (64, 48), (10, 120, 200)), "HEIF")

    png = convert_to_png(heic, max_edge=2000)

    assert png.startswith(PNG_SIGNATURE)
    assert _open(png).size == (64, 48)


def test_webp_becomes_png():
    webp = _encode(Image.new("RGB", (40, 40), (1, 2, 3)), "WEBP")

    assert convert_to_png(webp, max_edge=2000).startswith(PNG_SIGNATURE)


def test_large_image_is_downscaled_keeping_aspect_ratio():
    jpeg = _encode(Image.new("RGB", (400, 300)), "JPEG")

    result = _open(convert_to_png(jpeg, max_edge=100))

    assert result.size == (100, 75)


def test_small_image_is_not_upscaled():
    jpeg = _encode(Image.new("RGB", (40, 30)), "JPEG")

    assert _open(convert_to_png(jpeg, max_edge=2000)).size == (40, 30)


def test_exif_orientation_is_applied():
    # Orientation 6 = "rotate 90 degrees clockwise to display": a 200x100 file is shown 100x200.
    exif = Image.Exif()
    exif[0x0112] = 6
    jpeg = _encode(Image.new("RGB", (200, 100)), "JPEG", exif=exif)

    result = _open(convert_to_png(jpeg, max_edge=2000))

    assert result.size == (100, 200)


def test_transparency_is_flattened_onto_white():
    rgba = Image.new("RGBA", (10, 10), (0, 0, 0, 0))

    result = _open(convert_to_png(_encode(rgba, "PNG"), max_edge=2000))

    assert result.mode == "RGB"
    assert result.getpixel((5, 5)) == (255, 255, 255)


@pytest.mark.parametrize("mode", ["L", "P", "CMYK"])
def test_other_modes_become_rgb(mode):
    image = Image.new("RGB", (10, 10), (50, 60, 70)).convert(mode)
    fmt = "TIFF" if mode == "CMYK" else "PNG"

    assert _open(convert_to_png(_encode(image, fmt), max_edge=2000)).mode == "RGB"


def test_not_an_image_raises():
    with pytest.raises(UnidentifiedImageError):
        convert_to_png(b"definitely not an image", max_edge=2000)


# --- is_ready_png: when the file can be copied instead of converted ----------------------------
def _png(size=(80, 60), **kwargs) -> bytes:
    return _encode(Image.new("RGB", size, (20, 30, 40)), "PNG", **kwargs)


def test_a_small_valid_png_is_ready():
    assert is_ready_png(_png(), max_edge=2000)


@pytest.mark.parametrize("fmt", ["JPEG", "WEBP", "HEIF"])
def test_other_formats_are_not_ready(fmt):
    assert not is_ready_png(_encode(Image.new("RGB", (40, 40)), fmt), max_edge=2000)


def test_a_png_with_a_too_long_side_is_not_ready():
    assert not is_ready_png(_png((300, 100)), max_edge=200)
    assert is_ready_png(_png((300, 100)), max_edge=300)


def test_a_png_over_the_byte_limit_is_not_ready():
    png = _png()

    assert is_ready_png(png, max_edge=2000, max_bytes=len(png))
    assert not is_ready_png(png, max_edge=2000, max_bytes=len(png) - 1)


def test_a_png_with_exif_rotation_is_not_ready():
    exif = Image.Exif()
    exif[0x0112] = 6

    assert not is_ready_png(_png(exif=exif), max_edge=2000)


def test_a_truncated_png_is_not_ready():
    png = _png((200, 200))

    assert not is_ready_png(png[: len(png) // 2], max_edge=2000)


def test_garbage_is_not_ready():
    assert not is_ready_png(b"not an image", max_edge=2000)
    assert not is_ready_png(b"", max_edge=2000)
