"""Image conversion: any format Pillow can read (JPEG, PNG, WebP, HEIC/HEIF, ...) to PNG.

Kept free of AWS code so it can be tested with plain bytes.
"""

from io import BytesIO

from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

# Adds HEIC/HEIF support to Pillow's Image.open.
register_heif_opener()

# A PNG at most this big is copied unchanged. Kept below the model API's per-image size limit
# (5 MB at the time of writing; check the docs), so a copied file is never rejected.
MAX_COPY_BYTES = 4 * 1024 * 1024
EXIF_ORIENTATION = 0x0112


def is_ready_png(data: bytes, max_edge: int, max_bytes: int = MAX_COPY_BYTES) -> bool:
    """True if `data` is already a PNG the parser can use as it is, so it can be copied.

    "Ready" means: a complete, valid PNG, no bigger than `max_bytes`, whose longest side is at
    most `max_edge` pixels, and with no EXIF rotation to apply. Anything else (another format,
    too large in bytes or pixels, rotated, truncated or corrupt) goes through `convert_to_png`.
    """
    if len(data) > max_bytes:
        return False
    try:
        with Image.open(BytesIO(data)) as image:
            if image.format != "PNG" or max(image.size) > max_edge:
                return False
            if image.getexif().get(EXIF_ORIENTATION, 1) != 1:
                return False
        # verify() must be the first call after open() (and invalidates the image), hence the
        # second open. It checks the whole file (chunk CRCs): a truncated PNG is not copied.
        with Image.open(BytesIO(data)) as image:
            image.verify()
    except Exception:
        return False
    return True


def convert_to_png(data: bytes, max_edge: int) -> bytes:
    """Return `data` as a PNG whose longest side is at most `max_edge` pixels.

    - EXIF orientation is applied first: phone photos are often stored rotated, and a PNG
      carries no such flag, so without this the model would see a sideways receipt.
    - Transparency is flattened onto white (a receipt has no meaningful alpha channel).
    - Only downscales, never upscales: PNG of a full-size photo can be tens of MB, which costs
      tokens and risks the model's image size limits.
    """
    with Image.open(BytesIO(data)) as source:
        image = ImageOps.exif_transpose(source)
        image.load()

    if image.mode in ("RGBA", "LA", "P"):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        image = background
    elif image.mode != "RGB":
        image = image.convert("RGB")

    image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)

    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()
