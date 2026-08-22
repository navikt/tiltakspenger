# commit-audit-assist

Startup automation for a supervised browser session where an AI agent
performs UI tasks in an authenticated web application alongside a human
user, without the agent ever handling credentials.

## How it works

1. `start-agent-session.sh` launches Chrome with `--remote-debugging-port`
   and a persistent `--user-data-dir`, so the profile (and login) survives
   restarts.
2. The human logs in **manually** in the opened browser window — the
   script blocks and waits for confirmation before continuing.
3. Once confirmed, the script checks the Chrome DevTools Protocol (CDP)
   endpoint is reachable and lists open tabs as a sanity check.
4. The script prints a reminder to point the agent at `AGENTS.md` in
   this folder to start the review workflow.

Because the agent only attaches _after_ the human has authenticated, it
never sees or handles credentials — it only drives the DOM of an
already-authenticated session via CDP.

## Quick start

```sh
./start-agent-session.sh          # 1. launch browser, log in manually
```

Then tell your AI agent to read `AGENTS.md` in this folder and start the
review workflow. That file is the complete, self-contained instruction
set for the agent — it has everything it needs without any prior
conversation context, which is the whole point: any of your team can
hand a fresh LLM session this one file and get the same workflow.

## Usage

```bash
./start-agent-session.sh [start_url]
```

Optional env vars:

| Var           | Default          | Purpose                                                              |
| ------------- | ---------------- | -------------------------------------------------------------------- |
| `CDP_PORT`    | `9222`           | Remote debugging port (never use `8085` — reserved for `nais login`) |
| `PROFILE_DIR` | auto (see below) | Persistent browser profile dir                                       |
| `CHROME_BIN`  | auto-detected    | Override the Chrome/Chromium/Brave binary path                       |

### Snap-packaged browsers (Brave, Chromium on Ubuntu)

When the detected browser is installed as a **snap** (e.g. `/snap/bin/brave`),
its AppArmor confinement silently blocks writing a custom `--user-data-dir`
to arbitrary paths like `$HOME/.cache/...` — it fails with
`Permission denied` (or falls back to the snap's own default profile and
collides with an already-running instance). The script detects this and
defaults `PROFILE_DIR` to `$HOME/snap/<snap-name>/current/agent-browser-profile`
instead, which snap always grants write access to. Only set `PROFILE_DIR`
yourself if you need to override this.

## Non-authenticated sites

The agent can open additional tabs/contexts in the same CDP-attached
browser for unauthenticated research (e.g. `context.newPage()` in
Playwright), without any impact on the authenticated session's cookies.

## Driving the authenticated app: `lib/scoped-browser-session.js`

For tasks where the agent needs to act _inside_ an authenticated internal
app (e.g. a code-review tool), do **not** hand the agent your full,
already-authenticated browser context directly. Because internal apps
often share SSO/forward-auth cookies across a parent domain (e.g.
`.ansatt.nav.no`), an agent with unrestricted access to that context
could silently reuse your session to reach _other_ internal sites you
never intended it to touch.

`lib/scoped-browser-session.js` guards against this with two independent
layers, deliberately not relying on either alone:

1. **Cookie scoping** — only cookies that are actually valid for the one
   allowed hostname are copied into a brand-new, otherwise-empty browser
   context. Identity-provider cookies (Microsoft/Azure AD, ID-porten,
   etc.) are never copied, so the agent's context cannot use them to
   silently re-authenticate elsewhere.
2. **Origin allowlist enforcement** — every network request in that new
   context is intercepted via `context.route()`; anything whose hostname
   isn't an exact match for the allowed host is aborted. This is the
   real enforcement boundary: even a cookie that happens to be valid for
   a shared parent domain can't be leveraged, because the request itself
   never leaves the browser.

Every allowed and blocked request, plus which cookies were copied, is
appended as JSON lines to an audit log (default:
`audit-logs/session-<timestamp>.jsonl`, gitignored) for after-the-fact
review.

### Example usage

```js
const { createScopedSession } = require("./lib/scoped-browser-session");

(async () => {
  const session = await createScopedSession({
    cdpEndpoint: "http://localhost:9222",
    allowedHost: "nda.ansatt.nav.no",
  });

  await session.page.goto("https://nda.ansatt.nav.no/");
  // ... drive the page: session.page.click(...), session.page.fill(...), etc.

  await session.close(); // disconnects only — does not close your browser
})();
```

Note: a strict single-host allowlist also blocks legitimate third-party
subresources (e.g. a CDN-hosted font) if the app loads any — this is
expected and visible in the audit log as `request_blocked` entries; the
app will still function, just without those specific assets.

## NDA deployment-review workflow

Built on top of the scoped session above, `lib/nda-deployment-review.js`
adds a **second, path-level restriction**: the agent will refuse to act
on any URL that doesn't match

```
https://nda.ansatt.nav.no/team/tpts/env/prod-gcp/app/<repo>/deployments/*
```

GitHub commit content is deliberately **never fetched via the browser**
— it's read separately via the `gh` CLI, so the browser session never
needs to leave `nda.ansatt.nav.no`.

The workflow is split into two phases, and each phase's script supports
two window-lifecycle modes so a whole review session (many commits) can
share **one single browser window** instead of accumulating a new one
per script call:

- **REUSE** (the normal case, from the second call onwards): the script
  attaches to an already-open scoped window (`attachToExistingScopedSession`)
  and disconnects normally when done — no special invocation needed.
- **BOOTSTRAP** (only the very first call in a session, when no scoped
  window exists yet): the script creates the window itself and, because
  a `connectOverCDP`-created context is torn down the instant its
  creating connection disconnects, deliberately **holds that connection
  open** (up to a 2h safety cap) instead of exiting. **This call must be
  launched detached** (`nohup ... & disown`) or the window will close
  immediately.

Both scripts accept `-` as the URL argument to mean "whatever page is
currently loaded in the scoped window" (e.g. because the human navigated
it themselves, or because the previous call already moved it there) —
pass a real URL only for the very first navigation of a session.

### Phase 1 — read-only extraction

```sh
node extract-review-data.js "<deployment-url-or-'-'>" [cdp-port]
```

Navigates to the deployment page (or reads whatever page is already
loaded, if `-`) and prints JSON with:

- `url`: the page actually read (useful after an auto-advance, below).
- `commits`: the unapproved commit(s) for this page (sha, GitHub
  commit URL, author, message) — deduped, since the page repeats each
  commit in two separate boxes. Handles both page shapes NDA uses for
  "unapproved": the itemized "Ikke-godkjente commits (N)" list (several
  commits), and a single squash-merged PR flagged only because
  "Pull requesten har ingen godkjent code review" (missing an
  independent reviewer / four-eyes) — in that second shape there's no
  `<li>`-based list at all, so a fallback reads the single commit from
  the page's own "Commit SHA" detail field, `<h1>` title, and
  "Merget av"/"PR Opprettet av" fields instead.
- `hierarchy`: the full Tavle → Mål → Nøkkelresultat option tree, read
  dynamically from the "Knytt til mål" selects (not hardcoded, since the
  available goals/key-results — and even the Tavle's own name, which is
  period-specific, e.g. "...- T1 2026" — change over time).

If the page is already fully approved (no "Godkjenn manuelt" button),
`extract-review-data.js -` auto-clicks **"Neste"** to advance to the
next page in the filtered list and reads _that_ one instead, rather than
returning an empty result.

Nothing is submitted here. If this call had to bootstrap a brand-new
window (no scoped window existed yet), it closes that window normally
when done — extraction never needs to persist state, so it doesn't need
the hold-open/detach dance that Phase 2 does.

From here (in conversation, not in a script), for each non-dependabot
commit: fetch its diff via `gh api repos/navikt/<repo>/commits/<sha>`,
do a shallow read of the change (no deep codebase dive) looking for
obvious bugs or deceptively-crafted edits, then pick the best-matching
Mål (and optional Nøkkelresultat) from the extracted hierarchy —
defaulting to **"Sikker og stabil drift"** if nothing else is a clearly
better match. The full rules for this are in `AGENTS.md`, not repeated
here.

### Phase 2 — prepare, don't submit

```sh
# First call in a session (bootstrap) — must be detached:
nohup node prepare-review.js "<deployment-url>" "<objective-label>" \
  "<key-result-label-or-empty>" [cdp-port] > /tmp/prepare-review.log 2>&1 &
disown

# Every later call in the same session (reuse) — runs normally:
node prepare-review.js - "<objective-label>" "<key-result-label-or-empty>" [cdp-port]
```

This:

1. Clicks **"Godkjenn manuelt"** to reveal the approval form — does
   **not** click the final "Godkjenn" button.
2. Clicks **"Knytt til mål"** and selects the objective/key result —
   does **not** click the final "Legg til" button. The Tavle (board) is
   auto-picked when the form only offers one option; pass an explicit
   `--board=<label>` argument only if your team has more than one and
   the script asks you to disambiguate.
3. In bootstrap mode only: deliberately keeps the CDP connection open
   (up to a 2h safety cap) instead of exiting, since exiting would
   otherwise silently close the window and lose all the
   filled-in-but-unsubmitted state. In reuse mode, it just disconnects —
   the window stays open because the original bootstrap process is
   still holding its connection.

The human reviews the prepared state in the visible browser window and
manually clicks the two final buttons ("Godkjenn" and "Legg til") when
satisfied; nothing is auto-submitted by design.

### Optional: `auto-advance-on-completion.js`

```sh
nohup node auto-advance-on-completion.js [cdp-port] [poll-interval-ms] \
  > /tmp/auto-advance.log 2>&1 &
disown
```

Polls the currently-open scoped window (attach/reuse only — never
creates or closes it) and, once the human has clicked both final
buttons on the current page (detected via `isAlreadyApproved()` and
`isGoalLinked()`), automatically clicks "Neste" to move to the next
deployment. Pure convenience: it never touches either final submit
button itself, only the read-only "Neste" navigation, once both are
already done. Stop it with `kill <pid>` (`pgrep -af
auto-advance-on-completion.js` to find it) — it also stops on its own if
the page leaves the allowed scope, there's no more "Neste" to click, or
its circuit breaker trips (see below).

**Detection requires positive evidence, not just absence of the pending
state.** `isAlreadyApproved()` waits for either the "Godkjenn manuelt"
button or the "Manuelt godkjent" confirmation heading to actually be
present; `isGoalLinked()` waits for the "Endringsopphav" section to
render before checking whether it still shows the "Ingen kobling til
mål." placeholder. This matters because a page that's still
loading/hydrating right after a "Neste" click also has neither the
pending button nor the placeholder yet — treating that absence alone as
"done" caused a real bug where the poller raced through dozens of
still-unreviewed deployments in seconds. `goToNextDeployment()` also now
waits for the "Endringsopphav" heading to attach before returning, and
the poller double-checks (with a short delay) before acting, plus trips
a circuit breaker (stops itself) if it ever advances 4+ times within 60
seconds — a real human review realistically takes much longer than
that, so a burst that fast means something is wrong with detection
again and needs a person to look, not more auto-advancing.

**Nothing unsafe happens even if this misfires** — the poller only ever
clicks "Neste" (pure navigation), never a final submit button, so a
false "advance" cannot fake an approval; worst case is it scrolls past
some still-unreviewed deployments in the UI, which then need a manual
`extract-review-data.js "<url>"` visit to pick back up.

## Onboarding a fresh agent / another developer

`AGENTS.md` in this folder is the single, self-contained instruction
file meant to be handed to a brand-new LLM session with zero prior
context — it encodes the scope restrictions, the ignore-dependabot rule,
the default-goal fallback, the don't-submit-final-buttons rule, the
`gh`-CLI-only commit-reading rule, and the exact per-cycle workflow
(including the reuse/bootstrap distinction and the wait-for-go-ahead
behavior between commits). If you change any of that behavior in the
scripts below, update `AGENTS.md` to match.

This tool already generalizes across:

- **repo**: the URL pattern only fixes `team/tpts/env/prod-gcp`, not the
  `<repo>` segment — any repo under that team/env works unmodified.
- **Tavle (board) name**: auto-detected from the page's own dropdown
  rather than hardcoded, so it keeps working as the board's name changes
  each term.

It does **not** yet generalize across:

- **team/env**: `tpts`/`prod-gcp` are hardcoded in
  `lib/nda-deployment-review.js`'s `ALLOWED_URL_PATTERN` — a developer
  on a different team/env would need to edit that regex.
- **local browser setup**: `start-agent-session.sh`'s snap-confinement
  detection was built and tested against a snap-installed Brave on
  Ubuntu; it should safely no-op on a non-snap install (falls back to
  `$HOME/.cache/agent-browser-profile`), but that fallback path hasn't
  been exercised on another machine.
