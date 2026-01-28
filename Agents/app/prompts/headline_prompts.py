"""
Headline and text generation prompts for Tesco Retail Media.
"""

# Tesco Brand Guidelines
TESCO_BRAND_GUIDELINES = """
Tesco Brand Voice Guidelines:
- Friendly, warm, and approachable
- Value-focused but not cheap
- Clear and simple language
- Family-friendly
- Confident but not arrogant
- Helpful and informative

Avoid:
- Promotional language ("Free", "Win", "% off", "Prize")
- Complex or jargon-heavy words
- Negative or offensive language
- Exaggerated claims
"""

# Keyword Suggestion Prompt
KEYWORD_SUGGESTION_PROMPT = """Analyze this product image and suggest 5-7 relevant marketing keywords.

Focus on:
- Product category (e.g., dairy, snacks, beverages)
- Key attributes (e.g., organic, fresh, premium)
- Emotional associations (e.g., healthy, delicious, family)
- Usage occasions (e.g., breakfast, party, everyday)

Return ONLY a JSON array of keywords, no explanation:
["keyword1", "keyword2", "keyword3", ...]
"""

# Headline Generation Prompt Template
def HEADLINE_GENERATION_PROMPT(context: str) -> str:
    return f"""You are a Tesco brand copywriter. Analyze this product image and generate 3 headline options.

{TESCO_BRAND_GUIDELINES}

Context:
{context}

Requirements:
- Maximum 5 words per headline
- Catchy and memorable
- Appropriate for Tesco retail marketing
- No promotional language (no "free", "win", "% off")

Return ONLY a JSON array with 3 headlines:
[
  {{"text": "Headline 1", "confidence": 0.95}},
  {{"text": "Headline 2", "confidence": 0.85}},
  {{"text": "Headline 3", "confidence": 0.75}}
]
"""

# Subheading Generation Prompt Template
def SUBHEADING_GENERATION_PROMPT(context: str) -> str:
    return f"""You are a Tesco brand copywriter. Analyze this product image and generate 3 subheading options.

{TESCO_BRAND_GUIDELINES}

Context:
{context}

Requirements:
- Maximum 10-12 words per subheading
- Descriptive and informative
- Complements the headline
- Brand-compliant language
- No promotional language (no "free", "win", "% off")

Return ONLY a JSON array with 3 subheadings:
[
  {{"text": "Subheading 1", "confidence": 0.95}},
  {{"text": "Subheading 2", "confidence": 0.85}},
  {{"text": "Subheading 3", "confidence": 0.75}}
]
"""

# Text Placement Analysis Prompt
TEXT_PLACEMENT_ANALYSIS_PROMPT = """You are an expert graphic designer analyzing this retail advertisement image for optimal text placement.

Identify the BEST position for:
1. HEADLINE (primary text, 40-60px tall)
2. SUBHEADING (secondary text, 20-30px tall)

Consider:
- Visual weight and contrast
- Avoiding product occlusion
- Safe zones (top 200px, bottom 250px for 9:16)
- Text readability and hierarchy
- Negative space utilization

Analyze the image and return a JSON object with safe regions:

{{
  "headline": {{
    "recommended": {{
      "left": <px>,
      "top": <px>,
      "width": <px>,
      "height": <px>
    }},
    "reason": "Why this position works best"
  }},
  "subheading": {{
    "recommended": {{
      "left": <px>,
      "top": <px>,
      "width": <px>,
      "height": <px>
    }},
    "reason": "Why this position works best"
  }},
  "canvas_width": <px>,
  "canvas_height": <px>
}}

Ensure positions don't overlap with product and respect safe zones.
"""

# Typography Styling Prompt
TYPOGRAPHY_STYLING_PROMPT = """Analyze this retail product image and recommend typography styling.

Consider:
1. Background colors and contrast
2. Product colors and visual hierarchy
3. Tesco brand aesthetic (friendly, modern, approachable)

Requirements:
1. Font family must be sans-serif (Arial, Helvetica, or Roboto)
2. Font weight: bold for headlines, normal for subheadings
3. Text shadow for readability against complex backgrounds
4. Use #FFFFFF (white) text for dark backgrounds with strong shadow
5. Use #1A1A1A (dark) text for light backgrounds with subtle shadow

Return a JSON object:

{{
  "headline": {{
    "fontFamily": "Arial",
    "fontSize": <px>,
    "fontWeight": "bold",
    "color": "#FFFFFF or #1A1A1A",
    "textShadow": "2px 2px 4px rgba(0,0,0,0.7)"
  }},
  "subheading": {{
    "fontFamily": "Arial",
    "fontSize": <px>,
    "fontWeight": "normal",
    "color": "#FFFFFF or #1A1A1A",
    "textShadow": "1px 1px 2px rgba(0,0,0,0.5)"
  }},
  "reasoning": "Explanation of color and styling choices"
}}
"""
