import uuid
import io
import os
import time
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image

# Load .env from the Agents directory (parent of app/core)
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)
print(f"[AI_SERVICE] Loading .env from: {env_path}")
print(f"[AI_SERVICE] GOOGLE_API_KEY loaded: {'Yes' if os.getenv('GOOGLE_API_KEY') else 'No'}")

# Get GCP credentials from environment variables
PROJECT_ID = os.getenv("GCP_PROJECT_ID")
LOCATION = os.getenv("GCP_LOCATION")
# Use model from env (Imagen for image generation, Gemini for text)
MODEL_ID = os.getenv("GEMINI_MODEL_ID")

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


def generate_variations(product_filename: str, user_concept: str) -> list[str]:
    base_dir = Path(__file__).resolve().parent.parent
    static_folder = base_dir / "static"
    clean_name = Path(product_filename).name
    input_path = static_folder / clean_name

    if not input_path.exists():
        raise FileNotFoundError(f"File not found: {input_path}")

    with Image.open(input_path) as img:
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        img.thumbnail((1024, 1024))
        
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        product_bytes = img_byte_arr.getvalue()

    client = genai.Client(
        vertexai=True,
        project=PROJECT_ID,
        location=LOCATION,
    )

    styles = [
        # STUDIO - Clean e-commerce style
        f"""Professional e-commerce product photography of the provided product.
Background: Seamless pure white cyclorama studio backdrop, subtle gradient shadow beneath product.
Lighting: Three-point studio lighting setup - key light (softbox 45° left), fill light (right), hair light (top-back). 
Natural light falloff, no harsh highlights.
Camera: Shot on Canon EOS R5, 100mm macro lens, f/8, 1/160s, ISO 100.
Style: Clean, minimal, {user_concept}. Editorial quality suitable for Tesco retail website.
Realism: Natural product texture preserved, subtle surface imperfections visible, realistic reflections on glossy surfaces.
{TESCO_COMPLIANCE_SUFFIX}""",
        # LIFESTYLE - Contextual setting  
        f"""High-end lifestyle product photography featuring the provided product.
Scene: {user_concept} - Product naturally placed in an aspirational real-world setting, 
slightly asymmetric composition for organic feel.
Lighting: Natural window light from left side, golden hour warmth (5500K-6000K color temperature),
soft shadows with natural falloff, subtle rim light from window reflection.
Camera: Shot on Sony A7R IV, 35mm prime lens, f/2.8 for shallow depth of field, ISO 200.
Bokeh on background elements, foreground product tack-sharp.
Style: Editorial magazine quality, authentic lifestyle moment, premium brand aesthetic.
Realism: Environmental reflections on product, natural dust particles in light rays, 
micro-scratches on surfaces, realistic fabric textures.
{TESCO_COMPLIANCE_SUFFIX}""",
        # CREATIVE - Bold advertising
        f"""Bold commercial advertising campaign photography of the provided product.
Scene: Dramatic studio setup with colored gel lighting, {user_concept}.
Background: Deep gradient backdrop (dark to darker), professional studio environment.
Lighting: Cinematic three-point lighting with colored gels - teal/orange complementary scheme,
strong key light (grid softbox left), subtle fill, dramatic rim light creating edge separation.
Light falloff creating depth and dimension. Volumetric light haze optional.
Camera: Shot on Hasselblad H6D-100c, 80mm f/2.8 lens, medium format quality.
Shallow DOF with product sharp, slight motion blur on any floating elements.
Style: Premium advertising campaign, {user_concept}, brand hero shot quality.
Realism: Product surface catching colored light realistically, specular highlights on edges,
natural material properties (metal reflects, matte absorbs), subtle lens flare if applicable.
{TESCO_COMPLIANCE_SUFFIX}"""
    ]

    generated_files = []

    for i, style_prompt in enumerate(styles):
        try:
            full_prompt = f"""
            Keep the product in the input image EXACTLY unchanged.
            Generate a new background: {style_prompt}
            High realism, commercial photography.
            """

            response = client.models.generate_content(
                model=MODEL_ID,
                contents=[
                    types.Part.from_text(text=full_prompt),
                    types.Part.from_bytes(
                        mime_type="image/png",
                        data=product_bytes,
                    ),
                ],
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    image_config=types.ImageConfig(aspect_ratio="1:1"),
                ),
            )

            if response.candidates:
                candidate = response.candidates[0]
                if candidate.content and candidate.content.parts:
                    for part in candidate.content.parts:
                        if part.inline_data:
                            output_filename = f"var_{uuid.uuid4()}.png"
                            output_dir = static_folder / "output"
                            output_dir.mkdir(parents=True, exist_ok=True)
                            
                            out_path = output_dir / output_filename
                            part.as_image().save(out_path)
                            
                            generated_files.append(f"static/output/{output_filename}")
                            break
            
        except Exception as e:
            print(f"Error generating variation: {e}")
            continue

    return generated_files


def generate_variations_from_bytes(image_bytes: bytes, user_concept: str) -> list[str]:
    """
    Generate background variations from raw image bytes.
    Returns list of base64 encoded PNG images.
    """
    import base64
    
    # Process input image
    with Image.open(io.BytesIO(image_bytes)) as img:
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        img.thumbnail((1024, 1024))
        
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        product_bytes = img_byte_arr.getvalue()

    if not PROJECT_ID or not LOCATION or not MODEL_ID:
        raise ValueError("Missing required environment variables: GCP_PROJECT_ID, GCP_LOCATION, or GEMINI_MODEL_ID")
    
    try:
        client = genai.Client(
            vertexai=True,
            project=PROJECT_ID,
            location=LOCATION,
        )
    except Exception as e:
        print(f"Failed to initialize Gemini client: {e}")
        raise

    styles = [
        # STUDIO - Clean e-commerce style
        f"""Professional e-commerce product photography of the provided product.
Background: Seamless pure white cyclorama studio backdrop, subtle gradient shadow beneath product.
Lighting: Three-point studio lighting setup - key light (softbox 45° left), fill light (right), hair light (top-back). 
Natural light falloff, no harsh highlights.
Camera: Shot on Canon EOS R5, 100mm macro lens, f/8, 1/160s, ISO 100.
Style: Clean, minimal, {user_concept}. Editorial quality suitable for Tesco retail website.
Realism: Natural product texture preserved, subtle surface imperfections visible, realistic reflections on glossy surfaces.
{TESCO_COMPLIANCE_SUFFIX}""",
        # LIFESTYLE - Contextual setting  
        f"""High-end lifestyle product photography featuring the provided product.
Scene: {user_concept} - Product naturally placed in an aspirational real-world setting, 
slightly asymmetric composition for organic feel.
Lighting: Natural window light from left side, golden hour warmth (5500K-6000K color temperature),
soft shadows with natural falloff, subtle rim light from window reflection.
Camera: Shot on Sony A7R IV, 35mm prime lens, f/2.8 for shallow depth of field, ISO 200.
Bokeh on background elements, foreground product tack-sharp.
Style: Editorial magazine quality, authentic lifestyle moment, premium brand aesthetic.
Realism: Environmental reflections on product, natural dust particles in light rays, 
micro-scratches on surfaces, realistic fabric textures.
{TESCO_COMPLIANCE_SUFFIX}""",
        # CREATIVE - Bold advertising
        f"""Bold commercial advertising campaign photography of the provided product.
Scene: Dramatic studio setup with colored gel lighting, {user_concept}.
Background: Deep gradient backdrop (dark to darker), professional studio environment.
Lighting: Cinematic three-point lighting with colored gels - teal/orange complementary scheme,
strong key light (grid softbox left), subtle fill, dramatic rim light creating edge separation.
Light falloff creating depth and dimension. Volumetric light haze optional.
Camera: Shot on Hasselblad H6D-100c, 80mm f/2.8 lens, medium format quality.
Shallow DOF with product sharp, slight motion blur on any floating elements.
Style: Premium advertising campaign, {user_concept}, brand hero shot quality.
Realism: Product surface catching colored light realistically, specular highlights on edges,
natural material properties (metal reflects, matte absorbs), subtle lens flare if applicable.
{TESCO_COMPLIANCE_SUFFIX}"""
    ]

    generated_base64 = []

    for i, style_prompt in enumerate(styles):
        variation_num = i + 1
        
        # Add delay between requests to avoid rate limiting (except for first request)
        if i > 0:
            time.sleep(5)
        
        # Retry logic with exponential backoff for rate limiting
        max_retries = 3
        base_delay = 10
        
        for retry in range(max_retries):
            try:
                full_prompt = f"""
                Keep the product in the input image EXACTLY unchanged.
                Generate a new background: {style_prompt}
                High realism, commercial photography.
                """

                response = client.models.generate_content(
                    model=MODEL_ID,
                    contents=[
                        types.Part.from_text(text=full_prompt),
                        types.Part.from_bytes(
                            mime_type="image/png",
                            data=product_bytes,
                        ),
                    ],
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE"],
                        image_config=types.ImageConfig(aspect_ratio="1:1"),
                    ),
                )
                
                if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                    parts = response.candidates[0].content.parts
                    for part in parts:
                        if part.inline_data:
                            img_data = part.inline_data.data
                            base64_str = base64.b64encode(img_data).decode('utf-8')
                            generated_base64.append(base64_str)
                            break
                
                # Success - break out of retry loop
                break
                
            except Exception as e:
                error_msg = str(e)
                is_rate_limit = "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg or "quota" in error_msg.lower()
                
                print(f"Error generating variation {variation_num}: {e}")
                
                if is_rate_limit and retry < max_retries - 1:
                    wait_time = base_delay * (2 ** retry)
                    time.sleep(wait_time)
                    continue
                else:
                    break
    
    return generated_base64


def generate_single_variation(image_bytes: bytes, user_concept: str, style: str = "studio") -> str | None:
    """
    Generate a single background variation for SSE streaming using rembg + styled backgrounds.
    Returns base64 encoded image immediately.
    
    Args:
        image_bytes: Raw image bytes
        user_concept: User's concept/description
        style: One of 'studio', 'lifestyle', 'creative'
    
    Returns:
        Base64 encoded PNG image string, or None on failure
    """
    import base64
    from rembg import remove
    from PIL import ImageDraw, ImageFilter
    
    print(f"[AI DEBUG] Starting {style} variation generation")
    
    # First resize image to make rembg faster (512x512 is much faster than 1024x1024)
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            # Reduce to 512x512 for faster processing
            img.thumbnail((512, 512), Image.Resampling.LANCZOS)
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # Save to bytes for rembg
            temp_buffer = io.BytesIO()
            img.save(temp_buffer, format='PNG')
            resized_bytes = temp_buffer.getvalue()
            print(f"[AI DEBUG] Resized to {img.size} for faster processing")
    except Exception as e:
        print(f"[AI DEBUG] Error resizing: {e}")
        return None
    
    # Remove background using rembg with fast model
    try:
        print(f"[AI DEBUG] Removing background with rembg (fast model)...")
        # Use u2net_human_seg for faster processing (if it's a person) or u2net for general
        product_no_bg = remove(resized_bytes, alpha_matting=False)  # Disable alpha matting for speed
        product_img = Image.open(io.BytesIO(product_no_bg)).convert('RGBA')
        print(f"[AI DEBUG] Background removed in, product size: {product_img.size}")
    except Exception as e:
        print(f"[AI DEBUG] Error removing background: {e}")
        # Fallback: use original image without background removal
        try:
            with Image.open(io.BytesIO(image_bytes)) as img:
                img.thumbnail((512, 512), Image.Resampling.LANCZOS)
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                product_img = img.copy()
                print(f"[AI DEBUG] Using original image without background removal")
        except:
            return None
    
    # Create styled background based on style (512x512 for speed)
    canvas_size = (512, 512)
    
    try:
        if style == "studio":
            # Clean white studio background with subtle gradient
            print(f"[AI DEBUG] Creating studio background...")
            background = Image.new('RGB', canvas_size, (255, 255, 255))
            draw = ImageDraw.Draw(background)
            # Add subtle gradient
            for y in range(canvas_size[1]):
                gray_value = int(255 - (y / canvas_size[1]) * 10)  # Very subtle gradient
                draw.line([(0, y), (canvas_size[0], y)], fill=(gray_value, gray_value, gray_value))
                
        elif style == "lifestyle":
            # Warm, soft gradient background
            print(f"[AI DEBUG] Creating lifestyle background...")
            background = Image.new('RGB', canvas_size, (245, 235, 220))
            draw = ImageDraw.Draw(background)
            # Warm gradient (beige to cream)
            for y in range(canvas_size[1]):
                r = int(245 - (y / canvas_size[1]) * 30)
                g = int(235 - (y / canvas_size[1]) * 25)
                b = int(220 - (y / canvas_size[1]) * 20)
                draw.line([(0, y), (canvas_size[0], y)], fill=(r, g, b))
            # Add subtle blur for softness
            background = background.filter(ImageFilter.GaussianBlur(radius=3))
                
        else:  # creative
            # Bold gradient background (dark teal to navy)
            print(f"[AI DEBUG] Creating creative background...")
            background = Image.new('RGB', canvas_size, (20, 40, 60))
            draw = ImageDraw.Draw(background)
            # Dramatic gradient
            for y in range(canvas_size[1]):
                r = int(20 + (y / canvas_size[1]) * 30)
                g = int(40 + (y / canvas_size[1]) * 50)
                b = int(60 + (y / canvas_size[1]) * 80)
                draw.line([(0, y), (canvas_size[0], y)], fill=(r, g, b))
        
        # Resize product to fit canvas (max 70% of canvas size)
        max_size = int(min(canvas_size) * 0.7)
        product_img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        
        # Center product on background
        x = (canvas_size[0] - product_img.width) // 2
        y = (canvas_size[1] - product_img.height) // 2
        
        # Paste product onto background
        background.paste(product_img, (x, y), product_img)
        print(f"[AI DEBUG] Product composited at position ({x}, {y})")
        
        # Convert to base64
        output = io.BytesIO()
        background.save(output, format='PNG', optimize=True)
        base64_image = base64.b64encode(output.getvalue()).decode('utf-8')
        print(f"[AI DEBUG] ✓ Generated {len(base64_image)} chars for {style}")
        return base64_image
        
    except Exception as e:
        print(f"Error generating {style}: {e}")
        return None