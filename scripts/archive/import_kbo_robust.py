#!/usr/bin/env python3
"""
KBO Import - Robust Production Version
- Signal handling for graceful shutdown
- Detailed progress logging to file
- Auto-resume from last position
- Error recovery with exponential backoff
"""
import asyncio
import csv
import os
import sys
import signal
import json
from datetime import datetime
from pathlib import Path
import asyncpg
import time

# Configuration
KBO_DIR = Path("kbo_extracted")
BATCH_SIZE = 500
STATE_FILE = Path("logs/import_kbo_state.json")
LOG_FILE = Path("logs/import_kbo.log")
PROGRESS_INTERVAL = 1000
TOTAL_COMPANIES = 516000

# Runtime state
shutdown_requested = False
start_time = datetime.now()


def log(msg, to_console=True):
    """Log to both file and optionally console"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{timestamp}] {msg}"
    
    # Write to log file
    with open(LOG_FILE, 'a') as f:
        f.write(line + '\n')
    
    if to_console:
        print(line)
        sys.stdout.flush()


def save_state(start_count: int, processed: int):
    """Save progress state for resume"""
    state = {
        'start_count': start_count,
        'processed': processed,
        'total': start_count + processed,
        'timestamp': datetime.now().isoformat(),
        'percent': round((start_count + processed) / TOTAL_COMPANIES * 100, 2)
    }
    STATE_FILE.parent.mkdir(exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)
    return state


def load_state():
    """Load previous state if exists"""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception as e:
            log(f"Warning: Could not load state file: {e}")
    return None


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global shutdown_requested
    signame = signal.Signals(signum).name
    log(f"Received {signame}, initiating graceful shutdown...")
    shutdown_requested = True


# Register signal handlers
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


async def import_kbo_robust():
    """Import KBO data with full error handling and resume capability"""
    
    log("=" * 60)
    log("KBO Import Starting (Robust Mode)")
    log(f"Working directory: {os.getcwd()}")
    log("=" * 60)
    
    # Load state for resume
    state = load_state()
    if state:
        log(f"Resuming from saved state: {state['total']:,} companies ({state['percent']}%)")
    
    # Database connection with retry
    conn = None
    for attempt in range(5):
        try:
            conn = await asyncpg.connect(
                'postgresql://cdpadmin:<redacted>@cdp-postgres-b1ms.postgres.database.azure.com:5432/postgres?sslmode=require'
            )
            log("Connected to database")
            break
        except Exception as e:
            if attempt == 4:
                log(f"Failed to connect after 5 attempts: {e}")
                sys.exit(1)
            wait = 2 ** attempt
            log(f"Connection attempt {attempt + 1} failed, retrying in {wait}s...")
            await asyncio.sleep(wait)
    
    try:
        # Get starting count
        start_count = await conn.fetchval('SELECT COUNT(*) FROM companies')
        log(f"Current database count: {start_count:,} companies")
        
        # Load reference data
        log("Loading reference data...")
        names = {}
        with open(KBO_DIR / "denomination.csv", 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                if row['EntityNumber'] not in names or row['TypeOfDenomination'] == '001':
                    names[row['EntityNumber']] = row['Denomination']
        
        addresses = {}
        with open(KBO_DIR / "address.csv", 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                if row['EntityNumber'] not in addresses:
                    addresses[row['EntityNumber']] = row
        
        log(f"Loaded {len(names):,} names, {len(addresses):,} addresses")
        
        # Process enterprises
        log("Starting import loop...")
        batch = []
        processed = 0
        last_log_time = time.time()
        last_log_count = 0
        errors = 0
        max_errors = 10
        
        with open(KBO_DIR / "enterprise.csv", 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for i, row in enumerate(reader):
                # Check for shutdown
                if shutdown_requested:
                    log("Shutdown requested, finishing current batch...")
                    break
                
                # Skip already imported (using row index as proxy for resume)
                if i < start_count:
                    continue
                
                entity_num = row['EnterpriseNumber'].replace('.', '')
                addr = addresses.get(row['EnterpriseNumber'], {})
                name = names.get(row['EnterpriseNumber'], f'Company {entity_num}')
                
                batch.append((
                    entity_num, name[:500],
                    f"{addr.get('StreetNL', '')} {addr.get('HouseNumber', '')}".strip()[:200] if addr else None,
                    addr.get('MunicipalityNL', '')[:100] if addr else None,
                    addr.get('Zipcode', '')[:20] if addr else None,
                    'BE', row.get('JuridicalForm', '')[:50], 'KBO'
                ))
                
                if len(batch) >= BATCH_SIZE:
                    # Insert with retry on error
                    for db_attempt in range(3):
                        try:
                            await conn.executemany('''
                                INSERT INTO companies (kbo_number, company_name, street_address, city, postal_code, 
                                    country, legal_form, source_system, created_at)
                                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
                                ON CONFLICT (kbo_number) DO NOTHING
                            ''', batch)
                            break
                        except Exception as e:
                            errors += 1
                            if errors >= max_errors:
                                log(f"Too many errors ({errors}), aborting")
                                raise
                            log(f"DB error (attempt {db_attempt+1}): {e}")
                            await asyncio.sleep(2 ** db_attempt)
                    else:
                        log(f"Failed to insert batch after retries, skipping")
                        errors += 1
                    
                    processed += len(batch)
                    batch = []
                    
                    # Progress logging
                    now = time.time()
                    total = start_count + processed
                    percent = total / TOTAL_COMPANIES * 100
                    
                    if processed % PROGRESS_INTERVAL == 0 or (now - last_log_time) >= 30:
                        elapsed = now - last_log_time
                        rate = (processed - last_log_count) / elapsed * 3600 if elapsed > 0 else 0
                        remaining_companies = TOTAL_COMPANIES - total
                        eta_hours = remaining_companies / rate if rate > 0 else 0
                        
                        log(f"Progress: {total:,}/{TOTAL_COMPANIES:,} ({percent:.1f}%) | "
                            f"Rate: {rate:.0f}/hr | ETA: {eta_hours:.1f}h | "
                            f"Errors: {errors}")
                        
                        # Save state periodically
                        save_state(start_count, processed)
                        
                        last_log_time = now
                        last_log_count = processed
        
        # Insert remaining
        if batch and not shutdown_requested:
            await conn.executemany('''
                INSERT INTO companies (kbo_number, company_name, street_address, city, postal_code,
                    country, legal_form, source_system, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
                ON CONFLICT (kbo_number) DO NOTHING
            ''', batch)
            processed += len(batch)
        
        # Final stats
        final_count = await conn.fetchval('SELECT COUNT(*) FROM companies')
        total_time = (datetime.now() - start_time).total_seconds()
        
        log("=" * 60)
        if shutdown_requested:
            log("IMPORT PAUSED (shutdown requested)")
            save_state(start_count, processed)
            log(f"State saved to {STATE_FILE}")
        else:
            log("IMPORT COMPLETE!")
        
        log(f"Final count: {final_count:,} companies")
        log(f"This session: {processed:,} inserted")
        log(f"Total time: {total_time/3600:.1f} hours")
        log(f"Average rate: {processed/(total_time/3600):.0f} companies/hour")
        log("=" * 60)
        
    except Exception as e:
        log(f"FATAL ERROR: {e}", to_console=True)
        import traceback
        log(f"Traceback:\n{traceback.format_exc()}")
        save_state(start_count if 'start_count' in dir() else 0, processed if 'processed' in dir() else 0)
        raise
    finally:
        if conn:
            await conn.close()
            log("Database connection closed")


if __name__ == "__main__":
    try:
        asyncio.run(import_kbo_robust())
    except KeyboardInterrupt:
        log("Interrupted by user")
        sys.exit(130)
    except Exception as e:
        log(f"Unhandled exception: {e}")
        sys.exit(1)
