"""
Google Gemini Client Wrapper

Provides unified interface for Gemini API interactions with error handling,
retry logic, and safety features.
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any
import time

try:
    import google.generativeai as genai
    from google.generativeai import GenerativeModel
    from google.api_core.exceptions import GoogleAPIError
except ImportError:
    raise ImportError("google-generativeai package not installed. Run: pip install google-generativeai")

from .config import GeminiConfig

logger = logging.getLogger(__name__)

class GeminiClient:
    """
    Wrapper for Google Generative AI (Gemini) API.
    
    Handles:
    - API configuration and authentication
    - Vision and text model management
    - Retry logic with exponential backoff
    - Error handling and logging
    - Health checks
    """
    
    _instance: Optional['GeminiClient'] = None
    _vision_model: Optional[GenerativeModel] = None
    _text_model: Optional[GenerativeModel] = None
    
    def __init__(self):
        """Initialize Gemini client"""
        if not GeminiConfig.API_KEY:
            raise ValueError("GEMINI_API_KEY environment variable not set")
        
        genai.configure(api_key=GeminiConfig.API_KEY)
        self._initialize_models()
        logger.info("GeminiClient initialized successfully")
    
    @classmethod
    def get_instance(cls) -> 'GeminiClient':
        """Get singleton instance of GeminiClient"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def _initialize_models(self):
        """Initialize Gemini models"""
        try:
            vision_model_name = GeminiConfig.get_vision_model()
            text_model_name = GeminiConfig.get_text_model()
            
            self._vision_model = GenerativeModel(
                model_name=vision_model_name,
                safety_settings=GeminiConfig.SAFETY_SETTINGS,
            )
            
            self._text_model = GenerativeModel(
                model_name=text_model_name,
                safety_settings=GeminiConfig.SAFETY_SETTINGS,
            )
            
            logger.info(f"Initialized vision model: {vision_model_name}")
            logger.info(f"Initialized text model: {text_model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini models: {e}")
            raise
    
    def get_vision_model(self) -> GenerativeModel:
        """Get vision model instance"""
        if self._vision_model is None:
            self._initialize_models()
        return self._vision_model
    
    def get_text_model(self) -> GenerativeModel:
        """Get text model instance"""
        if self._text_model is None:
            self._initialize_models()
        return self._text_model
    
    async def generate_content(
        self,
        prompt: str,
        images: Optional[List[Any]] = None,
        model_type: str = "text",
        config: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> str:
        """
        Generate content using Gemini API with retry logic.
        
        Args:
            prompt: Text prompt
            images: Optional list of PIL Images for vision
            model_type: "text" or "vision"
            config: Generation config overrides
            **kwargs: Additional parameters
            
        Returns:
            Generated content text
            
        Raises:
            GoogleAPIError: If API call fails after retries
        """
        model = self.get_text_model() if model_type == "text" else self.get_vision_model()
        
        # Use provided config or default
        generation_config = config or (
            GeminiConfig.VISION_OCR_CONFIG if images else GeminiConfig.GENERATION_CONFIG
        )
        
        content_parts = []
        
        # Add images if provided
        if images:
            content_parts.extend(images)
        
        # Add text prompt
        content_parts.append(prompt)
        
        # Retry logic with exponential backoff
        for attempt in range(GeminiConfig.MAX_RETRIES):
            try:
                response = await asyncio.to_thread(
                    model.generate_content,
                    content_parts,
                    generation_config=generation_config,
                    stream=False,
                )
                
                if response.text:
                    logger.info(f"Generated {len(response.text)} chars in {attempt} attempts")
                    return response.text
                else:
                    logger.warning("Empty response from Gemini API")
                    if attempt < GeminiConfig.MAX_RETRIES - 1:
                        await asyncio.sleep(GeminiConfig.RETRY_DELAY * (2 ** attempt))
                        continue
                    raise ValueError("No text in Gemini response")
                    
            except GoogleAPIError as e:
                logger.error(f"Gemini API error (attempt {attempt + 1}): {e}")
                if attempt < GeminiConfig.MAX_RETRIES - 1:
                    wait_time = GeminiConfig.RETRY_DELAY * (2 ** attempt)
                    logger.info(f"Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    raise
            except Exception as e:
                logger.error(f"Unexpected error in generate_content: {e}")
                raise
        
        raise RuntimeError(f"Failed after {GeminiConfig.MAX_RETRIES} retries")
    
    async def analyze_image(
        self,
        image: Any,
        prompt: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Analyze image using Gemini Vision.
        
        Args:
            image: PIL Image or path to image
            prompt: Analysis prompt
            config: Generation config
            
        Returns:
            Analysis result
        """
        return await self.generate_content(
            prompt=prompt,
            images=[image],
            model_type="vision",
            config=config or GeminiConfig.VISION_OCR_CONFIG,
        )
    
    async def health_check(self) -> bool:
        """
        Verify Gemini API is accessible.
        
        Returns:
            True if API is accessible
        """
        try:
            response = await self.generate_content(
                prompt="Respond with: OK",
                config={"max_output_tokens": 10},
            )
            return "OK" in response or len(response) > 0
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def close(self):
        """Clean up resources"""
        self._vision_model = None
        self._text_model = None
        logger.info("GeminiClient closed")


# Module-level convenience functions
def get_gemini_client() -> GeminiClient:
    """Get Gemini client instance"""
    return GeminiClient.get_instance()


async def generate_with_gemini(
    prompt: str,
    images: Optional[List[Any]] = None,
    model_type: str = "text",
) -> str:
    """Convenience function for generating content"""
    client = get_gemini_client()
    return await client.generate_content(prompt, images, model_type)
