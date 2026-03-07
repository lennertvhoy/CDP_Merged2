#!/usr/bin/env python3
"""
Event Hub Consumer - Receives events and writes to PostgreSQL
"""
import asyncio
import json
import os
from azure.eventhub.aio import EventHubConsumerClient
import asyncpg
from dotenv import load_dotenv

load_dotenv('.env.database')

EVENT_HUB_CONNECTION = os.getenv('EVENTHUB_CONNECTION_STRING')
EVENT_HUB_NAME = "cdp-events"
CONSUMER_GROUP = "$Default"

async def process_event(partition_context, event):
    """Process single event from Event Hub"""
    try:
        data = json.loads(event.body_as_str())
        print(f"Received event: {data.get('event_type')} from {data.get('source')}")
        
        # Write to PostgreSQL
        conn = await asyncpg.connect(
            host=os.getenv('POSTGRES_HOST'),
            port=os.getenv('POSTGRES_PORT', '5432'),
            user=os.getenv('POSTGRES_USER'),
            password=os.getenv('POSTGRES_PASSWORD'),
            database=os.getenv('POSTGRES_DB', 'postgres'),
            ssl='require'
        )
        
        # Insert into event_archive
        await conn.execute('''
            INSERT INTO event_archive (uid, source, event_type, payload, created_at)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT DO NOTHING
        ''', 
            data.get('uid'),
            data.get('source'),
            data.get('event_type'),
            json.dumps(data),
            event.enqueued_time
        )
        
        await conn.close()
        
        # Update checkpoint
        await partition_context.update_checkpoint(event)
        
    except Exception as e:
        print(f"Error processing event: {e}")

async def main():
    client = EventHubConsumerClient.from_connection_string(
        EVENT_HUB_CONNECTION,
        consumer_group=CONSUMER_GROUP,
        eventhub_name=EVENT_HUB_NAME
    )
    
    async with client:
        await client.receive(
            on_event=process_event,
            starting_position="-1"  # Start from beginning
        )

if __name__ == "__main__":
    print("Starting Event Hub consumer...")
    print("Press Ctrl+C to stop")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
