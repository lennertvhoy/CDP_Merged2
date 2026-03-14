#!/usr/bin/env python3
"""
KBO Data Enrichment Script

Enriches cleaned KBO data with additional information:
1. Geocoding (lat/long) via Nominatim
2. AI-generated company descriptions via Azure OpenAI
3. Website discovery via pattern matching
4. Contact validation

Usage:
    python enrich_kbo.py --input-dir ./data/cleaned --output-dir ./data/enriched
"""

import argparse
import csv
import json
import logging
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class EnrichmentResult:
    """Result of enrichment operations."""
    entity_number: str
    success: bool
    field: str
    value: Any
    source: str
    timestamp: str
    error: Optional[str] = None


class GeocodingEnricher:
    """Geocode addresses using Nominatim (OpenStreetMap)."""
    
    API_URL = "https://nominatim.openstreetmap.org/search"
    
    def __init__(self, cache_file: Optional[str] = None):
        self.cache = {}
        self.cache_file = cache_file
        self.requests_made = 0
        
        if cache_file and Path(cache_file).exists():
            self._load_cache()
    
    def _load_cache(self):
        """Load geocoding cache."""
        try:
            with open(self.cache_file, 'r') as f:
                self.cache = json.load(f)
            logger.info(f"Loaded {len(self.cache)} cached geocoding results")
        except Exception as e:
            logger.warning(f"Could not load cache: {e}")
    
    def _save_cache(self):
        """Save geocoding cache."""
        if self.cache_file:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f)
    
    def geocode(self, street: str, house_number: str, postal_code: str, city: str, country: str = "Belgium") -> Optional[Dict]:
        """
        Geocode an address using Nominatim.
        Returns dict with lat, lon, display_name, or None if not found.
        """
        # Build address query
        address_parts = [street, house_number, postal_code, city, country]
        address = ", ".join(filter(None, address_parts))
        
        # Check cache
        cache_key = address.lower().strip()
        if cache_key in self.cache:
            logger.debug(f"Cache hit for: {address}")
            return self.cache[cache_key]
        
        try:
            import requests
            
            params = {
                'q': address,
                'format': 'json',
                'limit': 1,
                'countrycodes': 'be',
                'addressdetails': 1,
            }
            
            headers = {
                'User-Agent': 'KBO-Enricher/1.0 (contact@example.com)'
            }
            
            logger.debug(f"Geocoding: {address}")
            response = requests.get(self.API_URL, params=params, headers=headers, timeout=10)
            self.requests_made += 1
            
            # Respect rate limit (1 request per second)
            time.sleep(1)
            
            if response.status_code == 200:
                data = response.json()
                if data:
                    result = data[0]
                    geocoded = {
                        'latitude': float(result['lat']),
                        'longitude': float(result['lon']),
                        'display_name': result['display_name'],
                        'osm_type': result.get('osm_type'),
                        'osm_id': result.get('osm_id'),
                        'category': result.get('category'),
                        'type': result.get('type'),
                        'importance': result.get('importance'),
                        'boundingbox': result.get('boundingbox'),
                    }
                    
                    # Cache result
                    self.cache[cache_key] = geocoded
                    if self.requests_made % 10 == 0:
                        self._save_cache()
                    
                    return geocoded
            
            logger.warning(f"Geocoding failed for: {address} (status: {response.status_code})")
            
        except Exception as e:
            logger.error(f"Geocoding error for {address}: {e}")
        
        return None
    
    def enrich_address(self, address_row: Dict) -> Dict:
        """Enrich an address row with geocoding."""
        result = address_row.copy()
        
        geocoded = self.geocode(
            street=address_row.get('StreetNL', ''),
            house_number=address_row.get('HouseNumber', ''),
            postal_code=address_row.get('Zipcode', ''),
            city=address_row.get('MunicipalityNL', ''),
        )
        
        if geocoded:
            result['geo_latitude'] = geocoded['latitude']
            result['geo_longitude'] = geocoded['longitude']
            result['geo_display_name'] = geocoded['display_name']
            result['geo_type'] = geocoded['type']
            result['geo_importance'] = geocoded['importance']
            result['geo_enriched'] = True
            result['geo_enriched_at'] = datetime.now().isoformat()
        else:
            result['geo_enriched'] = False
        
        return result
    
    def close(self):
        """Save cache on shutdown."""
        self._save_cache()


class AzureOpenAIEnricher:
    """Generate company descriptions using Azure OpenAI."""
    
    def __init__(self, endpoint: Optional[str] = None, api_key: Optional[str] = None, deployment: str = "gpt-5.4"):
        self.endpoint = endpoint
        self.api_key = api_key
        self.deployment = deployment
        self.requests_made = 0
        
        # Try to load from environment if not provided
        if not self.endpoint or not self.api_key:
            self._load_from_env()
    
    def _load_from_env(self):
        """Load Azure OpenAI credentials from environment."""
        import os
        self.endpoint = self.endpoint or os.getenv('AZURE_OPENAI_ENDPOINT')
        self.api_key = self.api_key or os.getenv('AZURE_OPENAI_API_KEY')
        self.deployment = self.deployment or os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-5.4')
    
    def _get_nace_description(self, nace_codes: List[str]) -> str:
        """Get human-readable description for NACE codes."""
        # Simplified NACE descriptions (expand as needed)
        nace_map = {
            '01110': "Growing of cereals",
            '25110': "Manufacture of metal structures",
            '25990': "Manufacture of other fabricated metal products",
            '47110': "Retail sale in non-specialized stores with food",
            '47190': "Other retail sale in non-specialized stores",
            '49410': "Freight transport by road",
            '52290': "Other transportation support activities",
            '62010': "Computer programming activities",
            '63120': "Web portals",
            '63110': "Data processing, hosting and related activities",
            '70220': "Business and other management consultancy activities",
        }
        
        descriptions = []
        for code in nace_codes:
            desc = nace_map.get(code, f"Activity code {code}")
            descriptions.append(desc)
        
        return "; ".join(descriptions) if descriptions else "General business activities"
    
    def generate_description(self, company_name: str, legal_form: str, nace_codes: List[str]) -> Optional[str]:
        """Generate AI company description."""
        if not self.endpoint or not self.api_key:
            logger.warning("Azure OpenAI not configured, skipping description generation")
            return None
        
        try:
            import requests
            
            nace_description = self._get_nace_description(nace_codes)
            
            prompt = f"""Generate a concise company description (50-80 words) for a B2B directory.

Company: {company_name}
Legal Form: {legal_form}
Activities: {nace_description}

Requirements:
- Professional and informative tone
- Suitable for business directory
- Mention key activities
- Do not use marketing language
- Plain text, no markdown

Description:"""
            
            headers = {
                'Content-Type': 'application/json',
                'api-key': self.api_key,
            }
            
            payload = {
                'messages': [
                    {'role': 'system', 'content': 'You are a helpful assistant that generates concise, professional company descriptions.'},
                    {'role': 'user', 'content': prompt}
                ],
                'max_tokens': 150,
                'temperature': 0.3,
            }
            
            url = f"{self.endpoint}/openai/deployments/{self.deployment}/chat/completions?api-version=2024-02-01"
            
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            self.requests_made += 1
            
            if response.status_code == 200:
                data = response.json()
                description = data['choices'][0]['message']['content'].strip()
                return description
            else:
                logger.error(f"Azure OpenAI error: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Error generating description: {e}")
        
        return None
    
    def enrich_enterprise(self, enterprise: Dict, nace_codes: List[str]) -> Dict:
        """Enrich enterprise with AI-generated description."""
        result = enterprise.copy()
        
        description = self.generate_description(
            company_name=enterprise.get('Denomination', ''),
            legal_form=enterprise.get('JuridicalForm', ''),
            nace_codes=nace_codes
        )
        
        if description:
            result['ai_description'] = description
            result['ai_description_generated_at'] = datetime.now().isoformat()
            result['ai_model'] = self.deployment
        
        return result


class WebsiteDiscoveryEnricher:
    """Discover company websites via pattern matching and validation."""
    
    # Common email domains that aren't company websites
    GENERIC_DOMAINS = {
        'gmail.com', 'hotmail.com', 'outlook.com', 'yahoo.com',
        'live.com', 'icloud.com', 'protonmail.com', 'aol.com',
        'skynet.be', 'telenet.be', 'proximus.be', 'scarlet.be'
    }
    
    # Common TLDs to try
    TLDS = ['.be', '.com', '.eu', '.net', '.org']
    
    def __init__(self):
        self.cache = {}
        self.checked = 0
        self.found = 0
    
    def _extract_domain_from_email(self, email: str) -> Optional[str]:
        """Extract domain from email address."""
        if not email or '@' not in email:
            return None
        
        domain = email.split('@')[1].lower()
        
        if domain in self.GENERIC_DOMAINS:
            return None
        
        return domain
    
    def _generate_candidates(self, company_name: str) -> List[str]:
        """Generate website candidates from company name."""
        # Clean company name
        clean = company_name.lower()
        
        # Remove legal forms
        legal_forms = ['bvba', 'nv', 'sa', 'sprl', 'comm.v', 'vzw', 'asbl']
        for form in legal_forms:
            clean = clean.replace(form, '').strip()
        
        # Replace spaces and special chars
        clean = re.sub(r'[^\w\s]', '', clean)
        clean = clean.replace(' ', '').replace('-', '')
        
        candidates = []
        for tld in self.TLDS:
            candidates.append(f"{clean}{tld}")
        
        return candidates
    
    def _check_website(self, domain: str, protocol: str = 'https') -> Optional[Dict]:
        """Check if website exists."""
        import requests
        
        try:
            import dns.resolver
            # First check DNS
            try:
                dns.resolver.resolve(domain, 'A')
            except:
                return None
            
            # Then check HTTP
            url = f"{protocol}://{domain}"
            response = requests.head(url, timeout=5, allow_redirects=True)
            
            if response.status_code < 400:
                return {
                    'url': response.url,
                    'domain': domain,
                    'status_code': response.status_code,
                    'protocol': protocol,
                }
                
        except Exception as e:
            logger.debug(f"Website check failed for {domain}: {e}")
        
        return None
    
    def discover_website(self, company_name: str, email: Optional[str] = None) -> Optional[Dict]:
        """Discover website for company."""
        cache_key = f"{company_name}_{email}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        self.checked += 1
        
        # Try email domain first
        if email:
            domain = self._extract_domain_from_email(email)
            if domain:
                for protocol in ['https', 'http']:
                    result = self._check_website(domain, protocol)
                    if result:
                        self.found += 1
                        self.cache[cache_key] = result
                        return result
        
        # Try generated candidates
        candidates = self._generate_candidates(company_name)
        for candidate in candidates:
            for protocol in ['https', 'http']:
                result = self._check_website(candidate, protocol)
                if result:
                    self.found += 1
                    self.cache[cache_key] = result
                    return result
        
        self.cache[cache_key] = None
        return None
    
    def enrich_enterprise(self, enterprise: Dict, email: Optional[str] = None) -> Dict:
        """Enrich enterprise with website discovery."""
        result = enterprise.copy()
        
        website = self.discover_website(
            company_name=enterprise.get('Denomination', ''),
            email=email
        )
        
        if website:
            result['website_url'] = website['url']
            result['website_domain'] = website['domain']
            result['website_verified'] = True
            result['website_discovered_at'] = datetime.now().isoformat()
        else:
            result['website_verified'] = False
        
        return result


class KBOEnricher:
    """Main enrichment pipeline for KBO data."""
    
    def __init__(self, 
                 azure_endpoint: Optional[str] = None,
                 azure_key: Optional[str] = None,
                 geocoding_cache: Optional[str] = None):
        self.geocoder = GeocodingEnricher(cache_file=geocoding_cache)
        self.ai_enricher = AzureOpenAIEnricher(endpoint=azure_endpoint, api_key=azure_key)
        self.website_enricher = WebsiteDiscoveryEnricher()
        
        self.stats = {
            'addresses_geocoded': 0,
            'addresses_failed': 0,
            'descriptions_generated': 0,
            'descriptions_failed': 0,
            'websites_found': 0,
            'websites_not_found': 0,
        }
    
    def load_data(self, input_dir: Path) -> Dict[str, List[Dict]]:
        """Load all cleaned CSV files."""
        data = {}
        
        files = ['enterprise_cleaned', 'address_cleaned', 'contact_cleaned', 
                 'activity_cleaned', 'denomination_cleaned']
        
        for base in files:
            filepath = input_dir / f"{base}.csv"
            if filepath.exists():
                with open(filepath, 'r', encoding='utf-8') as f:
                    data[base] = list(csv.DictReader(f))
                logger.info(f"Loaded {len(data[base])} records from {filepath.name}")
        
        return data
    
    def build_entity_lookup(self, data: Dict) -> Dict[str, Dict]:
        """Build lookup tables for relationships."""
        lookup = defaultdict(lambda: {
            'denomination': None,
            'addresses': [],
            'contacts': [],
            'activities': []
        })
        
        # Index denominations
        for row in data.get('denomination_cleaned', []):
            kbo = row.get('EntityNumber', '')
            lookup[kbo]['denomination'] = row
        
        # Index addresses
        for row in data.get('address_cleaned', []):
            kbo = row.get('EntityNumber', '')
            lookup[kbo]['addresses'].append(row)
        
        # Index contacts
        for row in data.get('contact_cleaned', []):
            kbo = row.get('EntityNumber', '')
            lookup[kbo]['contacts'].append(row)
        
        # Index activities
        for row in data.get('activity_cleaned', []):
            kbo = row.get('EntityNumber', '')
            lookup[kbo]['activities'].append(row)
        
        return lookup
    
    def enrich_all(self, input_dir: Path, output_dir: Path):
        """Run full enrichment pipeline."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load data
        data = self.load_data(input_dir)
        lookup = self.build_entity_lookup(data)
        
        # Enrich addresses with geocoding
        if 'address_cleaned' in data:
            logger.info("Enriching addresses with geocoding...")
            enriched_addresses = []
            for addr in data['address_cleaned']:
                enriched = self.geocoder.enrich_address(addr)
                enriched_addresses.append(enriched)
                if enriched.get('geo_enriched'):
                    self.stats['addresses_geocoded'] += 1
                else:
                    self.stats['addresses_failed'] += 1
            
            self._write_csv(output_dir / 'address_enriched.csv', enriched_addresses)
        
        # Enrich enterprises with AI descriptions and websites
        if 'enterprise_cleaned' in data:
            logger.info("Enriching enterprises with descriptions and websites...")
            enriched_enterprises = []
            
            for enterprise in data['enterprise_cleaned']:
                kbo = enterprise.get('EnterpriseNumber', '')
                entity_data = lookup[kbo]
                
                # Merge denomination
                if entity_data['denomination']:
                    enterprise = {**enterprise, **entity_data['denomination']}
                
                # Get NACE codes for description
                nace_codes = [a.get('NaceCode', '') for a in entity_data['activities']]
                
                # Generate AI description
                try:
                    enterprise = self.ai_enricher.enrich_enterprise(enterprise, nace_codes)
                    if 'ai_description' in enterprise:
                        self.stats['descriptions_generated'] += 1
                    else:
                        self.stats['descriptions_failed'] += 1
                except Exception as e:
                    logger.error(f"AI enrichment failed for {kbo}: {e}")
                    self.stats['descriptions_failed'] += 1
                
                # Discover website (use first email)
                email = None
                for contact in entity_data['contacts']:
                    if contact.get('ContactType') == 'EMAIL' and contact.get('IsValid') == 'True':
                        email = contact.get('Value')
                        break
                
                try:
                    enterprise = self.website_enricher.enrich_enterprise(enterprise, email)
                    if enterprise.get('website_verified'):
                        self.stats['websites_found'] += 1
                    else:
                        self.stats['websites_not_found'] += 1
                except Exception as e:
                    logger.error(f"Website discovery failed for {kbo}: {e}")
                    self.stats['websites_not_found'] += 1
                
                enriched_enterprises.append(enterprise)
            
            self._write_csv(output_dir / 'enterprise_enriched.csv', enriched_enterprises)
        
        # Copy other files as-is (already cleaned)
        for filename in ['contact_cleaned.csv', 'activity_cleaned.csv', 'denomination_cleaned.csv']:
            src = input_dir / filename
            if src.exists():
                dst = output_dir / filename.replace('_cleaned', '_enriched')
                import shutil
                shutil.copy(src, dst)
        
        # Print stats
        self._print_stats()
        
        # Cleanup
        self.geocoder.close()
    
    def _write_csv(self, filepath: Path, rows: List[Dict]):
        """Write CSV file."""
        if not rows:
            logger.warning(f"No rows to write to {filepath}")
            return
        
        with open(filepath, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
    
    def _print_stats(self):
        """Print enrichment statistics."""
        logger.info("=" * 50)
        logger.info("ENRICHMENT STATISTICS")
        logger.info("=" * 50)
        for key, value in self.stats.items():
            logger.info(f"  {key}: {value}")


def main():
    parser = argparse.ArgumentParser(description='Enrich KBO data')
    parser.add_argument('--input-dir', default='./data/cleaned', help='Input directory (cleaned data)')
    parser.add_argument('--output-dir', default='./data/enriched', help='Output directory')
    parser.add_argument('--azure-endpoint', help='Azure OpenAI endpoint')
    parser.add_argument('--azure-key', help='Azure OpenAI API key')
    parser.add_argument('--geocoding-cache', default='./data/geocoding_cache.json', help='Geocoding cache file')
    
    args = parser.parse_args()
    
    enricher = KBOEnricher(
        azure_endpoint=args.azure_endpoint,
        azure_key=args.azure_key,
        geocoding_cache=args.geocoding_cache
    )
    
    enricher.enrich_all(Path(args.input_dir), Path(args.output_dir))


if __name__ == '__main__':
    main()
