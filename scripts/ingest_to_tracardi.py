#!/usr/bin/env python3
"""
KBO Data Ingestion Script for Tracardi

Ingests cleaned and enriched KBO data into Tracardi as profiles.

Usage:
    python ingest_to_tracardi.py --input-dir ./data/enriched --tracardi-api http://localhost:8686
"""

import argparse
import csv
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class TracardiProfile:
    """Represents a Tracardi profile for a KBO enterprise."""
    id: str  # KBO number
    name: str  # Company name
    type: str = "company"
    
    # Core fields
    kbo_number: str = ""
    status: str = ""
    legal_form: str = ""
    start_date: str = ""
    
    # Address fields
    street: str = ""
    house_number: str = ""
    postal_code: str = ""
    city: str = ""
    country: str = "Belgium"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    
    # Contact fields
    email: str = ""
    phone: str = ""
    website: str = ""
    
    # Business fields
    nace_codes: List[str] = None
    nace_sections: List[str] = None
    ai_description: str = ""
    
    # Metadata
    created_at: str = ""
    updated_at: str = ""
    source: str = "KBO Open Data"
    
    def __post_init__(self):
        if self.nace_codes is None:
            self.nace_codes = []
        if self.nace_sections is None:
            self.nace_sections = []
    
    def to_tracardi_dict(self) -> Dict[str, Any]:
        """Convert to Tracardi profile format."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "properties": {
                "kbo_number": self.kbo_number,
                "status": self.status,
                "legal_form": self.legal_form,
                "start_date": self.start_date,
                "address": {
                    "street": self.street,
                    "house_number": self.house_number,
                    "postal_code": self.postal_code,
                    "city": self.city,
                    "country": self.country,
                },
                "location": {
                    "lat": self.latitude,
                    "lon": self.longitude,
                } if self.latitude and self.longitude else None,
                "contact": {
                    "email": self.email,
                    "phone": self.phone,
                    "website": self.website,
                },
                "business": {
                    "nace_codes": self.nace_codes,
                    "nace_sections": list(set(self.nace_sections)),
                    "description": self.ai_description,
                },
            },
            "metadata": {
                "created_at": self.created_at or datetime.now().isoformat(),
                "updated_at": self.updated_at or datetime.now().isoformat(),
                "source": self.source,
            },
            "traits": {
                "company": True,
                "belgian_enterprise": True,
            }
        }


class TracardiIngester:
    """Ingest KBO data into Tracardi."""
    
    def __init__(self, api_url: str, api_token: Optional[str] = None):
        self.api_url = api_url.rstrip('/')
        self.api_token = api_token
        self.stats = {
            'profiles_created': 0,
            'profiles_updated': 0,
            'profiles_failed': 0,
            'total_processed': 0,
        }
    
    def load_data(self, input_dir: Path) -> Dict[str, List[Dict]]:
        """Load all enriched CSV files."""
        data = {}
        
        files = [
            ('enterprise', 'enterprise_enriched.csv'),
            ('address', 'address_enriched.csv'),
            ('contact', 'contact_enriched.csv'),
            ('activity', 'activity_enriched.csv'),
            ('denomination', 'denomination_enriched.csv'),
        ]
        
        for key, filename in files:
            filepath = input_dir / filename
            # Fall back to cleaned version if enriched doesn't exist
            if not filepath.exists():
                filepath = input_dir / filename.replace('_enriched', '_cleaned')
            
            if filepath.exists():
                with open(filepath, 'r', encoding='utf-8') as f:
                    data[key] = list(csv.DictReader(f))
                logger.info(f"Loaded {len(data[key])} records from {filepath.name}")
            else:
                data[key] = []
                logger.warning(f"File not found: {filepath}")
        
        return data
    
    def build_entity_lookup(self, data: Dict) -> Dict[str, Dict]:
        """Build lookup tables for relationships."""
        lookup = {}
        
        for row in data.get('enterprise', []):
            kbo = row.get('EnterpriseNumber', '') or row.get('EntityNumber', '')
            lookup[kbo] = {
                'enterprise': row,
                'addresses': [],
                'contacts': [],
                'activities': [],
                'denomination': None,
            }
        
        for row in data.get('address', []):
            kbo = row.get('EntityNumber', '')
            if kbo in lookup:
                lookup[kbo]['addresses'].append(row)
        
        for row in data.get('contact', []):
            kbo = row.get('EntityNumber', '')
            if kbo in lookup:
                lookup[kbo]['contacts'].append(row)
        
        for row in data.get('activity', []):
            kbo = row.get('EntityNumber', '')
            if kbo in lookup:
                lookup[kbo]['activities'].append(row)
        
        for row in data.get('denomination', []):
            kbo = row.get('EntityNumber', '')
            if kbo in lookup:
                lookup[kbo]['denomination'] = row
        
        return lookup
    
    def build_profile(self, kbo: str, entity_data: Dict) -> Optional[TracardiProfile]:
        """Build a TracardiProfile from entity data."""
        enterprise = entity_data['enterprise']
        denom = entity_data.get('denomination', {}) or {}
        addresses = entity_data.get('addresses', [])
        contacts = entity_data.get('contacts', [])
        activities = entity_data.get('activities', [])
        
        # Get primary address (first one)
        address = addresses[0] if addresses else {}
        
        # Get primary contact info
        email = ""
        phone = ""
        for contact in contacts:
            if contact.get('ContactType') == 'EMAIL':
                email = contact.get('Value', '')
            elif contact.get('ContactType') == 'TEL':
                phone = contact.get('Value', '')
        
        # Get NACE codes
        nace_codes = [a.get('NaceCode', '') for a in activities if a.get('NaceCode')]
        nace_sections = list(set([a.get('NaceSection', '') for a in activities if a.get('NaceSection')]))
        
        # Get company name
        name = denom.get('Denomination', '') if denom else f"Company {kbo}"
        
        # Get geolocation if available
        lat = address.get('geo_latitude')
        lon = address.get('geo_longitude')
        
        profile = TracardiProfile(
            id=kbo,
            name=name,
            kbo_number=kbo,
            status=enterprise.get('Status', ''),
            legal_form=enterprise.get('JuridicalForm', ''),
            start_date=enterprise.get('StartDate', ''),
            street=address.get('StreetNL', ''),
            house_number=address.get('HouseNumber', ''),
            postal_code=address.get('Zipcode', ''),
            city=address.get('MunicipalityNL', ''),
            country=address.get('CountryNL', 'Belgium'),
            latitude=float(lat) if lat else None,
            longitude=float(lon) if lon else None,
            email=email,
            phone=phone,
            website=enterprise.get('website_url', ''),
            nace_codes=nace_codes,
            nace_sections=nace_sections,
            ai_description=enterprise.get('ai_description', ''),
            created_at=datetime.now().isoformat(),
        )
        
        return profile
    
    def ingest_to_tracardi(self, profile: TracardiProfile) -> bool:
        """Send profile to Tracardi API."""
        try:
            import requests
            
            url = f"{self.api_url}/profile"
            headers = {
                'Content-Type': 'application/json',
            }
            if self.api_token:
                headers['Authorization'] = f"Bearer {self.api_token}"
            
            payload = profile.to_tracardi_dict()
            
            # For dry-run mode, just log
            if getattr(self, 'dry_run', False):
                logger.info(f"[DRY RUN] Would ingest: {profile.name} ({profile.kbo_number})")
                return True
            
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            
            if response.status_code in [200, 201]:
                logger.debug(f"Ingested profile: {profile.kbo_number}")
                return True
            else:
                logger.error(f"Failed to ingest {profile.kbo_number}: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error ingesting {profile.kbo_number}: {e}")
            return False
    
    def process_all(self, input_dir: Path, dry_run: bool = False):
        """Process all enriched data and ingest to Tracardi."""
        self.dry_run = dry_run
        
        # Load data
        data = self.load_data(input_dir)
        lookup = self.build_entity_lookup(data)
        
        logger.info(f"Processing {len(lookup)} enterprises...")
        
        # Process each enterprise
        for kbo, entity_data in lookup.items():
            self.stats['total_processed'] += 1
            
            try:
                profile = self.build_profile(kbo, entity_data)
                if profile:
                    success = self.ingest_to_tracardi(profile)
                    if success:
                        self.stats['profiles_created'] += 1
                    else:
                        self.stats['profiles_failed'] += 1
            except Exception as e:
                logger.error(f"Error processing {kbo}: {e}")
                self.stats['profiles_failed'] += 1
        
        # Print summary
        self._print_stats()
    
    def export_to_json(self, input_dir: Path, output_file: Path):
        """Export all profiles to JSON for manual import."""
        data = self.load_data(input_dir)
        lookup = self.build_entity_lookup(data)
        
        profiles = []
        for kbo, entity_data in lookup.items():
            profile = self.build_profile(kbo, entity_data)
            if profile:
                profiles.append(profile.to_tracardi_dict())
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(profiles, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Exported {len(profiles)} profiles to {output_file}")
    
    def _print_stats(self):
        """Print ingestion statistics."""
        logger.info("=" * 50)
        logger.info("INGESTION STATISTICS")
        logger.info("=" * 50)
        for key, value in self.stats.items():
            logger.info(f"  {key}: {value}")


def main():
    parser = argparse.ArgumentParser(description='Ingest KBO data to Tracardi')
    parser.add_argument('--input-dir', default='./data/enriched', help='Input directory (enriched data)')
    parser.add_argument('--tracardi-api', default='http://localhost:8686', help='Tracardi API URL')
    parser.add_argument('--api-token', help='Tracardi API token')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be ingested without sending')
    parser.add_argument('--export-json', help='Export to JSON file instead of ingesting')
    
    args = parser.parse_args()
    
    ingester = TracardiIngester(api_url=args.tracardi_api, api_token=args.api_token)
    
    if args.export_json:
        ingester.export_to_json(Path(args.input_dir), Path(args.export_json))
    else:
        ingester.process_all(Path(args.input_dir), dry_run=args.dry_run)


if __name__ == '__main__':
    main()
