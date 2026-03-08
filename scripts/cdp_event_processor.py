#!/usr/bin/env python3
"""
CDP Event Processor - Python-based workflow automation for Tracardi CE.

Since Tracardi Community Edition doesn't support production workflow execution,
this script provides:
1. Webhook processing for Resend email events
2. Engagement tracking in PostgreSQL
3. Next Best Action recommendation generation
4. Cross-sell/up-sell opportunity detection

Usage:
    # Run the processor
    python scripts/cdp_event_processor.py
    
    # Test with simulated events
    curl -X POST http://localhost:5001/webhook/resend \
      -H "Content-Type: application/json" \
      -d '{"type": "email.opened", "email_id": "test-123", "to": "test@example.com"}'

Environment:
    DATABASE_URL - PostgreSQL connection string
    RESEND_WEBHOOK_SECRET - Resend webhook signing secret
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import psycopg2
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

# Add repo root to path for imports
REPO_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(REPO_ROOT))

# Load environment
load_dotenv(REPO_ROOT / ".env.local")
load_dotenv(REPO_ROOT / ".env", override=False)

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://cdpadmin:cdpadmin123@localhost:5432/cdp")
RESEND_WEBHOOK_SECRET = os.getenv("RESEND_WEBHOOK_SECRET", "")

# Event type weights for scoring
EVENT_WEIGHTS = {
    "email.sent": 1,
    "email.delivered": 2,
    "email.opened": 5,
    "email.clicked": 10,
    "email.bounced": -5,
    "email.complained": -10,
}

# Industry cross-sell mappings (NACE code → recommended services)
CROSS_SELL_MAP = {
    # IT services
    "62010": ["cloud_migration", "cybersecurity_audit", "managed_services"],
    "62020": ["it_consulting", "cloud_solutions", "security_training"],
    "62030": ["custom_development", "system_integration", "support_contract"],
    # Legal/Accounting
    "69101": ["document_automation", "compliance_software", "secure_messaging"],
    "69201": ["accounting_software", "tax_automation", "financial_reporting"],
    # Construction
    "41101": ["project_management_software", "site_monitoring", "equipment_leasing"],
    "43210": ["electrical_maintenance", "energy_audit", "smart_building"],
}


def get_db_connection():
    """Get PostgreSQL database connection."""
    return psycopg2.connect(DATABASE_URL)


def verify_resend_signature(payload: bytes, signature: str | None, secret: str) -> bool:
    """Verify Resend webhook signature using Svix format."""
    if not secret or not signature:
        return False
    
    try:
        parts = signature.split(",")
        if len(parts) != 3 or parts[0] != "v1":
            return False
        
        timestamp_str = parts[1]
        sig = parts[2]
        
        # Verify timestamp is within 5-minute window
        try:
            timestamp = int(timestamp_str)
            now = int(datetime.now(UTC).timestamp())
            if abs(now - timestamp) > 300:
                return False
        except ValueError:
            return False
        
        # Compute expected signature
        signed_payload = f"{timestamp_str}.".encode() + payload
        expected_sig = hmac.new(
            secret.encode("utf-8"),
            signed_payload,
            hashlib.sha256,
        ).hexdigest()
        
        return hmac.compare_digest(sig, expected_sig)
        
    except Exception:
        return False


def update_engagement_score(email: str, event_type: str, event_data: dict) -> dict:
    """
    Update engagement score in PostgreSQL based on email event.
    
    Returns updated engagement metrics.
    """
    weight = EVENT_WEIGHTS.get(event_type, 0)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Try to find company by email domain
        domain = email.split("@")[1] if "@" in email else None
        
        if domain:
            cursor.execute("""
                SELECT c.id, c.kbo_number, c.company_name, c.industry_nace_code
                FROM companies c
                WHERE c.main_email LIKE %s
                LIMIT 1
            """, (f"%@{domain}",))
            
            row = cursor.fetchone()
            if row:
                company_id, kbo_number, company_name, nace_code = row
                
                # Update engagement tracking table
                cursor.execute("""
                    INSERT INTO company_engagement (
                        company_id, kbo_number, email, event_type, event_weight, 
                        event_data, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    company_id, kbo_number, email, event_type, weight,
                    json.dumps(event_data), datetime.now(UTC)
                ))
                
                # Calculate cumulative engagement score
                cursor.execute("""
                    SELECT 
                        COALESCE(SUM(event_weight), 0) as total_score,
                        COUNT(DISTINCT CASE WHEN event_type = 'email.opened' THEN 1 END) as opens,
                        COUNT(DISTINCT CASE WHEN event_type = 'email.clicked' THEN 1 END) as clicks,
                        MAX(created_at) as last_activity
                    FROM company_engagement
                    WHERE kbo_number = %s
                """, (kbo_number,))
                
                score_row = cursor.fetchone()
                total_score, opens, clicks, last_activity = score_row
                
                # Determine engagement level
                if total_score >= 50:
                    engagement_level = "high"
                elif total_score >= 20:
                    engagement_level = "medium"
                else:
                    engagement_level = "low"
                
                conn.commit()
                
                return {
                    "company_id": company_id,
                    "kbo_number": kbo_number,
                    "company_name": company_name,
                    "nace_code": nace_code,
                    "engagement_score": total_score,
                    "engagement_level": engagement_level,
                    "email_opens": opens,
                    "email_clicks": clicks,
                    "last_activity": last_activity.isoformat() if last_activity else None,
                }
        
        conn.commit()
        return {"status": "no_company_found", "email": email}
        
    except Exception as e:
        conn.rollback()
        print(f"Error updating engagement: {e}")
        return {"status": "error", "error": str(e)}
    finally:
        cursor.close()
        conn.close()


def generate_next_best_action(engagement_data: dict) -> dict:
    """
    Generate Next Best Action recommendation based on engagement and company data.
    
    Business case: "Actionadvies voor het salesteam" from the customer profile example.
    """
    kbo_number = engagement_data.get("kbo_number")
    nace_code = engagement_data.get("nace_code")
    engagement_level = engagement_data.get("engagement_level", "low")
    score = engagement_data.get("engagement_score", 0)
    
    if not kbo_number:
        return {"status": "insufficient_data"}
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get unified 360 view for this company
        cursor.execute("""
            SELECT 
                u.kbo_company_name,
                u.tl_company_name,
                u.exact_company_name,
                u.autotask_company_name,
                u.tl_open_deals_count,
                u.exact_total_invoiced,
                u.autotask_open_tickets,
                u.total_source_count
            FROM unified_company_360 u
            WHERE u.kbo_number = %s
        """, (kbo_number,))
        
        row = cursor.fetchone()
        if not row:
            return {"status": "company_not_found", "kbo_number": kbo_number}
        
        (kbo_name, tl_name, exact_name, autotask_name,
         open_deals, total_invoiced, open_tickets, source_count) = row
        
        # Build recommendation
        recommendations = []
        priority = "medium"
        
        # High engagement + no open deals = sales opportunity
        if engagement_level == "high" and (not open_deals or open_deals == 0):
            recommendations.append({
                "type": "sales_opportunity",
                "action": "Schedule sales call - high engagement with no active deals",
                "reason": f"Engagement score {score} indicates strong interest but no open opportunities"
            })
            priority = "high"
        
        # Cross-sell based on industry
        if nace_code and nace_code in CROSS_SELL_MAP:
            services = CROSS_SELL_MAP[nace_code][:2]  # Top 2 recommendations
            recommendations.append({
                "type": "cross_sell",
                "action": f"Propose {', '.join(services)} services",
                "reason": f"Industry {nace_code} typically needs these complementary services"
            })
        
        # Multi-division opportunity (only linked to 1-2 sources)
        if source_count and source_count < 3:
            recommendations.append({
                "type": "multi_division",
                "action": "Introduce other IT1 Group divisions",
                "reason": f"Company only connected to {source_count} source(s) - cross-division opportunity"
            })
        
        # Support issue opportunity
        if open_tickets and open_tickets > 0:
            recommendations.append({
                "type": "support_expansion",
                "action": "Review support contract for expansion",
                "reason": f"{open_tickets} open ticket(s) indicate support needs"
            })
        
        # Low engagement re-activation
        if engagement_level == "low":
            recommendations.append({
                "type": "re_activation",
                "action": "Send re-engagement campaign with special offer",
                "reason": "Low engagement - risk of churn"
            })
        
        return {
            "status": "success",
            "kbo_number": kbo_number,
            "company_name": tl_name or kbo_name or exact_name,
            "engagement_level": engagement_level,
            "engagement_score": score,
            "source_systems": source_count,
            "priority": priority,
            "recommendations": recommendations,
            "timestamp": datetime.now(UTC).isoformat()
        }
        
    except Exception as e:
        print(f"Error generating NBA: {e}")
        return {"status": "error", "error": str(e)}
    finally:
        cursor.close()
        conn.close()


def process_resend_event(resend_payload: dict) -> dict:
    """
    Process a Resend webhook event end-to-end.
    
    Flow:
    1. Parse event
    2. Update engagement score in PostgreSQL
    3. Generate Next Best Action recommendation
    4. Return complete processing result
    """
    event_type = resend_payload.get("type", "unknown")
    event_data = resend_payload.get("data", resend_payload)
    to_email = event_data.get("to", "")
    
    print(f"📧 Processing: {event_type} -> {to_email}")
    
    # Step 1: Update engagement tracking
    engagement = update_engagement_score(to_email, event_type, event_data)
    
    if engagement.get("status") == "no_company_found":
        return {
            "status": "processed",
            "event_type": event_type,
            "email": to_email,
            "engagement": None,
            "next_best_action": None,
            "note": "Company not found in database"
        }
    
    # Step 2: Generate Next Best Action
    nba = generate_next_best_action(engagement)
    
    result = {
        "status": "processed",
        "event_type": event_type,
        "email": to_email,
        "engagement": {
            "kbo_number": engagement.get("kbo_number"),
            "company_name": engagement.get("company_name"),
            "score": engagement.get("engagement_score"),
            "level": engagement.get("engagement_level"),
            "opens": engagement.get("email_opens"),
            "clicks": engagement.get("email_clicks"),
        },
        "next_best_action": nba
    }
    
    print(f"   ✅ Engagement score: {engagement.get('engagement_score')}")
    print(f"   ✅ Recommendations: {len(nba.get('recommendations', []))}")
    
    return result


# FastAPI app
app = FastAPI(title="CDP Event Processor")


@app.post("/webhook/resend")
async def handle_resend_webhook(
    request: Request,
    x_resend_signature: str | None = Header(None),
):
    """
    Receive webhooks from Resend and process engagement tracking.
    
    Returns Next Best Action recommendations for sales teams.
    """
    body = await request.body()
    
    # Verify signature if secret is configured
    if RESEND_WEBHOOK_SECRET:
        if not verify_resend_signature(body, x_resend_signature, RESEND_WEBHOOK_SECRET):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature"
            )
    
    # Parse Resend payload
    try:
        resend_payload = json.loads(body)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON: {e}"
        )
    
    # Process the event
    result = process_resend_event(resend_payload)
    
    return JSONResponse(result)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    # Test database connection
    db_status = "ok"
    try:
        conn = get_db_connection()
        conn.close()
    except Exception as e:
        db_status = f"error: {e}"
    
    return {
        "status": "ok",
        "service": "cdp-event-processor",
        "database": db_status,
        "signature_verification": bool(RESEND_WEBHOOK_SECRET),
    }


@app.get("/api/next-best-action/{kbo_number}")
async def get_next_best_action(kbo_number: str):
    """
    Get Next Best Action recommendation for a specific company.
    
    Business case: "Actionadvies voor het salesteam"
    """
    # Build minimal engagement data from current state
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT 
                COALESCE(SUM(event_weight), 0) as total_score,
                COUNT(DISTINCT CASE WHEN event_type = 'email.opened' THEN 1 END) as opens,
                COUNT(DISTINCT CASE WHEN event_type = 'email.clicked' THEN 1 END) as clicks,
                MAX(created_at) as last_activity
            FROM company_engagement
            WHERE kbo_number = %s
        """, (kbo_number,))
        
        row = cursor.fetchone()
        if row:
            total_score, opens, clicks, last_activity = row
            
            if total_score >= 50:
                engagement_level = "high"
            elif total_score >= 20:
                engagement_level = "medium"
            else:
                engagement_level = "low"
            
            engagement_data = {
                "kbo_number": kbo_number,
                "engagement_score": total_score,
                "engagement_level": engagement_level,
                "email_opens": opens,
                "email_clicks": clicks,
            }
            
            nba = generate_next_best_action(engagement_data)
            return JSONResponse(nba)
        else:
            return JSONResponse({
                "status": "no_engagement_data",
                "kbo_number": kbo_number,
                "message": "No engagement history found for this company"
            })
            
    finally:
        cursor.close()
        conn.close()


@app.get("/api/engagement/leads")
async def get_engaged_leads(min_score: int = 30):
    """
    Get list of engaged leads for sales follow-up.
    
    Query params:
        min_score: Minimum engagement score to include (default: 30)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT 
                ce.kbo_number,
                MAX(c.company_name) as company_name,
                SUM(ce.event_weight) as total_score,
                COUNT(DISTINCT CASE WHEN ce.event_type = 'email.opened' THEN 1 END) as opens,
                COUNT(DISTINCT CASE WHEN ce.event_type = 'email.clicked' THEN 1 END) as clicks,
                MAX(ce.created_at) as last_activity
            FROM company_engagement ce
            JOIN companies c ON ce.kbo_number = c.kbo_number
            GROUP BY ce.kbo_number
            HAVING SUM(ce.event_weight) >= %s
            ORDER BY total_score DESC
        """, (min_score,))
        
        leads = []
        for row in cursor.fetchall():
            kbo, name, score, opens, clicks, last_activity = row
            leads.append({
                "kbo_number": kbo,
                "company_name": name,
                "engagement_score": score,
                "email_opens": opens,
                "email_clicks": clicks,
                "last_activity": last_activity.isoformat() if last_activity else None
            })
        
        return JSONResponse({
            "status": "success",
            "count": len(leads),
            "min_score": min_score,
            "leads": leads
        })
        
    finally:
        cursor.close()
        conn.close()


@app.get("/")
async def root():
    """Root endpoint with API documentation."""
    return {
        "service": "CDP Event Processor",
        "version": "1.0.0",
        "description": "Python-based workflow automation for Tracardi CE",
        "features": [
            "Resend webhook processing",
            "Engagement score tracking",
            "Next Best Action recommendations",
            "Cross-sell opportunity detection",
            "Multi-division sales insights"
        ],
        "endpoints": {
            "POST /webhook/resend": "Receive Resend email events",
            "GET /api/next-best-action/{kbo_number}": "Get recommendations for company",
            "GET /api/engagement/leads": "Get engaged leads for sales",
            "GET /health": "Health check",
        },
    }


def init_database():
    """Initialize engagement tracking table if not exists."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS company_engagement (
                id SERIAL PRIMARY KEY,
                company_id INTEGER REFERENCES companies(id),
                kbo_number VARCHAR(20) NOT NULL,
                email VARCHAR(255),
                event_type VARCHAR(50) NOT NULL,
                event_weight INTEGER NOT NULL DEFAULT 0,
                event_data JSONB,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                INDEX idx_kbo_number (kbo_number),
                INDEX idx_created_at (created_at)
            )
        """)
        
        # Create indexes if they don't exist
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_company_engagement_kbo 
            ON company_engagement(kbo_number)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_company_engagement_created 
            ON company_engagement(created_at)
        """)
        
        conn.commit()
        print("✅ Database initialized successfully")
        
    except Exception as e:
        conn.rollback()
        print(f"⚠️ Database initialization warning: {e}")
    finally:
        cursor.close()
        conn.close()


def main():
    """Run the event processor."""
    import uvicorn
    
    # Initialize database
    init_database()
    
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5001
    
    print("=" * 70)
    print("  🚀 CDP Event Processor")
    print("  Python-based workflow automation for Tracardi CE")
    print("=" * 70)
    print(f"\n   Listening on: http://localhost:{port}")
    print(f"   Webhook URL:  http://localhost:{port}/webhook/resend")
    print(f"   Health check: http://localhost:{port}/health")
    print(f"   NBA API:      http://localhost:{port}/api/next-best-action/{{kbo}}")
    print(f"   Leads API:    http://localhost:{port}/api/engagement/leads")
    print(f"   Signature verification: {'enabled' if RESEND_WEBHOOK_SECRET else 'disabled'}")
    print("\n   Features:")
    print("   • Engagement score tracking")
    print("   • Next Best Action recommendations")
    print("   • Cross-sell opportunity detection")
    print("\n   Press Ctrl+C to stop")
    print("=" * 70)
    
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
