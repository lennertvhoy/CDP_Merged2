#!/usr/bin/env python3
"""
KBO Matching Verification Script

Verifies the accuracy and coverage of KBO matching between source systems
(Teamleader, Exact) and the canonical KBO database.

Usage:
    # Run full verification
    uv run python scripts/verify_kbo_matching.py
    
    # Check specific source system
    uv run python scripts/verify_kbo_matching.py --source teamleader
    
    # Show sample matches and mismatches
    uv run python scripts/verify_kbo_matching.py --samples 10
    
    # Export detailed report
    uv run python scripts/verify_kbo_matching.py --export report.json

Environment:
    Requires DATABASE_URL pointing to PostgreSQL
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import asyncpg

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.core.logger import get_logger
from src.config import settings

logger = get_logger(__name__)


def get_database_url() -> str:
    """Get database URL from settings or environment."""
    url = settings.DATABASE_URL or os.getenv("DATABASE_URL")
    if not url:
        logger.error("DATABASE_URL not configured. Set it in .env or environment.")
        sys.exit(1)
    return url


DEFAULT_DATABASE_URL = get_database_url()


@dataclass
class MatchQualityMetrics:
    """Metrics for KBO matching quality."""
    source_system: str
    total_records: int = 0
    with_kbo_number: int = 0
    with_org_uid: int = 0
    unmatched: int = 0
    match_rate_pct: float = 0.0
    vat_match_count: int = 0
    name_match_count: int = 0
    fuzzy_match_count: int = 0
    potential_matches: int = 0  # Unmatched but with possible matches


@dataclass
class SampleMatch:
    """Sample match record for verification."""
    source_system: str
    source_record_id: str
    company_name: str
    vat_number: str | None
    matched_kbo: str | None
    matched_org_uid: str | None
    match_type: str  # 'vat', 'name', 'fuzzy', 'none'
    confidence: float


@dataclass
class VerificationReport:
    """Complete verification report."""
    verified_at: str
    database_url: str
    metrics: list[MatchQualityMetrics] = field(default_factory=list)
    sample_matches: list[SampleMatch] = field(default_factory=list)
    sample_unmatched: list[dict] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


class KBOVerification:
    """Verify KBO matching accuracy and coverage."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool: asyncpg.Pool | None = None

    async def initialize(self) -> None:
        """Initialize database connection."""
        self.pool = await asyncpg.create_pool(self.database_url, min_size=1, max_size=3)
        logger.info("verification_initialized")

    async def close(self) -> None:
        """Close database connection."""
        if self.pool:
            await self.pool.close()

    async def get_source_metrics(self, source_system: str) -> MatchQualityMetrics:
        """Get matching metrics for a source system."""
        table = "crm_companies" if source_system == "teamleader" else "exact_customers"
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                SELECT 
                    COUNT(*) as total_records,
                    COUNT(kbo_number) as with_kbo_number,
                    COUNT(organization_uid) as with_org_uid,
                    COUNT(*) FILTER (WHERE kbo_number IS NULL AND organization_uid IS NULL) as unmatched
                FROM {table}
                WHERE source_system = $1
                """,
                source_system
            )

            # Get match type breakdown
            match_breakdown = await conn.fetchrow(
                f"""
                SELECT 
                    COUNT(*) FILTER (WHERE vat_number IS NOT NULL AND kbo_number IS NOT NULL) as vat_matches,
                    COUNT(*) FILTER (WHERE vat_number IS NULL AND kbo_number IS NOT NULL) as name_matches
                FROM {table}
                WHERE source_system = $1 AND kbo_number IS NOT NULL
                """,
                source_system
            )

        total = row["total_records"]
        matched = row["with_kbo_number"]
        
        return MatchQualityMetrics(
            source_system=source_system,
            total_records=total,
            with_kbo_number=matched,
            with_org_uid=row["with_org_uid"],
            unmatched=row["unmatched"],
            match_rate_pct=round(100.0 * matched / total, 2) if total > 0 else 0.0,
            vat_match_count=match_breakdown["vat_matches"],
            name_match_count=match_breakdown["name_matches"]
        )

    async def get_sample_matches(
        self, 
        source_system: str, 
        sample_size: int = 5
    ) -> list[SampleMatch]:
        """Get sample successful matches."""
        table = "crm_companies" if source_system == "teamleader" else "exact_customers"
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT 
                    source_record_id,
                    company_name,
                    vat_number,
                    kbo_number,
                    organization_uid
                FROM {table}
                WHERE source_system = $1 
                AND kbo_number IS NOT NULL
                ORDER BY last_sync_at DESC
                LIMIT $2
                """,
                source_system,
                sample_size
            )

        samples = []
        for row in rows:
            match_type = 'vat' if row['vat_number'] else 'name'
            samples.append(SampleMatch(
                source_system=source_system,
                source_record_id=row['source_record_id'],
                company_name=row['company_name'],
                vat_number=row['vat_number'],
                matched_kbo=row['kbo_number'],
                matched_org_uid=row['organization_uid'],
                match_type=match_type,
                confidence=0.95 if match_type == 'vat' else 0.75
            ))
        
        return samples

    async def get_sample_unmatched(
        self, 
        source_system: str, 
        sample_size: int = 5
    ) -> list[dict]:
        """Get sample unmatched records with potential matches."""
        table = "crm_companies" if source_system == "teamleader" else "exact_customers"
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT 
                    source_record_id,
                    company_name,
                    vat_number,
                    city
                FROM {table}
                WHERE source_system = $1 
                AND kbo_number IS NULL
                ORDER BY last_sync_at DESC
                LIMIT $2
                """,
                source_system,
                sample_size
            )

        unmatched = []
        for row in rows:
            # Try to find potential matches
            potential = []
            if row['vat_number']:
                # VAT provided but no match - possible data quality issue
                match = await conn.fetchrow(
                    "SELECT kbo_number, company_name FROM companies WHERE vat_number = $1",
                    row['vat_number']
                )
                if match:
                    potential.append({
                        'match_type': 'vat_exact',
                        'kbo_number': match['kbo_number'],
                        'company_name': match['company_name']
                    })
            
            # Try name similarity match
            name_matches = await conn.fetch(
                """
                SELECT kbo_number, company_name, 
                       similarity(company_name, $1) as sim
                FROM companies 
                WHERE company_name % $1
                ORDER BY sim DESC
                LIMIT 3
                """,
                row['company_name']
            )
            for m in name_matches:
                potential.append({
                    'match_type': f"fuzzy_{m['sim']:.2f}",
                    'kbo_number': m['kbo_number'],
                    'company_name': m['company_name']
                })

            unmatched.append({
                'source_record_id': row['source_record_id'],
                'company_name': row['company_name'],
                'vat_number': row['vat_number'],
                'city': row['city'],
                'potential_matches': potential
            })
        
        return unmatched

    async def generate_recommendations(
        self, 
        metrics: list[MatchQualityMetrics]
    ) -> list[str]:
        """Generate recommendations based on metrics."""
        recommendations = []
        
        for m in metrics:
            if m.match_rate_pct < 50:
                recommendations.append(
                    f"{m.source_system}: Low match rate ({m.match_rate_pct}%). "
                    "Consider reviewing VAT number formatting or company name variations."
                )
            elif m.match_rate_pct < 80:
                recommendations.append(
                    f"{m.source_system}: Moderate match rate ({m.match_rate_pct}%). "
                    "Manual review recommended for unmatched records."
                )
            else:
                recommendations.append(
                    f"{m.source_system}: Good match rate ({m.match_rate_pct}%). "
                    f"VAT matches: {m.vat_match_count}, Name matches: {m.name_match_count}"
                )

            if m.unmatched > 0:
                recommendations.append(
                    f"{m.source_system}: {m.unmatched} records need manual linking or KBO lookup."
                )

        return recommendations

    async def verify_identity_links_table(self) -> dict:
        """Verify source_identity_links table population."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT 
                    COUNT(*) as total_links,
                    COUNT(DISTINCT source_system) as source_systems,
                    COUNT(*) FILTER (WHERE source_system = 'teamleader') as tl_links,
                    COUNT(*) FILTER (WHERE source_system = 'exact') as exact_links,
                    COUNT(*) FILTER (WHERE is_primary = true) as primary_links
                FROM source_identity_links
                """
            )
        
        return dict(row) if row else {}

    async def run_verification(
        self, 
        source: str | None = None,
        samples: int = 5
    ) -> VerificationReport:
        """Run complete verification."""
        await self.initialize()
        
        try:
            sources = [source] if source else ['teamleader', 'exact']
            metrics = []
            all_samples = []
            all_unmatched = []

            for src in sources:
                logger.info(f"verifying_source", source=src)
                
                # Get metrics
                m = await self.get_source_metrics(src)
                metrics.append(m)
                
                # Get samples
                if samples > 0:
                    matches = await self.get_sample_matches(src, samples)
                    all_samples.extend(matches)
                    
                    unmatched = await self.get_sample_unmatched(src, samples)
                    all_unmatched.extend(unmatched)

            # Generate recommendations
            recommendations = await self.generate_recommendations(metrics)
            
            # Check identity links table
            identity_links = await self.verify_identity_links_table()
            if identity_links.get('total_links', 0) == 0:
                recommendations.append(
                    "source_identity_links table is empty. Run sync scripts to populate."
                )

            return VerificationReport(
                verified_at=datetime.utcnow().isoformat(),
                database_url=self.database_url.split('@')[-1],
                metrics=metrics,
                sample_matches=all_samples,
                sample_unmatched=all_unmatched,
                recommendations=recommendations
            )
        finally:
            await self.close()


def print_report(report: VerificationReport) -> None:
    """Print formatted verification report."""
    print("=" * 70)
    print("KBO Matching Verification Report")
    print("=" * 70)
    print(f"Verified at: {report.verified_at}")
    print(f"Database: {report.database_url}")
    print()

    # Metrics
    print("-" * 70)
    print("MATCH QUALITY METRICS")
    print("-" * 70)
    
    for m in report.metrics:
        print(f"\n📊 {m.source_system.upper()}")
        print(f"   Total records:     {m.total_records}")
        print(f"   With KBO match:    {m.with_kbo_number} ({m.match_rate_pct}%)")
        print(f"   With org UID:      {m.with_org_uid}")
        print(f"   Unmatched:         {m.unmatched}")
        print(f"   VAT matches:       {m.vat_match_count}")
        print(f"   Name matches:      {m.name_match_count}")

    # Sample matches
    if report.sample_matches:
        print("\n" + "-" * 70)
        print("SAMPLE SUCCESSFUL MATCHES")
        print("-" * 70)
        
        for s in report.sample_matches[:5]:
            match_icon = "✓" if s.match_type != 'none' else "✗"
            print(f"\n{match_icon} {s.company_name[:50]}")
            print(f"   Source: {s.source_system} / {s.source_record_id}")
            print(f"   VAT: {s.vat_number or 'N/A'}")
            print(f"   Matched KBO: {s.matched_kbo}")
            print(f"   Match type: {s.match_type} (confidence: {s.confidence})")

    # Sample unmatched
    if report.sample_unmatched:
        print("\n" + "-" * 70)
        print("SAMPLE UNMATCHED RECORDS")
        print("-" * 70)
        
        for u in report.sample_unmatched[:3]:
            print(f"\n⚠ {u['company_name'][:50]}")
            print(f"   Source ID: {u['source_record_id']}")
            print(f"   VAT: {u['vat_number'] or 'N/A'}")
            print(f"   City: {u['city'] or 'N/A'}")
            if u['potential_matches']:
                print(f"   Potential matches: {len(u['potential_matches'])}")
                for p in u['potential_matches'][:2]:
                    print(f"      - {p['company_name'][:40]} ({p['match_type']})")

    # Recommendations
    print("\n" + "-" * 70)
    print("RECOMMENDATIONS")
    print("-" * 70)
    
    for r in report.recommendations:
        print(f"\n• {r}")

    print("\n" + "=" * 70)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Verify KBO matching accuracy and coverage"
    )
    parser.add_argument(
        "--source",
        type=str,
        choices=['teamleader', 'exact'],
        help="Verify specific source system only"
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=5,
        help="Number of sample records to show (default: 5)"
    )
    parser.add_argument(
        "--export",
        type=str,
        help="Export report to JSON file"
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default=DEFAULT_DATABASE_URL,
        help="PostgreSQL connection URL"
    )
    return parser.parse_args()


async def main() -> int:
    """Main entry point."""
    args = parse_args()

    print("=" * 70)
    print("KBO Matching Verification")
    print("=" * 70)
    print()

    verifier = KBOVerification(database_url=args.database_url)
    
    try:
        report = await verifier.run_verification(
            source=args.source,
            samples=args.samples
        )
        
        print_report(report)
        
        if args.export:
            export_data = {
                'verified_at': report.verified_at,
                'database_url': report.database_url,
                'metrics': [asdict(m) for m in report.metrics],
                'sample_matches': [asdict(s) for s in report.sample_matches],
                'sample_unmatched': report.sample_unmatched,
                'recommendations': report.recommendations
            }
            with open(args.export, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            print(f"\n📄 Report exported to: {args.export}")
        
        # Return error code if match rates are low
        low_match_rates = [
            m for m in report.metrics 
            if m.match_rate_pct < 50 and m.total_records > 0
        ]
        
        if low_match_rates:
            print(f"\n⚠️  Warning: {len(low_match_rates)} source(s) have low match rates (< 50%)")
            return 1
        
        return 0
        
    except Exception as e:
        logger.error("verification_failed", error=str(e))
        print(f"\n❌ Verification failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
