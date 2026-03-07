#!/usr/bin/env python3
"""
Production Webhook Server for CDP
Receives events from Teamleader, Brevo, Website → Event Hub
"""
import os
import json
import hmac
import hashlib
from datetime import datetime
from flask import Flask, request, jsonify
from azure.eventhub import EventHubProducerClient, EventData
from dotenv import load_dotenv

load_dotenv('.env.database')

app = Flask(__name__)

# Event Hub configuration
EVENTHUB_CONNECTION = os.getenv('EVENTHUB_CONNECTION_STRING')
EVENTHUB_NAME = "cdp-events"

# Webhook secrets (load from env or config)
TEAMLEADER_SECRET = os.getenv('TEAMLEADER_WEBHOOK_SECRET', '')
BREVO_SECRET = os.getenv('BREVO_WEBHOOK_SECRET', '')

# Initialize Event Hub producer
producer = None

def get_producer():
    global producer
    if producer is None and EVENTHUB_CONNECTION:
        try:
            producer = EventHubProducerClient.from_connection_string(
                EVENTHUB_CONNECTION, 
                eventhub_name=EVENTHUB_NAME
            )
        except Exception as e:
            print(f"Failed to connect to Event Hub: {e}")
    return producer

def send_to_eventhub(event_data):
    """Send event to Azure Event Hub"""
    try:
        client = get_producer()
        if not client:
            return False
        
        event_batch = client.create_batch()
        event_batch.add(EventData(json.dumps(event_data)))
        client.send_batch(event_batch)
        return True
    except Exception as e:
        print(f"Event Hub error: {e}")
        return False

def verify_signature(payload, signature, secret):
    """Verify webhook signature"""
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)

@app.route('/webhook/teamleader', methods=['POST'])
def teamleader_webhook():
    """Receive Teamleader CRM events"""
    try:
        payload = request.get_data()
        data = request.get_json()
        
        # Transform to CDP event format
        event = {
            "source": "teamleader",
            "event_type": data.get("event_type", "unknown"),
            "entity_type": data.get("entity_type"),
            "entity_id": data.get("entity_id"),
            "uid": data.get("company_id") or data.get("contact_id") or data.get("entity_id"),
            "timestamp": datetime.utcnow().isoformat(),
            "payload": data
        }
        
        if send_to_eventhub(event):
            return jsonify({"status": "received", "source": "teamleader"}), 200
        else:
            return jsonify({"status": "queued", "error": "Event Hub unavailable"}), 202
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/webhook/brevo', methods=['POST'])
def brevo_webhook():
    """Receive Brevo email events"""
    try:
        data = request.get_json()
        
        # Brevo sends array of events
        events = data if isinstance(data, list) else [data]
        
        for evt in events:
            event = {
                "source": "brevo",
                "event_type": evt.get("event"),
                "email": evt.get("email"),
                "campaign_id": evt.get("id"),
                "message_id": evt.get("message-id"),
                "timestamp": evt.get("date") or datetime.utcnow().isoformat(),
                "payload": evt
            }
            send_to_eventhub(event)
        
        return jsonify({"status": "received", "count": len(events)}), 200
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/webhook/website', methods=['POST'])
def website_webhook():
    """Receive website tracking events"""
    try:
        data = request.get_json()
        
        event = {
            "source": "website",
            "event_type": data.get("event_type", "page_view"),
            "uid": data.get("uid") or data.get("anonymous_id"),
            "session_id": data.get("session_id"),
            "page_url": data.get("page_url"),
            "referrer": data.get("referrer"),
            "timestamp": datetime.utcnow().isoformat(),
            "payload": data
        }
        
        if send_to_eventhub(event):
            return jsonify({"status": "received"}), 200
        else:
            return jsonify({"status": "queued"}), 202
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    producer_ok = get_producer() is not None
    return jsonify({
        "status": "healthy",
        "eventhub_connected": producer_ok,
        "timestamp": datetime.utcnow().isoformat()
    }), 200

@app.route('/stats', methods=['GET'])
def stats():
    """Get basic stats"""
    return jsonify({
        "webhook_endpoints": [
            "/webhook/teamleader",
            "/webhook/brevo",
            "/webhook/website"
        ],
        "event_hub": EVENTHUB_NAME,
        "status": "active"
    })

if __name__ == '__main__':
    # Production: use gunicorn
    # Development: use Flask directly
    print("Starting CDP Webhook Server...")
    print(f"Event Hub: {EVENTHUB_NAME}")
    print(f"Endpoints:")
    print(f"  - /webhook/teamleader")
    print(f"  - /webhook/brevo")
    print(f"  - /webhook/website")
    print(f"  - /health")
    
    # Use 0.0.0.0 to accept external connections
    app.run(host='0.0.0.0', port=8080, debug=False)
