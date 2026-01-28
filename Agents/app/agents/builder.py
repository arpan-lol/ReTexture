from pydantic import BaseModel, Field
from typing import List, Dict, Any
from dotenv import load_dotenv
import logging
import os

load_dotenv()
PROJECT_ID = os.getenv("GCP_PROJECT_ID")
LOCATION = os.getenv("GCP_LOCATION")
MODEL_ID = os.getenv("GEMINI_MODEL_ID")
logger = logging.getLogger(__name__)

_agent = None
_agent_initialized = False

class ValidationOutput(BaseModel):
    canvas: str = Field(description="Updated HTML + CSS after validation")
    issues: List[Dict[str, Any]] = Field(description="List of validation issues found")

def init_agent():
    """
    Initialize the validation agent.
    Fails gracefully if Google API credentials are not available.
    """
    global _agent, _agent_initialized
    
    if _agent_initialized:
        return
    
    # Check if we should skip agent initialization
    if os.getenv("SKIP_VALIDATION_AGENT", "false").lower() == "true":
        logger.info("⚠️ Skipping validation agent initialization (SKIP_VALIDATION_AGENT=true)")
        _agent_initialized = True
        return
    
    try:
        from langchain.chat_models import init_chat_model
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import JsonOutputParser
        from app.agents.config import RULESET, SYSTEM_PROMPT
        
        parser = JsonOutputParser(pydantic_object=ValidationOutput)
        format_instructions = parser.get_format_instructions()

        safe_instructions = format_instructions.replace("{", "{{").replace("}", "}}")

        llm = init_chat_model(model="google_genai:gemini-2.5-flash-lite")

        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                SYSTEM_PROMPT
                + "\n\nFollow these output instructions:\n"
                + safe_instructions
            ),
            ("human", "{canvas}")
        ])

        _agent = prompt | llm | parser
        _agent_initialized = True
        logger.info("✅ Validation agent initialized successfully")
        
    except Exception as e:
        logger.warning(f"⚠️ Could not initialize validation agent: {e}")
        logger.info("Validation endpoint will not work, but remove-bg and generate will function.")
        _agent_initialized = True  # Mark as attempted so we don't retry



def is_agent_available():
    """Check if validation agent is available"""
    global _agent_initialized
    if not _agent_initialized:
        init_agent()
    return _agent is not None


def get_agent():
    if _agent is None:
        raise RuntimeError("Agent not initialized - check Google API credentials")
    return _agent
