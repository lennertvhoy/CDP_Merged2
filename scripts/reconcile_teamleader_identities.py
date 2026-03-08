#!/usr/bin/env python3
"""Reconcile Teamleader companies with KBO records via VAT number matching."""

import asyncio
import asyncpg

from src.core.database_url import resolve_database_url


async def reconcile_identities():
    """Link Teamleader companies to KBO records based on VAT numbers."""
    database_url = resolve_database_url()

    pool = await asyncpg.create_pool(database_url, min_size=1, max_size=3)

    async with pool.acquire() as conn:
        # Find Teamleader companies with VAT numbers
        crm_records = await conn.fetch(
            """
            SELECT id, company_name, vat_number, city
            FROM crm_companies
            WHERE vat_number IS NOT NULL
            """
        )
        
        print(f"Found {len(crm_records)} CRM companies with VAT numbers")
        
        linked_count = 0
        
        for record in crm_records:
            crm_id = str(record['id'])
            company_name = record['company_name']
            vat_number = record['vat_number']
            city = record['city']
            
            # Extract KBO number from VAT (BE 0123.456.789 -> 0123456789)
            # Remove BE prefix and dots/spaces
            kbo_from_vat = vat_number.replace('BE', '').replace('.', '').replace(' ', '').strip()
            
            # Also try formatted versions
            kbo_formats = [
                kbo_from_vat,
                kbo_from_vat.lstrip('0'),  # Without leading zeros
            ]
            
            # Find matching KBO company
            kbo_match = await conn.fetchrow(
                """
                SELECT company_uid, kbo_number, kbo_company_name
                FROM unified_company_360
                WHERE kbo_number = $1 OR kbo_number = $2
                LIMIT 1
                """,
                kbo_formats[0],
                kbo_formats[1] if len(kbo_formats) > 1 else kbo_formats[0]
            )
            
            if kbo_match:
                # Create or update identity link
                await conn.execute(
                    """
                    INSERT INTO source_identity_links (
                        uid, subject_type, source_system, source_entity_type,
                        source_record_id, is_primary, valid_from
                    )
                    VALUES (
                        $1, 'organization', 'teamleader', 'company',
                        $2, true, NOW()
                    )
                    ON CONFLICT (source_system, source_entity_type, source_record_id) 
                    DO UPDATE SET
                        uid = EXCLUDED.uid,
                        updated_at = NOW()
                    """,
                    kbo_match['company_uid'],
                    crm_id
                )
                
                # Update the unified view to reflect the link
                await conn.execute(
                    """
                    UPDATE unified_company_360
                    SET 
                        tl_company_id = $1,
                        tl_company_name = $2,
                        tl_city = $3,
                        identity_link_status = CASE 
                            WHEN exact_customer_id IS NOT NULL THEN 'linked_both'
                            ELSE 'linked_teamleader'
                        END
                    WHERE company_uid = $4
                    """,
                    crm_id,
                    company_name,
                    city,
                    kbo_match['company_uid']
                )
                
                print(f"✅ Linked: {company_name} -> KBO {kbo_match['kbo_number']}")
                linked_count += 1
            else:
                print(f"❌ No KBO match for: {company_name} (VAT: {vat_number})")
        
        print(f"\n{'='*60}")
        print(f"Linked {linked_count} of {len(crm_records)} CRM companies to KBO")
        
        # Show current identity link status distribution
        stats = await conn.fetch(
            """
            SELECT identity_link_status, COUNT(*) as count
            FROM unified_company_360
            GROUP BY identity_link_status
            ORDER BY count DESC
            """
        )
        
        print(f"\nCurrent identity link status:")
        for row in stats:
            print(f"  {row['identity_link_status']}: {row['count']}")

    await pool.close()


if __name__ == "__main__":
    asyncio.run(reconcile_identities())
