#!/usr/bin/env node
"use strict";

/**
 * extract-review-data.js
 *
 * Phase 1 of the deployment-review workflow: prints the unapproved-
 * commit list and full Tavle/Mål/Nøkkelresultat goal hierarchy for a
 * deployment page as JSON. Nothing is submitted or persisted.
 *
 * Prefers reusing an already-open scoped nda.ansatt.nav.no window
 * (attachToExistingScopedSession) over creating a new one — pass "-"
 * as the URL to act on whatever page is already loaded there (e.g.
 * because the human navigated it themselves), or pass a real URL to
 * navigate the reused window there first. If no scoped window exists
 * yet, falls back to a throwaway createScopedSession() that is closed
 * normally when done (safe, since extraction never needs to persist
 * state) — "-" cannot be used in that fallback case.
 *
 * Usage:
 *   node extract-review-data.js <deployment-url-or-'-'> [cdp-port]
 */

const {
  createScopedSession,
  attachToExistingScopedSession,
} = require("./lib/scoped-browser-session");
const {
  extractReviewData,
  assertAllowedUrl,
  isAlreadyApproved,
  isGoalLinked,
  goToNextDeployment,
} = require("./lib/nda-deployment-review");

const ALLOWED_HOST = "nda.ansatt.nav.no";

async function main() {
  const url = process.argv[2];
  const cdpPort = process.argv[3] || "9222";
  if (!url) {
    console.error(
      "Usage: node extract-review-data.js <deployment-url-or-'-'> [cdp-port]",
    );
    process.exit(1);
  }

  const cdpEndpoint = `http://localhost:${cdpPort}`;
  let session;
  try {
    session = await attachToExistingScopedSession({
      cdpEndpoint,
      allowedHost: ALLOWED_HOST,
    });
  } catch {
    if (url === "-") {
      console.error(
        'No existing scoped window found, and "-" (current page) needs one. Pass a real deployment URL instead.',
      );
      process.exit(1);
    }
    session = await createScopedSession({
      cdpEndpoint,
      allowedHost: ALLOWED_HOST,
    });
  }

  try {
    if (url !== "-") {
      await session.page.goto(url, {
        waitUntil: "networkidle",
        timeout: 20000,
      });
    } else {
      assertAllowedUrl(session.page.url());
      // If the current page is FULLY done (both approved AND goal
      // linked — the same "done" bar auto-advance-on-completion.js
      // uses), auto-advance to the next page in the filtered list
      // rather than re-reading a page with nothing left to do.
      // Checking isAlreadyApproved() alone here was a real bug: a
      // human can click "Godkjenn" and step away before linking a
      // Mål, and this call would then silently skip past that page
      // without ever surfacing the still-missing goal link.
      const [approved, goalLinked] = await Promise.all([
        isAlreadyApproved(session.page),
        isGoalLinked(session.page),
      ]);
      if (approved && goalLinked) {
        console.error(
          'Current page already approved and goal-linked — clicking "Neste" to advance.',
        );
        await goToNextDeployment(session.page);
        console.error("Advanced to:", session.page.url());
      }
    }
    const data = await extractReviewData(session.page);
    console.log(JSON.stringify({ url: session.page.url(), ...data }, null, 2));
  } finally {
    // session.close() is already the correct behavior for either case:
    // disconnect-only when reused (window is owned elsewhere), or a
    // full close when this connection created its own throwaway window.
    await session.close();
  }
}

main().catch((err) => {
  console.error("ERROR:", err.message);
  process.exit(1);
});
