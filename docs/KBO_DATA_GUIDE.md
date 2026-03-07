# KBO Data Acquisition Guide

This document explains how to obtain and update the Belgian KBO (Kruispuntbank Ondernemingen / Banque-Carrefour des Entreprises) data used by the CDP enrichment system.

## Overview

The KBO/BCE is Belgium's official crossroads bank for enterprises, containing data on:
- ~2 million registered enterprises
- ~1.7 million establishments
- ~3.3 million company names/denominations
- ~35 million business activities (NACE codes)
- ~2.9 million addresses
- ~700,000 contact details

## Data Structure

The KBO Open Data consists of 9 CSV files:

| File | Size | Records | Description |
|------|------|---------|-------------|
| `enterprise.csv` | ~86 MB | ~1.9M | Core enterprise data (KBO number, status, juridical form) |
| `establishment.csv` | ~68 MB | ~1.7M | Establishment/unit locations |
| `denomination.csv` | ~147 MB | ~3.3M | Company names and trade names |
| `address.csv` | ~289 MB | ~2.9M | Physical addresses for enterprises/establishments |
| `contact.csv` | ~33 MB | ~698K | Email, phone, and web addresses |
| `activity.csv` | ~1.5 GB | ~35M | NACE business activity codes |
| `branch.csv` | ~300 KB | ~7.3K | Branch office information |
| `code.csv` | ~1.9 MB | ~21.5K | Reference codes (juridical forms, types, etc.) |
| `meta.csv` | ~149 B | 6 | Metadata about the export |

## Download Instructions

### Official Source

1. **Website**: https://economie.fgov.be/en/themes/enterprises/crossroads-bank-enterprises/best-practices/kbo-open-data
2. **Direct URL**: Check the official FPS Economy website for the latest download link
3. **Format**: ZIP archive containing UTF-8 CSV files with comma delimiters

### Download Steps

```bash
# Navigate to the data directory
cd /home/ff/.openclaw/workspace/repos/CDP_Merged/data/kbo

# Download the latest KBO Open Data (replace URL with current link)
wget -O KboOpenData_latest.zip "https://example.com/kbo-opendata-download.zip"

# Backup existing data (optional but recommended)
mv enterprise.csv enterprise.csv.backup.$(date +%Y%m%d)

# Extract new data
unzip -o KboOpenData_latest.zip

# Verify extraction
ls -lh *.csv
wc -l *.csv
```

### Automated Download

For production environments, consider setting up a cron job:

```bash
# Add to crontab (runs monthly on the 1st at 3 AM)
0 3 1 * * /home/ff/.openclaw/workspace/repos/CDP_Merged/scripts/update_kbo_data.sh >> /var/log/kbo_update.log 2>&1
```

## Data Update Process

### 1. Check for New Releases

KBO data is typically updated **monthly**. Monitor:
- FPS Economy announcements
- The metadata file (`meta.csv`) contains the export date

### 2. Download New Data

Follow the download steps above with the new release URL.

### 3. Update Juridical Codes (if needed)

After extracting new data, check for new juridical forms:

```bash
# Extract unique juridical forms from code.csv
cd /home/ff/.openclaw/workspace/repos/CDP_Merged/data/kbo
grep 'JuridicalForm' code.csv | grep 'NL' | cut -d',' -f2,4 | sort -u > new_juridical_codes.txt

# Compare with existing codes
diff new_juridical_codes.txt ../../src/data/juridical_codes.json
```

If new codes are found, update `src/data/juridical_codes.json` accordingly.

### 4. Rebuild Indexes

After updating data, restart the enrichment pipeline to rebuild Elasticsearch indexes:

```bash
cd /home/ff/.openclaw/workspace/repos/CDP_Merged
make restart-services
python -m src.ingestion.kbo_loader --rebuild-index
```

## Backup Strategy

Current backup file location:
- **Backup**: `/home/ff/.openclaw/workspace/repos/CDP_Merged/KboOpenData_0285_2026_02_27_Full.zip`
- **Date**: 2026-02-27
- **Size**: ~299 MB (compressed), ~2.1 GB (uncompressed)

### Backup Recommendations

1. Keep at least 3 months of historical backups
2. Store backups in a separate location (S3, external drive)
3. Test restoration quarterly

```bash
# Create dated backup
cd /home/ff/.openclaw/workspace/repos/CDP_Merged/data/kbo
zip -r ../backups/KboOpenData_$(date +%Y%m%d).zip *.csv
```

## Data License

KBO Open Data is published under the **Open Data License** by the Belgian FPS Economy:
- Free for commercial and non-commercial use
- Attribution required (source: KBO/BCE)
- No warranty provided

Reference: https://economie.fgov.be/en/themes/enterprises/crossroads-bank-enterprises

## Troubleshooting

### Issue: CSV encoding problems
**Solution**: Files are UTF-8 encoded. If you see garbled characters, ensure your tools use UTF-8.

### Issue: Missing data after extraction
**Solution**: Check available disk space (need ~3 GB free). The archive is ~300 MB but extracts to ~2.1 GB.

### Issue: Slow ingestion
**Solution**: The full dataset has 45+ million rows. Use batch processing and consider:
- Increasing Elasticsearch heap size
- Using parallel processing (see `src/ingestion/kbo_loader.py`)
- Filtering for active enterprises only (`Status = "AC"`)

### Issue: Juridical form codes not found
**Solution**: Check `code.csv` for the latest codes. The system uses the numeric codes (e.g., "014" for NV).

## Current Data Status

- **Last Updated**: 2026-02-27
- **Source File**: KboOpenData_0285_2026_02_27_Full.zip
- **Extraction Path**: `data/kbo/`
- **Total Records**: ~45.5 million rows across all files
- **Enterprises**: ~1.94 million

## Related Documentation

- `src/data/juridical_codes.json` - Juridical form code mappings
- `src/ingestion/kbo_loader.py` - Data ingestion script
- `src/enrichment/cbe_integration.py` - CBE/KBO enrichment logic
- `docs/architecture.md` - System architecture overview
