"""
Base Agent class for Building Detection V2.

Provides common LLM initialization and utilities for all agents.
"""

import logging
from typing import Optional

from config import get_settings

logger = logging.getLogger(__name__)


class BaseAgent:
    """Base class for LLM-powered agents."""
    
    def __init__(self, enabled: bool = True, model: Optional[str] = None):
        """
        Initialize the agent.
        
        Args:
            enabled: Whether the agent is active
            model: LLM model to use (defaults to settings)
        """
        self.settings = get_settings()
        self.enabled = enabled
        self.model = model or self.settings.llm_model
        
        # Check for LiteLLM availability
        try:
            import litellm
            self.litellm = litellm
            self.litellm_available = True
        except ImportError:
            self.litellm_available = False
            logger.warning("LiteLLM not available. Install with: pip install litellm")
        
        # Log status
        agent_name = self.__class__.__name__
        if self.enabled and self.litellm_available:
            logger.info(f"{agent_name}: ENABLED (model: {self.model})")
        else:
            logger.warning(f"{agent_name}: DISABLED")
    
    async def _call_llm(
        self, 
        system_prompt: str, 
        user_content: list,
        temperature: Optional[float] = None
    ) -> Optional[dict]:
        """
        Make an async LLM call with JSON response format.
        
        Args:
            system_prompt: System message for the LLM
            user_content: User message content (can include images)
            temperature: Override default temperature
            
        Returns:
            Parsed JSON response dict, or None on error
        """
        if not self.enabled or not self.litellm_available:
            return None
        
        import json
        import os
        
        try:
            response = await self.litellm.acompletion(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                response_format={"type": "json_object"},
                temperature=temperature or self.settings.llm_temperature,
                api_key=os.getenv("GEMINI_API_KEY"),
                num_retries=self.settings.llm_num_retries
            )
            
            content = response.choices[0].message.content
            return json.loads(content)
            
        except Exception as e:
            logger.error(f"LLM call failed: {e}", exc_info=True)
            return None
