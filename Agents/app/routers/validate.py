from fastapi import APIRouter, HTTPException
from app.core.models import (
    ValidationRequest,
    ValidationResponse,
    AutoFixRequest,
    AutoFixResponse,
    FixApplied,
)
from app.agents.runner import run_validation
from app.services.validation_service import (
    prepare_html_for_llm,
    restore_html_from_llm,
    validate_html_structure,
)
import base64
import time
import json
import logging
import os
from pathlib import Path
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/validate")

# Load validation rules
RULES_PATH = Path(__file__).parent.parent / "resources" / "validation_rules.json"
with open(RULES_PATH, "r", encoding="utf-8") as f:
    VALIDATION_RULES = json.load(f)

# Gemini configuration
PROJECT_ID = os.getenv("GCP_PROJECT_ID")
LOCATION = os.getenv("GCP_LOCATION")
MODEL_ID = os.getenv("GEMINI_MODEL_ID")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")


@router.post("")
async def validate(req: ValidationRequest) -> ValidationResponse:
    """
    Validate canvas against Tesco compliance rules.
    Returns compliance status, violations, and HTML preview.
    """
    logger.info(f"[VALIDATE] ========== NEW VALIDATION REQUEST ==========")
    logger.info(f"[VALIDATE] Received canvas data ({len(req.canvas)} chars)")
    
    # Check if validation agent is available
    from app.agents.builder import is_agent_available
    if not is_agent_available():
        logger.warning("[VALIDATE] LLM agent not available, using rule-based validation only")
    
    try:
        decoded_canvas = base64.b64decode(req.canvas).decode("utf-8")
        logger.info(f"[VALIDATE] Decoded canvas size: {len(decoded_canvas)} chars")
        
        # Try to parse and log canvas structure for debugging
        try:
            canvas_json = json.loads(decoded_canvas)
            width = canvas_json.get('width', 'unknown')
            height = canvas_json.get('height', 'unknown')
            objects = canvas_json.get('objects', [])
            bg = canvas_json.get('background', 'unknown')
            
            logger.info(f"[VALIDATE] Canvas: {width}x{height}px, background: {bg}")
            logger.info(f"[VALIDATE] Objects: {len(objects)} elements")
            
            # Log element summary with custom properties
            for i, obj in enumerate(objects[:10]):  # Limit to first 10
                obj_type = obj.get('type', 'unknown')
                custom_id = obj.get('customId', '')
                is_tesco_tag = obj.get('isTescoTag', False)
                is_logo = obj.get('isLogo', False)
                
                if obj_type in ['text', 'textbox', 'i-text']:
                    text = (obj.get('text') or '')[:40]
                    font_size = obj.get('fontSize', 16)
                    logger.info(f"  [{i}] TEXT: '{text}' ({font_size}px) {f'[{custom_id}]' if custom_id else ''}")
                elif obj_type == 'image':
                    src = (obj.get('src') or '')[:50]
                    flags = []
                    if is_tesco_tag: flags.append('TESCO_TAG')
                    if is_logo: flags.append('LOGO')
                    if custom_id: flags.append(f'id:{custom_id}')
                    logger.info(f"  [{i}] IMAGE: {src[:30] if src else '(no src)'}... {' '.join(flags)}")
                else:
                    logger.info(f"  [{i}] {obj_type.upper()} {f'[{custom_id}]' if custom_id else ''}")
            
            if len(objects) > 10:
                logger.info(f"  ... and {len(objects) - 10} more elements")
                
        except json.JSONDecodeError:
            logger.warning("[VALIDATE] Could not parse canvas as JSON")
    except Exception as e:
        logger.error(f"[VALIDATE] Failed to decode canvas: {e}")
        decoded_canvas = req.canvas

    start = time.perf_counter()
    result = await run_validation(decoded_canvas)
    end = time.perf_counter()
    
    logger.info(f"[VALIDATE] ========== VALIDATION RESULT ==========")
    logger.info(f"[VALIDATE] Compliant: {result.compliant}")
    logger.info(f"[VALIDATE] Issues: {len(result.issues)}")
    for issue in result.issues:
        logger.info(f"  - [{issue.get('severity', 'unknown').upper()}] {issue.get('type')}: {issue.get('message')}")
    logger.info(f"[VALIDATE] Suggestions: {result.suggestions}")
    logger.info(f"[VALIDATE] Completed in {end - start:.4f}s")
    
    # Print HTML preview (first 2000 chars for readability)
    if result.canvas:
        logger.info(f"[VALIDATE] ========== HTML PREVIEW (first 2000 chars) ==========")
        preview = result.canvas[:2000] if len(result.canvas) > 2000 else result.canvas
        for line in preview.split('\n')[:50]:  # First 50 lines
            logger.info(f"  {line}")
        if len(result.canvas) > 2000:
            logger.info(f"  ... (truncated, total {len(result.canvas)} chars)")
    
    logger.info(f"[VALIDATE] ==========================================")

    return result


@router.post("/auto-fix")
async def auto_fix_compliance(req: AutoFixRequest) -> AutoFixResponse:
    """
    AI-powered compliance auto-fix endpoint.
    Receives HTML/CSS with violations, uses Gemini to fix compliance issues.
    Retries up to 3 times if invalid HTML is returned.
    """
    logger.info(f"🤖 [AUTO-FIX] ========== NEW AUTO-FIX REQUEST ==========")
    logger.info(f"🤖 [AUTO-FIX] Violations count: {len(req.violations)}")
    logger.info(f"🤖 [AUTO-FIX] Canvas size: {req.width}x{req.height}")
    logger.info(f"🤖 [AUTO-FIX] HTML length: {len(req.html)} chars")
    logger.info(f"🤖 [AUTO-FIX] CSS length: {len(req.css)} chars")
    logger.info(f"🤖 [AUTO-FIX] Images provided: {len(req.images) if req.images else 0}")
    
    for i, v in enumerate(req.violations):
        logger.info(f"🤖 [AUTO-FIX]   Violation {i+1}: [{v.severity}] {v.rule} - {v.message}")
        if v.autoFix:
            logger.info(f"🤖 [AUTO-FIX]     AutoFix hint: {v.autoFix}")
    
    logger.info(f"🤖 [AUTO-FIX] ==========================================")

    try:
        # Step 1: Extract base64 images and replace with placeholders
        cleaned_html, cleaned_css, image_map = await prepare_html_for_llm(
            req.html, req.css
        )

        # Step 2: Build LLM prompt with rules and violations
        prompt = _build_auto_fix_prompt(
            cleaned_html,
            cleaned_css,
            req.violations,
            req.width,
            req.height,
        )

        # Step 3: Call Gemini with retry logic (max 3 attempts)
        max_retries = 3
        corrected_html = None
        corrected_css = None
        fixes = []

        for attempt in range(1, max_retries + 1):
            logger.info(f"🔄 [AUTO-FIX] Attempt {attempt}/{max_retries}")

            try:
                llm_response = await _call_gemini_for_fixes(prompt)

                # Extract structured response
                corrected_html = llm_response.get("html", "")
                corrected_css = llm_response.get("css", "")
                fixes = llm_response.get("fixes", [])

                # Validate HTML structure
                is_valid = await validate_html_structure(corrected_html)

                if is_valid:
                    logger.info(
                        f"✅ [AUTO-FIX] Valid HTML received on attempt {attempt}"
                    )
                    break
                else:
                    logger.warning(
                        f"⚠️ [AUTO-FIX] Invalid HTML on attempt {attempt}, retrying..."
                    )
                    if attempt < max_retries:
                        # Add validation feedback to prompt for next attempt
                        prompt += f"\n\n[RETRY {attempt}] Previous HTML was malformed. Ensure all tags are properly closed and nested."
                        time.sleep(1)  # Rate limiting

            except Exception as e:
                logger.error(f"❌ [AUTO-FIX] Attempt {attempt} failed: {e}")
                if attempt == max_retries:
                    raise
                time.sleep(1)

        # Check if we got valid HTML
        if not corrected_html or not await validate_html_structure(corrected_html):
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate valid HTML after {max_retries} attempts",
            )

        # Step 4: Restore base64 images
        final_html, final_css = await restore_html_from_llm(
            corrected_html,
            corrected_css,
            req.images,  # Use images from request, not image_map
        )

        # Step 5: Parse fixes into structured format
        structured_fixes = [
            FixApplied(
                rule=fix.get("rule", "UNKNOWN"),
                elementId=fix.get("elementId"),
                element_selector=fix.get("element_selector"),
                property=fix.get("property", ""),
                old_value=fix.get("old_value"),
                new_value=fix.get("new_value", ""),
                description=fix.get("description", ""),
            )
            for fix in fixes
        ]

        logger.info(
            f"✅ [AUTO-FIX] Completed with {len(structured_fixes)} fixes applied"
        )

        return AutoFixResponse(
            success=True,
            corrected_html=final_html,
            corrected_css=final_css,
            fixes_applied=structured_fixes,
            remaining_violations=[],
            llm_iterations=attempt,
            error=None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [AUTO-FIX] Fatal error: {e}")
        return AutoFixResponse(
            success=False,
            corrected_html=req.html,  # Return original on failure
            corrected_css=req.css,
            fixes_applied=[],
            remaining_violations=[v.rule for v in req.violations],
            llm_iterations=0,
            error=str(e),
        )


def _build_auto_fix_prompt(
    html: str, css: str, violations: list, canvas_width: int, canvas_height: int
) -> str:
    """Build structured prompt for Gemini auto-fix with HARDCODED pixel positions"""

    # Get relevant rules from violations
    violation_rules = {v.rule for v in violations}
    relevant_rules = [
        rule
        for rule in VALIDATION_RULES.get("rules", [])
        if rule["id"] in violation_rules
    ]

    # === HARDCODED ELEMENT POSITIONS (SCALED TO CANVAS SIZE) ===
    EDGE_PADDING = 20
    
    HARDCODED_POSITIONS = {
        # Headlines - TOP LEFT area
        "headline": {
            "left": EDGE_PADDING,
            "top": EDGE_PADDING,
            "width": int(canvas_width * 0.6),  # 60% of canvas
            "fontSize": max(36, int(canvas_height * 0.05)),  # 5% of height
            "fontWeight": "bold",
            "color": "#000000",
            "textAlign": "left",
            "fontFamily": "Arial, sans-serif"
        },
        # Subheadline - Below headline
        "subheadline": {
            "left": EDGE_PADDING,
            "top": EDGE_PADDING + int(canvas_height * 0.08),  # Below headline
            "width": int(canvas_width * 0.6),
            "fontSize": max(22, int(canvas_height * 0.035)),
            "fontWeight": "normal",
            "color": "#000000",
            "textAlign": "left",
            "fontFamily": "Arial, sans-serif"
        },
        # Tesco Tag Sticker - Bottom left, BIG SIZE
        "tesco_sticker": {
            "left": EDGE_PADDING,
            "top": canvas_height - 120,  # Near bottom
            "width": max(200, int(canvas_width * 0.25)),  # 25% of width
            "height": max(80, int(canvas_height * 0.12)),  # 12% of height
        },
        # Brand Logo - TOP RIGHT corner (when missing, add Tesco logo here)
        "brand_logo": {
            "left": canvas_width - 120,  # Right side
            "top": EDGE_PADDING,  # Top right
            "width": 100,
            "height": 40,
            "position": "top-right"
        },
        # Value Tile / Price Sticker - Bottom right corner, BIG
        "value_tile": {
            "left": canvas_width - 140,
            "top": canvas_height - 140,
            "width": max(120, int(canvas_width * 0.12)),
            "height": max(120, int(canvas_height * 0.15)),
        }
    }

    prompt = f"""You are a Tesco Retail Media compliance specialist. Fix the provided HTML/CSS to resolve compliance violations.

=== CANVAS SPECIFICATIONS ===
Width: {canvas_width}px
Height: {canvas_height}px

=== ⚠️ CRITICAL: HARDCODED ELEMENT POSITIONS (USE EXACTLY THESE VALUES!) ===

📝 HEADLINE (if missing or needs fixing):
   - Position: left={HARDCODED_POSITIONS['headline']['left']}px, top={HARDCODED_POSITIONS['headline']['top']}px
   - Size: fontSize={HARDCODED_POSITIONS['headline']['fontSize']}px, width={HARDCODED_POSITIONS['headline']['width']}px
   - Style: fontWeight=bold, color={HARDCODED_POSITIONS['headline']['color']}, textAlign=left
   - ⚠️ DO NOT use "Your headline here"! Generate creative text like: "Fresh & Delicious", "Quality You Trust", "Taste the Best"

📝 SUBHEADLINE (if missing or needs fixing):
   - Position: left={HARDCODED_POSITIONS['subheadline']['left']}px, top={HARDCODED_POSITIONS['subheadline']['top']}px
   - Size: fontSize={HARDCODED_POSITIONS['subheadline']['fontSize']}px, width={HARDCODED_POSITIONS['subheadline']['width']}px
   - Style: fontWeight=normal, color={HARDCODED_POSITIONS['subheadline']['color']}, textAlign=left
   - ⚠️ DO NOT use placeholder! Generate text like: "Quality you can trust", "Fresh from farm to table"

🏷️ TESCO TAG STICKER (if missing):
   - Position: left={HARDCODED_POSITIONS['tesco_sticker']['left']}px, top={HARDCODED_POSITIONS['tesco_sticker']['top']}px
   - Size: width={HARDCODED_POSITIONS['tesco_sticker']['width']}px, height={HARDCODED_POSITIONS['tesco_sticker']['height']}px
   - Text: "Available at Tesco" - BIG FONT (24px minimum)
   - Must be clearly visible! INCREASE SIZE if too small!

🏢 BRAND LOGO / TESCO LOGO (if missing):
   - Position: left={HARDCODED_POSITIONS['brand_logo']['left']}px (TOP RIGHT!), top={HARDCODED_POSITIONS['brand_logo']['top']}px
   - Size: width={HARDCODED_POSITIONS['brand_logo']['width']}px, height={HARDCODED_POSITIONS['brand_logo']['height']}px
   - ⚠️ IMPORTANT: If no brand logo exists, ADD "Tesco" text at TOP RIGHT corner!
   - Use Tesco blue color: #00539F

💰 VALUE TILE (if present):
   - Position: left={HARDCODED_POSITIONS['value_tile']['left']}px, top={HARDCODED_POSITIONS['value_tile']['top']}px
   - Size: width={HARDCODED_POSITIONS['value_tile']['width']}px, height={HARDCODED_POSITIONS['value_tile']['height']}px

=== VIOLATIONS DETECTED ({len(violations)}) ===
"""

    for i, violation in enumerate(violations, 1):
        prompt += f"\n{i}. {violation.rule}: {violation.message}"
        if violation.elementId:
            prompt += f" (Element ID: {violation.elementId})"

    prompt += f"\n\n=== COMPLIANCE RULES ===\n"

    for rule in relevant_rules:
        prompt += f"""
Rule: {rule["name"]} ({rule["id"]})
Severity: {rule["severity"]}
Description: {rule["description"]}
Fix Instructions: {rule["fix_instruction"]}
Example: {rule.get("example_fix", "N/A")}
---
"""

    prompt += f"""

=== CURRENT HTML ===
{html}

=== CURRENT CSS ===
{css}

=== ⚠️ CRITICAL INSTRUCTIONS ===
1. USE THE EXACT PIXEL POSITIONS SPECIFIED ABOVE - copy them exactly!
2. For HEADLINE: Generate creative text like "Fresh & Delicious", "Quality You Trust" - NOT "Your headline here"!
3. For SUBHEADLINE: Generate text like "Quality you can trust" - NOT placeholder text!
4. For TESCO STICKER: Make it BIG ({HARDCODED_POSITIONS['tesco_sticker']['width']}x{HARDCODED_POSITIONS['tesco_sticker']['height']}px), text "Available at Tesco"
5. For BRAND LOGO: Add "Tesco" text at TOP RIGHT (left={HARDCODED_POSITIONS['brand_logo']['left']}px, top={HARDCODED_POSITIONS['brand_logo']['top']}px), color=#00539F
6. Preserve image placeholders ({{{{ IMG_N }}}}) exactly as-is
7. Return ONLY valid, well-formed HTML/CSS
8. Ensure all opening tags have matching closing tags

=== EXAMPLE FIX FOR MISSING HEADLINE ===
Add this div:
<div style="position: absolute; left: {HARDCODED_POSITIONS['headline']['left']}px; top: {HARDCODED_POSITIONS['headline']['top']}px; font-size: {HARDCODED_POSITIONS['headline']['fontSize']}px; font-weight: bold; color: {HARDCODED_POSITIONS['headline']['color']};">Fresh & Delicious</div>

=== EXAMPLE FIX FOR MISSING BRAND LOGO ===
Add this div at TOP RIGHT:
<div style="position: absolute; left: {HARDCODED_POSITIONS['brand_logo']['left']}px; top: {HARDCODED_POSITIONS['brand_logo']['top']}px; font-size: 20px; font-weight: bold; color: #00539F;">Tesco</div>

=== OUTPUT FORMAT (JSON) ===
Return a JSON object with this exact structure:
{{
  "html": "corrected HTML with all fixes applied",
  "css": "corrected CSS with all style fixes",
  "fixes": [
    {{
      "rule": "RULE_ID",
      "elementId": "element-id or null",
      "element_selector": ".element-class or tag",
      "property": "property name (fontSize, y, color, etc.)",
      "old_value": "previous value",
      "new_value": "corrected value with EXACT pixel values",
      "description": "brief description of what was fixed"
    }}
  ]
}}

Begin correction now. USE THE EXACT POSITIONS I SPECIFIED!
"""

    return prompt


async def _call_gemini_for_fixes(prompt: str) -> dict:
    """Call Gemini API for structured auto-fix response"""

    try:
        # Use API key if available, otherwise fall back to Vertex AI (ADC)
        if GOOGLE_API_KEY:
            logger.info("🔑 [AUTO-FIX] Using Google API Key authentication")
            client = genai.Client(api_key=GOOGLE_API_KEY)
            model_name = "gemini-2.5-flash"  # Consumer API model
        else:
            logger.info("☁️ [AUTO-FIX] Using Vertex AI authentication (ADC)")
            client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
            model_name = MODEL_ID  # Use configured model for Vertex AI

        # Log the input prompt
        logger.info("=" * 80)
        logger.info("📝 [AUTO-FIX] INPUT PROMPT TO GEMINI:")
        logger.info("=" * 80)
        logger.info(f"\n{prompt}\n")
        logger.info("=" * 80)
        logger.info(f"🤖 [AUTO-FIX] Calling Gemini model: {model_name}")

        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,  # Low temperature for deterministic fixes
                response_mime_type="application/json",  # Force JSON output
                max_output_tokens=8192,  # Allow large HTML responses
            ),
        )

        # Log the raw response
        logger.info("=" * 80)
        logger.info("📤 [AUTO-FIX] RAW OUTPUT FROM GEMINI:")
        logger.info("=" * 80)
        logger.info(f"\n{response.text}\n")
        logger.info("=" * 80)

        # Parse JSON response
        result = json.loads(response.text)

        logger.info(
            f"✨ [AUTO-FIX] Gemini returned {len(result.get('fixes', []))} fixes"
        )

        # Log structured output summary
        logger.info("📊 [AUTO-FIX] Parsed fixes summary:")
        for i, fix in enumerate(result.get("fixes", []), 1):
            logger.info(
                f"  {i}. {fix.get('rule', 'UNKNOWN')}: {fix.get('description', 'No description')}"
            )

        return result

    except json.JSONDecodeError as e:
        logger.error(f"❌ [AUTO-FIX] Invalid JSON from Gemini: {e}")
        logger.error(f"Raw response text: {response.text[:500]}...")
        # Try to extract JSON from response
        try:
            import re

            json_match = re.search(r"\{.*\}", response.text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except:
            pass
        raise HTTPException(status_code=500, detail="LLM returned invalid JSON")

    except Exception as e:
        logger.error(f"❌ [AUTO-FIX] Gemini API error: {e}")
        raise HTTPException(status_code=500, detail=f"AI service error: {str(e)}")


# ==================== GENERATE CONTENT FOR AUTO-FIX ====================
from pydantic import BaseModel
from typing import Optional, List

class GenerateContentRequest(BaseModel):
    """Request to generate content for auto-fix"""
    rule: str  # The rule that failed (e.g., "SUBHEAD", "HEADLINE", "TESCO_TAG")
    context: Optional[str] = None  # Context from the canvas (e.g., headline text)
    product_name: Optional[str] = None  # Product name if available
    canvas_objects: Optional[List[dict]] = None  # Canvas objects for context

class GenerateContentResponse(BaseModel):
    """Response with generated content"""
    content: str
    rule: str
    suggestion: Optional[str] = None


@router.post("/generate-content")
async def generate_content_for_fix(req: GenerateContentRequest) -> GenerateContentResponse:
    """
    Generate proper content for auto-fix based on the rule that failed.
    Uses AI to generate contextual content instead of placeholder text.
    """
    logger.info(f"✨ [GENERATE] ========== GENERATE CONTENT REQUEST ==========")
    logger.info(f"✨ [GENERATE] Rule: {req.rule}")
    logger.info(f"✨ [GENERATE] Context: {req.context}")
    logger.info(f"✨ [GENERATE] Product: {req.product_name}")
    
    try:
        # Extract context from canvas objects if provided
        headline_text = ""
        product_info = req.product_name or ""
        
        if req.canvas_objects:
            for obj in req.canvas_objects:
                if obj.get('type') in ['text', 'textbox', 'i-text']:
                    text = obj.get('text', '')
                    font_size = obj.get('fontSize', 16)
                    # Likely headline if large font
                    if font_size >= 24 and len(text) > 5:
                        headline_text = text
                        break
        
        if req.context:
            headline_text = req.context
        
        # Build prompt based on rule
        prompt = _build_content_generation_prompt(req.rule, headline_text, product_info)
        
        # Call Gemini to generate content
        client = genai.Client(api_key=GOOGLE_API_KEY)
        model_name = "gemini-2.5-flash"
        
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=256,
            ),
        )
        
        generated_text = response.text.strip()
        
        # Clean up the response (remove quotes if present)
        if generated_text.startswith('"') and generated_text.endswith('"'):
            generated_text = generated_text[1:-1]
        if generated_text.startswith("'") and generated_text.endswith("'"):
            generated_text = generated_text[1:-1]
        
        logger.info(f"✨ [GENERATE] Generated: {generated_text}")
        logger.info(f"✨ [GENERATE] ==========================================")
        
        return GenerateContentResponse(
            content=generated_text,
            rule=req.rule,
            suggestion=f"Added {req.rule.lower().replace('_', ' ')} based on your design"
        )
        
    except Exception as e:
        logger.error(f"❌ [GENERATE] Error: {e}")
        # Return fallback content
        fallback = _get_fallback_content(req.rule, headline_text)
        return GenerateContentResponse(
            content=fallback,
            rule=req.rule,
            suggestion="Added default content (AI generation failed)"
        )


def _build_content_generation_prompt(rule: str, headline: str, product: str) -> str:
    """Build prompt for content generation based on rule type - generates PRODUCT-SPECIFIC creative text"""
    
    if rule == "SUBHEAD" or rule == "MISSING_SUBHEAD":
        return f"""Generate a creative, compelling PARAGRAPH subheadline for a Tesco retail advertisement.

Product/Context: "{product or headline or 'Fresh product'}"

Requirements:
- Write 12-20 words as a COMPLETE SENTENCE or two short sentences
- Must relate DIRECTLY to the product shown
- Highlight product benefits (fresh, quality, taste, value, everyday essentials)
- Professional but warm Tesco tone
- Descriptive and informative like a product tagline
- Do NOT include prices or promotions
- Do NOT include CTAs

Examples of GOOD longer subheadlines:
- For skincare: "Discover simple routines for healthy, happy skin with our everyday essentials."
- For banana: "Perfectly ripe and naturally sweet, picked at the peak of freshness for your family."
- For milk: "Fresh from farm to fridge daily, bringing quality dairy to your breakfast table."
- For bread: "Baked fresh every single day, crafted with care for that perfect golden taste."
- For snacks: "Delicious moments anytime you want them, perfect for sharing with family and friends."
- Generic: "Quality you can trust for your everyday needs, delivering value with every purchase."

Return ONLY the subhead text (12-20 words), no quotes or explanation."""

    elif rule == "HEADLINE" or rule == "MISSING_HEADLINE":
        return f"""Generate a catchy, creative headline for a Tesco retail advertisement.

Product/Context: "{product or 'Quality product'}"

Requirements:
- Maximum 5 words
- Bold and attention-grabbing
- Must connect to the product
- Creative and memorable (like "Nano Banana" style)
- Do NOT include prices
- Do NOT include CTAs

Examples of GOOD headlines:
- For banana: "Go Bananas!", "Nano Banana Bliss", "Yellow Perfection"
- For milk: "Pure & Fresh", "Dairy Delight"
- For bread: "Rise & Shine", "Golden Goodness"
- For snacks: "Snack Attack!", "Crunch Time"
- Generic: "Taste the Difference", "Quality Every Day"

Return ONLY the headline text, no quotes or explanation."""

    elif rule == "TESCO_TAG" or rule == "MISSING_TAG":
        # Tesco tags are specific - return the correct one
        return "Available at Tesco"
    
    elif rule == "CLUBCARD_DATE":
        from datetime import datetime, timedelta
        end_date = datetime.now() + timedelta(days=30)
        return f"Clubcard/app required. Ends {end_date.strftime('%d/%m')}"
    
    elif rule == "DRINKAWARE":
        return "drinkaware.co.uk"
    
    elif rule == "LOGO" or rule == "MISSING_LOGO":
        # When logo is missing, we return instruction to add Tesco logo
        return "ADD_TESCO_LOGO_RIGHT_SIDE"
    
    else:
        return f"""Generate appropriate text content for a Tesco retail advertisement.

Product/Context: "{product or headline or 'Retail product'}"

Requirements:
- Professional retail tone
- Creative and product-relevant
- Tesco brand appropriate
- Maximum 10 words

Return ONLY the text, no quotes or explanation."""


def _get_fallback_content(rule: str, headline: str = "") -> str:
    """Return fallback content if AI generation fails"""
    fallbacks = {
        "SUBHEAD": "Discover quality products for your everyday needs, delivering value and freshness with every purchase.",
        "HEADLINE": "Quality Guaranteed",
        "TESCO_TAG": "Available at Tesco",
        "MISSING_TAG": "Available at Tesco",
        "CLUBCARD_DATE": "Clubcard/app required. Ends 31/01",
        "DRINKAWARE": "drinkaware.co.uk",
        "LEP_TAG": "Selected stores. While stocks last",
    }
    return fallbacks.get(rule, "")

