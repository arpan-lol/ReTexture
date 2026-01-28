"""
AI generation prompts for background variations and image generation.
"""

# Tesco Retail Media Compliance Rules - Applied to all AI generations
TESCO_COMPLIANCE_SUFFIX = """

=== TESCO RETAIL MEDIA COMPLIANCE (MANDATORY) ===
Layout Rules:
- Leave top 100px relatively clear for headline text overlay
- Leave bottom 150px relatively clear for Tesco tag, logo, and value tile placement
- Center the product with breathing room on all sides

Hard Restrictions - Absolutely NO:
- Text, words, letters, typography, numbers, or any written content
- Logos, watermarks, symbols, brand marks, or trademarks  
- People, faces, human figures, hands, or body parts
- Offensive, controversial, or non-brand-safe imagery
- Distortions or modifications to the original product
- Cluttered backgrounds that compete with the product

Brand Safety:
- Professional, family-friendly, premium retail aesthetic
- Background should complement, never overpower the product
- Maintain natural, realistic product appearance
"""

# STUDIO - Clean e-commerce style
STYLE_STUDIO_PROMPT = """Professional e-commerce product photography of the provided product.
Background: Seamless pure white cyclorama studio backdrop, subtle gradient shadow beneath product.
Lighting: Three-point studio lighting setup - key light (softbox 45° left), fill light (right), hair light (top-back). 
Natural light falloff, no harsh highlights.
Camera: Shot on Canon EOS R5, 100mm macro lens, f/8, 1/160s, ISO 100.
Style: Clean, minimal, {concept}. Editorial quality suitable for Tesco retail website.
Realism: Natural product texture preserved, subtle surface imperfections visible, realistic reflections on glossy surfaces.
{compliance_suffix}"""

# LIFESTYLE - Contextual setting
STYLE_LIFESTYLE_PROMPT = """High-end lifestyle product photography featuring the provided product.
Scene: {concept} - Product naturally placed in an aspirational real-world setting, 
slightly asymmetric composition for organic feel.
Lighting: Natural window light from left side, golden hour warmth (5500K-6000K color temperature),
soft shadows with natural falloff, subtle rim light from window reflection.
Camera: Shot on Sony A7R IV, 35mm prime lens, f/2.8 for shallow depth of field, ISO 200.
Bokeh on background elements, foreground product tack-sharp.
Style: Editorial magazine quality, authentic lifestyle moment, premium brand aesthetic.
Realism: Environmental reflections on product, natural dust particles in light rays, 
micro-scratches on surfaces, realistic fabric textures.
{compliance_suffix}"""

# CREATIVE - Bold advertising
STYLE_CREATIVE_PROMPT = """Bold commercial advertising campaign photography of the provided product.
Scene: Dramatic studio setup with colored gel lighting, {concept}.
Background: Deep gradient backdrop (dark to darker), professional studio environment.
Lighting: Cinematic three-point lighting with colored gels - teal/orange complementary scheme,
strong key light (grid softbox left), subtle fill, dramatic rim light creating edge separation.
Light falloff creating depth and dimension. Volumetric light haze optional.
Camera: Shot on RED Komodo, 50mm cinema lens, f/2.8, 1/200s, ISO 400.
Film grain texture (35mm Kodak emulation), cinematic color grade.
Style: High-impact, attention-grabbing, commercial advertising aesthetic. {concept}.
Realism: Dramatic but believable lighting, product highlights visible, 
specular reflections controlled, realistic material properties.
{compliance_suffix}"""

# SEASONAL - Holiday themed
STYLE_SEASONAL_PROMPT = """Seasonal lifestyle photography featuring the provided product.
Scene: {concept} - warm, inviting seasonal setting with natural holiday elements.
Background: Soft-focus background with seasonal bokeh (fairy lights, snow, foliage depending on season),
creating festive atmosphere without competing with product.
Lighting: Warm ambient light (3000K-3500K) with practical light sources visible in background,
creating cozy, inviting mood. Soft key light on product from 45° angle.
Camera: Shot on Fujifilm X-T5, 56mm lens, f/1.4 for creamy bokeh, ISO 320.
Classic film color science, warm highlights, rich shadows.
Style: Festive yet sophisticated, family-friendly, celebration-ready. {concept}.
Realism: Natural seasonal props (pine branches, snow, pumpkins), authentic holiday atmosphere,
product shown in context but clearly featured, organic composition.
{compliance_suffix}"""


def get_background_generation_prompt(style: str, concept: str) -> str:
    """
    Generate the full prompt for background generation based on style and user concept.
    
    Args:
        style: One of "studio", "lifestyle", "creative", "seasonal"
        concept: User's creative concept/theme for the background
        
    Returns:
        Complete prompt string with compliance suffix
    """
    style_prompts = {
        "studio": STYLE_STUDIO_PROMPT,
        "lifestyle": STYLE_LIFESTYLE_PROMPT,
        "creative": STYLE_CREATIVE_PROMPT,
        "seasonal": STYLE_SEASONAL_PROMPT,
    }
    
    prompt_template = style_prompts.get(style, STYLE_STUDIO_PROMPT)
    
    return prompt_template.format(
        concept=concept,
        compliance_suffix=TESCO_COMPLIANCE_SUFFIX
    )
