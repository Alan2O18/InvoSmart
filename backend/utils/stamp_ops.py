import io
import random
import logging
from PIL import Image

logger = logging.getLogger(__name__)

def get_rotated_stamp_bytes(image_path: str, max_angle: int = 10) -> bytes:
    """
    Load an image, rotate it by a random angle within [-max_angle, max_angle],
    and return its PNG bytes preserving transparency.
    """
    try:
        img = Image.open(image_path).convert("RGBA")
        angle = random.uniform(-max_angle, max_angle)
        
        # Rotate using bicubic resampling and expand the bounding box to fit the rotated image
        rotated = img.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
        
        buf = io.BytesIO()
        rotated.save(buf, format="PNG")
        
        logger.debug(f"[StampOps] Rotated stamp '{image_path}' by {angle:.2f} degrees")
        return buf.getvalue()
    except Exception as e:
        logger.error(f"[StampOps] Failed to rotate stamp: {e}")
        # Fallback to returning original bytes if rotation fails
        with open(image_path, "rb") as f:
            return f.read()
