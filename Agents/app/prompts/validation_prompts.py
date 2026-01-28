"""
Validation and auto-fix prompts for compliance correction.
"""

def AUTO_FIX_SYSTEM_PROMPT(
    canvas_width: int,
    canvas_height: int,
    violations: list,
    relevant_rules: list,
    html: str,
    css: str
) -> str:
    """Build structured prompt for Gemini auto-fix with HARDCODED pixel positions"""

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
  "corrected_html": "<full HTML with fixes>",
  "corrected_css": "<full CSS with fixes>",
  "fixes": [
    {{
      "rule": "RULE_ID",
      "elementId": "element-id or null",
      "element_selector": "div.headline or null",
      "property": "CSS property changed",
      "old_value": "old value",
      "new_value": "new value",
      "description": "What was fixed"
    }}
  ]
}}

Do NOT wrap in markdown code blocks. Return pure JSON only."""

    return prompt


# Content Generation Prompts
CONTENT_GENERATION_SUBHEADLINE_PROMPT = """Generate a creative, compelling PARAGRAPH subheadline for a Tesco retail advertisement.

Product/Context: "{product}"

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

CONTENT_GENERATION_HEADLINE_PROMPT = """Generate a catchy, creative headline for a Tesco retail advertisement.

Product/Context: "{product}"

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

CONTENT_GENERATION_FALLBACK_PROMPT = """Generate appropriate text content for a Tesco retail advertisement.

Product/Context: "{product}"

Requirements:
- Professional retail tone
- Creative and product-relevant
- Tesco brand appropriate
- Maximum 10 words

Return ONLY the text, no quotes or explanation."""
