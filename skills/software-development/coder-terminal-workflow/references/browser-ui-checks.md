# Browser UI checks for a Vite/React project (no Playwright installed)

When a TASK asks for «консоль браузера — без красных ошибок», a DOM/state assertion, or a
screenshot, and the project has no Playwright (check `package.json` first — a Vite scaffold often
ships only `vite`/`oxlint`/`tsc`), drive the agent's browser tool against the local dev server.
If the TASK names Playwright and a specific output shape, say in the report that you substituted
the browser tool and why — never quietly swap a prescribed measurement method.

## 1. Start the dev server and wait for it — never sleep blindly

```python
# terminal(background=True): npm run dev   (workdir = project root)
import time, urllib.request
for i in range(30):
    try:
        r = urllib.request.urlopen("http://localhost:5173/", timeout=3)
        print("HTTP", r.status, "after", i, "tries"); break
    except Exception: time.sleep(1)
```

- Vite silently moves to the next free port when 5173 is taken — read the background process
  output for the actual `Local:` line instead of assuming the port.
- The page `<title>` may still be the scaffold's default (e.g. `vite-tmp`). Confirm you are on
  the right app via `package.json` / `index.html`, not the title.

## 2. Capture console + JS errors — inject the collector BEFORE navigating

A `console.log` from a `useEffect` that ran on a previous load is not replayed, so a collector
installed *after* load proves nothing. Install it with `Page.addScriptToEvaluateOnNewDocument`,
then navigate:

```python
collector = """
window.__logs = [];
['log','info','warn','error'].forEach(function(k){ var o = console[k];
  console[k] = function(){ window.__logs.push(k + ': ' + Array.prototype.map.call(arguments, function(a){
    try { return (typeof a === 'string') ? a : JSON.stringify(a); } catch(e){ return String(a); }
  }).join(' ')); return o.apply(console, arguments); }; });
window.__errors = [];
window.addEventListener('error', function(e){ window.__errors.push(String(e.message)); });
window.addEventListener('unhandledrejection', function(e){ window.__errors.push('unhandledrejection: ' + String(e.reason)); });
"""
cdp('Page.addScriptToEvaluateOnNewDocument', source=collector)
goto_url("http://localhost:5173/"); wait_for_load(); time.sleep(2)
print(js("JSON.stringify(window.__logs)"))
print(js("JSON.stringify(window.__errors)"))
```

**Prove the absence of a debug dump by quoting the capture, not by asserting it.** A cleaned-up
page yields only the React DevTools info line in `logs` and `[]` in `errors`. Paste that JSON into
REPORT.md — «дамп отсутствует» is a claim, the capture is evidence. Repeat on every route the
TASK names (home, list, detail): a stale `useEffect` dump can survive on one route only.

## 3. DOM assertions instead of screenshots

Use JS when the question is state, not appearance:

- visible text: `js("document.body.innerText")`
- form shape: map `document.querySelectorAll('input')` → `{type,id,placeholder,autocomplete}`
- navigation: map `document.querySelectorAll('a')` → `{tag,text,href}`
- real entity link by shape:
  `js("JSON.stringify(Array.from(document.querySelectorAll('a')).map(a=>a.getAttribute('href')).filter(h=>h && /^\\/stories\\/[0-9a-f-]{36}$/.test(h)))")`

**Pitfall: a loose selector verifies the wrong page.** `a[href^="/stories/"]` returns the *nav*
links (`/stories/new`, `/stories/all`) first, so «страница рассказа открылась» gets confirmed on a
list route. Match the entity's real shape (a UUID), not its route prefix.

## 4. Baseline a number before the change

For counters or behaviour a later migration might break, record the «до» value with its evidence:
the list showed 377 views for a story, its detail page showed 378 → the RPC works for an anonymous
visitor right now. That one pair is what makes the post-migration check meaningful instead of a
claim.

## 5. Screenshots only when the TASK wants visual comparison

`capture_screenshot()` prints a path — put it in the report; you inspect the image yourself, never
through a separate vision tool. Do not try to read long SQL/console text out of a phone
screenshot of a dashboard: ask for the text instead. A 968×2557 screenshot of Supabase
Authentication carries user metadata (created/confirmed/last sign-in) but can never carry a
`pg_get_functiondef` body or a policy's `USING` expression.

## 7. The deployed site is a separate target — check it, don't assume it

When a TASK hands the *user* a step like «открыть прод-URL → F5 → если 404, добавить
`vercel.json`», that check is doable from here in one call. Do it and report the evidence rather
than leaving an untested assumption in the report.

- **Deep link + reload, and read the status off the navigation entry:**
  `js("(() => { const n = performance.getEntriesByType('navigation')[0]; return n ? n.responseStatus : 'n/a' })()")`
  after `goto_url(<deep url>)`. A static host with no SPA rewrite answers **404** with its own
  error page (`404: NOT_FOUND`, no `#root`) on `/stories/<uuid>` and `/stories/all`, while `/`
  returns 200 — that pair is the evidence for the `vercel.json` decision (`rewrites` every path →
  `/index.html`; existing files are served before rewrites, so `assets/*` is safe). A rewrite only
  takes effect on the next deploy, which is the architect's push — state that the F5 check has to
  be repeated after it.
- **A 200 root that renders nothing is a failure, not a pass.** Install the console/error
  collector (§2) on the prod origin, then read `#root.children.length` and `window.__errors`.
  `Uncaught Error: supabaseUrl is required` on a Vite SPA means the host has no `VITE_*` env vars:
  the bundle throws before React mounts. Report it as a host-configuration blocker with the exact
  captured error — values come from `.env.example`/`.env.local` and never enter chat or the repo.
- **Detect a stale deploy by bundle hash**: the `/assets/index-<hash>.js` name in the served
  `index.html` versus your local `npm run build` output. If they differ, prod is an older build and
  a check against it is testing the wrong commit — say so next to the 404 finding.

## 8. Stop the server and verify the port is free

Kill the listening PID via pwsh (see SKILL.md «Stopping a background server»), then confirm the
port stopped answering before reporting it down:
`curl -s -o /dev/null -w '%{http_code}\n' --max-time 3 http://localhost:5173/` → `000` (curl exit 7)
means free.
