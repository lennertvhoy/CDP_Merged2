"""
CBE Webhook Listener - Real-time company change events from Belgian Crossroads Bank for Enterprises.

This service receives webhook notifications when company data changes in the KBO registry.
"""

import json
import logging
import sys
from datetime import datetime
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("cbe_webhook")

app = FastAPI(
    title="CBE Webhook Listener",
    description="Receive real-time company change events from Belgian CBE",
    version="1.0.0",
)


class CBEChangeEvent(BaseModel):
    """CBE company change event payload."""

    company_number: str = Field(..., min_length=9, max_length=10, description="KBO/BCE company number")
    change_type: Literal["create", "update", "delete"] = Field(..., description="Type of change")
    timestamp: str = Field(..., description="ISO 8601 timestamp of the change")
    source: str = Field(default="cbe", description="Event source system")

    @validator("company_number")
    def validate_company_number(cls, v: str) -> str:
        """Normalize company number to 10 digits."""
        # Remove any non-digit characters
        digits = "".join(c for c in v if c.isdigit())
        # Pad to 10 digits if needed
        if len(digits) == 9:
            digits = "0" + digits
        if len(digits) != 10:
            raise ValueError(f"Company number must be 9 or 10 digits, got {len(digits)}")
        return digits

    @validator("timestamp")
    def validate_timestamp(cls, v: str) -> str:
        """Validate timestamp is valid ISO 8601."""
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError as err:
            raise ValueError("Timestamp must be valid ISO 8601 format") from err
        return v


class WebhookResponse(BaseModel):
    """Webhook response payload."""

    status: str
    message: str
    received_at: str
    company_number: str | None = None


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint for container probes."""
    return {"status": "healthy", "service": "cbe-webhook", "timestamp": datetime.utcnow().isoformat()}


@app.post("/webhook/cbe", response_model=WebhookResponse)
async def receive_cbe_webhook(event: CBEChangeEvent) -> WebhookResponse:
    """
    Receive CBE company change events.

    - **company_number**: KBO/BCE number (9-10 digits)
    - **change_type**: create, update, or delete
    - **timestamp**: ISO 8601 timestamp
    """
    received_at = datetime.utcnow().isoformat()

    # Log event in structured JSON format
    log_entry = {
        "event": "cbe_company_change",
        "company_number": event.company_number,
        "change_type": event.change_type,
        "timestamp": event.timestamp,
        "received_at": received_at,
        "source": event.source,
    }
    logger.info(json.dumps(log_entry))

    # TODO: In future ACPs, publish to Event Hub / Service Bus
    # For now, just log the event

    return WebhookResponse(
        status="success",
        message="Event received and logged",
        received_at=received_at,
        company_number=event.company_number,
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Handle validation errors."""
    logger.warning(json.dumps({"error": "validation_error", "message": str(exc)}))
    return JSONResponse(
        status_code=400,
        content={"status": "error", "message": str(exc)},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected errors."""
    logger.error(json.dumps({"error": "internal_error", "message": str(exc)}))
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": "Internal server error"},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
