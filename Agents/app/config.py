import os
from pathlib import Path
from typing import Dict, List

# =============================================================================
# COLOR CONSTANTS
# =============================================================================

class Colors:
    """Standard color palette used across the application"""
    # Text colors
    WHITE = "#FFFFFF"
    BLACK = "#000000"
    DARK_GRAY = "#1A1A1A"
    
    # Tesco brand colors
    TESCO_BLUE = "#00539F"
    TESCO_RED = "#EE1C2E"
    
    # Default backgrounds
    DEFAULT_DARK_BG = "#1a1a1a"
    DEFAULT_LIGHT_BG = "#FFFFFF"
    
    # Shadow colors (RGBA)
    SHADOW_DARK = "rgba(0,0,0,0.7)"
    SHADOW_MEDIUM = "rgba(0,0,0,0.5)"
    SHADOW_LIGHT = "rgba(0,0,0,0.3)"


# =============================================================================
# URL CONSTANTS
# =============================================================================

class URLs:
    """API URLs and endpoints"""
    # CORS allowed origins
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://retexture.vercel.app",
        "https://retexture.onrender.com"
    ]
    
    # Local development URLs
    LOCAL_CLIENT = "http://localhost:3000"
    LOCAL_VITE = "http://localhost:5173"
    
    # Production URLs
    PROD_VERCEL = "https://retexture.vercel.app"
    PROD_RENDER = "https://retexture.onrender.com"
    
    # Default logo URLs (fallback)
    TESCO_LOGO_PATH = "/images/tesco-logo.png"
    TESCO_LOGO_URL = "http://localhost:3000/images/tesco-logo.png"  # TODO: Make this configurable


# =============================================================================
# FILE PATH CONSTANTS
# =============================================================================

class Paths:
    """File system paths used throughout the application"""
    # Base directories
    BASE_DIR = Path(__file__).resolve().parent.parent
    APP_DIR = BASE_DIR / "app"
    
    # Static file paths
    STATIC_DIR = "static"
    IMAGES_DIR = "images"
    OUTPUT_DIR = "output"
    UPLOADS_DIR = "uploads"
    
    # Resource files
    RESOURCES_DIR = APP_DIR / "resources"
    RULESET_FILE = RESOURCES_DIR / "ruleset.txt"
    VALIDATION_RULES_FILE = RESOURCES_DIR / "validation_rules.json"
    
    # Logo paths (relative)
    TESCO_LOGO_REL = "images/tesco-logo.png"
    DRINKAWARE_LOGO_REL = "images/drinkaware-logo.png"
    
    @staticmethod
    def get_static_path(filename: str) -> str:
        """Get path for static file"""
        return f"{Paths.STATIC_DIR}/{filename}"
    
    @staticmethod
    def get_output_path(filename: str) -> str:
        """Get path for output file"""
        return f"{Paths.STATIC_DIR}/{Paths.OUTPUT_DIR}/{filename}"


# =============================================================================
# TYPOGRAPHY CONSTANTS
# =============================================================================

class Typography:
    """Typography settings and defaults"""
    # Font families
    DEFAULT_SANS_SERIF = "Arial, sans-serif"
    ROBOTO = "Roboto, sans-serif"
    HELVETICA = "Helvetica, sans-serif"
    
    # Font weights
    NORMAL = "normal"
    BOLD = "bold"
    
    # Minimum font sizes (accessibility)
    MIN_FONT_SIZE = 20  # px
    MIN_HEADLINE_SIZE = 24  # px
    
    # Default font sizes
    DEFAULT_HEADLINE_SIZE = 42  # px
    DEFAULT_SUBHEAD_SIZE = 22  # px
    DEFAULT_BODY_SIZE = 16  # px
    
    # Text alignment
    ALIGN_LEFT = "left"
    ALIGN_CENTER = "center"
    ALIGN_RIGHT = "right"


# =============================================================================
# LAYOUT CONSTANTS
# =============================================================================

class Layout:
    """Canvas layout and positioning constants"""
    # Safe zones (for 9:16 format)
    SAFE_ZONE_TOP = 200  # px
    SAFE_ZONE_BOTTOM = 250  # px
    
    # Alternative safe zones
    ALT_SAFE_ZONE_TOP = 100  # px
    ALT_SAFE_ZONE_BOTTOM = 150  # px
    
    # Edge padding
    EDGE_PADDING = 20  # px
    
    # Element positioning percentages
    HEADLINE_WIDTH_PERCENT = 0.6  # 60% of canvas
    HEADLINE_HEIGHT_PERCENT = 0.05  # 5% of canvas height
    SUBHEAD_HEIGHT_PERCENT = 0.035  # 3.5% of canvas height
    
    TESCO_STICKER_WIDTH_PERCENT = 0.25  # 25% of canvas width
    TESCO_STICKER_HEIGHT_PERCENT = 0.12  # 12% of canvas height
    
    VALUE_TILE_WIDTH_PERCENT = 0.12  # 12% of canvas width
    VALUE_TILE_HEIGHT_PERCENT = 0.15  # 15% of canvas height
    
    # Minimum element sizes
    MIN_TESCO_STICKER_WIDTH = 200  # px
    MIN_TESCO_STICKER_HEIGHT = 80  # px
    MIN_VALUE_TILE_SIZE = 120  # px
    
    # Logo sizes
    BRAND_LOGO_WIDTH = 100  # px
    BRAND_LOGO_HEIGHT = 40  # px


# =============================================================================
# AI/GEMINI CONFIGURATION
# =============================================================================

class AIConfig:
    """AI model and generation settings"""
    # Model IDs
    DEFAULT_MODEL = os.getenv("GEMINI_MODEL_ID", "gemini-2.5-flash")
    
    # GCP Configuration
    PROJECT_ID = os.getenv("GCP_PROJECT_ID")
    LOCATION = os.getenv("GCP_LOCATION")
    
    # API Keys
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    
    # Generation limits
    MAX_GENERATIONS_PER_DESIGN = 10
    MAX_AUTO_FIX_RETRIES = 3
    
    # Image generation settings
    IMAGE_MAX_SIZE = 1024  # px (thumbnail size)
    IMAGE_FORMAT = "PNG"
    IMAGE_ASPECT_RATIO = "1:1"


# =============================================================================
# TESCO BRAND CONSTANTS
# =============================================================================

class TescoBrand:
    """Tesco-specific brand constants"""
    # Brand tags
    AVAILABLE_AT_TESCO = "Available at Tesco"
    ONLY_AT_TESCO = "Only at Tesco"
    
    # Clubcard text
    CLUBCARD_DISCLAIMER = "Clubcard/app required. Ends {date}"
    
    # Drink aware
    DRINKAWARE_URL = "drinkaware.co.uk"
    
    # LEP (Limited Edition Product) tag
    LEP_TAG = "Selected stores. While stocks last"
    
    # Brand voice keywords to avoid
    BLOCKED_PROMOTIONAL_WORDS = [
        "free", "win", "prize", "competition",
        "% off", "discount", "sale", "save"
    ]
    
    # Sustainability claims (require verification)
    SUSTAINABILITY_KEYWORDS = [
        "green", "eco-friendly", "sustainable",
        "carbon neutral", "organic" # organic may require certification
    ]


# =============================================================================
# VALIDATION CONSTANTS
# =============================================================================

class ValidationConfig:
    """Validation and compliance settings"""
    # Contrast ratios (WCAG)
    MIN_CONTRAST_RATIO = 4.5  # for normal text
    MIN_CONTRAST_RATIO_LARGE = 3.0  # for large text (18pt+)
    
    # Brightness thresholds
    DARK_THRESHOLD = 128  # 0-255 scale
    LIGHT_THRESHOLD = 200  # 0-255 scale


# =============================================================================
# SERVER CONFIGURATION
# =============================================================================

class ServerConfig:
    """Server and deployment settings"""
    HOST = "0.0.0.0"
    PORT = 8000
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    
    # CORS settings
    ALLOW_CREDENTIALS = True
    ALLOW_METHODS = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    ALLOW_HEADERS = ["*"]
    EXPOSE_HEADERS = ["*"]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_text_color_for_background(brightness: int) -> str:
    """
    Determine appropriate text color based on background brightness.
    
    Args:
        brightness: Background brightness value (0-255)
        
    Returns:
        Hex color code for text
    """
    if brightness > ValidationConfig.DARK_THRESHOLD:
        return Colors.DARK_GRAY  # Dark text on light background
    else:
        return Colors.WHITE  # White text on dark background


def get_shadow_for_background(brightness: int) -> str:
    """
    Determine appropriate text shadow based on background brightness.
    
    Args:
        brightness: Background brightness value (0-255)
        
    Returns:
        CSS text-shadow value
    """
    if brightness > ValidationConfig.DARK_THRESHOLD:
        return f"1px 1px 2px {Colors.SHADOW_LIGHT}"
    else:
        return f"2px 2px 4px {Colors.SHADOW_DARK}"


# Export commonly used values for easy import
__all__ = [
    "Colors",
    "URLs",
    "Paths",
    "Typography",
    "Layout",
    "AIConfig",
    "TescoBrand",
    "ValidationConfig",
    "ServerConfig",
    "get_text_color_for_background",
    "get_shadow_for_background",
]
