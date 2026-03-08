"""Production-ready Autotask PSA client with pagination, rate limiting, and retries.

This is a HYPERREALISTIC MOCK implementation for development and testing.
When DEMO_MODE=True (default), it returns realistic mock data without API calls.
When DEMO_MODE=False, it connects to the real Autotask API (requires credentials).

To get production credentials:
1. Request API access from Autotask (zone discovery required)
2. Obtain API username and password
3. Configure .env.autotask with credentials
"""

from __future__ import annotations

import os
import time
import uuid
from collections.abc import Generator, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

AUTOTASK_ENV_PATH = Path(__file__).resolve().parents[2] / ".env.autotask"

# Zone discovery URLs - Autotask requires zone-specific endpoints
AUTOTASK_ZONES = {
    "na": "https://webservices.autotask.net/atservicesrest/v1.0",  # North America
    "eu": "https://webservices-eu.autotask.net/atservicesrest/v1.0",  # Europe
    "au": "https://webservices-au.autotask.net/atservicesrest/v1.0",  # Australia
}

# Rate limit configuration
DEFAULT_RATE_LIMIT_CALLS = 1000  # requests per window (Autotask allows high volume)
DEFAULT_RATE_LIMIT_WINDOW = 60  # seconds
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE = 2.0  # seconds

# Demo mode flag - set to False for production API calls
DEMO_MODE = os.getenv("AUTOTASK_DEMO_MODE", "true").lower() in ("true", "1", "yes")


def load_autotask_env_file(path: Path = AUTOTASK_ENV_PATH) -> bool:
    """Load simple KEY=VALUE pairs from the local Autotask env file."""
    if not path.exists():
        return False

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip("'").strip('"')
        os.environ.setdefault(key.strip(), value)

    return True


def _require_env(name: str, env: Mapping[str, str]) -> str:
    value = env.get(name)
    if value:
        return value
    raise ValueError(f"Missing required Autotask environment variable: {name}")


@dataclass(frozen=True)
class AutotaskCredentials:
    """Credentials required for Autotask API authentication."""

    username: str
    password: str
    integration_code: str  # API integration code from Autotask
    zone: str = "eu"  # Default to EU zone

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> AutotaskCredentials:
        resolved_env = os.environ if env is None else env
        return cls(
            username=_require_env("AUTOTASK_USERNAME", resolved_env),
            password=_require_env("AUTOTASK_PASSWORD", resolved_env),
            integration_code=_require_env("AUTOTASK_INTEGRATION_CODE", resolved_env),
            zone=resolved_env.get("AUTOTASK_ZONE", "eu"),
        )


class RateLimiter:
    """Simple token bucket rate limiter for API calls."""

    def __init__(
        self,
        max_calls: int = DEFAULT_RATE_LIMIT_CALLS,
        window_seconds: int = DEFAULT_RATE_LIMIT_WINDOW,
    ) -> None:
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self.calls: list[float] = []

    def _clean_old_calls(self) -> None:
        """Remove calls outside the current window."""
        cutoff = time.time() - self.window_seconds
        self.calls = [c for c in self.calls if c > cutoff]

    def acquire(self) -> None:
        """Block until a rate limit token is available."""
        while True:
            self._clean_old_calls()
            if len(self.calls) < self.max_calls:
                self.calls.append(time.time())
                return
            time.sleep(0.1)


@dataclass
class AutotaskCompany:
    """Represents an Autotask company/account."""

    id: str
    name: str
    address1: str | None = None
    address2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None
    phone: str | None = None
    fax: str | None = None
    web_address: str | None = None
    company_type: str = "Client"
    market_segment_id: int | None = None
    account_manager_id: int | None = None
    territory_id: int | None = None
    tax_id: str | None = None  # VAT/BTW number
    create_date: datetime = field(default_factory=datetime.utcnow)
    last_modified_date: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "companyName": self.name,
            "address1": self.address1,
            "address2": self.address2,
            "city": self.city,
            "state": self.state,
            "postalCode": self.postal_code,
            "country": self.country,
            "phone": self.phone,
            "fax": self.fax,
            "webAddress": self.web_address,
            "companyType": self.company_type,
            "marketSegmentID": self.market_segment_id,
            "accountManagerID": self.account_manager_id,
            "territoryID": self.territory_id,
            "taxID": self.tax_id,
            "createDate": self.create_date.isoformat() if self.create_date else None,
            "lastModifiedDate": self.last_modified_date.isoformat() if self.last_modified_date else None,
        }


@dataclass
class AutotaskTicket:
    """Represents an Autotask service desk ticket."""

    id: str
    title: str
    description: str | None = None
    company_id: str | None = None
    contact_id: str | None = None
    status: str = "New"
    priority: str = "Medium"
    queue_id: int | None = None
    ticket_type: str | None = None
    issue_type: str | None = None
    sub_issue_type: str | None = None
    assigned_resource_id: int | None = None
    create_date: datetime = field(default_factory=datetime.utcnow)
    last_modified_date: datetime = field(default_factory=datetime.utcnow)
    due_date: datetime | None = None
    completed_date: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "companyID": self.company_id,
            "contactID": self.contact_id,
            "status": self.status,
            "priority": self.priority,
            "queueID": self.queue_id,
            "ticketType": self.ticket_type,
            "issueType": self.issue_type,
            "subIssueType": self.sub_issue_type,
            "assignedResourceID": self.assigned_resource_id,
            "createDate": self.create_date.isoformat() if self.create_date else None,
            "lastModifiedDate": self.last_modified_date.isoformat() if self.last_modified_date else None,
            "dueDate": self.due_date.isoformat() if self.due_date else None,
            "completedDate": self.completed_date.isoformat() if self.completed_date else None,
        }


@dataclass
class AutotaskContract:
    """Represents an Autotask service contract."""

    id: str
    company_id: str
    contract_name: str
    contract_type: str = "Fixed Fee"
    status: str = "Active"
    contract_value: float = 0.0
    start_date: datetime = field(default_factory=datetime.utcnow)
    end_date: datetime = field(default_factory=lambda: datetime.utcnow() + timedelta(days=365))
    billing_code_id: int | None = None
    service_level_agreement_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "companyID": self.company_id,
            "contractName": self.contract_name,
            "contractType": self.contract_type,
            "status": self.status,
            "contractValue": self.contract_value,
            "startDate": self.start_date.isoformat() if self.start_date else None,
            "endDate": self.end_date.isoformat() if self.end_date else None,
            "billingCodeID": self.billing_code_id,
            "serviceLevelAgreementID": self.service_level_agreement_id,
        }


class AutotaskMockData:
    """Hyperrealistic mock data for Autotask development and testing."""

    @staticmethod
    def get_companies() -> list[AutotaskCompany]:
        """Return realistic mock companies."""
        return [
            AutotaskCompany(
                id="AT-001",
                name="TechFlow Solutions BV",
                address1="Innovation Street 42",
                city="Eindhoven",
                postal_code="5612",
                country="Netherlands",
                phone="+31 40 123 4567",
                web_address="https://techflow.nl",
                company_type="Client",
                tax_id="NL123456789B01",
                market_segment_id=1,
            ),
            AutotaskCompany(
                id="AT-002",
                name="B.B.S. Entreprise",
                address1="Noordersingel 25",
                city="Antwerp",
                postal_code="2140",
                country="Belgium",
                phone="+32 3 555 1234",
                web_address="https://bbsentreprise.be",
                company_type="Client",
                tax_id="BE0438.437.723",
                market_segment_id=2,
            ),
            AutotaskCompany(
                id="AT-003",
                name="Legal Partners Advocaten",
                address1="Avenue Louise 250",
                city="Brussels",
                postal_code="1050",
                country="Belgium",
                phone="+32 2 777 8888",
                web_address="https://legalpartners.be",
                company_type="Client",
                tax_id="BE0987.654.321",
                market_segment_id=3,
            ),
            AutotaskCompany(
                id="AT-004",
                name="Green Energy Systems",
                address1="Rue de l'Énergie 15",
                city="Luxembourg",
                postal_code="L-1234",
                country="Luxembourg",
                phone="+352 27 12 34 56",
                web_address="https://greenenergy.lu",
                company_type="Prospect",
                tax_id="LU12345678",
                market_segment_id=4,
            ),
            AutotaskCompany(
                id="AT-005",
                name="Finance First Advisors",
                address1="Boulevard Royal 10",
                city="Luxembourg",
                postal_code="L-2449",
                country="Luxembourg",
                phone="+352 45 67 89 01",
                web_address="https://financefirst.lu",
                company_type="Client",
                tax_id="LU87654321",
                market_segment_id=5,
            ),
        ]

    @staticmethod
    def get_tickets() -> list[AutotaskTicket]:
        """Return realistic mock tickets."""
        now = datetime.utcnow()
        return [
            AutotaskTicket(
                id="TKT-1001",
                title="Email sync issues on mobile devices",
                description="User reports emails not syncing on iPhone and Android devices after recent update.",
                company_id="AT-001",
                status="In Progress",
                priority="High",
                queue_id=1,
                ticket_type="Incident",
                issue_type="Email",
                create_date=now - timedelta(days=2),
                due_date=now + timedelta(days=1),
            ),
            AutotaskTicket(
                id="TKT-1002",
                title="VPN connection drops intermittently",
                description="Remote users experiencing disconnects every 30-45 minutes.",
                company_id="AT-002",
                status="New",
                priority="Medium",
                queue_id=2,
                ticket_type="Incident",
                issue_type="Network",
                create_date=now - timedelta(days=1),
            ),
            AutotaskTicket(
                id="TKT-1003",
                title="Request for new user onboarding",
                description="New hire starting next Monday needs laptop, accounts, and email setup.",
                company_id="AT-001",
                status="New",
                priority="Low",
                queue_id=3,
                ticket_type="Service Request",
                issue_type="User Access",
                create_date=now - timedelta(hours=4),
            ),
            AutotaskTicket(
                id="TKT-1004",
                title="Backup verification failed",
                description="Daily backup job completed but verification step reported checksum errors.",
                company_id="AT-003",
                status="Escalated",
                priority="Critical",
                queue_id=1,
                ticket_type="Incident",
                issue_type="Backup",
                create_date=now - timedelta(hours=6),
                due_date=now + timedelta(hours=2),
            ),
            AutotaskTicket(
                id="TKT-1005",
                title="Office 365 license renewal",
                description="Annual renewal for 25 E3 licenses due next month.",
                company_id="AT-005",
                status="Completed",
                priority="Low",
                queue_id=4,
                ticket_type="Task",
                issue_type="Licensing",
                create_date=now - timedelta(days=7),
                completed_date=now - timedelta(days=1),
            ),
        ]

    @staticmethod
    def get_contracts() -> list[AutotaskContract]:
        """Return realistic mock contracts."""
        now = datetime.utcnow()
        return [
            AutotaskContract(
                id="CNT-001",
                company_id="AT-001",
                contract_name="Managed Services - Gold",
                contract_type="Recurring",
                status="Active",
                contract_value=85000.0,
                start_date=now - timedelta(days=180),
                end_date=now + timedelta(days=185),
            ),
            AutotaskContract(
                id="CNT-002",
                company_id="AT-002",
                contract_name="Break-Fix Support",
                contract_type="Time & Materials",
                status="Active",
                contract_value=15000.0,
                start_date=now - timedelta(days=90),
                end_date=now + timedelta(days=275),
            ),
            AutotaskContract(
                id="CNT-003",
                company_id="AT-003",
                contract_name="Security Audit & Compliance",
                contract_type="Fixed Fee",
                status="Active",
                contract_value=25000.0,
                start_date=now - timedelta(days=30),
                end_date=now + timedelta(days=335),
            ),
        ]


class AutotaskClient:
    """Production-ready Autotask PSA API client.
    
    In DEMO_MODE (default), returns hyperrealistic mock data without API calls.
    Set AUTOTASK_DEMO_MODE=false and provide credentials for live API access.
    """

    def __init__(
        self,
        credentials: AutotaskCredentials | None = None,
        rate_limiter: RateLimiter | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_base: float = DEFAULT_BACKOFF_BASE,
    ) -> None:
        load_autotask_env_file()
        self._demo_mode = DEMO_MODE
        
        # Only load credentials if not in demo mode
        if not self._demo_mode:
            self.credentials = credentials or AutotaskCredentials.from_env()
        else:
            self.credentials = credentials  # May be None in demo mode
            
        self.rate_limiter = rate_limiter or RateLimiter()
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self._client: httpx.Client | None = None

        if self._demo_mode:
            self._mock_data = AutotaskMockData()

    def _get_client(self) -> httpx.Client:
        """Get or create HTTP client with proper authentication headers."""
        if self._client is None:
            if self._demo_mode:
                # No real client needed in demo mode
                return httpx.Client()
            
            base_url = AUTOTASK_ZONES.get(
                self.credentials.zone, 
                AUTOTASK_ZONES["eu"]
            )
            headers = {
                "ApiIntegrationCode": self.credentials.integration_code,
                "UserName": self.credentials.username,
                "Secret": self.credentials.password,
                "Content-Type": "application/json",
            }
            self._client = httpx.Client(
                base_url=base_url,
                headers=headers,
                timeout=30.0,
            )
        return self._client

    def _make_request(self, method: str, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        """Make rate-limited request with retry logic."""
        if self._demo_mode:
            return self._handle_demo_request(method, endpoint, **kwargs)

        self.rate_limiter.acquire()
        client = self._get_client()
        url = f"{client.base_url.rstrip('/')}/{endpoint.lstrip('/')}"

        for attempt in range(self.max_retries):
            try:
                response = client.request(method, url, **kwargs)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:  # Rate limited
                    wait_time = self.backoff_base * (2 ** attempt)
                    time.sleep(wait_time)
                    continue
                raise
            except httpx.RequestError:
                if attempt < self.max_retries - 1:
                    wait_time = self.backoff_base * (2 ** attempt)
                    time.sleep(wait_time)
                    continue
                raise

        raise RuntimeError(f"Max retries exceeded for {method} {endpoint}")

    def _handle_demo_request(self, method: str, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        """Handle demo mode requests with realistic mock responses."""
        # Parse the endpoint to determine what data to return
        if "Companies" in endpoint:
            if method == "GET":
                companies = self._mock_data.get_companies()
                return {
                    "items": [c.to_dict() for c in companies],
                    "pageDetails": {
                        "count": len(companies),
                        "nextPageUrl": None,
                    }
                }
            elif method == "POST":
                # Create new company
                data = kwargs.get("json", {})
                return {
                    "item": {
                        "id": f"AT-{uuid.uuid4().hex[:6].upper()}",
                        "companyName": data.get("companyName", "New Company"),
                        **{k: v for k, v in data.items() if k != "companyName"},
                    }
                }
        
        elif "Tickets" in endpoint:
            if method == "GET":
                tickets = self._mock_data.get_tickets()
                return {
                    "items": [t.to_dict() for t in tickets],
                    "pageDetails": {
                        "count": len(tickets),
                        "nextPageUrl": None,
                    }
                }
            elif method == "POST":
                data = kwargs.get("json", {})
                return {
                    "item": {
                        "id": f"TKT-{uuid.uuid4().hex[:6].upper()}",
                        "title": data.get("title", "New Ticket"),
                        **{k: v for k, v in data.items() if k != "title"},
                    }
                }
        
        elif "Contracts" in endpoint:
            if method == "GET":
                contracts = self._mock_data.get_contracts()
                return {
                    "items": [c.to_dict() for c in contracts],
                    "pageDetails": {
                        "count": len(contracts),
                        "nextPageUrl": None,
                    }
                }

        # Default empty response
        return {"items": [], "pageDetails": {"count": 0, "nextPageUrl": None}}

    def get_companies(self) -> Generator[AutotaskCompany, None, None]:
        """Fetch all companies with automatic pagination."""
        if self._demo_mode:
            for company in self._mock_data.get_companies():
                yield company
            return

        page = 1
        while True:
            response = self._make_request(
                "GET", 
                f"/Companies?page={page}&pageSize=500"
            )
            for item in response.get("items", []):
                yield AutotaskCompany(
                    id=str(item.get("id")),
                    name=item.get("companyName", ""),
                    address1=item.get("address1"),
                    address2=item.get("address2"),
                    city=item.get("city"),
                    state=item.get("state"),
                    postal_code=item.get("postalCode"),
                    country=item.get("country"),
                    phone=item.get("phone"),
                    fax=item.get("fax"),
                    web_address=item.get("webAddress"),
                    company_type=item.get("companyType", "Client"),
                    market_segment_id=item.get("marketSegmentID"),
                    account_manager_id=item.get("accountManagerID"),
                    territory_id=item.get("territoryID"),
                    tax_id=item.get("taxID"),
                )
            
            if not response.get("pageDetails", {}).get("nextPageUrl"):
                break
            page += 1

    def get_tickets(self, company_id: str | None = None) -> Generator[AutotaskTicket, None, None]:
        """Fetch tickets, optionally filtered by company."""
        if self._demo_mode:
            for ticket in self._mock_data.get_tickets():
                if company_id is None or ticket.company_id == company_id:
                    yield ticket
            return

        filter_param = f"&companyID={company_id}" if company_id else ""
        page = 1
        while True:
            response = self._make_request(
                "GET",
                f"/Tickets?page={page}&pageSize=500{filter_param}"
            )
            for item in response.get("items", []):
                yield AutotaskTicket(
                    id=str(item.get("id")),
                    title=item.get("title", ""),
                    description=item.get("description"),
                    company_id=str(item.get("companyID")) if item.get("companyID") else None,
                    contact_id=str(item.get("contactID")) if item.get("contactID") else None,
                    status=item.get("status", "New"),
                    priority=item.get("priority", "Medium"),
                    queue_id=item.get("queueID"),
                    ticket_type=item.get("ticketType"),
                    issue_type=item.get("issueType"),
                    sub_issue_type=item.get("subIssueType"),
                    assigned_resource_id=item.get("assignedResourceID"),
                )
            
            if not response.get("pageDetails", {}).get("nextPageUrl"):
                break
            page += 1

    def get_contracts(self, company_id: str | None = None) -> Generator[AutotaskContract, None, None]:
        """Fetch contracts, optionally filtered by company."""
        if self._demo_mode:
            for contract in self._mock_data.get_contracts():
                if company_id is None or contract.company_id == company_id:
                    yield contract
            return

        filter_param = f"&companyID={company_id}" if company_id else ""
        page = 1
        while True:
            response = self._make_request(
                "GET",
                f"/Contracts?page={page}&pageSize=500{filter_param}"
            )
            for item in response.get("items", []):
                yield AutotaskContract(
                    id=str(item.get("id")),
                    company_id=str(item.get("companyID")),
                    contract_name=item.get("contractName", ""),
                    contract_type=item.get("contractType", "Fixed Fee"),
                    status=item.get("status", "Active"),
                    contract_value=item.get("contractValue", 0.0),
                )
            
            if not response.get("pageDetails", {}).get("nextPageUrl"):
                break
            page += 1

    def create_company(self, company: AutotaskCompany) -> AutotaskCompany:
        """Create a new company in Autotask."""
        response = self._make_request(
            "POST",
            "/Companies",
            json=company.to_dict()
        )
        item = response.get("item", {})
        return AutotaskCompany(
            id=str(item.get("id")),
            name=item.get("companyName", ""),
            **{k: v for k, v in item.items() if k not in ("id", "companyName")}
        )

    def create_ticket(self, ticket: AutotaskTicket) -> AutotaskTicket:
        """Create a new ticket in Autotask."""
        response = self._make_request(
            "POST",
            "/Tickets",
            json=ticket.to_dict()
        )
        item = response.get("item", {})
        return AutotaskTicket(
            id=str(item.get("id")),
            title=item.get("title", ""),
            **{k: v for k, v in item.items() if k not in ("id", "title")}
        )

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            self._client.close()
            self._client = None

    def __enter__(self) -> AutotaskClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


def demo() -> None:
    """Run a demonstration of the Autotask client capabilities."""
    print("=" * 60)
    print("Autotask PSA Client - Demo Mode")
    print("=" * 60)
    print(f"Demo Mode: {DEMO_MODE}")
    print()

    client = AutotaskClient()

    print("Companies:")
    print("-" * 40)
    for company in client.get_companies():
        print(f"  {company.id}: {company.name}")
        print(f"    Location: {company.city}, {company.country}")
        print(f"    Tax ID: {company.tax_id}")
        print()

    print("\nTickets:")
    print("-" * 40)
    for ticket in client.get_tickets():
        print(f"  {ticket.id}: {ticket.title}")
        print(f"    Status: {ticket.status} | Priority: {ticket.priority}")
        print(f"    Company: {ticket.company_id}")
        print()

    print("\nContracts:")
    print("-" * 40)
    for contract in client.get_contracts():
        print(f"  {contract.id}: {contract.contract_name}")
        print(f"    Value: €{contract.contract_value:,.2f} | Status: {contract.status}")
        print()

    print("=" * 60)
    print("Demo complete!")
    print("=" * 60)


if __name__ == "__main__":
    demo()
