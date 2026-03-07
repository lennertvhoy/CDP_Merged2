#!/bin/bash
# Hourly status report for KBO import
# Sends status update every hour

cd /home/ff/.openclaw/workspace/repos/CDP_Merged
source .venv/bin/activate

python -c "
import asyncio
import asyncpg
import os
from datetime import datetime

async def check():
    try:
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            raise RuntimeError('DATABASE_URL must be set before running hourly_status.sh')
        conn = await asyncpg.connect(database_url)
        count = await conn.fetchval('SELECT COUNT(*) FROM companies')
        
        remaining = 516000 - count
        percent = count / 516000 * 100
        
        # Estimate completion
        if count > 14000:
            # Calculate rate based on progress since 14K
            hours_elapsed = 1  # approximate
            rate = (count - 14000) / hours_elapsed
            if rate > 0:
                hours_remaining = remaining / rate
                eta = f'{hours_remaining:.1f} hours ({hours_remaining/24:.1f} days)'
            else:
                eta = 'Calculating...'
        else:
            eta = '~36 hours'
        
        status_msg = f'''[{datetime.now().strftime('%Y-%m-%d %H:%M')}] KBO Import Status:
• Progress: {count:,} / 516,000 companies ({percent:.1f}%)
• Remaining: {remaining:,} companies
• Estimated completion: {eta}
'''
        
        print(status_msg)
        
        # Also write to status file
        with open('/tmp/kbo_import_status.log', 'a') as f:
            f.write(f'{datetime.now().isoformat()},{count},{percent:.2f}\n')
        
        await conn.close()
    except Exception as e:
        print(f'Error checking status: {e}')

asyncio.run(check())
" 2>&1
