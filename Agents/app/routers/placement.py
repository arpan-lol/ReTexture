"""
Robust Placement System - Spatial Grid + Constraint Scoring

Architecture:
1. Build spatial grid (3x3 partitioning for density analysis)
2. Generate candidates (grid-based, anchoring, empty regions)
3. Score each candidate against constraints (graduated penalties)
4. Return highest-scored placement

LLM integration is optional - system works deterministically without it.
"""
import json
import re
import time
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError, Field, field_validator
from typing import List, Optional
from google import genai
from google.genai import types
import os

# Import new placement system
from app.core.shared_ai_client import LLMClient
from app.core.spatial_grid import SpatialGrid, Rectangle
from app.core.placement_constraints import ConstraintScorer
from app.core.placement_generator import CandidateGenerator

router = APIRouter(prefix="/placement", tags=["placement"])

model = None
try:
    client = LLMClient.get_client()
    model = client.models
    print(f"✅ [PLACEMENT] Gemini client initialized: {LLMClient.get_auth_method()}")
except Exception as e:
    print(f"⚠️ [PLACEMENT] Gemini client init failed: {e}")
    print("   Placement will use deterministic algorithm only (no LLM refinement)")


# --- Rate Limiting ---
class RateLimiter:
    def __init__(self, min_interval_seconds=2.0):
        self.last_request_time = 0
        self.min_interval = min_interval_seconds

    def check(self):
        now = time.time()
        if now - self.last_request_time < self.min_interval:
            return False
        self.last_request_time = now
        return True

rate_limiter = RateLimiter(min_interval_seconds=2.0)  # 2 seconds between LLM calls


# --- Data Models with Robust Validation ---
class CanvasElement(BaseModel):
    id: str
    type: str
    x: float  # Allow negative - will be clamped
    y: float  # Allow negative - will be clamped
    width: float = Field(gt=0)  # Must be > 0
    height: float = Field(gt=0)
    text: Optional[str] = None

class SubjectBounds(BaseModel):
    x: float  # Allow negative - will be clamped
    y: float  # Allow negative - will be clamped
    width: float = Field(gt=0)
    height: float = Field(gt=0)

class ElementToPlace(BaseModel):
    type: str = Field(min_length=1)  # Must not be empty
    width: float = Field(gt=0)
    height: float = Field(gt=0)

class CanvasSize(BaseModel):
    w: float = Field(gt=0, description="Canvas width")
    h: float = Field(gt=0, description="Canvas height")

class PlacementRequest(BaseModel):
    canvas_size: CanvasSize
    elements: List[CanvasElement] = Field(default_factory=list)  # Allow empty list
    element_to_place: ElementToPlace
    subject_bounds: Optional[SubjectBounds] = None
    image_base64: Optional[str] = None

class PlacementResponse(BaseModel):
    x: int
    y: int
    confidence: float
    reasoning: str

# Debug endpoint to see raw request
@router.post("/smart-debug")
async def debug_placement(request: Request):
    """Debug endpoint to see raw incoming request"""
    body = await request.json()
    print("[DEBUG] Raw request body:")
    print(json.dumps(body, indent=2))
    return {"received": body}

@router.post("/smart", response_model=PlacementResponse)
async def smart_placement(request: PlacementRequest):
    """
    Robust placement using spatial grid + constraint scoring
    
    Algorithm:
    1. Build spatial grid from existing elements
    2. Generate 50-100 candidate positions
    3. Score each against constraints
    4. Return best candidate
    
    Deterministic and explainable - no LLM required.
    """
    print(f"[PLACEMENT] Received request for {request.element_to_place.type}")
    print(f"[PLACEMENT] Canvas: {request.canvas_size.w}x{request.canvas_size.h}")
    print(f"[PLACEMENT] Elements: {len(request.elements)} existing")
    
    try:
        # Step 1: Build spatial grid
        grid = SpatialGrid(
            canvas_width=request.canvas_size.w,
            canvas_height=request.canvas_size.h,
            grid_size=3  # 3x3 grid
        )
        
        # Add existing elements to grid (CLAMP negative coordinates)
        for elem in request.elements:
            # Clamp to canvas bounds - elements outside canvas are invalid
            x_clamped = max(0, min(elem.x, request.canvas_size.w - elem.width))
            y_clamped = max(0, min(elem.y, request.canvas_size.h - elem.height))
            
            if elem.x < 0 or elem.y < 0:
                print(f"[PLACEMENT] ⚠️  Clamped element {elem.id} from ({elem.x:.0f},{elem.y:.0f}) to ({x_clamped:.0f},{y_clamped:.0f})")
            
            grid.add_element(
                x=x_clamped,
                y=y_clamped,
                width=elem.width,
                height=elem.height,
                element_type=elem.type,
                element_id=elem.id,
                text=elem.text
            )
        
        print("[PLACEMENT] Spatial grid built")
        print(grid.get_visual_summary())
        
        # Step 2: Initialize constraint scorer
        subject_rect = None
        if request.subject_bounds:
            # CLAMP subject_bounds to canvas
            sb_x = max(0, request.subject_bounds.x)
            sb_y = max(0, request.subject_bounds.y)
            sb_width = min(request.subject_bounds.width, request.canvas_size.w - sb_x)
            sb_height = min(request.subject_bounds.height, request.canvas_size.h - sb_y)
            
            if request.subject_bounds.x < 0 or request.subject_bounds.y < 0:
                print(f"[PLACEMENT] ⚠️  Clamped subject_bounds from ({request.subject_bounds.x:.0f},{request.subject_bounds.y:.0f}) to ({sb_x:.0f},{sb_y:.0f})")
            
            subject_rect = Rectangle(
                x=sb_x,
                y=sb_y,
                width=sb_width,
                height=sb_height
            )
        
        scorer = ConstraintScorer(
            canvas_width=request.canvas_size.w,
            canvas_height=request.canvas_size.h,
            spatial_grid=grid,
            subject_bounds=subject_rect
        )
        
        # Step 3: Generate candidates
        generator = CandidateGenerator(
            canvas_width=request.canvas_size.w,
            canvas_height=request.canvas_size.h,
            spatial_grid=grid,
            scorer=scorer
        )
        
        candidates = generator.generate_candidates(
            width=request.element_to_place.width,
            height=request.element_to_place.height,
            element_type=request.element_to_place.type,
            max_candidates=100
        )
        
        print(f"[PLACEMENT] Generated {len(candidates)} candidates")
        
        if not candidates:
            # Fallback: Safe default position
            print("[PLACEMENT] No valid candidates - using fallback")
            return PlacementResponse(
                x=40,
                y=40,
                confidence=0.3,
                reasoning="No valid placements found - using safe default"
            )
        
        # Step 4: Return best candidate
        best = candidates[0]
        print(f"[PLACEMENT] Best placement: ({int(best.x)}, {int(best.y)}) score={best.score:.1f}")
        print(f"[PLACEMENT] Method: {best.method}")
        print(f"[PLACEMENT] Reasoning: {best.reasoning[:2]}")  # First 2 reasons
        
        # Confidence based on score (0-100 -> 0.0-1.0)
        confidence = best.score / 100.0
        
        # Build reasoning summary
        reasoning_text = f"{best.method} placement (score: {best.score:.1f}). "
        if best.reasoning:
            reasoning_text += " ".join(best.reasoning[:3])  # Top 3 reasons
        
        return PlacementResponse(
            x=int(best.x),
            y=int(best.y),
            confidence=confidence,
            reasoning=reasoning_text
        )
        
    except Exception as e:
        print(f"[PLACEMENT] Error: {e}")
        import traceback
        traceback.print_exc()
        
        # Fallback on error
        return PlacementResponse(
            x=40,
            y=40,
            confidence=0.3,
            reasoning=f"Error in placement system: {str(e)}"
        )

