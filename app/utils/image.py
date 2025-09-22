import os
import base64
from typing import Optional
from pathlib import Path
from PIL import Image
import io

# Base directory for the project
PROJECT_DIR = Path(__file__).parent.parent.parent
IMAGES_DIR = PROJECT_DIR / "resource" / "images"

def ensure_images_directory():
    """Ensure the images directory exists"""
    try:
        IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        print(f"Images directory ensured at: {IMAGES_DIR}")
    except Exception as e:
        print(f"Error creating images directory: {e}")
        raise

def save_image_from_base64(item_id: str, base64_data: str) -> str:
    """
    Save base64 image data to file, convert to JPEG and resize to 640x480.
    Returns relative path like "resource/images/{item_id}.jpg".
    """
    ensure_images_directory()

    try:
        # Extract base64 part if data URL provided
        if base64_data.startswith("data:"):
            try:
                image_part = base64_data.split(",", 1)[1]
            except IndexError:
                raise ValueError("Invalid data URL")
        else:
            image_part = base64_data

        # Normalize whitespace and padding
        image_part = image_part.strip().replace(" ", "")

        try:
            image_bytes = base64.b64decode(image_part, validate=True)
        except Exception as e:
            raise ValueError("Invalid base64 image data")

        # Open image with Pillow
        try:
            with Image.open(io.BytesIO(image_bytes)) as img:
                # Force convert to RGB for JPEG and handle palette/transparency
                img = img.convert("RGB")

                # Resize to exact 640x480
                target_size = (640, 480)
                img = img.resize(target_size, Image.LANCZOS)

                # Prepare filename and path (always .jpg)
                filename = f"{item_id}.jpg"
                file_path = IMAGES_DIR / filename

                # Remove other files with same item_id but different extensions
                for p in IMAGES_DIR.glob(f"{item_id}.*"):
                    try:
                        if p.name != filename:
                            p.unlink()
                    except Exception:
                        # ignore deletion errors
                        pass

                # Save as JPEG
                img.save(file_path, format="JPEG", quality=85, optimize=True)

        except Exception as e:
            raise ValueError("Invalid image format or corrupted image")

        return f"resource/images/{filename}"

    except ValueError:
        # re-raise ValueError so callers can handle standardized errors
        raise
    except Exception as e:
        # generic failure
        raise ValueError(f"Failed to save image: {e}")

def delete_image(image_path: str):
    """Delete image file"""
    if not image_path:
        return
    
    try:
        full_path = PROJECT_DIR / image_path
        if full_path.exists():
            full_path.unlink()
            print(f"Image deleted: {full_path}")
        else:
            print(f"Image file not found for deletion: {full_path}")
    except Exception as e:
        print(f"Error deleting image {image_path}: {e}")
        # Silently fail if image deletion fails

def get_image_full_path(image_path: str) -> Optional[Path]:
    """Get full path to image file"""
    if not image_path:
        return None
    
    full_path = PROJECT_DIR / image_path
    if full_path.exists():
        return full_path
    return None

def get_image_url(item_id: str, base_url: str = "") -> Optional[str]:
    """Generate image URL for item"""
    return f"{base_url}/items/{item_id}/image"

def validate_image_format(base64_data: str) -> bool:
    """Validate if the base64 data represents a valid image"""
    try:
        # Handle data URL format
        if base64_data.startswith('data:'):
            image_part = base64_data.split(',')[1]
        else:
            image_part = base64_data
        
        # Decode base64
        image_bytes = base64.b64decode(image_part)
        
        # Try to open with Pillow
        with Image.open(io.BytesIO(image_bytes)) as img:
            # If we can open it, it's a valid image
            return True
            
    except Exception:
        return False

def get_image_info(image_path: str) -> Optional[dict]:
    """Get image information (size, format, etc.)"""
    full_path = get_image_full_path(image_path)
    if not full_path:
        return None
    
    try:
        with Image.open(full_path) as img:
            return {
                "format": img.format,
                "mode": img.mode,
                "size": img.size,
                "width": img.width,
                "height": img.height
            }
    except Exception:
        return None