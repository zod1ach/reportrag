"""Base agent with retry and validation logic."""

import logging
import time
from typing import Any, Dict

from app.services.llm_client import LLMClient

logger = logging.getLogger(__name__)


class BaseAgent:
    """Base class for all agents with retry and validation logic."""

    def __init__(self, llm_client: LLMClient, db_session):
        """Initialize base agent."""
        self.llm = llm_client
        self.db = db_session

    def execute(self, payload: Dict[str, Any], max_retries: int = 3) -> Dict[str, Any]:
        """
        Execute the agent with retries.

        Args:
            payload: Input payload dict
            max_retries: Maximum number of retry attempts

        Returns:
            Agent output dict

        Raises:
            Exception: If execution fails after max retries
        """
        for attempt in range(max_retries):
            try:
                logger.info(f"Agent {self.__class__.__name__} attempt {attempt + 1}/{max_retries}")

                # Refresh database session to see recently committed data
                self.db.expire_all()

                result = self._run(payload)

                if self._validate(result):
                    logger.info(f"Agent {self.__class__.__name__} succeeded")
                    return result
                else:
                    logger.warning(f"Agent {self.__class__.__name__} validation failed")

            except Exception as e:
                logger.error(f"Agent {self.__class__.__name__} error: {str(e)}")
                if attempt == max_retries - 1:
                    raise

                # Add delay before retrying to avoid rapid-fire requests
                delay = 30 * (attempt + 1)  # 30s, 60s delays
                logger.warning(f"Agent {self.__class__.__name__} waiting {delay}s before retry {attempt + 2}...")
                time.sleep(delay)

        raise ValueError(f"Agent {self.__class__.__name__} failed after {max_retries} retries")

    def _run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run the agent logic (to be implemented by subclasses).

        Args:
            payload: Input payload

        Returns:
            Output dict
        """
        raise NotImplementedError

    def _validate(self, result: Dict[str, Any]) -> bool:
        """
        Validate the agent output (to be overridden by subclasses).

        Args:
            result: Agent output

        Returns:
            True if valid, False otherwise
        """
        return True
