# Screenshot Library

Organized visual documentation for the CDP Merged project.

## Directory Structure

```
docs/screenshots/
├── browser/        # Browser automation screenshots (Playwright)
│   ├── chainlit-ui-*.png       # Chainlit UI screenshots
│   └── page-*.png              # General browser captures
├── chatbot/        # Chatbot verification screenshots
│   ├── chatbot_final_verification.png
│   └── chatbot_working_*.png
└── tracardi/       # Tracardi dashboard screenshots
    ├── tracardi_dashboard_*.png
    ├── tracardi_login_*.png
    ├── tracardi_profile_*.png
    └── tracardi_recovery_*.png
```

## Usage Rules

1. **Always save screenshots here** - Never commit root-level PNG files
2. **Use descriptive names** - Include date/component/purpose
3. **Clean up old screenshots** - Remove outdated captures periodically
4. **Respect .gitignore** - Transient artifacts are excluded

## Creating Screenshots

### Browser/Playwright
```python
# Save to organized location
page.screenshot(path="docs/screenshots/browser/my-screenshot.png")
```

### Manual Captures
1. Save to appropriate subdirectory
2. Use descriptive filename with date
3. Update this README if adding new categories

## Screenshot Categories

| Category | Purpose | Example Files |
|----------|---------|---------------|
| browser | UI verification, E2E tests | chainlit-ui-*.png |
| chatbot | Chatbot functionality | chatbot_working_*.png |
| tracardi | Tracardi dashboard state | tracardi_dashboard_*.png |
