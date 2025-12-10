"""Structured logging for inference requests."""
import os
import logging
from logging.handlers import RotatingFileHandler
from typing import Dict, Any, Optional
from datetime import datetime


class InferenceLogger:
    """Logger for inference requests with structured output."""
    
    def __init__(self):
        self.log_dir = "logs"
        os.makedirs(self.log_dir, exist_ok=True)
        
        self.logger = logging.getLogger("inference")
        self.logger.setLevel(getattr(logging, os.getenv("LOG_LEVEL", "INFO")))
        
        if not self.logger.handlers:
            handler = RotatingFileHandler(
                f"{self.log_dir}/inference.log",
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5
            )
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def log_request(
        self,
        user_id: str,
        catalog_id: str,
        status: str,
        latency_ms: float,
        ai_provider: str,
        error: Optional[str] = None
    ):
        """Log inference request with all details."""
        log_data = {
            "user_id": user_id,
            "catalog_id": catalog_id,
            "status": status,
            "latency_ms": latency_ms,
            "ai_provider": ai_provider,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if error:
            log_data["error"] = error
            self.logger.error(f"Inference request: {log_data}")
        else:
            self.logger.info(f"Inference request: {log_data}")


logger = InferenceLogger()

