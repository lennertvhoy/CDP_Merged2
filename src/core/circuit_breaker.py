import logging
import time
from enum import Enum

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "CLOSED"  # Normal operation
    OPEN = "OPEN"  # Failing, fast reject
    HALF_OPEN = "HALF_OPEN"  # Testing recovery


class CircuitBreakerOpenException(Exception):
    """Raised when the circuit breaker is open."""

    pass


class CircuitBreaker:
    """
    A simple Circuit Breaker to prevent cascading failures.
    """

    def __init__(self, name: str, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = CircuitState.CLOSED
        self.failures = 0
        self.last_failure_time = 0.0

    def record_failure(self):
        self.failures += 1
        self.last_failure_time = time.monotonic()
        if self.state == CircuitState.CLOSED and self.failures >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(f"CircuitBreaker '{self.name}' opened after {self.failures} failures.")

    def record_success(self):
        if self.state != CircuitState.CLOSED:
            logger.info(f"CircuitBreaker '{self.name}' closed (recovered).")
        self.failures = 0
        self.state = CircuitState.CLOSED

    def can_execute(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if time.monotonic() - self.last_failure_time >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        # HALF_OPEN state allows one request through to test if the service has recovered
        return False
