import asyncio
import os
import sys

# Set env vars to ensure they are available
os.environ['TRACARDI_API_URL'] = 'http://52.148.232.140:8686'
os.environ['TRACARDI_USERNAME'] = 'admin@cdpmerged.local'
os.environ['TRACARDI_PASSWORD'] = 'admin'

sys.path.insert(0, '/home/ff/.openclaw/workspace/repos/CDP_Merged/src')

async def check_enrichment():
    from services.tracardi import TracardiClient
    client = TracardiClient()
    
    # Check total profiles
    res = await client.search_profiles("id EXISTS", limit=1)
    print(f"Total Profiles: {res.get('total', 0)}")
    
    # Check specific metrics
    res_emails = await client.search_profiles("traits.email EXISTS", limit=1)
    print(f"Emails: {res_emails.get('total', 0)}")
    
    res_phones = await client.search_profiles("traits.phone EXISTS", limit=1)
    print(f"Phones: {res_phones.get('total', 0)}")
    
    res_website = await client.search_profiles("traits.website_url EXISTS", limit=1)
    print(f"Discovered Websites: {res_website.get('total', 0)}")
    
    res_ai = await client.search_profiles("traits.business_description EXISTS", limit=1)
    print(f"AI Descriptions: {res_ai.get('total', 0)}")
    
    res_geo = await client.search_profiles("traits.geo_latitude EXISTS", limit=1)
    print(f"Geocoded: {res_geo.get('total', 0)}")

if __name__ == "__main__":
    asyncio.run(check_enrichment())
