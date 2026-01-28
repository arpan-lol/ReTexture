import os
import logging
from typing import Optional
from google import genai

logger = logging.getLogger(__name__)


class LLMClient:
    
    _client: Optional[genai.Client] = None
    _auth_method: Optional[str] = None
    _initialized: bool = False
    
    @classmethod
    def get_client(cls) -> genai.Client:
        if cls._client is None:
            cls._initialize_client()
        return cls._client
    
    @classmethod
    def _initialize_client(cls):
        use_vertex = os.getenv("USE_VERTEX_AI", "true").lower() == "true"
        
        try:
            if use_vertex:
                cls._init_vertex_ai()
            else:
                cls._init_api_key()
                
            cls._initialized = True
            logger.info(f"✅ Gemini client initialized using {cls._auth_method}")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Gemini client: {e}")
            raise RuntimeError(f"Gemini client initialization failed: {e}")
    
    @classmethod
    def _init_vertex_ai(cls):
        project_id = os.getenv("GCP_PROJECT_ID")
        location = os.getenv("GCP_LOCATION", "us-central1")
        
        if not project_id:
            raise ValueError(
                "GCP_PROJECT_ID environment variable is required for Vertex AI. "
                "Set USE_VERTEX_AI=false to use API Key instead."
            )
        
        logger.info(f"Initializing Vertex AI client (project={project_id}, location={location})")
        
        cls._client = genai.Client(
            vertexai=True,
            project=project_id,
            location=location
        )
        cls._auth_method = "Vertex AI"
    
    @classmethod
    def _init_api_key(cls):
        api_key = os.getenv("GOOGLE_API_KEY")
        
        if not api_key:
            raise ValueError(
                "GOOGLE_API_KEY environment variable is required. "
                "Set USE_VERTEX_AI=true to use Vertex AI instead."
            )
        
        logger.info("Initializing API Key client")
        
        cls._client = genai.Client(api_key=api_key)
        cls._auth_method = "API Key"
    
    @classmethod
    def reset(cls):
        cls._client = None
        cls._auth_method = None
        cls._initialized = False
    
    @classmethod
    def is_initialized(cls) -> bool:
        return cls._initialized
    
    @classmethod
    def get_auth_method(cls) -> Optional[str]:
        return cls._auth_method


def get_model_id() -> str:
    return os.getenv("GEMINI_MODEL_ID", "gemini-2.5-flash")

