# Azure Function for processing Event Hub events
# Deploy to: Azure Functions (Python)

import logging
import json
import os
import asyncpg
from azure.functions import EventHubEvent


def get_pg_connection() -> str:
    """Resolve PostgreSQL connection string from environment."""
    connection = os.getenv("PG_CONNECTION_STRING") or os.getenv("DATABASE_URL")
    if connection:
        return connection
    raise RuntimeError("PG_CONNECTION_STRING or DATABASE_URL must be set.")

async def main(event: EventHubEvent):
    """
    Process events from Event Hub and write to PostgreSQL
    Trigger: Event Hub trigger
    """
    try:
        data = json.loads(event.get_body().decode('utf-8'))
        logging.info(f"Processing event: {data.get('event_type')} from {data.get('source')}")
        
        conn = await asyncpg.connect(get_pg_connection())
        
        # Store raw event
        await conn.execute('''
            INSERT INTO event_archive (uid, source, event_type, payload, created_at)
            VALUES ($1, $2, $3, $4, $5)
        ''', 
            data.get('uid'),
            data.get('source'),
            data.get('event_type'),
            json.dumps(data),
            data.get('timestamp')
        )
        
        # Update engagement score based on event type
        if data.get('event_type') in ['email_opened', 'email_clicked', 'page_view']:
            score_delta = {
                'email_opened': 2,
                'email_clicked': 5,
                'page_view': 1
            }.get(data['event_type'], 0)
            
            await conn.execute('''
                UPDATE companies 
                SET engagement_score = COALESCE(engagement_score, 0) + $1,
                    updated_at = NOW()
                WHERE kbo_number = $2 OR source_id = $2
            ''', score_delta, data.get('uid'))
        
        await conn.close()
        logging.info("Event processed successfully")
        
    except Exception as e:
        logging.error(f"Error processing event: {e}")
        raise
