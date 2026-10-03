# Browser Session Management

Run multiple isolated browser sessions concurrently with state persistence.

## Named Browser Sessions

Use `-s` flag to isolate browser contexts:

```bash
# Browser 1: Authentication flow
playwright-cli -s=auth open https://app.example.com/login

# Browser 2: Public browsing (separate cookies, storage)
playwright-cli -s=public open https://example.com

# Commands are isolated by browser session
playwright-cli -s=auth fill e1 "user@example.com"
playwright-cli -s=public snapshot
```

## Browser Session Isolation Properties

Each browser session has independent:
- Cookies
- LocalStorage / SessionStorage
- IndexedDB
- Cache
- Browsing history
- Open tabs

## Browser Session Commands

```bash
# List all browser sessions
playwright-cli list

# Stop a browser session (close the browser)
playwright-cli close                # stop the default browser
playwright-cli -s=mysession close   # stop a named browser

# Stop all browser sessions
playwright-cli close-all

# Forcefully kill all daemon processes (for stale/zombie processes)
playwright-cli kill-all

# Delete browser session user data (profile directory)
playwright-cli delete-data                # delete default browser data
playwright-cli -s=mysession delete-data   # delete named browser data
```

## Environment Variable

Set a default browser session name via environment variable:

```bash
export PLAYWRIGHT_CLI_SESSION="mysession"
playwright-cli open example.com  # Uses "mysession" automatically
```

## Common Patterns

### Concurrent Scraping

```bash
#!/bin/bash
# Scrape multiple sites concurrently

# Start all browsers
playwright-cli -s=site1 open https://site1.com &
playwright-cli -s=site2 open https://site2.com &
playwright-cli -s=site3 open https://site3.com &
wait

# Take snapshots from each
playwright-cli -s=site1 snapshot
playwright-cli -s=site2 snapshot
playwright-cli -s=site3 snapshot

# Cleanup
playwright-cli close-all
```

### A/B Testing Sessions

```bash
# Test different user experiences
playwright-cli -s=variant-a open "https://app.com?variant=a"
playwright-cli -s=variant-b open "https://app.com?variant=b"

# Compare
playwright-cli -s=variant-a screenshot
playwright-cli -s=variant-b screenshot
```

### Persistent Profile

By default, browser profile is kept in memory only. Use `--persistent` flag on `open` to persist the browser profile to disk:

```bash
# Use persistent profile (auto-generated location)
playwright-cli open https://example.com --persistent

# Use persistent profile with custom directory
playwright-cli open https://example.com --profile=/path/to/profile
```

## Default Browser Session

When `-s` is omitted, commands use the default browser session:

```bash
# These use the same default browser session
playwright-cli open https://example.com
playwright-cli snapshot
playwright-cli close  # Stops default browser
```

## Browser Session Configuration

Configure a browser session with specific settings when opening:

```bash
# Open with config file
playwright-cli open https://example.com --config=.playwright/my-cli.json

# Open with specific browser
playwright-cli open https://example.com --browser=firefox

# Open in headed mode
playwright-cli open https://example.com --headed

# Open with persistent profile
playwright-cli open https://example.com --persistent
```

## Human-operated headed sessions

Use this pattern when a person needs to interact with a visible browser and the agent needs to inspect the result afterward.

### 1. Create or reuse one named session

```bash
playwright-cli -s=shared-work open https://example.com --headed
playwright-cli list
playwright-cli -s=shared-work tab-list
```

Use a semantic session name. Reuse that name for every command in the workflow. Do not switch to another headless session for state reads; it will have independent tabs, storage, and in-page state.

### 2. Prepare the page, then stop driving

Navigate the shared session to the right URL and let the user act:

```bash
playwright-cli -s=shared-work goto https://example.com/workspace
playwright-cli -s=shared-work eval "() => ({ url: location.href, title: document.title })"
```

Avoid tab cleanup while the user is working. If there are multiple tabs, select the intended tab instead of closing tabs:

```bash
playwright-cli -s=shared-work tab-list
playwright-cli -s=shared-work tab-select 0
```

### 3. Inspect the same tab after user action

Start with a small probe:

```bash
playwright-cli -s=shared-work eval "() => ({
  url: location.href,
  title: document.title,
  activeElement: document.activeElement?.tagName,
  readyState: document.readyState
})"
```

Then extract the task-specific state. Prefer structured data from DOM datasets, form values, or app globals over screenshots when available:

```bash
playwright-cli -s=shared-work eval "() => ({
  rows: [...document.querySelectorAll('[data-id]')].map(el => ({
    text: el.textContent?.trim(),
    dataset: { ...el.dataset }
  }))
})"
```

### 4. Handle blockers without losing state

If `eval`, `snapshot`, or `screenshot` reports an open dialog, dismiss or accept according to the task and retry. For navigation prompts, prefer dismiss unless the user explicitly wants to navigate away:

```bash
playwright-cli -s=shared-work dialog-dismiss
playwright-cli -s=shared-work eval "() => ({ url: location.href })"
```

### 5. Report uncertainty explicitly

If state is invisible to the DOM, say so and name the next inspection surface:

- app globals exposed on `window`
- framework stores or custom selection models
- canvas/WebGL screenshot plus pixel/visual checks
- console/network logs

An empty normal DOM selection does not prove that the user selected nothing; many apps keep selections in custom state outside standard DOM focus/selection APIs.

## Best Practices

### 1. Name Browser Sessions Semantically

```bash
# GOOD: Clear purpose
playwright-cli -s=github-auth open https://github.com
playwright-cli -s=docs-scrape open https://docs.example.com

# AVOID: Generic names
playwright-cli -s=s1 open https://github.com
```

### 2. Clean Up Only Task-Owned Sessions

```bash
# Stop browsers when done
playwright-cli -s=auth close
playwright-cli -s=scrape close

# Only with explicit authorization to close every session
playwright-cli close-all

# Only with explicit authorization to affect other browser tasks
playwright-cli kill-all
```

For an independent headless review, create a separate semantic session, use a
task-local configuration with `browser.launchOptions.headless: true` when an
explicit override is needed, and verify `headed: false` using `list`. Keep the
existing human-operated session unchanged. Inspect only the task session's
artifacts and close only that session at completion. Do not change shared server
assets or settings that trigger live reload in the human's page without approval.

### 3. Delete Stale Browser Data

```bash
# Remove old browser data to free disk space
playwright-cli -s=oldsession delete-data
```
