#!/usr/bin/env node
"use strict";

/**
 * wait-for-next-review.js
 *
 * Blocks (cheaply — no LLM involved, just polling) until the browser
 * has navigated to a genuinely NEW, not-yet-reviewed deployment page,
 * then prints that page's full review data (commits + goal hierarchy)
 * as JSON and exits 0. Meant to be called in a loop by an agent that
 * then does the actual (LLM) commit review + prepare-review.js step,
 * so the agent only "wakes up" (spends reasoning) once per real new
 * page, instead of polling itself.
 *
 * Reuses the exact same "already-approved page auto-advances" logic as
 * extract-review-data.js, so it never needs to click "Neste" itself for
 * that case — the separate, already-running auto-advance-on-completion.js
 * poller (or extractReviewData's own fallback) is what does that. This
 * script only ever performs read-only polling of the current page.
 *
 * IMPORTANT: this script deliberately never clicks "Neste" itself,
 * even when the current page is fully done (approved + goal linked).
 * An earlier version did (mirroring extract-review-data.js's own
 * "already approved -> advance" fallback), and that caused two real
 * bugs: (1) it only checked isAlreadyApproved(), not isGoalLinked() —
 * so it advanced the instant the human clicked final "Godkjenn", before
 * they'd gotten a chance to also confirm the goal link; and (2) even
 * after requiring both conditions, having TWO independent processes
 * (this one and the separate auto-advance-on-completion.js poller) each
 * race to click "Neste" once both conditions are met risked a
 * double-advance (one click succeeds, the other's in-flight click lands
 * on the already-navigated next page and skips yet another one).
 * Advancing is exclusively auto-advance-on-completion.js's job now —
 * make sure that poller is running, or nothing will ever move forward.
 * This script only ever detects the resulting page change.
 *
 * "New" is determined purely by the page's URL path (deployment id)
 * against a small state file, so it survives being invoked as a fresh
 * process each time (the intended usage pattern) — you don't need to
 * keep it running continuously yourself, and it's safe to call again
 * immediately after it just reported something.
 *
 * Deliberately does NOT factor the commit list into the "is this new"
 * signature (an earlier version did, comparing sorted shas) — the
 * commit list can transiently change or even go empty once a review is
 * underway on the SAME page (e.g. right after prepare-review.js reveals
 * the manual-approval form, which can replace/hide the itemized commit
 * box), and that was misread as "a new page appeared" even though nothing
 * had navigated. Since a given deployment URL always refers to the same
 * commit set, the URL path alone is sufficient and avoids that whole
 * class of false positives.
 *
 * A page is only treated as "new and ready" once its URL is observed
 * unchanged across two consecutive polls (a couple of seconds apart) —
 * this avoids acting on a page that's still mid-hydration right after a
 * client-side "Neste" navigation (the same class of race that
 * previously caused auto-advance-on-completion.js to misbehave; see
 * lib/nda-deployment-review.js for the full writeup).
 *
 * Usage:
 *   node wait-for-next-review.js [cdp-port] [poll-interval-ms] [idle-timeout-ms]
 *
 * Exit codes:
 *   0 — new page found; JSON printed to stdout, state file updated.
 *   1 — hard error (no scoped window, page structure changed, etc.)
 *   2 — idle timeout reached with no new page — caller should decide
 *       whether to keep waiting (call again) or stop.
 */

const fs = require("fs");
const {
  attachToExistingScopedSession,
} = require("./lib/scoped-browser-session");
const {
  extractReviewData,
  assertAllowedUrl,
  ALLOWED_URL_PATTERN,
} = require("./lib/nda-deployment-review");

const ALLOWED_HOST = "nda.ansatt.nav.no";
const STATE_FILE = "/tmp/tp-auto-review-state.json";

function readState() {
  try {
    return JSON.parse(fs.readFileSync(STATE_FILE, "utf8"));
  } catch {
    return { lastReportedPath: null };
  }
}

function writeState(state) {
  fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
}

function pathOf(url) {
  return url.split("?")[0];
}

async function main() {
  const cdpPort = process.argv[2] || "9222";
  const pollIntervalMs = Number(process.argv[3]) || 3000;
  const idleTimeoutMs = Number(process.argv[4]) || 4 * 60 * 60 * 1000; // 4h default
  const cdpEndpoint = `http://localhost:${cdpPort}`;

  let session;
  try {
    session = await attachToExistingScopedSession({
      cdpEndpoint,
      allowedHost: ALLOWED_HOST,
    });
  } catch (err) {
    console.error("No existing scoped window found:", err.message);
    process.exit(1);
  }

  const state = readState();
  const startedAt = Date.now();
  let previousTickPath = null;

  try {
    while (true) {
      if (Date.now() - startedAt > idleTimeoutMs) {
        console.error(
          `Idle timeout (${idleTimeoutMs}ms) reached with no new page — caller should decide whether to keep waiting.`,
        );
        process.exit(2);
      }

      const url = session.page.url();
      if (!ALLOWED_URL_PATTERN.test(url)) {
        console.error(
          `Current page is no longer in the allowed scope (${url}).`,
        );
        process.exit(1);
      }
      assertAllowedUrl(url);

      // Cheap check on every poll tick: just the URL path, no DOM
      // reads at all. Do NOT call extractReviewData() here (opens
      // the "Knytt til mål" panel — visibly flickers the human's
      // goal selection) nor rely on the commit list for "is this
      // new" (it can transiently change/empty out once a review is
      // already underway on this same page, e.g. right after
      // prepare-review.js reveals the manual-approval form — see
      // this file's top doc comment for the full story).
      //
      // This script NEVER clicks "Neste" itself, even if the
      // current page is fully done (approved + goal linked) — see
      // the top doc comment for why. It only waits for the URL to
      // actually change, which happens once the separate
      // auto-advance-on-completion.js poller does its job.
      const currentUrl = session.page.url();
      const currentPath = pathOf(currentUrl);

      if (
        currentPath !== state.lastReportedPath &&
        currentPath === previousTickPath
      ) {
        // Stable across two consecutive polls, and genuinely a
        // different deployment than the last one we already
        // reported — safe to report as ready. Only NOW do the
        // one-time, more expensive full read (commits + goal
        // hierarchy), since we're about to hand this off for
        // real review.
        const data = await extractReviewData(session.page);
        state.lastReportedPath = currentPath;
        writeState(state);
        console.log(JSON.stringify({ url: currentUrl, ...data }, null, 2));
        process.exit(0);
      }

      previousTickPath = currentPath;
      await new Promise((resolve) => setTimeout(resolve, pollIntervalMs));
    }
  } finally {
    await session.close();
  }
}

main().catch((err) => {
  console.error("ERROR:", err.message);
  process.exit(1);
});
