# Autotask PSA Integration

**Status:** Hyperrealistic Mock + Unified 360 Integration Complete  
**Date:** March 8, 2026  
**Type:** Service Management / PSA Integration

---

## Overview

Autotask Professional Services Automation (PSA) integration provides:
- **Service Desk Ticket Management**
- **Contract & SLA Tracking**  
- **Company/Account Management**
- **Support Analytics & Reporting**

This integration completes the IT1 Group 360° view alongside:
- ✅ **Teamleader** (CRM/Sales)
- ✅ **Exact Online** (Finance/Accounting)
- ✅ **Autotask** (Service/PSA) ← This implementation

---

## Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| API Client | ✅ Complete | `src/services/autotask.py` |
| Mock Data | ✅ Complete | 5 companies, 5 tickets, 3 contracts |
| Sync Pipeline | ✅ Complete | `scripts/sync_autotask_to_postgres.py` |
| Database Schema | ✅ Complete | 3 tables + sync cursor |
| Identity Linking | ✅ Complete | VAT/Tax ID matching to KBO |
| Unified 360 Integration | ✅ Complete | `007_add_autotask_to_unified_360.sql` adds `autotask_*` fields and `linked_all` status |
| Production API | ⏸️ Ready | Requires credentials |

---

## Architecture

### Demo Mode (Default)

When `AUTOTASK_DEMO_MODE=true` (default), the integration returns hyperrealistic mock data without requiring API credentials.

```python
from src.services.autotask import AutotaskClient

# Demo mode - no credentials needed
client = AutotaskClient()

for company in client.get_companies():
    print(f"{company.id}: {company.name}")
```

### Production Mode

When `AUTOTASK_DEMO_MODE=false`, the client connects to the real Autotask REST API.

**Requirements:**
1. Autotask API username
2. Autotask API password
3. Integration code (from Autotask admin)
4. Zone selection (na, eu, au)

```bash
# Configure credentials
cp .env.autotask.example .env.autotask
# Edit .env.autotask with your credentials

# Run in production mode
export AUTOTASK_DEMO_MODE=false
uv run python scripts/sync_autotask_to_postgres.py --full
```

---

## Data Model

### Companies

```python
@dataclass
class AutotaskCompany:
    id: str                    # AT-001, AT-002, etc.
    name: str                  # Company name
    address1: str | None       # Primary address
    city: str | None           # City
    postal_code: str | None    # Postal code
    country: str | None        # Country
    phone: str | None          # Phone number
    web_address: str | None    # Website
    tax_id: str | None         # VAT/BTW number (for KBO matching)
    company_type: str          # Client, Prospect, etc.
```

### Tickets

```python
@dataclass
class AutotaskTicket:
    id: str                    # TKT-1001, TKT-1002, etc.
    title: str                 # Ticket title
    description: str | None    # Problem description
    company_id: str | None     # Linked company
    status: str                # New, In Progress, Completed, etc.
    priority: str              # Low, Medium, High, Critical
    ticket_type: str | None    # Incident, Service Request, Task
```

### Contracts

```python
@dataclass
class AutotaskContract:
    id: str                    # CNT-001, CNT-002, etc.
    company_id: str            # Linked company
    contract_name: str         # Contract name
    contract_type: str         # Recurring, Fixed Fee, Time & Materials
    status: str                # Active, Inactive
    contract_value: float      # Contract value in EUR
    start_date: datetime       # Contract start
    end_date: datetime         # Contract end
```

---

## Mock Data

### Companies (5)

| ID | Name | Location | Tax ID |
|----|------|----------|--------|
| AT-001 | TechFlow Solutions BV | Eindhoven, NL | NL123456789B01 |
| AT-002 | B.B.S. Entreprise | Antwerp, BE | BE0438.437.723 |
| AT-003 | Legal Partners Advocaten | Brussels, BE | BE0987.654.321 |
| AT-004 | Green Energy Systems | Luxembourg, LU | LU12345678 |
| AT-005 | Finance First Advisors | Luxembourg, LU | LU87654321 |

### Tickets (5)

| ID | Title | Company | Status | Priority |
|----|-------|---------|--------|----------|
| TKT-1001 | Email sync issues on mobile devices | AT-001 | In Progress | High |
| TKT-1002 | VPN connection drops intermittently | AT-002 | New | Medium |
| TKT-1003 | Request for new user onboarding | AT-001 | New | Low |
| TKT-1004 | Backup verification failed | AT-003 | Escalated | Critical |
| TKT-1005 | Office 365 license renewal | AT-005 | Completed | Low |

### Contracts (3)

| ID | Name | Company | Value | Status |
|----|------|---------|-------|--------|
| CNT-001 | Managed Services - Gold | AT-001 | €85,000 | Active |
| CNT-002 | Break-Fix Support | AT-002 | €15,000 | Active |
| CNT-003 | Security Audit & Compliance | AT-003 | €25,000 | Active |

---

## Usage

### Direct API Client

```python
from src.services.autotask import AutotaskClient

with AutotaskClient() as client:
    # Get all companies
    for company in client.get_companies():
        print(f"{company.name} ({company.city})")
    
    # Get tickets for a company
    for ticket in client.get_tickets(company_id="AT-001"):
        print(f"  [{ticket.status}] {ticket.title}")
    
    # Get contracts
    for contract in client.get_contracts():
        print(f"  {contract.contract_name}: €{contract.contract_value:,.2f}")
```

### Database Sync

```bash
# Demo mode (default)
uv run python scripts/sync_autotask_to_postgres.py

# Full sync (clears existing data)
uv run python scripts/sync_autotask_to_postgres.py --full

# Production sync
export AUTOTASK_DEMO_MODE=false
uv run python scripts/sync_autotask_to_postgres.py --full --production
```

### Query Synced Data

```sql
-- View Autotask companies
SELECT * FROM autotask_companies;

-- View tickets with company info
SELECT 
    t.id,
    t.title,
    t.status,
    t.priority,
    c.name as company_name
FROM autotask_tickets t
JOIN autotask_companies c ON t.company_id = c.id;

-- View contract values by company
SELECT 
    c.name,
    COUNT(ct.id) as contracts,
    SUM(ct.contract_value) as total_value
FROM autotask_companies c
LEFT JOIN autotask_contracts ct ON c.id = ct.company_id
GROUP BY c.name;
```

---

## Identity Linking

The sync automatically attempts to match Autotask companies to KBO records using Tax ID (VAT/BTW number), stores `kbo_number` / `organization_uid`, and projects the matched records into `unified_company_360`:

```sql
-- View matched identities
SELECT 
    sil.uid as kbo_id,
    c.commercial_name as kbo_name,
    ac.name as autotask_name,
    ac.tax_id
FROM source_identity_links sil
JOIN companies c ON sil.uid = c.id
JOIN autotask_companies ac ON sil.source_record_id = ac.id
WHERE sil.source_system = 'autotask';
```

---

## Configuration

### Environment Variables

Create `.env.autotask` from the example:

```bash
cp .env.autotask.example .env.autotask
```

| Variable | Required | Description |
|----------|----------|-------------|
| `AUTOTASK_USERNAME` | Yes (prod) | API username |
| `AUTOTASK_PASSWORD` | Yes (prod) | API password |
| `AUTOTASK_INTEGRATION_CODE` | Yes (prod) | Integration code from Autotask |
| `AUTOTASK_ZONE` | No | Zone: na, eu, au (default: eu) |
| `AUTOTASK_DEMO_MODE` | No | true/false (default: true) |

---

## Database Schema

### Tables Created

```sql
-- Companies
autotask_companies
    - id (PK)
    - name, address fields
    - tax_id (for KBO matching)
    - synced_at

-- Tickets
autotask_tickets
    - id (PK)
    - company_id (FK)
    - title, description, status
    - priority, queue_id
    - create_date, due_date, completed_date
    - synced_at

-- Contracts
autotask_contracts
    - id (PK)
    - company_id (FK)
    - contract_name, contract_type
    - contract_value, status
    - start_date, end_date
    - synced_at

-- Sync tracking
autotask_sync_cursor
    - last_sync_at
    - companies_count
    - tickets_count
    - contracts_count
```

---

## Future Enhancements

1. **Production Credentials**: Obtain real Autotask API access
2. **Real-time Webhooks**: Implement ticket update webhooks
3. **Resource Management**: Sync technician/resource data
4. **Time Entries**: Track billable hours
5. **SLA Monitoring**: Alert on SLA breaches
6. **Dashboard Integration**: Add Autotask metrics to chatbot

---

## Related Documentation

- [Teamleader Integration](./TEAMLEADER_INTEGRATION.md)
- [Exact Online Integration](./EXACT_INTEGRATION.md)
- [Unified 360° Views](./UNIFIED_360_VIEWS.md)
- [AGENTS.md](/AGENTS.md)
