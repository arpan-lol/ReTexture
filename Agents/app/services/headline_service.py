"""
Headline/Subheading Generator Service
Uses Google Gemini Vision to analyze product images and generate Tesco brand-compliant headlines.
"""

import os
import base64
import json
import logging
import sys
from datetime import datetime
from typing import Optional
from google import genai
from google.genai import types

from app.core.shared_ai_client import LLMClient, get_model_id
from app.core.rate_limiter import get_headline_rate_limiter
from app.core.json_parser import (
    JSONParseError,
    parse_keyword_response,
    parse_headline_response,
    extract_json_object,
    safe_extract_json
)
from app.prompts.headline_prompts import (
    TESCO_BRAND_GUIDELINES,
    KEYWORD_SUGGESTION_PROMPT,
    HEADLINE_GENERATION_PROMPT,
    SUBHEADING_GENERATION_PROMPT,
    TEXT_PLACEMENT_ANALYSIS_PROMPT,
    TYPOGRAPHY_STYLING_PROMPT
)
from app.config import Colors, Typography, AIConfig


# Configure JSON logging for heavy terminal output
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "service": "headline-service",
            "function": record.funcName,
            "message": record.getMessage(),
        }
        if hasattr(record, "extra_data"):
            log_obj["data"] = record.extra_data
        return json.dumps(log_obj)


# Configure logger with JSON format
logger = logging.getLogger("headline_service")
logger.setLevel(logging.DEBUG)

# Remove existing handlers
for handler in logger.handlers[:]:
    logger.removeHandler(handler)

# Add console handler with JSON formatter
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(JsonFormatter())
logger.addHandler(console_handler)


def log_json(level: str, message: str, **data):
    """Helper to log with extra data"""
    extra = {"extra_data": data} if data else {}
    record = logger.makeRecord(
        logger.name, getattr(logging, level.upper()), "", 0, message, (), None
    )
    if data:
        record.extra_data = data
    logger.handle(record)


# Configuration
MODEL_ID = get_model_id()
rate_limiter = get_headline_rate_limiter()

log_json(
    "INFO",
    "🚀 Headline Service Initialized",
    model=MODEL_ID,
)


def _init_gemini_client():
    """Initialize Gemini client with shared factory"""
    log_json(
        "INFO",
        "📦 Initializing Gemini client...",
        model=MODEL_ID,
    )

    try:
        client = LLMClient.get_client()
        log_json("INFO", f"✅ Gemini client initialized ({LLMClient.get_auth_method()})")
        return client
    except Exception as e:
        log_json("ERROR", f"❌ Failed to initialize Gemini client: {e}")
        raise


def _check_rate_limit(design_id: str) -> bool:
    """Check if design has exceeded rate limit (time-windowed)"""
    is_allowed = rate_limiter.check_limit(design_id)
    
    if not is_allowed:
        limit_info = rate_limiter.get_limit_info(design_id)
        logger.warning(
            f"⚠️ [HEADLINE SERVICE] Rate limit exceeded for design {design_id}: "
            f"{limit_info['used']}/{limit_info['limit']} in last {limit_info['window_minutes']}min"
        )
    
    return is_allowed


def _decode_base64_image(image_base64: str) -> bytes:
    """Decode base64 image string to bytes"""
    logger.info("🖼️ [HEADLINE SERVICE] Decoding base64 image...")

    # Remove data URL prefix if present
    if "," in image_base64:
        image_base64 = image_base64.split(",")[1]

    image_bytes = base64.b64decode(image_base64)
    logger.info(f"✅ [HEADLINE SERVICE] Image decoded: {len(image_bytes)} bytes")
    return image_bytes


async def suggest_keywords(image_base64: str) -> dict:
    """
    Analyze product image and suggest relevant keywords.
    Like VS Code commit message suggestion.
    """
    logger.info("🔍 [HEADLINE SERVICE] suggest_keywords called")

    try:
        client = _init_gemini_client()
        image_bytes = _decode_base64_image(image_base64)

        prompt = KEYWORD_SUGGESTION_PROMPT

        logger.info("📤 [HEADLINE SERVICE] Sending keyword request to Gemini...")

        response = client.models.generate_content(
            model=MODEL_ID,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                        types.Part.from_text(text=prompt),
                    ],
                )
            ],
        )

        result_text = response.text.strip()
        logger.info(f"📥 [HEADLINE SERVICE] Gemini response: {result_text}")

        # Parse JSON response with robust parser
        try:
            keywords = parse_keyword_response(result_text)
            logger.info(f"✅ [HEADLINE SERVICE] Keywords extracted: {keywords}")
        except JSONParseError as e:
            logger.warning(f"⚠️ [HEADLINE SERVICE] JSON parsing failed: {e}, using fallback")
            keywords = ["product", "quality", "fresh", "value", "Tesco"]

        return {"success": True, "keywords": keywords}

    except Exception as e:
        logger.error(f"❌ [HEADLINE SERVICE] Keyword suggestion failed: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "keywords": ["product", "quality", "fresh", "value", "Tesco"],  # Fallback
        }


async def generate_headlines(
    image_base64: str,
    design_id: str = "default",
    campaign_type: Optional[str] = None,
    user_keywords: Optional[list] = None,
) -> dict:
    """
    Generate 3 headline options based on product image.
    """
    logger.info("📝 [HEADLINE SERVICE] generate_headlines called")
    logger.info(f"  ↳ design_id: {design_id}")
    logger.info(f"  ↳ campaign_type: {campaign_type}")
    logger.info(f"  ↳ user_keywords: {user_keywords}")

    # Check rate limit
    if not _check_rate_limit(design_id):
        return {
            "success": False,
            "error": f"Rate limit exceeded. Maximum {MAX_GENERATIONS_PER_DESIGN} generations per design.",
            "headlines": [],
        }

    try:
        client = _init_gemini_client()
        image_bytes = _decode_base64_image(image_base64)

        # Build context
        context_parts = []
        if campaign_type:
            context_parts.append(f"Campaign Type: {campaign_type}")
        if user_keywords:
            context_parts.append(f"Keywords: {', '.join(user_keywords)}")
        context = (
            "\n".join(context_parts) if context_parts else "General product promotion"
        )

        prompt = HEADLINE_GENERATION_PROMPT(context)

        logger.info("📤 [HEADLINE SERVICE] Sending headline request to Gemini...")

        response = client.models.generate_content(
            model=MODEL_ID,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                        types.Part.from_text(text=prompt),
                    ],
                )
            ],
        )

        result_text = response.text.strip()
        logger.info(f"📥 [HEADLINE SERVICE] Gemini response: {result_text[:200]}...")

        # Parse JSON response with robust parser
        try:
            headlines = parse_headline_response(result_text)
            logger.info(f"✅ [HEADLINE SERVICE] Headlines generated: {len(headlines)}")
        except JSONParseError as e:
            logger.warning(f"⚠️ [HEADLINE SERVICE] JSON parsing failed: {e}, using fallback")
            headlines = [
                {"text": "Quality You Can Trust", "confidence": 0.9},
                {"text": "Fresh Every Day", "confidence": 0.8},
                {"text": "Taste the Difference", "confidence": 0.7},
            ]

        return {"success": True, "headlines": headlines}

    except Exception as e:
        logger.error(f"❌ [HEADLINE SERVICE] Headline generation failed: {str(e)}")
        return {"success": False, "error": str(e), "headlines": []}


async def generate_subheadings(
    image_base64: str,
    design_id: str = "default",
    campaign_type: Optional[str] = None,
    user_keywords: Optional[list] = None,
) -> dict:
    """
    Generate 3 subheading options based on product image.
    """
    logger.info("📝 [HEADLINE SERVICE] generate_subheadings called")
    logger.info(f"  ↳ design_id: {design_id}")
    logger.info(f"  ↳ campaign_type: {campaign_type}")
    logger.info(f"  ↳ user_keywords: {user_keywords}")

    # Check rate limit
    if not _check_rate_limit(design_id):
        return {
            "success": False,
            "error": f"Rate limit exceeded. Maximum {MAX_GENERATIONS_PER_DESIGN} generations per design.",
            "subheadings": [],
        }

    try:
        client = _init_gemini_client()
        image_bytes = _decode_base64_image(image_base64)

        # Build context
        context_parts = []
        if campaign_type:
            context_parts.append(f"Campaign Type: {campaign_type}")
        if user_keywords:
            context_parts.append(f"Keywords: {', '.join(user_keywords)}")
        context = (
            "\n".join(context_parts) if context_parts else "General product promotion"
        )

        prompt = SUBHEADING_GENERATION_PROMPT(context)

        logger.info("📤 [HEADLINE SERVICE] Sending subheading request to Gemini...")

        response = client.models.generate_content(
            model=MODEL_ID,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                        types.Part.from_text(text=prompt),
                    ],
                )
            ],
        )

        result_text = response.text.strip()
        logger.info(f"📥 [HEADLINE SERVICE] Gemini response: {result_text[:200]}...")

        # Parse JSON response with robust parser
        try:
            subheadings = parse_headline_response(result_text)  # Same structure as headlines
            logger.info(f"✅ [HEADLINE SERVICE] Subheadings generated: {len(subheadings)}")
        except JSONParseError as e:
            logger.warning(f"⚠️ [HEADLINE SERVICE] JSON parsing failed: {e}, using fallback")
            subheadings = [
                {
                    "text": "Premium quality products sourced for your family",
                    "confidence": 0.9,
                },
                {
                    "text": "Carefully selected to bring you the best value",
                    "confidence": 0.8,
                },
                {"text": "Fresh from farm to your table every day", "confidence": 0.7},
            ]

        return {"success": True, "subheadings": subheadings}

    except Exception as e:
        logger.error(f"❌ [HEADLINE SERVICE] Subheading generation failed: {str(e)}")
        return {"success": False, "error": str(e), "subheadings": []}


async def analyze_image_for_placement(
    image_base64: str, canvas_width: int, canvas_height: int
) -> dict:
    """
    🎯 SMART AI-POWERED PLACEMENT
    Uses Gemini Vision to analyze the image and find optimal text placement.
    """
    log_json(
        "INFO",
        "🎯 Analyzing image for smart placement...",
        canvas_width=canvas_width,
        canvas_height=canvas_height,
    )

    try:
        client = _init_gemini_client()
        image_bytes = _decode_base64_image(image_base64)

        prompt = f"""You are an expert graphic designer analyzing this retail advertisement image for optimal text placement.

Canvas dimensions: {canvas_width}px x {canvas_height}px

## TASK: Find the best position for headline and subheading text

### STEP 1: Identify the SALIENT REGION (main product/subject)
Detect where the main product or focal point is located. Text must NEVER overlap this area.

### STEP 2: Apply RULE OF THIRDS
Divide the image into a 3x3 grid:
- TOP THIRD (y: 0-33%): IDEAL for headlines if product is in center/bottom
- MIDDLE THIRD (y: 33-67%): DANGER ZONE - usually contains the product, AVOID
- BOTTOM THIRD (y: 67-100%): Good for call-to-action, but check for product overlap

### STEP 3: Determine text placement using ENERGY OPTIMIZATION
- MINIMIZE TEXT INTRUSION: Never overlap important content
- MAXIMIZE VISUAL SPACE UTILITY: Use the largest empty area
- ENSURE READABILITY: Choose contrasting colors

### PLACEMENT ZONES (y_percent ranges):
- SAFE TOP ZONE: y_percent = 5-20 (Headlines go here if possible)
- SECONDARY TOP: y_percent = 20-30 (Subheadings can go here)  
- DANGER ZONE: y_percent = 30-75 (Products usually here - AVOID!)
- SAFE BOTTOM ZONE: y_percent = 75-95 (Bottom placement if top is blocked)

Return ONLY a JSON object (no markdown, no explanation):
{{
    "subject_position": "center-bottom",
    "empty_zones": ["top"],
    "background_brightness": "dark",
    "headline": {{
        "x_percent": 50,
        "y_percent": 12,
        "align": "center",
        "fontSize": 42,
        "fontWeight": "bold",
        "color": "#FFFFFF",
        "shadow": true,
        "shadowColor": "rgba(0,0,0,0.6)"
    }},
    "subheading": {{
        "x_percent": 50,
        "y_percent": 22,
        "align": "center", 
        "fontSize": 22,
        "fontWeight": "normal",
        "color": "#FFFFFF",
        "shadow": true,
        "shadowColor": "rgba(0,0,0,0.4)"
    }}
}}

CRITICAL RULES:
1. Headline y_percent MUST be in range 5-25 (TOP SAFE ZONE) unless impossible
2. Subheading y_percent should be 8-12% below headline
3. NEVER place text in y_percent 35-70 (where products typically are)
4. Use #FFFFFF (white) text for dark backgrounds with strong shadow
5. Use #1A1A1A (dark) text for light backgrounds with subtle shadow
"""

        log_json("INFO", "📤 Sending smart placement request to Gemini...")

        response = client.models.generate_content(
            model=MODEL_ID,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                        types.Part.from_text(text=prompt),
                    ],
                )
            ],
        )

        result_text = response.text.strip()
        log_json(
            "INFO",
            "📥 Gemini placement response received",
            response_length=len(result_text),
        )

        # Parse JSON response with robust parser
        try:
            placement = extract_json_object(result_text)
            log_json(
                "INFO",
                "✅ Smart placement calculated",
                subject_position=placement.get("subject_position"),
                background=placement.get("background_brightness"),
            )
            return {"success": True, "placement": placement}
        except JSONParseError as e:
            log_json("WARNING", f"⚠️ Smart placement JSON parsing failed: {e}, using defaults")
            return _get_default_placement(canvas_width, canvas_height)

    except Exception as e:
        log_json("ERROR", f"❌ Smart placement failed: {str(e)}")
        return _get_default_placement(canvas_width, canvas_height)


def _get_default_placement(canvas_width: int, canvas_height: int) -> dict:
    """Fallback placement when AI analysis fails - uses percentage-based positioning"""
    return {
        "success": True,
        "placement": {
            "subject_position": "center",
            "empty_zones": ["top"],
            "background_brightness": "dark",
            "headline": {
                "x_percent": 50,
                "y_percent": 15,
                "align": "center",
                "fontSize": 42,
                "fontWeight": "bold",
                "color": "#FFFFFF",
                "shadow": True,
                "shadowColor": "rgba(0,0,0,0.5)",
                "shadowBlur": 4,
                "shadowOffsetX": 2,
                "shadowOffsetY": 2,
            },
            "subheading": {
                "x_percent": 50,
                "y_percent": 28,
                "align": "center",
                "fontSize": 22,
                "fontWeight": "normal",
                "color": "#FFFFFF",
                "shadow": True,
                "shadowColor": "rgba(0,0,0,0.3)",
                "shadowBlur": 3,
                "shadowOffsetX": 1,
                "shadowOffsetY": 1,
            },
        },
    }


def calculate_optimal_placement(canvas_width: int, canvas_height: int) -> dict:
    """
    Calculate optimal text placement positions (synchronous fallback).
    Returns positions for headline and subheading.
    """
    logger.info(
        f"📐 [HEADLINE SERVICE] Calculating placement for {canvas_width}x{canvas_height}"
    )

    # Headline: centered, in top 15%
    headline_x = canvas_width // 2
    headline_y = int(canvas_height * 0.15)

    # Subheading: centered, below headline
    subheading_x = canvas_width // 2
    subheading_y = int(canvas_height * 0.22)

    placement = {
        "headline": {
            "x": headline_x,
            "y": headline_y,
            "fontSize": 42,
            "fontWeight": "bold",
            "align": "center",
            "color": "#FFFFFF",
            "shadow": True,
            "shadowColor": "rgba(0,0,0,0.5)",
            "shadowBlur": 4,
            "shadowOffsetX": 2,
            "shadowOffsetY": 2,
            "fontFamily": "Arial, sans-serif",
        },
        "subheading": {
            "x": subheading_x,
            "y": subheading_y,
            "fontSize": 22,
            "fontWeight": "normal",
            "align": "center",
            "color": "#FFFFFF",
            "shadow": True,
            "shadowColor": "rgba(0,0,0,0.3)",
            "shadowBlur": 3,
            "shadowOffsetX": 1,
            "shadowOffsetY": 1,
            "fontFamily": "Arial, sans-serif",
        },
    }

    logger.info(f"✅ [HEADLINE SERVICE] Placement calculated: {placement}")
    return placement


def suggest_text_color(background_color: str = "#1a1a1a") -> dict:
    """
    Suggest text color based on background for contrast.
    """
    logger.info(
        f"🎨 [HEADLINE SERVICE] Suggesting text color for background: {background_color}"
    )

    # Simple luminance check
    if background_color.startswith("#"):
        r = int(background_color[1:3], 16)
        g = int(background_color[3:5], 16)
        b = int(background_color[5:7], 16)
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255

        if luminance > 0.5:
            # Dark text for light background
            text_color = "#1a1a1a"
        else:
            # Light text for dark background
            text_color = "#FFFFFF"
    else:
        text_color = "#FFFFFF"  # Default to white

    logger.info(f"✅ [HEADLINE SERVICE] Suggested text color: {text_color}")

    return {
        "text_color": text_color,
        "luminance": luminance if "luminance" in locals() else 0.5,
    }


def reset_rate_limit(design_id: str):
    """Reset rate limit for a design (for testing)"""
    rate_limiter.reset_key(design_id)
    logger.info(f"🔄 [HEADLINE SERVICE] Rate limit reset for design: {design_id}")


# ============== FONT STYLING SERVICE ==============

# Available font moods that map to frontend font config
AVAILABLE_MOODS = [
    "premium",
    "modern",
    "playful",
    "family",
    "fresh",
    "bold",
    "clean",
    "everyday",
]


async def analyze_font_style(image_base64: str) -> dict:
    """
    🎨 AI-Powered Font Style Recommendation
    Analyzes the product image and recommends typography styling.

    Returns mood-based font recommendation that maps to frontend config.
    """
    log_json("INFO", "🎨 Analyzing image for font style recommendation...")

    try:
        client = _init_gemini_client()
        image_bytes = _decode_base64_image(image_base64)

        prompt = f"""Analyze this retail product image and recommend typography styling.

Consider:
1. Product category (grocery, premium, fresh, household, etc.)
2. Visual mood (bright, dark, colorful, minimal, etc.)
3. Target audience (families, young adults, health-conscious, etc.)
4. Brand positioning (value, premium, everyday, specialty)

Choose ONE mood from: {", ".join(AVAILABLE_MOODS)}

Return ONLY a JSON object (no markdown):
{{
    "mood": "modern",
    "reasoning": "Brief explanation of why this mood fits",
    "fontWeight": "semibold",
    "letterSpacing": "normal",
    "textTransform": "none",
    "suggestedCase": "Title Case"
}}

Font weights: regular, medium, semibold, bold, extrabold
Letter spacing: tight, normal, wide, extraWide
Text transform: none, uppercase, capitalize
"""

        response = client.models.generate_content(
            model=MODEL_ID,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                        types.Part.from_text(text=prompt),
                    ],
                )
            ],
        )

        result_text = response.text.strip()
        log_json(
            "INFO",
            "📥 Font analysis response received",
            response_length=len(result_text),
        )

        # Parse JSON response with robust parser
        try:
            font_style = extract_json_object(result_text)

            # Validate mood
            if font_style.get("mood") not in AVAILABLE_MOODS:
                log_json("WARNING", f"Invalid mood '{font_style.get('mood')}', using 'modern'")
                font_style["mood"] = "modern"

            log_json(
                "INFO",
                "✅ Font style recommended",
                mood=font_style.get("mood"),
                weight=font_style.get("fontWeight"),
            )

            return {"success": True, "fontStyle": font_style}
        except JSONParseError as e:
            log_json("WARNING", f"⚠️ Font analysis JSON parsing failed: {e}, using defaults")
            return _get_default_font_style()

    except Exception as e:
        log_json("ERROR", f"❌ Font analysis failed: {str(e)}")
        return _get_default_font_style()


def _get_default_font_style() -> dict:
    """Default font style when analysis fails"""
    return {
        "success": True,
        "fontStyle": {
            "mood": "modern",
            "reasoning": "Default modern style for clean readability",
            "fontWeight": "semibold",
            "letterSpacing": "normal",
            "textTransform": "none",
            "suggestedCase": "Title Case",
        },
    }
