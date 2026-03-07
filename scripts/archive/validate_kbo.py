#!/usr/bin/env python3
"""
KBO Data Quality Validation Script

Runs data quality checks on KBO data and generates a report.
Useful for validating both raw and cleaned data.

Usage:
    python validate_kbo.py --input-dir ./data/kbo --report ./reports/quality_report.json
    python validate_kbo.py --input-dir ./data/cleaned --report ./reports/cleaned_quality.json
"""

import argparse
import csv
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import Counter, defaultdict
from datetime import datetime
from dataclasses import dataclass, asdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class QualityMetric:
    """Single quality metric."""
    name: str
    value: Any
    threshold: Optional[float] = None
    passed: bool = True
    details: Optional[str] = None


@dataclass
class QualityReport:
    """Complete quality report."""
    timestamp: str
    source_directory: str
    total_records: int
    metrics: List[QualityMetric]
    issues: List[Dict]
    recommendations: List[str]
    
    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp,
            'source_directory': self.source_directory,
            'total_records': self.total_records,
            'metrics': [asdict(m) for m in self.metrics],
            'issues': self.issues,
            'recommendations': self.recommendations,
            'overall_score': self.calculate_score(),
        }
    
    def calculate_score(self) -> float:
        """Calculate overall quality score (0-100)."""
        if not self.metrics:
            return 0.0
        
        passed = sum(1 for m in self.metrics if m.passed)
        return (passed / len(self.metrics)) * 100


class KBODataValidator:
    """Validate KBO data quality."""
    
    def __init__(self):
        self.metrics = []
        self.issues = []
        self.recommendations = []
    
    def validate_kbo_format(self, kbo: str) -> bool:
        """Check KBO number format."""
        if not kbo:
            return False
        return len(kbo) == 10 and kbo.isdigit()
    
    def validate_kbo_check_digit(self, kbo: str) -> bool:
        """Validate KBO check digit."""
        if not self.validate_kbo_format(kbo):
            return False
        
        prefix = int(kbo[:9])
        check_digit = int(kbo[9])
        calculated = (97 - (prefix % 97)) % 97
        if calculated == 0:
            calculated = 97
        
        return check_digit == calculated or check_digit == (prefix % 97)
    
    def validate_postal_code(self, pc: str) -> bool:
        """Validate Belgian postal code."""
        if not pc or len(pc) != 4:
            return False
        return pc.isdigit() and 1000 <= int(pc) <= 9999
    
    def validate_email_format(self, email: str) -> bool:
        """Basic email format validation."""
        import re
        if not email:
            return False
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    def load_csv(self, filepath: Path) -> List[Dict]:
        """Load CSV file."""
        if not filepath.exists():
            return []
        
        with open(filepath, 'r', encoding='utf-8') as f:
            return list(csv.DictReader(f))
    
    def analyze_enterprises(self, enterprises: List[Dict]) -> Dict[str, Any]:
        """Analyze enterprise data quality."""
        results = {
            'total': len(enterprises),
            'valid_kbo_format': 0,
            'valid_kbo_checkdigit': 0,
            'status_distribution': Counter(),
            'juridical_form_distribution': Counter(),
            'missing_start_date': 0,
            'duplicate_kbos': [],
        }
        
        seen_kbos = set()
        
        for enterprise in enterprises:
            kbo = enterprise.get('EnterpriseNumber', '')
            
            # KBO validation
            if self.validate_kbo_format(kbo):
                results['valid_kbo_format'] += 1
                if self.validate_kbo_check_digit(kbo):
                    results['valid_kbo_checkdigit'] += 1
                else:
                    self.issues.append({
                        'type': 'invalid_kbo_checkdigit',
                        'entity': kbo,
                        'message': f'KBO {kbo} has invalid check digit'
                    })
            else:
                self.issues.append({
                    'type': 'invalid_kbo_format',
                    'entity': kbo,
                    'message': f'KBO {kbo} has invalid format'
                })
            
            # Check for duplicates
            if kbo in seen_kbos:
                results['duplicate_kbos'].append(kbo)
                self.issues.append({
                    'type': 'duplicate_kbo',
                    'entity': kbo,
                    'message': f'Duplicate KBO number: {kbo}'
                })
            seen_kbos.add(kbo)
            
            # Status distribution
            status = enterprise.get('Status', 'UNKNOWN')
            results['status_distribution'][status] += 1
            
            # Juridical form distribution
            form = enterprise.get('JuridicalForm', 'UNKNOWN')
            results['juridical_form_distribution'][form] += 1
            
            # Missing start date
            if not enterprise.get('StartDate'):
                results['missing_start_date'] += 1
        
        return results
    
    def analyze_addresses(self, addresses: List[Dict]) -> Dict[str, Any]:
        """Analyze address data quality."""
        results = {
            'total': len(addresses),
            'valid_postal_codes': 0,
            'missing_street': 0,
            'missing_city': 0,
            'missing_country': 0,
            'country_distribution': Counter(),
            'orphaned_addresses': [],
        }
        
        for address in addresses:
            # Postal code validation
            pc = address.get('Zipcode', '')
            if self.validate_postal_code(pc):
                results['valid_postal_codes'] += 1
            else:
                self.issues.append({
                    'type': 'invalid_postal_code',
                    'entity': address.get('EntityNumber'),
                    'message': f'Invalid postal code: {pc}'
                })
            
            # Missing fields
            if not address.get('StreetNL'):
                results['missing_street'] += 1
            if not address.get('MunicipalityNL'):
                results['missing_city'] += 1
            if not address.get('CountryNL'):
                results['missing_country'] += 1
            
            # Country distribution
            country = address.get('CountryNL', 'UNKNOWN')
            results['country_distribution'][country] += 1
        
        return results
    
    def analyze_contacts(self, contacts: List[Dict]) -> Dict[str, Any]:
        """Analyze contact data quality."""
        results = {
            'total': len(contacts),
            'email_count': 0,
            'phone_count': 0,
            'valid_emails': 0,
            'invalid_emails': 0,
            'contact_type_distribution': Counter(),
            'entities_with_email': set(),
            'entities_with_phone': set(),
        }
        
        for contact in contacts:
            contact_type = contact.get('ContactType', '').upper()
            value = contact.get('Value', '')
            entity = contact.get('EntityNumber', '')
            
            results['contact_type_distribution'][contact_type] += 1
            
            if contact_type == 'EMAIL':
                results['email_count'] += 1
                results['entities_with_email'].add(entity)
                
                if self.validate_email_format(value):
                    results['valid_emails'] += 1
                else:
                    results['invalid_emails'] += 1
                    self.issues.append({
                        'type': 'invalid_email',
                        'entity': entity,
                        'message': f'Invalid email format: {value}'
                    })
                    
            elif contact_type == 'TEL':
                results['phone_count'] += 1
                results['entities_with_phone'].add(entity)
        
        return results
    
    def analyze_activities(self, activities: List[Dict]) -> Dict[str, Any]:
        """Analyze activity data quality."""
        results = {
            'total': len(activities),
            'nace_distribution': Counter(),
            'entities_with_activities': set(),
            'nace_section_distribution': Counter(),
        }
        
        for activity in activities:
            nace = activity.get('NaceCode', '')
            entity = activity.get('EntityNumber', '')
            
            results['nace_distribution'][nace] += 1
            results['entities_with_activities'].add(entity)
            
            # Get NACE section (first digit)
            if nace:
                section = nace[0] if nace[0].isalpha() else nace[0]
                results['nace_section_distribution'][section] += 1
        
        return results
    
    def analyze_denomination(self, denominations: List[Dict]) -> Dict[str, Any]:
        """Analyze denomination data quality."""
        results = {
            'total': len(denominations),
            'missing_denomination': 0,
            'entities_with_name': set(),
            'short_names': [],  # Less than 3 characters
        }
        
        for denom in denominations:
            name = denom.get('Denomination', '')
            entity = denom.get('EntityNumber', '')
            
            if not name:
                results['missing_denomination'] += 1
                self.issues.append({
                    'type': 'missing_denomination',
                    'entity': entity,
                    'message': 'Missing company name'
                })
            elif len(name) < 3:
                results['short_names'].append(name)
            
            results['entities_with_name'].add(entity)
        
        return results
    
    def check_relationship_integrity(self, 
                                      enterprises: List[Dict],
                                      addresses: List[Dict],
                                      contacts: List[Dict],
                                      activities: List[Dict],
                                      denominations: List[Dict]) -> Dict[str, Any]:
        """Check referential integrity between tables."""
        results = {
            'enterprise_count': len(enterprises),
            'enterprises_with_address': 0,
            'enterprises_with_contact': 0,
            'enterprises_with_activity': 0,
            'enterprises_with_name': 0,
            'orphaned_addresses': 0,
            'orphaned_contacts': 0,
            'orphaned_activities': 0,
            'orphaned_denominations': 0,
        }
        
        # Build set of valid enterprise numbers
        valid_kbos = {e.get('EnterpriseNumber', '') for e in enterprises}
        
        # Check each relationship
        for address in addresses:
            if address.get('EntityNumber', '') in valid_kbos:
                results['enterprises_with_address'] += 1
            else:
                results['orphaned_addresses'] += 1
                self.issues.append({
                    'type': 'orphaned_address',
                    'entity': address.get('EntityNumber'),
                    'message': 'Address references non-existent enterprise'
                })
        
        for contact in contacts:
            if contact.get('EntityNumber', '') in valid_kbos:
                results['enterprises_with_contact'] += 1
            else:
                results['orphaned_contacts'] += 1
        
        for activity in activities:
            if activity.get('EntityNumber', '') in valid_kbos:
                results['enterprises_with_activity'] += 1
            else:
                results['orphaned_activities'] += 1
        
        for denom in denominations:
            if denom.get('EntityNumber', '') in valid_kbos:
                results['enterprises_with_name'] += 1
            else:
                results['orphaned_denominations'] += 1
        
        return results
    
    def generate_recommendations(self, analyses: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on analysis."""
        recommendations = []
        
        # Enterprise recommendations
        if analyses.get('enterprises'):
            ent = analyses['enterprises']
            if ent['duplicate_kbos']:
                recommendations.append(f"Remove {len(ent['duplicate_kbos'])} duplicate KBO numbers")
            
            invalid_kbo_pct = (ent['total'] - ent['valid_kbo_format']) / ent['total'] * 100
            if invalid_kbo_pct > 5:
                recommendations.append(f"High rate of invalid KBO formats ({invalid_kbo_pct:.1f}%) - investigate source data")
        
        # Address recommendations
        if analyses.get('addresses'):
            addr = analyses['addresses']
            valid_pc_pct = addr['valid_postal_codes'] / addr['total'] * 100 if addr['total'] > 0 else 100
            if valid_pc_pct < 90:
                recommendations.append(f"Only {valid_pc_pct:.1f}% valid postal codes - consider geocoding for correction")
        
        # Contact recommendations
        if analyses.get('contacts'):
            con = analyses['contacts']
            if con['invalid_emails'] > 0:
                recommendations.append(f"{con['invalid_emails']} invalid emails - clean or remove")
        
        # Relationship recommendations
        if analyses.get('relationships'):
            rel = analyses['relationships']
            if rel['orphaned_addresses'] > 0:
                recommendations.append(f"{rel['orphaned_addresses']} orphaned addresses - remove or fix references")
            if rel['orphaned_contacts'] > 0:
                recommendations.append(f"{rel['orphaned_contacts']} orphaned contacts - remove or fix references")
        
        return recommendations
    
    def validate_directory(self, input_dir: Path) -> QualityReport:
        """Run full validation on a directory."""
        logger.info(f"Validating data in {input_dir}")
        
        # Load all files
        files = {
            'enterprise': input_dir / 'enterprise.csv',
            'address': input_dir / 'address.csv',
            'contact': input_dir / 'contact.csv',
            'activity': input_dir / 'activity.csv',
            'denomination': input_dir / 'denomination.csv',
        }
        
        # Also try cleaned versions
        cleaned_files = {
            'enterprise': input_dir / 'enterprise_cleaned.csv',
            'address': input_dir / 'address_cleaned.csv',
            'contact': input_dir / 'contact_cleaned.csv',
            'activity': input_dir / 'activity_cleaned.csv',
            'denomination': input_dir / 'denomination_cleaned.csv',
        }
        
        # Use cleaned if available, else raw
        data = {}
        for key in files:
            if cleaned_files[key].exists():
                data[key] = self.load_csv(cleaned_files[key])
            elif files[key].exists():
                data[key] = self.load_csv(files[key])
            else:
                data[key] = []
        
        # Run analyses
        analyses = {}
        
        if data['enterprise']:
            analyses['enterprises'] = self.analyze_enterprises(data['enterprise'])
        if data['address']:
            analyses['addresses'] = self.analyze_addresses(data['address'])
        if data['contact']:
            analyses['contacts'] = self.analyze_contacts(data['contact'])
        if data['activity']:
            analyses['activities'] = self.analyze_activities(data['activity'])
        if data['denomination']:
            analyses['denominations'] = self.analyze_denomination(data['denomination'])
        
        # Check relationships
        if all(data.values()):
            analyses['relationships'] = self.check_relationship_integrity(
                data['enterprise'], data['address'], data['contact'],
                data['activity'], data['denomination']
            )
        
        # Build metrics
        self.metrics = []
        
        if 'enterprises' in analyses:
            ent = analyses['enterprises']
            self.metrics.append(QualityMetric(
                name='KBO Format Validity',
                value=f"{ent['valid_kbo_format']}/{ent['total']}",
                threshold=95.0,
                passed=(ent['valid_kbo_format'] / ent['total'] * 100) >= 95 if ent['total'] > 0 else True
            ))
            self.metrics.append(QualityMetric(
                name='No Duplicates',
                value=len(ent['duplicate_kbos']),
                threshold=0,
                passed=len(ent['duplicate_kbos']) == 0
            ))
        
        if 'addresses' in analyses:
            addr = analyses['addresses']
            self.metrics.append(QualityMetric(
                name='Postal Code Validity',
                value=f"{addr['valid_postal_codes']}/{addr['total']}",
                threshold=90.0,
                passed=(addr['valid_postal_codes'] / addr['total'] * 100) >= 90 if addr['total'] > 0 else True
            ))
        
        if 'contacts' in analyses:
            con = analyses['contacts']
            if con['email_count'] > 0:
                valid_email_pct = con['valid_emails'] / con['email_count'] * 100
                self.metrics.append(QualityMetric(
                    name='Email Validity',
                    value=f"{con['valid_emails']}/{con['email_count']}",
                    threshold=95.0,
                    passed=valid_email_pct >= 95
                ))
        
        if 'relationships' in analyses:
            rel = analyses['relationships']
            self.metrics.append(QualityMetric(
                name='No Orphaned Records',
                value=rel['orphaned_addresses'] + rel['orphaned_contacts'],
                threshold=0,
                passed=(rel['orphaned_addresses'] + rel['orphaned_contacts']) == 0
            ))
        
        # Generate recommendations
        self.recommendations = self.generate_recommendations(analyses)
        
        # Build report
        total_records = sum(len(v) for v in data.values())
        
        return QualityReport(
            timestamp=datetime.now().isoformat(),
            source_directory=str(input_dir),
            total_records=total_records,
            metrics=self.metrics,
            issues=self.issues[:100],  # Limit issues in report
            recommendations=self.recommendations
        )
    
    def print_report(self, report: QualityReport):
        """Print quality report to console."""
        print("\n" + "=" * 60)
        print("KBO DATA QUALITY REPORT")
        print("=" * 60)
        print(f"Timestamp: {report.timestamp}")
        print(f"Source: {report.source_directory}")
        print(f"Total Records: {report.total_records}")
        print(f"Overall Score: {report.calculate_score():.1f}/100")
        print("\nMETRICS:")
        print("-" * 40)
        for metric in report.metrics:
            status = "✓ PASS" if metric.passed else "✗ FAIL"
            print(f"  {status} | {metric.name}: {metric.value}")
        
        if report.issues:
            print("\nTOP ISSUES:")
            print("-" * 40)
            for issue in report.issues[:10]:
                print(f"  [{issue['type']}] {issue['message']}")
        
        if report.recommendations:
            print("\nRECOMMENDATIONS:")
            print("-" * 40)
            for rec in report.recommendations:
                print(f"  • {rec}")
        
        print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(description='Validate KBO data quality')
    parser.add_argument('--input-dir', default='./data/kbo', help='Input directory')
    parser.add_argument('--report', help='Output report file (JSON)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    validator = KBODataValidator()
    report = validator.validate_directory(Path(args.input_dir))
    
    # Print to console
    validator.print_report(report)
    
    # Save to file if requested
    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, 'w') as f:
            json.dump(report.to_dict(), f, indent=2)
        logger.info(f"Report saved to {report_path}")


if __name__ == '__main__':
    main()
