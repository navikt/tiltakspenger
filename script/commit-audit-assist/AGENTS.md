# AGENTS.md — NDA deployment-review workflow

You are an AI agent doing a **supervised** code review of deployments in
NAV's internal "NDA" tool, alongside a human who can see the same
browser window and finishes what you prepare. You never see credentials
and you never submit anything final — you only propose, the human
approves.

Read this whole file before doing anything. It is the only context you
have; nothing from any prior conversation carries over.

## Scope — what you are allowed to touch

- The browser you drive is **hard-locked** to the single hostname
  `nda.ansatt.nav.no` (enforced at the network level in
  `lib/scoped-browser-session.js` — you cannot navigate it anywhere
  else, and it does not carry the human's SSO cookies for any other
  site).
- Within that host, you may only act on pages matching:
  `https://nda.ansatt.nav.no/team/tpts/env/prod-gcp/app/<repo>/deployments/*`
  (`<repo>` may be any repo name — this is not restricted to one repo).
  All helper functions enforce this and will throw if you try anything
  else.
- **Never fetch GitHub commit content through the browser.** Always use
  the `gh` CLI (already authenticated in this environment) — this keeps
  the browser session from ever needing to leave `nda.ansatt.nav.no`.
- **Never click a final submit button** ("Godkjenn" on the manual-approval
  form, "Legg til" on the goal-linking form). The scripts below are built
  to stop just short of those on purpose — leave final submission to the
  human.

## One-time setup (per session, done by the human)

The human runs, in their own terminal, **before** you do anything:

```sh
./start-agent-session.sh
```

This launches a real, visible Chrome/Brave/Chromium window with a CDP
debug port open (default `9222`), waits for the human to log in
manually, then confirms the endpoint is reachable. If this hasn't been
done yet, ask the human to do it and tell you the CDP port (assume
`9222` if they don't say otherwise).

You do not need to run this yourself, and you never see the login.

### Optional: auto-advance poller

Once a scoped window exists (after the first `extract-review-data.js`
or `prepare-review.js` call), you may start this **once**, detached, in
the background:

```sh
nohup node auto-advance-on-completion.js [cdp-port] > /tmp/auto-advance.log 2>&1 &
disown
```

It polls the current page every few seconds and, as soon as the human
has clicked **both** final buttons ("Godkjenn" and "Legg til") on the
current deployment, automatically clicks "Neste" for them — so the page
is already on the next unreviewed deployment by the time the human asks
you to continue. This is a convenience only: it never does any review
work itself, and everything in the cycle below still applies exactly
the same whether or not it's running. Don't start a second one — check
`pgrep -af auto-advance-on-completion.js` first if unsure whether one is
already running.

It cannot falsely approve anything — it only ever clicks the read-only
"Neste" control, never a final submit button — but it does rely on
detecting the page having actually finished rendering before deciding
it's done, and has a built-in circuit breaker (stops itself if it
advances 4+ times within 60s, since that's far faster than a real human
review) as a safety net. If you ever see it behaving oddly (advancing
without the human having actually reviewed anything), kill it
immediately with `kill <pid>` and tell the human — don't try to
diagnose it silently while it keeps running.

### Optional: fully autonomous review loop

If the human asks you to keep reviewing continuously, without saying
"next" each time, use `wait-for-next-review.js` instead of stopping
after step 6 below. It blocks (cheap polling, no reasoning needed from
you) until the page shows a genuinely new, settled set of commits, then
prints that page's data (same shape as `extract-review-data.js`) and
exits 0 — call it again immediately afterwards to keep waiting. It
exits 2 on an idle timeout (nothing happened for a while — normal, just
call it again or stop and tell the human) and 1 on a hard error (stop
for real and report it). It never clicks "Neste" itself — that stays
the separate poller's job, and **the auto-advance poller above must
actually be running** or this loop will just idle-timeout forever once
a page is fully done (approved + goal linked), since nothing will ever
click "Neste" for it. It maintains its own state file
(`/tmp/tp-auto-review-state.json`) so it's safe to invoke repeatedly:

```sh
node wait-for-next-review.js [cdp-port] [poll-interval-ms] [idle-timeout-ms]
```

**One page per turn — always report to chat, then pause.** The human
needs to see every review's summary in chat to decide whether to
approve — logging alone is not enough, even in this autonomous mode.
So for each page this reports:

1. Do the review + `prepare-review.js` exactly as in steps 2–5 below.
2. Append the entry to `auto-review-log.md` in this folder as before
   (create it with a `# Auto-review log` heading if missing) — that
   file remains the durable, chronological record. Log every page,
   including "None found" ones.
3. **End your turn/response with the same summary as chat-visible
   text** (deployment id/URL, commit(s) + author, the goal you chose,
   and the findings) — do not silently continue to the next page in
   the same turn, and do not rely on the log file alone to inform the
   human.
4. Then stop and wait idle. Do not call `wait-for-next-review.js`
   again until you're explicitly told to continue — one call to
   `wait-for-next-review.js`, one review, one chat report, then pause,
   every cycle.

This applies even if you were told earlier in the same session to "keep
watching" or "review continuously" — that instruction means "don't make
me say 'next' by hand for every single page", not "skip telling me what
you found". If in doubt, report and pause rather than chaining pages.

## Per-review-cycle workflow

Repeat this cycle once per commit/deployment, **stopping after step 6
to wait for the human's go-ahead** before starting the next one (this
applies in the autonomous loop too — see above: report to chat AND log,
then pause either way).

### 1. Get the current page's data

```sh
node extract-review-data.js - [cdp-port]
```

- The literal `-` means "whatever page is currently loaded" — use this
  every time except the very first call of the whole session, when you
  don't yet know the URL (ask the human for the starting deployment URL,
  or pass it explicitly instead of `-`).
- If there is no scoped window open yet, this creates one itself
  (bootstrap) as a normal, short-lived call — no special handling
  needed for _this_ script.
- If the page it lands on is **fully done** (already approved AND goal
  linked — same "done" bar as `auto-advance-on-completion.js`), it
  auto-clicks "Neste" to advance to the next deployment in the filtered
  list and re-reads that page instead — you don't need to detect or
  handle this yourself. (Checking only "approved" here was a real bug —
  it could skip past a page a human had approved but not yet
  goal-linked, without ever surfacing the gap.)
- **Never call this a second time on a page you (or the autonomous
  loop) already logged/prepared** — even though `extractReviewData()`
  now correctly restores any pending, unsaved goal selection afterward
  (an earlier version didn't, and silently corrupted an already-correct
  selection; see `lib/nda-deployment-review.js`), re-reading an
  already-in-progress page is still unnecessary rework and briefly
  flickers the human's in-progress selection in front of them. Check
  `auto-review-log.md` (or your own memory of what you already did)
  before calling this, rather than re-reading to "double check".
- Prints JSON to stdout: `{ url, commits: [{sha, url, message, author}],
hierarchy: [{board, objectives: [{objective, keyResults}]}] }`.
  `hierarchy` is read live from the page's own dropdowns — never assume
  fixed Mål/Nøkkelresultat names; only use labels that appear in this
  output.
- `commits` may legitimately contain just **one** entry even when the
  page has no itemized "Ikke-godkjente commits" list — some deployments
  are flagged unapproved because a single squash-merged PR is missing
  an independent code review (four-eyes), not because of several listed
  commits. This is handled automatically; you don't need to special-case
  it or read the page yourself.

### 2. Filter out commits you should not review

Drop any commit whose `author` is a bot account (e.g. Dependabot). Do
not read or comment on these at all.

### 3. Read and evaluate each remaining commit via `gh`

For each commit's sha, fetch its diff (never via the browser):

```sh
gh api repos/navikt/<repo>/commits/<sha> --jq '.files[] | {filename, additions, deletions, patch}'
```

(`<repo>` comes from the deployment URL you just extracted.) Do a
**shallow** review — read the diff and the surrounding context that the
GitHub commit view itself gives you. Do **not** go spelunking through
the rest of the codebase at this stage. Look specifically for:

- obvious bugs (logic errors, off-by-one, wrong variable used, etc.)
- changes that look intentionally deceptive or hard to justify (e.g.
  something that quietly weakens a check, hides an error, or does
  something unrelated to what the commit message claims)

If there are multiple non-dependabot commits on the page, review each
one but treat them together when picking a goal in step 4 if they're
clearly part of the same piece of work.

### 4. Pick a Mål (and optionally a Nøkkelresultat)

From the `hierarchy` you already have, pick whichever `objective` best
matches what the commit(s) actually do, and a `keyResult` under it if
one clearly fits. If nothing is a good match, or you're unsure, default
to the objective **"Sikker og stabil drift"** with no specific key
result — this is the intended fallback, not a last resort to avoid.

### 5. Prepare the approval + goal link (do not submit)

```sh
nohup node prepare-review.js - "<objective-label>" "<key-result-label-or-empty>" [cdp-port] \
  > /tmp/prepare-review.log 2>&1 &
disown
```

- Use `-` here too, for the same reason as step 1 — it acts on the page
  currently loaded in the scoped window, which is exactly the page you
  just extracted data from (or the "Neste"-advanced page, if that
  happened).
- **Only launch it detached (`nohup ... & disown`) the very first time
  in a session**, when no scoped window exists yet (it will say
  "created a new one (bootstrap mode)" and needs to hold the connection
  open to keep the window alive). On every subsequent call within the
  same session it will print "Reusing existing scoped window." and exits
  normally on its own — detaching is harmless but unnecessary. If you're
  not sure whether one already ran, it's always safe to launch detached;
  just don't launch two bootstrap processes for the same CDP port.
- The Tavle (board) is picked automatically when there's only one
  option — you never need to specify it. Only pass `--board=<label>`
  (as an extra trailing argument) if the human's team has more than one
  Tavle and the script errors out asking you to disambiguate.
- This clicks "Godkjenn manuelt" (reveal only) and "Knytt til mål" +
  your selections (select only) — it does not touch either final submit
  button, by design.

### 6. Report to the human, then wait

Tell the human, concisely:

- which objective (and key result, if any) you picked
- a short summary of what the commit(s) do
- any bugs or suspicious/deceptive-looking changes you found (or
  explicitly say you found none)

Then **stop and wait** for the human to say to continue (e.g. "next")
before repeating the cycle. Do not proceed automatically — the human
needs to actually click the two final buttons in the browser first.

## Things you must never do

- Never navigate the scoped browser window to any host other than
  `nda.ansatt.nav.no` (it's blocked at the network layer anyway, but
  don't try).
- Never click "Godkjenn" (final approval) or "Legg til" (final goal
  link submit).
- Never fetch commit/file content from github.com through the scoped
  browser — use `gh`.
- Never assume a fixed board/objective/key-result label beyond the
  documented "Sikker og stabil drift" default — always read the actual
  options from the page via `extract-review-data.js`.
- Never run two `prepare-review.js` **bootstrap** invocations
  concurrently against the same CDP port (it would open a second,
  redundant scoped window). If the human says a scoped window is
  already open, trust that and use reuse-mode as normal — you don't
  need to independently verify.

## If something looks wrong

If a script errors with something like "page structure may have
changed" or a required button/element isn't found, the NDA site's HTML
likely changed since `lib/nda-deployment-review.js` was written — stop,
report the exact error to the human, and don't try to work around it by
guessing at new selectors yourself.
