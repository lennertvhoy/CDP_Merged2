#!/usr/bin/env python3
"""
KBO Data Cleanup Script

Performs deduplication, validation, and normalization on KBO data
before ingestion into Tracardi.

Usage:
    python cleanup_kbo.py --input-dir ./data/kbo --output-dir ./data/cleaned
"""

import argparse
import csv
import re
import logging
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Set

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class KBOValidator:
    """Validation utilities for KBO data."""
    
    # Belgian postal code ranges by region
    POSTAL_CODE_RANGES = {
        'Brussels': range(1000, 1300),
        'Flanders': range(1300, 4000),
        'Wallonia': range(4000, 10000),
    }
    
    # Common temporary/disposable email domains
    DISPOSABLE_DOMAINS = {
        'tempmail.com', 'throwaway.com', 'mailinator.com',
        'guerrillamail.com', 'yopmail.com', 'sharklasers.com'
    }
    
    @staticmethod
    def validate_kbo(kbo_number: str) -> Tuple[bool, Optional[str]]:
        """
        Validate Belgian KBO number using check digit algorithm.
        
        KBO numbers are 10 digits. The check digit is calculated as:
        check_digit = 97 - (prefix % 97) or prefix % 97
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not kbo_number:
            return False, "KBO number is empty"
        
        # Clean the number (remove spaces, dots)
        cleaned = re.sub(r'[\s\.]', '', kbo_number)
        
        if len(cleaned) != 10:
            return False, f"KBO number must be 10 digits, got {len(cleaned)}"
        
        if not cleaned.isdigit():
            return False, "KBO number must contain only digits"
        
        # Check digit validation
        prefix = int(cleaned[:9])
        check_digit = int(cleaned[9])
        calculated = (97 - (prefix % 97)) % 97
        
        if calculated == 0:
            calculated = 97
        
        if check_digit != calculated and check_digit != (prefix % 97):
            return False, f"Invalid check digit for KBO {kbo_number}"
        
        return True, None
    
    @staticmethod
    def validate_postal_code(pc: str) -> Tuple[bool, Optional[str]]:
        """Validate Belgian postal code (4 digits, 1000-9999)."""
        if not pc:
            return False, "Postal code is empty"
        
        cleaned = pc.strip()
        
        if len(cleaned) != 4:
            return False, f"Postal code must be 4 digits, got {len(cleaned)}"
        
        if not cleaned.isdigit():
            return False, "Postal code must contain only digits"
        
        pc_int = int(cleaned)
        if not (1000 <= pc_int <= 9999):
            return False, f"Postal code {pc_int} out of Belgian range"
        
        return True, None
    
    @staticmethod
    def validate_email(email: str) -> Tuple[bool, Optional[str]]:
        """Validate email format and check for disposable domains."""
        if not email:
            return False, "Email is empty"
        
        email = email.strip().lower()
        
        # Basic format validation
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email):
            return False, "Invalid email format"
        
        # Check for disposable domains
        domain = email.split('@')[1]
        if domain in KBOValidator.DISPOSABLE_DOMAINS:
            return False, f"Disposable email domain: {domain}"
        
        return True, None
    
    @staticmethod
    def validate_phone(phone: str) -> Tuple[bool, Optional[str]]:
        """Validate Belgian phone number format."""
        if not phone:
            return False, "Phone number is empty"
        
        # Remove all non-digit characters except +
        cleaned = re.sub(r'[^\d+]', '', phone.strip())
        
        # Belgian patterns
        # International: +32X XXX XX XX (10-11 digits after +)
        # National: 0X XXX XX XX (9-10 digits)
        
        if cleaned.startswith('+32'):
            digits_only = cleaned[3:]
            if len(digits_only) not in [8, 9]:
                return False, f"Invalid international phone length: {len(digits_only)} digits"
        elif cleaned.startswith('0'):
            digits_only = cleaned[1:]
            if len(digits_only) not in [8, 9]:
                return False, f"Invalid national phone length: {len(digits_only)} digits"
        else:
            return False, "Phone must start with +32 or 0"
        
        return True, None
    
    @staticmethod
    def normalize_phone(phone: str) -> str:
        """Normalize phone to international format (+32)."""
        if not phone:
            return ""
        
        cleaned = re.sub(r'[^\d]', '', phone.strip())
        
        if cleaned.startswith('0'):
            return '+32' + cleaned[1:]
        elif cleaned.startswith('32'):
            return '+' + cleaned
        elif cleaned.startswith('+32'):
            return cleaned
        
        return phone


class KBOCleaner:
    """Main cleanup pipeline for KBO data."""
    
    def __init__(self, skip_kbo_checkdigit: bool = False):
        self.validator = KBOValidator()
        self.skip_kbo_checkdigit = skip_kbo_checkdigit
        self.stats = {
            'enterprises_read': 0,
            'enterprises_valid': 0,
            'enterprises_invalid': 0,
            'enterprises_filtered': 0,
            'duplicates_removed': 0,
        }
    
    # Legal form standardization
    LEGAL_FORM_MAP = {
        'bvba': 'BVBA',
        'b.v.b.a.': 'BVBA',
        'nv': 'NV',
        'n.v.': 'NV',
        'sa': 'SA',
        's.a.': 'SA',
        'sprl': 'SPRL',
        's.p.r.l.': 'SPRL',
        'comm.v': 'COMM.V',
        'vzw': 'VZW',
        'v.z.w.': 'VZW',
        'asbl': 'ASBL',
        'a.s.b.l.': 'ASBL',
    }
    
    # Street abbreviations to expand
    STREET_ABBREVS = {
        'str.': 'straat',
        'str': 'straat',
        'ave.': 'avenue',
        'ave': 'avenue',
        'av.': 'avenue',
        'bd.': 'boulevard',
        'bd': 'boulevard',
        'blvd.': 'boulevard',
        'pl.': 'plein',
        'pl': 'plein',
        'ln.': 'laan',
        'ln': 'laan',
    }
    
    # Test/dummy patterns to filter
    TEST_PATTERNS = [
        r'^test',
        r'^demo',
        r'^xxxx',
        r'^999999',
        r'^[0]+$',  # All zeros
    ]
    
    def normalize_company_name(self, name: str) -> str:
        """Normalize company name (trim, title case, preserve acronyms)."""
        if not name:
            return ""
        
        name = name.strip()
        
        # Standardize legal forms
        name_lower = name.lower()
        for old, new in self.LEGAL_FORM_MAP.items():
            name_lower = name_lower.replace(old, new)
        
        # Title case while preserving acronyms
        words = name_lower.split()
        normalized_words = []
        
        for word in words:
            # Preserve all-caps words (likely acronyms)
            if word.isupper() and len(word) <= 5:
                normalized_words.append(word)
            else:
                normalized_words.append(word.capitalize())
        
        return ' '.join(normalized_words)
    
    def normalize_address(self, street: str, house_number: str) -> Tuple[str, str]:
        """Normalize street name and house number."""
        if not street:
            return "", house_number or ""
        
        street = street.strip().lower()
        
        # Expand abbreviations
        for abbrev, full in self.STREET_ABBREVS.items():
            street = street.replace(abbrev, full)
        
        # Title case
        street = ' '.join(word.capitalize() for word in street.split())
        
        # Clean house number
        house_number = (house_number or "").strip()
        
        return street, house_number
    
    def normalize_city(self, city: str) -> str:
        """Normalize city name."""
        if not city:
            return ""
        
        city = city.strip()
        
        # Special case handling for common variations
        city_map = {
            'brussel': 'Brussel',
            'bruxelles': 'Bruxelles',
            'brussels': 'Brussel',
            'antwerpen': 'Antwerpen',
            'anvers': 'Anvers',
            'gent': 'Gent',
            'gand': 'Gand',
            'luik': 'Luik',
            'liege': 'Liège',
            'liege': 'Liège',
        }
        
        city_lower = city.lower()
        return city_map.get(city_lower, city)
    
    def normalize_nace(self, nace: str) -> str:
        """Normalize NACE code to 5 digits."""
        if not nace:
            return ""
        
        nace = nace.strip()
        
        # Pad with leading zeros if needed
        if nace.isdigit():
            return nace.zfill(5)
        
        return nace
    
    def is_test_record(self, enterprise_number: str, name: str) -> bool:
        """Check if record appears to be test data."""
        text_to_check = f"{enterprise_number} {name}".lower()
        
        for pattern in self.TEST_PATTERNS:
            if re.search(pattern, text_to_check):
                return True
        
        return False
    
    def should_filter_enterprise(self, enterprise: Dict) -> Tuple[bool, str]:
        """Determine if enterprise should be filtered out."""
        kbo = enterprise.get('EnterpriseNumber', '')
        
        # Check for test data
        if self.is_test_record(kbo, enterprise.get('Denomination', '')):
            return True, "Test/dummy record"
        
        # Validate KBO format (basic: 10 digits)
        if not kbo or len(kbo) != 10 or not kbo.isdigit():
            return True, f"Invalid KBO format: must be 10 digits"
        
        # Validate KBO check digit (optional)
        if not self.skip_kbo_checkdigit:
            is_valid, error = self.validator.validate_kbo(kbo)
            if not is_valid:
                return True, f"Invalid KBO: {error}"
        
        # Filter inactive status (optional - can be configured)
        status = enterprise.get('Status', '')
        if status in ['INAC', 'STIC', 'ERAS']:  # Inactive, Striking off, Erased
            return True, f"Inactive status: {status}"
        
        return False, ""
    
    def deduplicate_enterprises(self, enterprises: List[Dict]) -> List[Dict]:
        """Remove duplicate enterprises, keeping most recent/complete."""
        seen = {}
        duplicates = []
        
        for enterprise in enterprises:
            kbo = enterprise.get('EnterpriseNumber', '')
            
            if kbo in seen:
                # Compare and keep better record
                existing = seen[kbo]
                
                # Prefer ACTIVE status
                if enterprise.get('Status') == 'AC' and existing.get('Status') != 'AC':
                    duplicates.append(existing)
                    seen[kbo] = enterprise
                else:
                    duplicates.append(enterprise)
            else:
                seen[kbo] = enterprise
        
        self.stats['duplicates_removed'] = len(duplicates)
        return list(seen.values())
    
    def cleanup_enterprise(self, row: Dict) -> Optional[Dict]:
        """Clean and validate a single enterprise record."""
        self.stats['enterprises_read'] += 1
        
        # Check if should be filtered
        should_filter, reason = self.should_filter_enterprise(row)
        if should_filter:
            logger.debug(f"Filtering enterprise {row.get('EnterpriseNumber')}: {reason}")
            self.stats['enterprises_filtered'] += 1
            return None
        
        self.stats['enterprises_valid'] += 1
        
        # Normalize fields
        cleaned = {
            'EnterpriseNumber': row.get('EnterpriseNumber', '').strip(),
            'Status': row.get('Status', '').strip().upper(),
            'JuridicalForm': row.get('JuridicalForm', '').strip(),
            'StartDate': row.get('StartDate', '').strip(),
        }
        
        return cleaned
    
    def cleanup_address(self, row: Dict) -> Optional[Dict]:
        """Clean and validate address record."""
        street, house_number = self.normalize_address(
            row.get('StreetNL', ''),
            row.get('HouseNumber', '')
        )
        
        postal_code = row.get('Zipcode', '').strip()
        city = self.normalize_city(row.get('MunicipalityNL', ''))
        
        # Validate postal code
        is_valid, error = self.validator.validate_postal_code(postal_code)
        if not is_valid:
            logger.debug(f"Invalid postal code {postal_code}: {error}")
        
        return {
            'EntityNumber': row.get('EntityNumber', '').strip(),
            'TypeOfAddress': row.get('TypeOfAddress', 'REGO').strip(),
            'CountryNL': row.get('CountryNL', 'België').strip(),
            'StreetNL': street,
            'HouseNumber': house_number,
            'Zipcode': postal_code,
            'MunicipalityNL': city,
            'PostalCodeValid': is_valid,
        }
    
    def cleanup_contact(self, row: Dict) -> Optional[Dict]:
        """Clean and validate contact record."""
        contact_type = row.get('ContactType', '').strip().upper()
        value = row.get('Value', '').strip()
        
        is_valid = False
        error = None
        normalized_value = value
        
        if contact_type == 'EMAIL':
            is_valid, error = self.validator.validate_email(value)
            normalized_value = value.lower() if value else ""
        elif contact_type == 'TEL':
            is_valid, error = self.validator.validate_phone(value)
            normalized_value = self.validator.normalize_phone(value)
        
        if error:
            logger.debug(f"Invalid {contact_type} {value}: {error}")
        
        return {
            'EntityNumber': row.get('EntityNumber', '').strip(),
            'ContactType': contact_type,
            'Value': normalized_value,
            'OriginalValue': value,
            'IsValid': is_valid,
        }
    
    def cleanup_activity(self, row: Dict) -> Optional[Dict]:
        """Clean activity record."""
        nace = self.normalize_nace(row.get('NaceCode', ''))
        
        return {
            'EntityNumber': row.get('EntityNumber', '').strip(),
            'NaceCode': nace,
            'NaceSection': nace[0] if len(nace) >= 1 else '',
        }
    
    def cleanup_denomination(self, row: Dict) -> Optional[Dict]:
        """Clean denomination record."""
        name = self.normalize_company_name(row.get('Denomination', ''))
        
        return {
            'EntityNumber': row.get('EntityNumber', '').strip(),
            'Denomination': name,
            'DenominationLower': name.lower(),
        }
    
    def process_all(self, input_dir: Path, output_dir: Path):
        """Process all KBO files."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Process enterprises first
        enterprise_file = input_dir / 'enterprise.csv'
        if enterprise_file.exists():
            logger.info(f"Processing {enterprise_file}")
            enterprises = self._read_csv(enterprise_file)
            
            # Clean and filter
            cleaned_enterprises = []
            for row in enterprises:
                cleaned = self.cleanup_enterprise(row)
                if cleaned:
                    cleaned_enterprises.append(cleaned)
            
            # Deduplicate
            cleaned_enterprises = self.deduplicate_enterprises(cleaned_enterprises)
            
            # Write output
            self._write_csv(output_dir / 'enterprise_cleaned.csv', cleaned_enterprises)
            logger.info(f"Enterprises: {len(cleaned_enterprises)} valid (filtered {self.stats['enterprises_filtered']}, duplicates {self.stats['duplicates_removed']})")
        
        # Process other files
        file_processors = {
            'address.csv': self.cleanup_address,
            'contact.csv': self.cleanup_contact,
            'activity.csv': self.cleanup_activity,
            'denomination.csv': self.cleanup_denomination,
        }
        
        for filename, processor in file_processors.items():
            filepath = input_dir / filename
            if filepath.exists():
                logger.info(f"Processing {filepath}")
                rows = self._read_csv(filepath)
                cleaned_rows = [processor(row) for row in rows if processor(row)]
                self._write_csv(output_dir / f"{filename.replace('.csv', '_cleaned.csv')}", cleaned_rows)
                logger.info(f"  → {len(cleaned_rows)} records written")
        
        # Print summary
        self._print_stats()
    
    def _read_csv(self, filepath: Path) -> List[Dict]:
        """Read CSV file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            return list(csv.DictReader(f))
    
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
        """Print processing statistics."""
        logger.info("=" * 50)
        logger.info("CLEANUP STATISTICS")
        logger.info("=" * 50)
        for key, value in self.stats.items():
            logger.info(f"  {key}: {value}")


def main():
    parser = argparse.ArgumentParser(description='Clean KBO data')
    parser.add_argument('--input-dir', default='./data/kbo', help='Input directory')
    parser.add_argument('--output-dir', default='./data/cleaned', help='Output directory')
    parser.add_argument('--lenient', action='store_true', help='Skip KBO check digit validation (for sample/testing)')
    
    args = parser.parse_args()
    
    cleaner = KBOCleaner(skip_kbo_checkdigit=args.lenient)
    cleaner.process_all(Path(args.input_dir), Path(args.output_dir))


if __name__ == '__main__':
    main()
