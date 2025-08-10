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
    Save base64 image data to file and return relative path
    """
    # Always ensure directory exists before saving
    ensure_images_directory()
    
    try:
        # Handle data URL format (data:image/jpeg;base64,...)
        if base64_data.startswith('data:'):
            image_part = base64_data.split(',')[1]
        else:
            image_part = base64_data
        
        # Decode base64
        image_bytes = base64.b64decode(image_part)
        
        # Use Pillow to open and validate the image
        try:
            with Image.open(io.BytesIO(image_bytes)) as img:
                # Get the image format
                img_format = img.format.lower() if img.format else 'jpeg'
                
                # Convert format names to file extensions
                format_to_ext = {
                    'jpeg': 'jpg',
                    'jpg': 'jpg',
                    'png': 'png',
                    'gif': 'gif',
                    'bmp': 'bmp',
                    'webp': 'webp'
                }
                
                file_ext = format_to_ext.get(img_format, 'jpg')
                
                # Create filename with item ID
                filename = f"{item_id}.{file_ext}"
                file_path = IMAGES_DIR / filename
                
                # Convert to RGB if necessary (for JPEG)
                if file_ext == 'jpg' and img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                
                # Save the image
                img.save(file_path, format=img_format.upper() if img_format != 'jpg' else 'JPEG', quality=85)
                
        except Exception as e:
            raise ValueError(f"Invalid image format or corrupted image: {str(e)}")
        
        print(f"Image saved: {file_path}")
        
        # Return relative path (using forward slashes for cross-platform compatibility)
        return f"resource/images/{filename}"
        
    except Exception as e:
        print(f"Error saving image for item {item_id}: {e}")
        raise ValueError(f"Failed to save image: {str(e)}")

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