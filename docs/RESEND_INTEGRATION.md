# Resend Email Provider Integration

## Overview

The CDP now supports [Resend](https://resend.com) as an alternative email provider to Flexmail. Resend offers a modern API for transactional emails with excellent deliverability, comprehensive analytics, and developer-friendly documentation.

**Key Benefits:**
- Simple, RESTful API design
- Excellent deliverability rates
- Real-time email analytics
- Profile enrichment via email domain lookup
- Competitive pricing with generous free tier

---

## Configuration

### Environment Variables

Add the following to your `.env` file:

```bash
# Select Resend as the email provider
EMAIL_PROVIDER=resend

# Your Resend API key (get from https://resend.com/api-keys)
RESEND_API_KEY=re_your_api_key_here

# Default sender email (must be verified in Resend)
RESEND_FROM_EMAIL=noreply@yourdomain.com
```

### Verification Requirements

Before sending emails, you must:

1. **Verify your domain** in the Resend dashboard
2. **Add DNS records** (SPF, DKIM, DMARC) as instructed
3. **Verify your sender email** address

---

## Features

### 1. Transactional Email Sending

Send individual emails with HTML or text content:

```python
from src.services import ResendClient

client = ResendClient()

# Send a simple email
result = await client.send_email(
    to="user@example.com",
    subject="Welcome to our platform",
    html="<h1>Welcome!</h1><p>Thanks for joining us.</p>",
)

print(f"Email sent with ID: {result['id']}")
```

### 2. Bulk Email Campaigns

Send emails to multiple recipients efficiently:

```python
recipients = ["user1@example.com", "user2@example.com", "user3@example.com"]

results = await client.send_bulk_emails(
    to_list=recipients,
    subject="Monthly Newsletter",
    html="<h1>Latest Updates</h1><p>Check out what's new!</p>",
)

# Results contain status for each recipient
for result in results:
    print(f"{result['to']}: {result['status']}")
```

### 3. Profile Enrichment via Email

Resend can be used to enrich profile data based on email domains:

```python
# Extract company information from email domain
enrichment = await client.enrich_from_email("john@apple.com")

# Returns:
# {
#     "domain": "apple.com",
#     "company": "Apple Inc.",
#     "confidence": 0.95
# }
```

### 4. Email Validation

Validate email addresses before sending:

```python
validation = await client.validate_email("user@example.com")

if validation["valid"]:
    await client.send_email(to="user@example.com", ...)
else:
    print(f"Invalid email: {validation['reason']}")
```

---

## Usage Examples

### Basic Email Send

```python
import asyncio
from src.services import ResendClient

async def send_welcome_email(user_email: str, user_name: str):
    client = ResendClient()
    
    html_content = f"""
    <html>
        <body>
            <h1>Welcome, {user_name}!</h1>
            <p>Thank you for signing up. We're excited to have you on board.</p>
            <a href="https://yourapp.com/getting-started">Get Started</a>
        </body>
    </html>
    """
    
    result = await client.send_email(
        to=user_email,
        subject="Welcome to Our Platform! 🎉",
        html=html_content,
        text=f"Welcome, {user_name}! Thank you for signing up.",
    )
    
    return result

# Usage
asyncio.run(send_welcome_email("user@example.com", "John Doe"))
```

### Campaign with Personalization

```python
async def send_personalized_campaign(users: list[dict]):
    """Send personalized emails to a list of users."""
    client = ResendClient()
    
    for user in users:
        html = f"""
        <html>
            <body>
                <h1>Hi {user['first_name']},</h1>
                <p>We noticed you're interested in {user['interest']}.</p>
                <p>Check out these recommendations just for you!</p>
            </body>
        </html>
        """
        
        await client.send_email(
            to=user['email'],
            subject=f"{user['first_name']}, check out these recommendations!",
            html=html,
        )
```

### Error Handling

```python
from httpx import HTTPStatusError

async def safe_send_email(client: ResendClient, **kwargs):
    try:
        result = await client.send_email(**kwargs)
        return {"success": True, "data": result}
    except HTTPStatusError as e:
        if e.response.status_code == 422:
            return {
                "success": False,
                "error": "Invalid email address or unverified domain"
            }
        elif e.response.status_code == 429:
            return {
                "success": False,
                "error": "Rate limit exceeded. Please retry later."
            }
        raise
```

---

## Migration from Flexmail

If you're currently using Flexmail and want to migrate to Resend:

### 1. Update Environment Configuration

```bash
# Old configuration
EMAIL_PROVIDER=flexmail
FLEXMAIL_API_KEY=your_flexmail_key
FLEXMAIL_ACCOUNT_ID=your_account_id

# New configuration
EMAIL_PROVIDER=resend
RESEND_API_KEY=re_your_resend_key
RESEND_FROM_EMAIL=verified@yourdomain.com
```

### 2. Code Changes

The `ResendClient` and `FlexmailClient` have similar interfaces:

| Flexmail | Resend |
|----------|--------|
| `FlexmailClient()` | `ResendClient()` |
| `send_email(to, subject, html)` | `send_email(to, subject, html)` |
| `send_bulk(to_list, subject, html)` | `send_bulk_emails(to_list, subject, html)` |

### 3. Feature Comparison

| Feature | Flexmail | Resend |
|---------|----------|--------|
| Transactional emails | ✅ | ✅ |
| Bulk campaigns | ✅ | ✅ |
| Template support | ✅ | ❌ (use HTML strings) |
| Webhooks | ✅ | ✅ |
| Analytics | ✅ | ✅ |
| Free tier | Limited | 3,000 emails/month |

### 4. Testing Your Migration

```python
import pytest
from src.services import ResendClient

@pytest.mark.asyncio
async def test_resend_integration():
    """Test that Resend is properly configured."""
    client = ResendClient()
    
    # Test with your verified email
    result = await client.send_email(
        to="your-verified-email@domain.com",
        subject="Migration Test",
        html="<p>Resend integration is working!</p>",
    )
    
    assert "id" in result
    assert result["to"] == "your-verified-email@domain.com"
```

---

## API Reference

### ResendClient

#### `__init__(api_key: str | None = None, from_email: str | None = None)`

Initialize the Resend client.

**Parameters:**
- `api_key` (optional): Resend API key. If not provided, uses `RESEND_API_KEY` from settings
- `from_email` (optional): Default sender email. If not provided, uses `RESEND_FROM_EMAIL` from settings

#### `send_email(to: str, subject: str, html: str, text: str | None = None, from_email: str | None = None) -> dict`

Send a single email.

**Parameters:**
- `to`: Recipient email address
- `subject`: Email subject line
- `html`: HTML content of the email
- `text` (optional): Plain text version
- `from_email` (optional): Override default sender

**Returns:**
```json
{
    "id": "msg_123456789",
    "to": "recipient@example.com",
    "created_at": "2024-01-15T10:30:00Z"
}
```

#### `send_bulk_emails(to_list: list[str], subject: str, html: str, text: str | None = None) -> list[dict]`

Send emails to multiple recipients.

**Parameters:**
- `to_list`: List of recipient email addresses
- `subject`: Email subject line
- `html`: HTML content
- `text` (optional): Plain text version

**Returns:** List of result dictionaries with status for each recipient

---

## Troubleshooting

### Common Issues

#### "Domain not verified"

**Error:** `422 Unprocessable Entity - Domain not verified`

**Solution:** 
1. Go to Resend dashboard → Domains
2. Add and verify your domain
3. Ensure DNS records are properly configured

#### "Rate limit exceeded"

**Error:** `429 Too Many Requests`

**Solution:**
- Implement exponential backoff
- Consider upgrading your Resend plan
- Batch requests appropriately

#### "Invalid API key"

**Error:** `401 Unauthorized`

**Solution:**
- Verify your `RESEND_API_KEY` is correct
- Ensure the key has sending permissions
- Check for trailing spaces in environment variable

### Debug Mode

Enable debug logging to see request details:

```python
import logging

logging.basicConfig(level=logging.DEBUG)

client = ResendClient()
# All HTTP requests will be logged
```

---

## Best Practices

1. **Always use verified domains** for better deliverability
2. **Include both HTML and text versions** for accessibility
3. **Implement retry logic** for transient failures
4. **Monitor your sending reputation** in Resend dashboard
5. **Use bulk sending** for campaigns to improve efficiency
6. **Validate emails** before sending to reduce bounces

---

## Additional Resources

- [Resend Documentation](https://resend.com/docs)
- [Resend API Reference](https://resend.com/docs/api-reference/introduction)
- [Resend Python SDK](https://github.com/resend/resend-python)
- [Email Best Practices](https://resend.com/docs/dashboard/domains/introduction)

---

*Last updated: 2026-02-26*
