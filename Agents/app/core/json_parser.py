#heavily vibecoded this shit, we really need to switch to langchain
import json
import re
import logging
from typing import Any, Dict, List, Optional, TypeVar, Type
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar('T')


class JSONParseError(Exception):
    """Raised when JSON extraction or validation fails"""
    pass


def extract_json(text: str, expected_type: str = "any") -> Any:

    if not text or not text.strip():
        raise JSONParseError("Empty response text")
    
    text = text.strip()
    
    # Try to find JSON in markdown code blocks first
    markdown_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    if markdown_match:
        json_str = markdown_match.group(1).strip()
        return _parse_and_validate_json(json_str, expected_type)
    
    # Try to find JSON object {...}
    if expected_type in ("object", "any"):
        object_match = re.search(r'\{[\s\S]*\}', text)
        if object_match:
            json_str = object_match.group(0)
            try:
                return _parse_and_validate_json(json_str, "object")
            except JSONParseError:
                pass  # Try array next
    
    # Try to find JSON array [...]
    if expected_type in ("array", "any"):
        array_match = re.search(r'\[[\s\S]*\]', text)
        if array_match:
            json_str = array_match.group(0)
            return _parse_and_validate_json(json_str, "array")
    
    # Last resort: try parsing entire text as JSON
    try:
        return _parse_and_validate_json(text, expected_type)
    except JSONParseError:
        pass
    
    raise JSONParseError(f"No valid JSON found in response. Expected {expected_type}.")


def _parse_and_validate_json(json_str: str, expected_type: str) -> Any:
    """Parse JSON string and validate type"""
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise JSONParseError(f"Invalid JSON syntax: {e}")
    
    if expected_type == "object" and not isinstance(data, dict):
        raise JSONParseError(f"Expected object, got {type(data).__name__}")
    
    if expected_type == "array" and not isinstance(data, list):
        raise JSONParseError(f"Expected array, got {type(data).__name__}")
    
    return data


def extract_json_array(text: str, item_type: Optional[Type] = None) -> List[Any]:
    data = extract_json(text, expected_type="array")
    
    if item_type is not None:
        for i, item in enumerate(data):
            if not isinstance(item, item_type):
                raise JSONParseError(
                    f"Array item {i} has wrong type: expected {item_type.__name__}, "
                    f"got {type(item).__name__}"
                )
    
    return data


def extract_json_object(text: str) -> Dict[str, Any]:

    return extract_json(text, expected_type="object")


def extract_and_validate_model(
    text: str, 
    model_class: Type[BaseModel]
) -> BaseModel:
    
    try:
        data = extract_json_object(text)
    except JSONParseError:
        # Try array format (some LLMs return array instead of object)
        data = extract_json(text, expected_type="any")
    
    try:
        return model_class(**data)
    except ValidationError as e:
        error_details = []
        for error in e.errors():
            field = ".".join(str(loc) for loc in error['loc'])
            error_details.append(f"{field}: {error['msg']}")
        
        raise JSONParseError(
            f"JSON structure doesn't match expected schema:\n" + 
            "\n".join(error_details)
        )


def safe_extract_json(
    text: str, 
    expected_type: str = "any",
    fallback: Any = None
) -> Any:

    try:
        return extract_json(text, expected_type)
    except JSONParseError as e:
        logger.warning(f"JSON extraction failed (using fallback): {e}")
        return fallback


# Example usage and type definitions

class KeywordResponse(BaseModel):
    """Example: Keyword suggestion response"""
    keywords: List[str]


class HeadlineItem(BaseModel):
    """Example: Single headline with confidence"""
    text: str
    confidence: float


class HeadlineListResponse(BaseModel):
    """Example: List of headlines"""
    headlines: List[HeadlineItem]


def parse_keyword_response(llm_text: str) -> List[str]:

    keywords = extract_json_array(llm_text, item_type=str)
    
    if not keywords:
        raise JSONParseError("Keyword list is empty")
    
    if len(keywords) > 20:
        logger.warning(f"Got {len(keywords)} keywords, truncating to 20")
        keywords = keywords[:20]
    
    return keywords


def parse_headline_response(llm_text: str) -> List[Dict[str, Any]]:

    headlines = extract_json_array(llm_text, item_type=dict)
    
    # Validate structure of each headline
    for i, item in enumerate(headlines):
        if "text" not in item:
            raise JSONParseError(f"Headline {i} missing 'text' field")
        
        if not isinstance(item["text"], str):
            raise JSONParseError(f"Headline {i} 'text' must be string")
        
        # Confidence is optional but should be float if present
        if "confidence" in item and not isinstance(item["confidence"], (int, float)):
            raise JSONParseError(f"Headline {i} 'confidence' must be number")
    
    return headlines
