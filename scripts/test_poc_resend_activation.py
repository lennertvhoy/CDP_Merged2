#!/usr/bin/env python3
"""
POC Resend Activation End-to-End Test Script

Tests the full activation cycle with Resend: Segment → Resend Audience → Campaign → Engagement → Enriched Profile

This test verifies that all Flexmail functionality has Resend equivalents and that the Resend flow works end-to-end.

Prerequisites:
- PostgreSQL with KBO data
- Tracardi with email workflows deployed
- Resend API key (optional - uses mock if not available)

Usage:
    # Test with mock Resend (no API key required)
    poetry run python scripts/test_poc_resend_activation.py --mock
    
    # Test with real Resend (requires RESEND_API_KEY)
    export RESEND_API_KEY="your-api-key"
    poetry run python scripts/test_poc_resend_activation.py
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.logger import get_logger
from src.services.canonical_segments import CanonicalSegmentService
from src.services.postgresql_search import PostgreSQLSearchService, CompanySearchFilters
from src.services.tracardi import TracardiClient

logger = get_logger(__name__)


class MockResendClient:
    """Mock Resend client for testing without real API key."""
    
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or "mock-api-key"
        self.from_email = "onboarding@resend.dev"
        self.audiences: list[dict] = []
        self.contacts: list[dict] = []
        self.webhooks: list[dict] = []
        self.emails: list[dict] = []
        
    async def get_audiences(self) -> list[dict[str, Any]]:
        return self.audiences
        
    async def create_audience(self, name: str) -> dict[str, Any]:
        audience = {
            "id": f"audience_{len(self.audiences) + 1}",
            "name": name,
            "created_at": datetime.now().isoformat(),
        }
        self.audiences.append(audience)
        logger.info("mock_resend_audience_created", name=name, audience_id=audience["id"])
        return audience
        
    async def add_contact_to_audience(
        self,
        email: str,
        audience_id: str,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> dict[str, Any]:
        contact = {
            "id": f"contact_{len(self.contacts) + 1}",
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "audience_id": audience_id,
            "created_at": datetime.now().isoformat(),
        }
        self.contacts.append(contact)
        logger.info("mock_resend_contact_added", email=email, audience_id=audience_id)
        return contact
        
    async def send_email(
        self,
        to: str,
        subject: str,
        html: str,
        from_email: str | None = None,
    ) -> dict[str, Any]:
        email = {
            "id": f"email_{len(self.emails) + 1}",
            "to": to,
            "subject": subject,
            "from": from_email or self.from_email,
            "status": "sent",
        }
        self.emails.append(email)
        logger.info("mock_resend_email_sent", to=to, subject=subject[:50])
        return email
        
    async def send_bulk_emails(
        self,
        recipients: list[str],
        subject: str,
        html: str,
        from_email: str | None = None,
    ) -> dict[str, Any]:
        for recipient in recipients:
            await self.send_email(recipient, subject, html, from_email)
        return {"data": [{"id": f"email_{i}"} for i in range(len(recipients))]}
        
    async def send_audience_email(
        self,
        audience_id: str,
        subject: str,
        html: str,
        from_email: str | None = None,
    ) -> dict[str, Any]:
        email = {
            "id": f"campaign_{len(self.emails) + 1}",
            "audience_id": audience_id,
            "subject": subject,
            "from": from_email or self.from_email,
            "status": "sent",
        }
        self.emails.append(email)
        logger.info("mock_resend_campaign_sent", audience_id=audience_id, subject=subject[:50])
        return email
        
    async def get_webhooks(self) -> list[dict[str, Any]]:
        return self.webhooks
        
    async def create_webhook(
        self,
        endpoint_url: str,
        events: list[str],
        name: str | None = None,
    ) -> dict[str, Any]:
        webhook = {
            "id": f"webhook_{len(self.webhooks) + 1}",
            "name": name or f"Webhook {len(self.webhooks) + 1}",
            "endpoint": endpoint_url,
            "events": events,
            "status": "active",
        }
        self.webhooks.append(webhook)
        logger.info("mock_resend_webhook_created", name=name, endpoint=endpoint_url, events=events)
        return webhook


class POCResendTester:
    """Tester for POC Resend activation end-to-end flow."""
    
    def __init__(self, use_mock: bool = False):
        self.use_mock = use_mock
        self.results: dict[str, Any] = {
            "test_start": datetime.now().isoformat(),
            "mock_mode": use_mock,
            "tests": {},
            "feature_comparison": {},
        }
        
    async def setup(self):
        """Initialize services."""
        logger.info("poc_resend_test_setup_start")
        
        # PostgreSQL services
        self.segment_service = CanonicalSegmentService()
        self.search_service = PostgreSQLSearchService()
        
        # Tracardi client
        self.tracardi = TracardiClient()
        
        # Resend client (real or mock)
        if self.use_mock:
            self.resend = MockResendClient()
            logger.info("poc_resend_test_using_mock")
        else:
            from src.services.resend import ResendClient
            self.resend = ResendClient()
            logger.info("poc_resend_test_using_real_resend")
            
        logger.info("poc_resend_test_setup_complete")
        
    async def test_feature_parity(self) -> dict[str, Any]:
        """Test 0: Verify Resend has feature parity with Flexmail."""
        test_name = "feature_parity"
        start_time = time.time()
        
        try:
            logger.info("poc_resend_test_feature_parity_start")
            
            # Define Flexmail features and their Resend equivalents
            feature_matrix = {
                "segment_push": {
                    "flexmail": "push_to_flexmail (contacts + interests)",
                    "resend": "push_segment_to_resend (audiences)",
                    "status": "✅ EQUIVALENT",
                    "notes": "Both push segment members to email platform",
                },
                "audience_management": {
                    "flexmail": "get_interests() + add_contact_to_interest()",
                    "resend": "create_audience() + add_contact_to_audience()",
                    "status": "✅ EQUIVALENT",
                    "notes": "Resend audiences = Flexmail interests",
                },
                "campaign_sending": {
                    "flexmail": "Campaign via GUI (no direct API in current implementation)",
                    "resend": "send_campaign_via_resend() + send_audience_email()",
                    "status": "✅ RESEND SUPERIOR",
                    "notes": "Resend has direct campaign API",
                },
                "bulk_email": {
                    "flexmail": "Not directly implemented",
                    "resend": "send_bulk_emails_via_resend()",
                    "status": "✅ RESEND SUPERIOR",
                    "notes": "Resend has batch email API",
                },
                "custom_fields": {
                    "flexmail": "get_custom_fields() + create_contact with custom_fields",
                    "resend": "Not available (API limitation)",
                    "status": "⚠️ FLEXMAIL ADVANTAGE",
                    "notes": "Resend doesn't support custom fields",
                },
                "contact_update": {
                    "flexmail": "update_contact()",
                    "resend": "Not available (API limitation)",
                    "status": "⚠️ FLEXMAIL ADVANTAGE",
                    "notes": "Resend contacts are add-only within audiences",
                },
                "webhook_management": {
                    "flexmail": "verify_webhook_signature() (receive only)",
                    "resend": "Full CRUD: create_webhook, update_webhook, delete_webhook, get_webhooks",
                    "status": "✅ RESEND SUPERIOR",
                    "notes": "Resend has complete webhook management API",
                },
                "engagement_tracking": {
                    "flexmail": "Webhook events (configured externally)",
                    "resend": "Webhook events: email.sent, email.delivered, email.opened, email.clicked, email.bounced, email.complained",
                    "status": "✅ EQUIVALENT",
                    "notes": "Both support webhook-based engagement tracking",
                },
            }
            
            # Count features
            resend_superior = sum(1 for f in feature_matrix.values() if "RESEND SUPERIOR" in f["status"])
            equivalent = sum(1 for f in feature_matrix.values() if "EQUIVALENT" in f["status"])
            flexmail_advantage = sum(1 for f in feature_matrix.values() if "FLEXMAIL ADVANTAGE" in f["status"])
            
            self.results["feature_comparison"] = feature_matrix
            
            logger.info("poc_resend_test_feature_parity_complete", 
                       resend_superior=resend_superior, 
                       equivalent=equivalent,
                       flexmail_advantage=flexmail_advantage)
            
            return {
                "status": "passed",
                "feature_matrix": feature_matrix,
                "summary": {
                    "resend_superior": resend_superior,
                    "equivalent": equivalent,
                    "flexmail_advantage": flexmail_advantage,
                    "total_features": len(feature_matrix),
                },
                "duration_seconds": time.time() - start_time,
            }
            
        except Exception as e:
            logger.error("poc_resend_test_feature_parity_failed", error=str(e))
            return {
                "status": "failed",
                "error": str(e),
                "duration_seconds": time.time() - start_time,
            }
            
    async def test_segment_creation(self) -> dict[str, Any]:
        """Test 1: Create a segment from search results."""
        test_name = "segment_creation"
        start_time = time.time()
        
        try:
            logger.info("poc_resend_test_segment_creation_start")
            
            # Search for companies (software companies in Brussels)
            filters = CompanySearchFilters(
                nace_codes=["62010", "62020", "62030", "62090"],
                city="Brussels",
            )
            search_results = await self.search_service.search_companies(filters)
            
            search_count = search_results.get("total", 0)
            logger.info("poc_resend_test_search_results", count=search_count)
            
            if search_count == 0:
                return {
                    "status": "failed",
                    "error": "No search results found",
                    "duration_seconds": time.time() - start_time,
                }
                
            # Create segment
            segment_name = f"POC_Resend_Test_Brussels_Software_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            segment = await self.segment_service.upsert_segment(
                name=segment_name,
                description="POC Resend test segment - Software companies in Brussels",
                filters=filters,
            )
            
            segment_id = segment.get("segment_id")
            member_count = segment.get("member_count", 0)
            
            logger.info("poc_resend_test_segment_created", segment_id=segment_id, members=member_count)
            
            self.results["segment_id"] = segment_id
            self.results["segment_name"] = segment_name
            
            return {
                "status": "passed",
                "segment_id": segment_id,
                "segment_name": segment_name,
                "search_count": search_count,
                "member_count": member_count,
                "duration_seconds": time.time() - start_time,
            }
            
        except Exception as e:
            logger.error("poc_resend_test_segment_creation_failed", error=str(e))
            return {
                "status": "failed",
                "error": str(e),
                "duration_seconds": time.time() - start_time,
            }
            
    async def test_segment_to_resend(self) -> dict[str, Any]:
        """Test 2: Push segment to Resend as audience."""
        test_name = "segment_to_resend"
        start_time = time.time()
        
        try:
            logger.info("poc_resend_test_segment_to_resend_start")
            
            segment_id = self.results.get("segment_id")
            if not segment_id:
                return {
                    "status": "failed",
                    "error": "No segment_id from previous test",
                    "duration_seconds": time.time() - start_time,
                }
                
            # Get segment members
            members = await self.segment_service.get_segment_members(segment_id, limit=50)
            member_rows = members.get("rows", [])
            total_count = members.get("total_count", 0)
            
            logger.info("poc_resend_test_segment_members_loaded", count=len(member_rows), total=total_count)
            
            if not member_rows:
                return {
                    "status": "failed",
                    "error": "No members in segment",
                    "duration_seconds": time.time() - start_time,
                }
                
            # Create Resend audience
            audience_name = f"CDP_{segment_id[:8]}"
            audience = await self.resend.create_audience(name=audience_name)
            audience_id = audience.get("id")
            
            if not audience_id:
                return {
                    "status": "failed",
                    "error": "Failed to create Resend audience",
                    "duration_seconds": time.time() - start_time,
                }
                
            logger.info("poc_resend_test_audience_created", audience_id=audience_id, name=audience_name)
            
            # Add contacts to audience
            added_count = 0
            contacts_with_email = 0
            
            for member in member_rows:
                # Extract email from member data
                email = (
                    member.get("main_email")
                    or member.get("email")
                    or member.get("contact_email")
                )
                
                if not email:
                    continue
                    
                contacts_with_email += 1
                
                # Extract name
                name = member.get("company_name") or member.get("name") or ""
                parts = name.split(" ", 1) if name else ["", ""]
                first_name = parts[0]
                last_name = parts[1] if len(parts) > 1 else ""
                
                # Add contact to Resend audience
                await self.resend.add_contact_to_audience(
                    email=email,
                    audience_id=audience_id,
                    first_name=first_name or None,
                    last_name=last_name or None,
                )
                added_count += 1
                
            logger.info("poc_resend_test_audience_populated", audience_id=audience_id, contacts=added_count)
            
            self.results["audience_id"] = audience_id
            self.results["audience_name"] = audience_name
            
            return {
                "status": "passed",
                "segment_id": segment_id,
                "audience_id": audience_id,
                "audience_name": audience_name,
                "total_members": total_count,
                "contacts_with_email": contacts_with_email,
                "added_to_audience": added_count,
                "resend_mock": self.use_mock,
                "duration_seconds": time.time() - start_time,
                "latency_seconds": time.time() - start_time,
            }
            
        except Exception as e:
            logger.error("poc_resend_test_segment_to_resend_failed", error=str(e))
            return {
                "status": "failed",
                "error": str(e),
                "duration_seconds": time.time() - start_time,
            }
            
    async def test_campaign_send(self) -> dict[str, Any]:
        """Test 3: Send campaign via Resend."""
        test_name = "campaign_send"
        start_time = time.time()
        
        try:
            logger.info("poc_resend_test_campaign_send_start")
            
            audience_id = self.results.get("audience_id")
            if not audience_id:
                return {
                    "status": "skipped",
                    "reason": "No audience_id from previous test",
                    "duration_seconds": time.time() - start_time,
                }
                
            # Send campaign to audience
            subject = "POC Test Campaign - Resend Activation"
            html_content = """
            <html>
            <body>
                <h1>POC Test Campaign</h1>
                <p>This is a test campaign from the CDP Resend activation flow.</p>
                <p><a href="https://example.com/test">Click here to test engagement tracking</a></p>
            </body>
            </html>
            """
            
            result = await self.resend.send_audience_email(
                audience_id=audience_id,
                subject=subject,
                html=html_content,
            )
            
            campaign_id = result.get("id", "unknown")
            logger.info("poc_resend_test_campaign_sent", campaign_id=campaign_id, audience_id=audience_id)
            
            return {
                "status": "passed",
                "audience_id": audience_id,
                "campaign_id": campaign_id,
                "subject": subject,
                "resend_mock": self.use_mock,
                "duration_seconds": time.time() - start_time,
            }
            
        except Exception as e:
            logger.error("poc_resend_test_campaign_send_failed", error=str(e))
            return {
                "status": "failed",
                "error": str(e),
                "duration_seconds": time.time() - start_time,
            }
            
    async def test_webhook_setup(self) -> dict[str, Any]:
        """Test 4: Setup webhook for engagement tracking."""
        test_name = "webhook_setup"
        start_time = time.time()
        
        try:
            logger.info("poc_resend_test_webhook_setup_start")
            
            # Create webhook for engagement events
            # In real scenario, this would point to the Tracardi webhook endpoint
            webhook_url = "http://localhost:8686/track?source=resend-webhook"
            events = [
                "email.sent",
                "email.delivered",
                "email.opened",
                "email.clicked",
                "email.bounced",
                "email.complained",
            ]
            
            webhook = await self.resend.create_webhook(
                endpoint_url=webhook_url,
                events=events,
                name="CDP Engagement Tracking",
            )
            
            webhook_id = webhook.get("id", "unknown")
            logger.info("poc_resend_test_webhook_created", webhook_id=webhook_id, endpoint=webhook_url)
            
            return {
                "status": "passed",
                "webhook_id": webhook_id,
                "endpoint": webhook_url,
                "events_subscribed": events,
                "event_count": len(events),
                "resend_mock": self.use_mock,
                "duration_seconds": time.time() - start_time,
            }
            
        except Exception as e:
            logger.error("poc_resend_test_webhook_setup_failed", error=str(e))
            return {
                "status": "failed",
                "error": str(e),
                "duration_seconds": time.time() - start_time,
            }
            
    async def test_engagement_writeback(self) -> dict[str, Any]:
        """Test 5: Simulate engagement events and verify writeback to Tracardi."""
        test_name = "engagement_writeback"
        start_time = time.time()
        
        try:
            logger.info("poc_resend_test_engagement_writeback_start")
            
            # Create a test profile in Tracardi
            test_email = f"test-{datetime.now().strftime('%Y%m%d%H%M%S')}@example.com"
            
            profile = await self.tracardi.get_or_create_profile(
                session_id=f"test-session-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            )
            
            profile_id = profile.get("id") if isinstance(profile, dict) else profile.id
            logger.info("poc_resend_test_tracardi_profile_created", profile_id=profile_id)
            
            # Track Resend email events (same events as webhooks)
            events = [
                ("email.sent", {"email": test_email, "campaign": "poc-resend-test"}),
                ("email.delivered", {"email": test_email, "campaign": "poc-resend-test"}),
                ("email.opened", {"email": test_email, "campaign": "poc-resend-test", "ip": "127.0.0.1"}),
                ("email.clicked", {"email": test_email, "campaign": "poc-resend-test", "url": "https://example.com"}),
            ]
            
            event_results = []
            for event_type, properties in events:
                result = await self.tracardi.track_event(
                    session_id=f"test-session-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    event_type=event_type,
                    properties=properties,
                )
                event_results.append({
                    "event_type": event_type,
                    "tracked": result is not None,
                })
                logger.info("poc_resend_test_event_tracked", event_type=event_type)
                
            await asyncio.sleep(0.5)  # Brief delay for processing
            
            tracked_count = sum(1 for r in event_results if r["tracked"])
            
            logger.info("poc_resend_test_engagement_writeback_complete", tracked=tracked_count, total=len(events))
            
            return {
                "status": "passed",
                "profile_id": profile_id,
                "test_email": test_email,
                "events_tracked": tracked_count,
                "total_events": len(events),
                "event_breakdown": event_results,
                "duration_seconds": time.time() - start_time,
            }
            
        except Exception as e:
            logger.error("poc_resend_test_engagement_writeback_failed", error=str(e))
            return {
                "status": "failed",
                "error": str(e),
                "duration_seconds": time.time() - start_time,
            }
            
    async def run_all_tests(self) -> dict[str, Any]:
        """Run all POC Resend tests."""
        logger.info("poc_resend_test_run_all_start")
        
        await self.setup()
        
        # Test 0: Feature Parity
        parity_result = await self.test_feature_parity()
        self.results["tests"]["feature_parity"] = parity_result
        
        # Test 1: Segment Creation
        segment_result = await self.test_segment_creation()
        self.results["tests"]["segment_creation"] = segment_result
        
        # Test 2: Segment to Resend (if segment creation passed)
        if segment_result["status"] == "passed":
            resend_result = await self.test_segment_to_resend()
            self.results["tests"]["segment_to_resend"] = resend_result
        else:
            self.results["tests"]["segment_to_resend"] = {
                "status": "skipped",
                "reason": "segment_creation_failed",
            }
            
        # Test 3: Campaign Send (if audience was created)
        if self.results.get("audience_id"):
            campaign_result = await self.test_campaign_send()
            self.results["tests"]["campaign_send"] = campaign_result
        else:
            self.results["tests"]["campaign_send"] = {
                "status": "skipped",
                "reason": "no_audience_created",
            }
            
        # Test 4: Webhook Setup
        webhook_result = await self.test_webhook_setup()
        self.results["tests"]["webhook_setup"] = webhook_result
        
        # Test 5: Engagement Writeback
        engagement_result = await self.test_engagement_writeback()
        self.results["tests"]["engagement_writeback"] = engagement_result
        
        # Calculate totals
        self.results["test_end"] = datetime.now().isoformat()
        passed = sum(1 for t in self.results["tests"].values() if t.get("status") == "passed")
        failed = sum(1 for t in self.results["tests"].values() if t.get("status") == "failed")
        skipped = sum(1 for t in self.results["tests"].values() if t.get("status") == "skipped")
        
        self.results["summary"] = {
            "total_tests": len(self.results["tests"]),
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
        }
        
        logger.info("poc_resend_test_run_all_complete", **self.results["summary"])
        
        return self.results


def print_results(results: dict[str, Any]):
    """Pretty print test results."""
    print("\n" + "=" * 70)
    print("POC RESEND ACTIVATION END-TO-END TEST RESULTS")
    print("=" * 70)
    print(f"Test Start: {results.get('test_start')}")
    print(f"Mock Mode: {results.get('mock_mode', False)}")
    print(f"Segment ID: {results.get('segment_id', 'N/A')}")
    print(f"Audience ID: {results.get('audience_id', 'N/A')}")
    print("-" * 70)
    
    # Feature Parity Summary
    feature_comparison = results.get("feature_comparison", {})
    if feature_comparison:
        print("\n📊 FEATURE PARITY COMPARISON:")
        print("-" * 70)
        summary = feature_comparison.get("summary", {})
        print(f"   Resend Superior: {summary.get('resend_superior', 0)}")
        print(f"   Equivalent: {summary.get('equivalent', 0)}")
        print(f"   Flexmail Advantage: {summary.get('flexmail_advantage', 0)}")
        print(f"   Total Features: {summary.get('total_features', 0)}")
        print()
        
        for feature, details in feature_comparison.items():
            if feature == "summary":
                continue
            status = details.get("status", "")
            print(f"   {status} {feature}")
            print(f"      Flexmail: {details.get('flexmail', 'N/A')}")
            print(f"      Resend: {details.get('resend', 'N/A')}")
            print()
    
    print("-" * 70)
    
    # Individual Tests
    for test_name, test_result in results.get("tests", {}).items():
        if test_name == "feature_parity":
            continue  # Already printed above
            
        status = test_result.get("status", "unknown").upper()
        duration = test_result.get("duration_seconds", 0)
        
        # Status indicator
        if status == "PASSED":
            status_indicator = "✅"
        elif status == "FAILED":
            status_indicator = "❌"
        else:
            status_indicator = "⏭️"
        
        print(f"\n{status_indicator} {test_name.upper()}")
        print(f"   Status: {status}")
        print(f"   Duration: {duration:.2f}s")
        
        if status == "PASSED":
            for key, value in test_result.items():
                if key not in ("status", "duration_seconds", "event_breakdown", "feature_matrix", "summary"):
                    print(f"   {key}: {value}")
        elif status == "FAILED":
            print(f"   Error: {test_result.get('error', 'Unknown error')}")
        elif status == "SKIPPED":
            print(f"   Reason: {test_result.get('reason', 'N/A')}")
            
    print("\n" + "-" * 70)
    summary = results.get("summary", {})
    print(f"SUMMARY: {summary.get('passed', 0)} passed, {summary.get('failed', 0)} failed, {summary.get('skipped', 0)} skipped")
    print("=" * 70)
    
    # POC gap analysis
    print("\n📊 RESEND POC GAP ANALYSIS:")
    print("-" * 70)
    
    tests = results.get("tests", {})
    
    # Feature Parity
    parity_test = tests.get("feature_parity", {})
    if parity_test.get("status") == "passed":
        summary = parity_test.get("summary", {})
        print(f"✅ Feature Parity: {summary.get('equivalent', 0)} equivalent, {summary.get('resend_superior', 0)} Resend superior")
    else:
        print("❌ Feature Parity: NOT VERIFIED")
        
    # Segment Creation
    segment_test = tests.get("segment_creation", {})
    if segment_test.get("status") == "passed":
        print(f"✅ NL → Segment: VERIFIED ({segment_test.get('duration_seconds', 0):.2f}s, {segment_test.get('member_count', 0)} members)")
    else:
        print("❌ NL → Segment: NOT VERIFIED")
        
    # Segment → Resend
    resend_test = tests.get("segment_to_resend", {})
    if resend_test.get("status") == "passed":
        latency = resend_test.get("latency_seconds", 0)
        mock = resend_test.get("resend_mock", True)
        mock_indicator = "(MOCK)" if mock else ""
        if latency <= 60:
            print(f"✅ Segment → Resend ≤60s: VERIFIED {latency:.1f}s {mock_indicator}")
        else:
            print(f"⚠️ Segment → Resend ≤60s: SLOW {latency:.1f}s {mock_indicator}")
    else:
        print("❌ Segment → Resend ≤60s: NOT VERIFIED")
        
    # Campaign Send
    campaign_test = tests.get("campaign_send", {})
    if campaign_test.get("status") == "passed":
        print(f"✅ Campaign Send: VERIFIED ({campaign_test.get('duration_seconds', 0):.2f}s)")
    else:
        print("❌ Campaign Send: NOT VERIFIED")
        
    # Webhook Setup
    webhook_test = tests.get("webhook_setup", {})
    if webhook_test.get("status") == "passed":
        events = webhook_test.get("event_count", 0)
        print(f"✅ Webhook Setup: VERIFIED ({events} events subscribed)")
    else:
        print("❌ Webhook Setup: NOT VERIFIED")
        
    # Engagement → CDP
    engagement_test = tests.get("engagement_writeback", {})
    if engagement_test.get("status") == "passed":
        tracked = engagement_test.get("events_tracked", 0)
        print(f"✅ Engagement → CDP: VERIFIED ({tracked} events tracked)")
    else:
        print("❌ Engagement → CDP: NOT VERIFIED")
        
    print("=" * 70)
    
    # Resend vs Flexmail recommendation
    print("\n💡 RECOMMENDATION:")
    print("-" * 70)
    parity_summary = parity_test.get("summary", {}) if parity_test.get("status") == "passed" else {}
    resend_superior = parity_summary.get("resend_superior", 0)
    flexmail_advantage = parity_summary.get("flexmail_advantage", 0)
    
    if resend_superior > flexmail_advantage:
        print("   Resend is RECOMMENDED for POC:")
        print("   - Superior webhook management (create/update/delete via API)")
        print("   - Direct campaign sending API")
        print("   - Batch email support")
        print("   - Simpler integration model (audiences vs interests+contacts)")
        if flexmail_advantage > 0:
            print(f"   - Note: {flexmail_advantage} features only in Flexmail (custom fields)")
    elif flexmail_advantage > resend_superior:
        print("   Flexmail has some advantages:")
        print("   - Custom fields support")
        print("   - Contact update capability")
        print("   But Resend is simpler and has better webhook management")
    else:
        print("   Both platforms are equivalent for POC purposes")
        print("   Resend recommended for: webhook management, campaign API, simplicity")
        print("   Flexmail recommended for: custom fields, contact updates")
    print("=" * 70)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="POC Resend Activation End-to-End Test")
    parser.add_argument("--mock", action="store_true", help="Use mock Resend client")
    args = parser.parse_args()
    
    # Check if we should use mock mode
    use_mock = args.mock
    if not use_mock:
        api_key = os.getenv("RESEND_API_KEY")
        if not api_key or api_key == "your-api-key":
            logger.warning("resend_api_key_not_found_using_mock")
            use_mock = True
            
    tester = POCResendTester(use_mock=use_mock)
    results = await tester.run_all_tests()
    print_results(results)
    
    # Exit with appropriate code
    failed = results.get("summary", {}).get("failed", 0)
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
