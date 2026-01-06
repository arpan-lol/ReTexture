from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

# from rembg import remove  # Moved inside endpoint to prevent startup hang
from PIL import Image
import io
import base64
import json
import logging
import os
from app.core.models import ValidationRequest, ValidationResponse
from app.core.prompts import COMPLIANCE_SYSTEM_PROMPT
from app.routers import headline_routes  # NEW: Headline generator routes
from app.routers import validate  # NEW: Validation and auto-fix routes
from google import genai
from google.genai import types

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Agent API")

# Register headline routes
app.include_router(headline_routes.router)
# Register validation routes
app.include_router(validate.router)


# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all for debugging
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def health():
    return {"status": "ok", "message": "Agent API is running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# Remove Background Endpoint
@app.post("/remove-bg")
async def remove_background(file: UploadFile = File(...)):
    """
    Remove background from image.
    Returns base64 encoded PNG image.
    """
    print("=" * 60)
    print("[AGENT DEBUG] /remove-bg endpoint called")
    print("=" * 60)

    try:
        # Log incoming file details
        print(f"[AGENT DEBUG] Received file: {file.filename}")
        print(f"[AGENT DEBUG] Content type: {file.content_type}")

        if not file.content_type.startswith("image/"):
            print(f"[AGENT DEBUG] ERROR: Invalid content type - {file.content_type}")
            logger.error(f"[AGENT] Invalid content type: {file.content_type}")
            raise HTTPException(status_code=400, detail="File must be an image")

        print(f"[AGENT DEBUG] Reading {file.filename} data...")
        input_data = await file.read()
        print(f"[AGENT DEBUG] File size: {len(input_data)} bytes")
        logger.info(
            f"[AGENT] Processing image: {file.filename}, size: {len(input_data)} bytes"
        )

        # Resize large images to prevent ONNX memory allocation errors
        MAX_SIZE = 1024  # Reduced to 1024px to prevent memory issues
        print("[AGENT DEBUG] Checking image dimensions...")
        img = Image.open(io.BytesIO(input_data))
        original_size = img.size
        original_mode = img.mode
        print(
            f"[AGENT DEBUG] Original image size: {original_size}, mode: {original_mode}"
        )

        # Always resize to be safe - rembg works best with smaller images
        if max(img.size) > MAX_SIZE:
            print(
                f"[AGENT DEBUG] Image too large ({max(img.size)}px), resizing to max {MAX_SIZE}px..."
            )
            img.thumbnail((MAX_SIZE, MAX_SIZE), Image.LANCZOS)
            print(f"[AGENT DEBUG] Resized to: {img.size}")

        # Convert to RGB if needed (rembg handles RGBA output)
        if img.mode not in ("RGB", "RGBA"):
            print(f"[AGENT DEBUG] Converting from {img.mode} to RGB...")
            img = img.convert("RGB")

        # Convert back to bytes
        img_byte_arr = io.BytesIO()
        save_format = (
            "PNG" if img.mode == "RGBA" else "PNG"
        )  # Always use PNG for quality
        img.save(img_byte_arr, format=save_format, optimize=True)
        input_data = img_byte_arr.getvalue()
        print(f"[AGENT DEBUG] Processed image size: {len(input_data)} bytes")

        # Close image to free memory
        img.close()

        # Remove background using rembg
        print("[AGENT DEBUG] Starting rembg background removal...")
        print("[AGENT DEBUG] Loading rembg (this may take a moment)...")
        from rembg import remove

        print(
            "[AGENT DEBUG] This may take 10-30 seconds for first run (model loading)..."
        )
        output_data = remove(input_data)
        print(
            f"[AGENT DEBUG] Background removal complete! Output size: {len(output_data)} bytes"
        )

        # Encode to base64
        print("[AGENT DEBUG] Encoding output to base64...")
        base64_image = base64.b64encode(output_data).decode("utf-8")
        print(
            f"[AGENT DEBUG] Base64 encoding complete! Length: {len(base64_image)} chars"
        )

        logger.info(f"Background removed, output size: {len(base64_image)} chars")

        print("[AGENT DEBUG] Sending success response...")
        print(f"[AGENT DEBUG] - success: True")
        print(f"[AGENT DEBUG] - image_data length: {len(base64_image)} chars")
        print("=" * 60)
        print("[AGENT DEBUG] /remove-bg completed successfully!")
        print("=" * 60)

        return {"success": True, "image_data": base64_image, "format": "png"}

    except HTTPException as he:
        print(f"[AGENT DEBUG] HTTP Exception: {he.detail}")
        raise he
    except Exception as e:
        print(f"[AGENT DEBUG] ERROR in remove_background: {type(e).__name__}: {e}")
        import traceback

        print(f"[AGENT DEBUG] Traceback:\n{traceback.format_exc()}")
        logger.error(f"Error removing background: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Generate Variations Endpoint
class VariationsRequest(BaseModel):
    image_data: str  # Base64 encoded image
    concept: Optional[str] = "product photography"


@app.post("/generate/variations")
async def generate_variations(req: VariationsRequest):
    """
    Generate background variations for a product image.
    Note: This is a placeholder - actual Gemini AI integration requires GCP credentials.
    """
    print("=" * 60)
    print("[AGENT DEBUG] /generate/variations endpoint called")
    print("=" * 60)

    try:
        print(f"[AGENT DEBUG] Concept: {req.concept}")
        print(f"[AGENT DEBUG] Image data length: {len(req.image_data)} chars")
        print(f"[AGENT DEBUG] Image data starts with: {req.image_data[:50]}...")

        logger.info(f"Generate variations called with concept: {req.concept}")

        # Try to use actual AI if credentials are available
        try:
            print("[AGENT DEBUG] Attempting to import AI service...")
            from app.core.ai_service import generate_variations_from_bytes
            import base64 as b64

            print("[AGENT DEBUG] AI service imported successfully")
            print("[AGENT DEBUG] Decoding base64 image data...")

            image_bytes = b64.b64decode(req.image_data)
            print(f"[AGENT DEBUG] Decoded image bytes: {len(image_bytes)} bytes")

            print(
                f"[AGENT DEBUG] Calling generate_variations_from_bytes with concept: {req.concept}"
            )
            variations = generate_variations_from_bytes(
                image_bytes, req.concept or "product photography"
            )
            print(f"[AGENT DEBUG] AI service returned: {type(variations)}")

            if variations:
                print(f"[AGENT DEBUG] Got {len(variations)} variations from AI")
                for i, v in enumerate(variations):
                    print(
                        f"[AGENT DEBUG] Variation {i + 1} length: {len(v) if v else 0} chars"
                    )

                print("[AGENT DEBUG] Returning successful AI-generated variations")
                print("=" * 60)
                return {"success": True, "variations": variations}
            else:
                print("[AGENT DEBUG] AI returned empty/None variations")

        except ImportError as ie:
            print(f"[AGENT DEBUG] AI service import failed: {ie}")
            logger.warning(f"AI generation not available: {ie}")
        except Exception as ai_error:
            print(
                f"[AGENT DEBUG] AI generation error: {type(ai_error).__name__}: {ai_error}"
            )
            import traceback

            print(f"[AGENT DEBUG] AI Traceback:\n{traceback.format_exc()}")
            logger.warning(f"AI generation not available: {ai_error}")

        # Return the input image as a "variation" as fallback
        print("[AGENT DEBUG] Falling back to returning original image as variation")
        print("=" * 60)
        print("[AGENT DEBUG] /generate/variations completed (fallback mode)")
        print("=" * 60)

        return {
            "success": True,
            "variations": [req.image_data],  # Return input as single variation
            "message": "AI generation not configured - returning original image",
        }

    except Exception as e:
        print(f"[AGENT DEBUG] ERROR in generate_variations: {type(e).__name__}: {e}")
        import traceback

        print(f"[AGENT DEBUG] Traceback:\n{traceback.format_exc()}")
        logger.error(f"Error generating variations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Streaming Variations Endpoint (SSE)
@app.post("/generate/variations/stream")
async def generate_variations_stream(req: VariationsRequest):
    """
    Generate background variations with streaming (SSE).
    Each variation is sent to the client as soon as it's generated.
    """
    print("=" * 60)
    print("[AGENT] 🚀 /generate/variations/stream endpoint called")
    print(f"[AGENT] Request concept: {req.concept}")
    print(f"[AGENT] Request image_data length: {len(req.image_data)}")
    print("=" * 60)

    async def event_generator():
        print("[AGENT] 📡 SSE event_generator started")
        try:
            from app.core.ai_service import generate_single_variation
            import base64 as b64

            image_bytes = b64.b64decode(req.image_data)
            concept = req.concept or "product photography"
            print(f"[AGENT] Decoded image bytes: {len(image_bytes)}")
            log_memory_usage("Before generation")

            # Send initial event
            start_event = f"data: {json.dumps({'type': 'start', 'total': 3})}\n\n"
            print(f"[AGENT] 📤 Sending START event: {start_event[:50]}...")
            yield start_event

            styles = ["studio", "lifestyle", "creative"]
            
            # Process variations SEQUENTIALLY to stay within 512MB memory limit
            print(f"[AGENT] 🎨 Starting SEQUENTIAL generation (memory-efficient)")

            for i, style in enumerate(styles):
                print(f"\n[AGENT] === VARIATION {i + 1}/3 ({style}) ===")

                # Send progress event
                progress_event = f"data: {json.dumps({'type': 'progress', 'index': i, 'style': style})}\n\n"
                print(f"[AGENT] 📤 Sending PROGRESS event for {style}")
                yield progress_event

                try:
                    print(f"[AGENT] 🎨 Generating {style} variation...")
                    variation = generate_single_variation(image_bytes, concept, style)
                    log_memory_usage(f"After {style} generation")

                    if variation:
                        print(
                            f"[AGENT] ✅ Variation {i + 1} ({style}) completed! Length: {len(variation)}"
                        )
                        # Stream immediately when ready
                        variation_event = f"data: {json.dumps({'type': 'variation', 'index': i, 'data': variation})}\n\n"
                        print(
                            f"[AGENT] 📤 Streaming {style} variation IMMEDIATELY (length: {len(variation_event)})"
                        )
                        yield variation_event
                        print(f"[AGENT] ✅ Variation {i + 1} ({style}) STREAMED!")
                    else:
                        print(f"[AGENT] ❌ Variation {i + 1} ({style}) returned empty!")
                        error_event = f"data: {json.dumps({'type': 'error', 'index': i, 'message': 'Empty result'})}\n\n"
                        yield error_event

                except Exception as e:
                    print(f"[AGENT] ❌ Error generating variation {i + 1} ({style}): {e}")
                    import traceback
                    print(f"[AGENT] Traceback:\n{traceback.format_exc()}")
                    error_event = f"data: {json.dumps({'type': 'error', 'index': i, 'message': str(e)})}\n\n"
                    yield error_event

            complete_event = f"data: {json.dumps({'type': 'complete'})}\n\n"
            print(f"[AGENT] 📤 Sending COMPLETE event")
            yield complete_event
            print(f"[AGENT] ✅ SSE stream finished successfully!")
            print("=" * 60)

        except Exception as e:
            print(f"[AGENT] ❌ Fatal error in event_generator: {str(e)}")
            logger.error(f"[AGENT] Fatal error in SSE stream: {e}")
            import traceback

            trace = traceback.format_exc()
            print(f"[AGENT] Traceback:\n{trace}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    print(f"[AGENT] Returning StreamingResponse for concept '{req.concept}'")
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/validate")
async def validate_canvas(req: ValidationRequest) -> ValidationResponse:
    """
    Validate and auto-correct canvas HTML/CSS for Tesco compliance.
    """
    print("=" * 60)
    print("[AGENT] /validate endpoint called")
    print("=" * 60)

    try:
        # 1. Decode base64 canvas String
        decoded_bytes = base64.b64decode(req.canvas)
        canvas_content = decoded_bytes.decode("utf-8")
        print(f"[AGENT] Decoded canvas content: {len(canvas_content)} chars")

        # 2. Call Gemini for validation & correction
        client = genai.Client(
            vertexai=True,
            project=os.getenv("GCP_PROJECT_ID"),
            location=os.getenv("GCP_LOCATION"),
        )

        prompt = f"{COMPLIANCE_SYSTEM_PROMPT}\n\nCanvas HTML/CSS:\n{canvas_content}"

        print("[AGENT] Calling Gemini for compliance check...")
        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL_ID", "gemini-2.5-flash"),
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )

        print("[AGENT] Gemini response received")
        result = json.loads(response.text)

        # 3. Format response
        return ValidationResponse(
            canvas=result.get("corrected_canvas", req.canvas),
            compliant=result.get("compliant", False),
            issues=result.get("issues", []),
            suggestions=result.get("suggestions", []),
        )

    except Exception as e:
        print(f"[AGENT] ❌ Error in /validate: {e}")
        import traceback

        print(traceback.format_exc())

        # Return a non-compliant fallback if AI fails
        return ValidationResponse(
            canvas=req.canvas,
            compliant=False,
            issues=[
                {
                    "type": "system_error",
                    "message": f"Validation engine error: {str(e)}",
                    "fix": "Try again later",
                }
            ],
            suggestions=["Ensure the canvas content is valid HTML/CSS"],
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
