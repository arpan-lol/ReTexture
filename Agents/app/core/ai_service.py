import uuid
import io
import os
import time
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image
from app.core.shared_ai_client import LLMClient, get_model_id

from app.prompts.generation_prompts import get_background_generation_prompt
from app.config import AIConfig, Paths

# Load .env from the Agents directory (parent of app/core)
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)
print(f"[AI_SERVICE] Loading .env from: {env_path}")
print(f"[AI_SERVICE] GOOGLE_API_KEY loaded: {'Yes' if os.getenv('GOOGLE_API_KEY') else 'No'}")

# Get GCP credentials from environment variables
PROJECT_ID = AIConfig.PROJECT_ID
LOCATION = AIConfig.LOCATION
MODEL_ID = get_model_id()


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

    client = LLMClient.get_client()

    styles = ["studio", "lifestyle", "creative"]

    generated_files = []

    for i, style in enumerate(styles):
        style_prompt = get_background_generation_prompt(style, user_concept)
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

    try:
        client = LLMClient.get_client()
    except Exception as e:
        print(f"Failed to initialize Gemini client: {e}")
        raise

    styles = ["studio", "lifestyle", "creative"]

    generated_base64 = []

    for i, style in enumerate(styles):
        variation_num = i + 1
        style_prompt = get_background_generation_prompt(style, user_concept)
        
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
    
    # Process image at full quality (1024x1024)
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            # Keep full size for quality
            img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # Save to bytes for rembg
            temp_buffer = io.BytesIO()
            img.save(temp_buffer, format='PNG')
            processed_bytes = temp_buffer.getvalue()
            print(f"[AI DEBUG] Prepared image at {img.size}")
    except Exception as e:
        print(f"[AI DEBUG] Error processing: {e}")
        return None
    
    # Remove background using rembg with faster model
    try:
        print(f"[AI DEBUG] Removing background with rembg (u2netp fast model)...")
        # Use u2netp model - 3-4x faster while maintaining good quality
        product_no_bg = remove(processed_bytes, model_name='u2netp')
        product_img = Image.open(io.BytesIO(product_no_bg)).convert('RGBA')
        print(f"[AI DEBUG] Background removed, product size: {product_img.size}")
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
    
    # Create styled background at full quality (1024x1024)
    canvas_size = (1024, 1024)
    
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