"""Custom formatters for SQLAdmin fields."""
import json
from datetime import datetime
from typing import Any
from uuid import UUID


def format_uuid(value: Any) -> str:
    """
    Format UUID for display.
    Shows first 8 characters followed by ellipsis.
    
    Args:
        value: UUID value
        
    Returns:
        str: Formatted UUID string
    """
    if value is None:
        return ""
    
    uuid_str = str(value)
    return f"{uuid_str[:8]}..."


def format_datetime(value: Any) -> str:
    """
    Format datetime for display.
    Shows datetime with timezone.
    
    Args:
        value: Datetime value
        
    Returns:
        str: Formatted datetime string
    """
    if value is None:
        return ""
    
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S %Z")
    
    return str(value)


def format_json(value: Any) -> str:
    """
    Format JSON field for display.
    Pretty-prints JSON data.
    
    Args:
        value: JSON value (dict or list)
        
    Returns:
        str: Formatted JSON string
    """
    if value is None:
        return ""
    
    try:
        if isinstance(value, (dict, list)):
            return json.dumps(value, indent=2)
        return str(value)
    except Exception:
        return str(value)


def format_price(value: Any) -> str:
    """
    Format price/currency field for display.
    Shows with currency symbol.
    
    Args:
        value: Decimal/float price value
        
    Returns:
        str: Formatted price string
    """
    if value is None:
        return ""
    
    try:
        return f"${float(value):.2f}"
    except Exception:
        return str(value)


def format_color(value: Any) -> str:
    """
    Format color field for display.
    Shows color with hex code.
    
    Args:
        value: Hex color string
        
    Returns:
        str: Formatted color string with preview
    """
    if value is None:
        return ""
    
    # Return color with visual preview (HTML/CSS will render this)
    return f'<span style="display:inline-block;width:20px;height:20px;background:{value};border:1px solid #ccc;margin-right:5px;"></span>{value}'


def format_image_list(value: Any) -> str:
    """
    Format image list for display.
    Shows thumbnail previews.
    
    Args:
        value: List of image URLs
        
    Returns:
        str: HTML with image thumbnails
    """
    if value is None or not value:
        return ""
    
    try:
        if isinstance(value, list):
            images_html = []
            for url in value[:3]:  # Show max 3 images
                images_html.append(
                    f'<img src="{url}" style="width:50px;height:50px;object-fit:cover;margin:2px;" />'
                )
            
            count_text = f" (+{len(value) - 3} more)" if len(value) > 3 else ""
            return "".join(images_html) + count_text
        
        return str(value)
    except Exception:
        return str(value)


def format_boolean(value: Any) -> str:
    """
    Format boolean for display.
    Shows checkmark or X.
    
    Args:
        value: Boolean value
        
    Returns:
        str: Unicode checkmark or X
    """
    if value is None:
        return ""
    
    return "✓" if value else "✗"


def format_address(value: Any) -> str:
    """
    Format address JSON for display.
    Shows formatted address string.
    
    Args:
        value: Address dict
        
    Returns:
        str: Formatted address string
    """
    if value is None or not value:
        return ""
    
    try:
        if isinstance(value, dict):
            parts = []
            if value.get("street"):
                parts.append(value["street"])
            if value.get("city"):
                parts.append(value["city"])
            if value.get("state"):
                parts.append(value["state"])
            if value.get("zip"):
                parts.append(value["zip"])
            if value.get("country"):
                parts.append(value["country"])
            
            return ", ".join(parts)
        
        return str(value)
    except Exception:
        return str(value)
