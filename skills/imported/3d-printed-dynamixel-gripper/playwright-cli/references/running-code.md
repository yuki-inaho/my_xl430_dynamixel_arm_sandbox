# Running Custom Playwright Code

Use `run-code` to execute arbitrary Playwright code for advanced scenarios not covered by CLI commands.

## Syntax

```bash
playwright-cli run-code "async page => {
  // Your Playwright code here
  // Access page.context() for browser context operations
}"
```

## Geolocation

```bash
# Grant geolocation permission and set location
playwright-cli run-code "async page => {
  await page.context().grantPermissions(['geolocation']);
  await page.context().setGeolocation({ latitude: 37.7749, longitude: -122.4194 });
}"

# Set location to London
playwright-cli run-code "async page => {
  await page.context().grantPermissions(['geolocation']);
  await page.context().setGeolocation({ latitude: 51.5074, longitude: -0.1278 });
}"

# Clear geolocation override
playwright-cli run-code "async page => {
  await page.context().clearPermissions();
}"
```

## Permissions

```bash
# Grant multiple permissions
playwright-cli run-code "async page => {
  await page.context().grantPermissions([
    'geolocation',
    'notifications',
    'camera',
    'microphone'
  ]);
}"

# Grant permissions for specific origin
playwright-cli run-code "async page => {
  await page.context().grantPermissions(['clipboard-read'], {
    origin: 'https://example.com'
  });
}"
```

## Media Emulation

```bash
# Emulate dark color scheme
playwright-cli run-code "async page => {
  await page.emulateMedia({ colorScheme: 'dark' });
}"

# Emulate light color scheme
playwright-cli run-code "async page => {
  await page.emulateMedia({ colorScheme: 'light' });
}"

# Emulate reduced motion
playwright-cli run-code "async page => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
}"

# Emulate print media
playwright-cli run-code "async page => {
  await page.emulateMedia({ media: 'print' });
}"
```

## Wait Strategies

```bash
# Wait for network idle
playwright-cli run-code "async page => {
  await page.waitForLoadState('networkidle');
}"

# Wait for specific element
playwright-cli run-code "async page => {
  await page.waitForSelector('.loading', { state: 'hidden' });
}"

# Wait for function to return true
playwright-cli run-code "async page => {
  await page.waitForFunction(() => window.appReady === true);
}"

# Wait with timeout
playwright-cli run-code "async page => {
  await page.waitForSelector('.result', { timeout: 10000 });
}"
```

## Frames and Iframes

```bash
# Work with iframe
playwright-cli run-code "async page => {
  const frame = page.locator('iframe#my-iframe').contentFrame();
  await frame.locator('button').click();
}"

# Get all frames
playwright-cli run-code "async page => {
  const frames = page.frames();
  return frames.map(f => f.url());
}"
```

## File Downloads

```bash
# Handle file download
playwright-cli run-code "async page => {
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.click('a.download-link')
  ]);
  await download.saveAs('./downloaded-file.pdf');
  return download.suggestedFilename();
}"
```

## Clipboard

```bash
# Read clipboard (requires permission)
playwright-cli run-code "async page => {
  await page.context().grantPermissions(['clipboard-read']);
  return await page.evaluate(() => navigator.clipboard.readText());
}"

# Write to clipboard
playwright-cli run-code "async page => {
  await page.evaluate(text => navigator.clipboard.writeText(text), 'Hello clipboard!');
}"
```

## Page Information

```bash
# Get page title
playwright-cli run-code "async page => {
  return await page.title();
}"

# Get current URL
playwright-cli run-code "async page => {
  return page.url();
}"

# Get page content
playwright-cli run-code "async page => {
  return await page.content();
}"

# Get viewport size
playwright-cli run-code "async page => {
  return page.viewportSize();
}"
```

## JavaScript Execution

```bash
# Execute JavaScript and return result
playwright-cli run-code "async page => {
  return await page.evaluate(() => {
    return {
      userAgent: navigator.userAgent,
      language: navigator.language,
      cookiesEnabled: navigator.cookieEnabled
    };
  });
}"

# Pass arguments to evaluate
playwright-cli run-code "async page => {
  const multiplier = 5;
  return await page.evaluate(m => document.querySelectorAll('li').length * m, multiplier);
}"
```

## Inspecting application state

Use page evaluation to extract structured state after the page has been driven by either the agent or a human. Start with a small probe before serializing larger objects:

```bash
playwright-cli eval "() => ({
  url: location.href,
  title: document.title,
  readyState: document.readyState,
  focused: document.activeElement?.tagName
})"
```

For DOM-backed state, return compact JSON with text, classes, and datasets:

```bash
playwright-cli eval "() => JSON.stringify(
  [...document.querySelectorAll('[data-id], [aria-selected=true], .selected')]
    .map(el => ({
      tag: el.tagName,
      text: el.textContent?.trim().replace(/\\s+/g, ' ').slice(0, 160),
      className: String(el.className || ''),
      dataset: { ...el.dataset }
    })),
  null,
  2
)"
```

For custom apps, inspect likely globals and keep serialization shallow to avoid circular references:

```bash
playwright-cli eval "() => {
  const app = globalThis.app ?? globalThis.App ?? globalThis.__APP__ ?? null;
  const summarize = value => {
    if (!value || typeof value !== 'object') return value;
    return {
      className: value.constructor?.name,
      keys: Object.getOwnPropertyNames(value).slice(0, 50),
      id: value.id,
      name: value.name,
      type: value.type
    };
  };
  return JSON.stringify({
    app: summarize(app),
    selection: summarize(app?.selection ?? app?.store?.selection)
  }, null, 2);
}"
```

If the app renders into canvas or WebGL, a screenshot may be the only complete visual record. Pair screenshots with DOM/app-state extraction so the final report can distinguish visual evidence from structured metadata.

## File Chooser Ownership

Use one mechanism to handle each file chooser. With CLI commands, click the
observed import control, wait for the reported chooser, then use `upload`:

```bash
playwright-cli -s=review click e42
playwright-cli -s=review upload /absolute/path/to/document.ext
```

Do not also call `fileChooser.setFiles` inside `run-code` for that same chooser.
The CLI may surface a modal while the custom callback is still pending; handling
it twice can trigger duplicate change/cancel cleanup and runtime errors. Let
each command finish before issuing another operation against the same modal.
Wait for the expected imported item, then inspect console errors and duplicate
items before recording a screenshot. File input can avoid copying artifacts
into a watched development-server directory that would reload another user's tab.

If a click times out despite a visible target, inspect the reported intercepting
element. A runtime-error iframe is evidence to investigate, not a reason to force
the click. Record the error before restarting a task-owned disposable tab. Check
for `beforeunload` and other dialogs; do not discard a user's unsaved document.
Verify that a screenshot command completed and the file exists before inspecting it.

## Error Handling

```bash
# Try-catch in run-code
playwright-cli run-code "async page => {
  try {
    await page.click('.maybe-missing', { timeout: 1000 });
    return 'clicked';
  } catch (e) {
    return 'element not found';
  }
}"
```

## Complex Workflows

```bash
# Login and save state
playwright-cli run-code "async page => {
  await page.goto('https://example.com/login');
  await page.fill('input[name=email]', 'user@example.com');
  await page.fill('input[name=password]', 'secret');
  await page.click('button[type=submit]');
  await page.waitForURL('**/dashboard');
  await page.context().storageState({ path: 'auth.json' });
  return 'Login successful';
}"

# Scrape data from multiple pages
playwright-cli run-code "async page => {
  const results = [];
  for (let i = 1; i <= 3; i++) {
    await page.goto(\`https://example.com/page/\${i}\`);
    const items = await page.locator('.item').allTextContents();
    results.push(...items);
  }
  return results;
}"
```
