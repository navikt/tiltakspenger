#!/usr/bin/env node
'use strict';

/**
 * prepare-review.js
 *
 * Phase 2 of the deployment-review workflow: reveals the
 * "Godkjenn manuelt" approval form (WITHOUT clicking the final
 * "Godkjenn" button), then opens "Knytt til mål" and selects the given
 * objective/key result (WITHOUT clicking the final "Legg til" button).
 * The Tavle (board) is auto-selected when there's only one option —
 * pass --board explicitly only if your team has more than one.
 *
 * Two modes, chosen automatically:
 *
 *  - REUSE (preferred): if a scoped nda.ansatt.nav.no window is already
 *    open (created by an earlier run of this script), this script
 *    attaches to it via attachToExistingScopedSession(), optionally
 *    navigates it to <deployment-url> (pass "-" to instead act on
 *    whatever page is already loaded there — e.g. because the human
 *    navigated it themselves), performs the actions, then disconnects
 *    normally. It does NOT hold the process open in this mode — the
 *    window's lifetime is already owned by whichever process first
 *    created it (see BOOTSTRAP mode below), so this run can be a normal,
 *    short-lived, synchronous script.
 *
 *  - BOOTSTRAP (first run of a session only): if no scoped window
 *    exists yet, one is created via createScopedSession(), and — since
 *    a connectOverCDP-created context is torn down the moment its
 *    creating connection disconnects — this script then deliberately
 *    holds the CDP connection open (up to MAX_HOLD_OPEN_MS) instead of
 *    exiting, so the window stays visible for the rest of the session.
 *    This mode MUST be launched detached (e.g. `nohup ... & disown`).
 *
 * Usage:
 *   node prepare-review.js <deployment-url-or-'-'> <objective-label> [key-result-label] [cdp-port] [--board=<label>]
 *
 * First run of a session (bootstrap), must be detached:
 *   nohup node prepare-review.js "<url>" "Sikker og stabil drift" "" 9222 \
 *     > /tmp/prepare-review.log 2>&1 &
 *   disown
 *
 * Subsequent runs (reuse), can be run normally/synchronously:
 *   node prepare-review.js "<url>" "P4 kritisk funksjonalitet" "<key result>"
 *   node prepare-review.js - "Sikker og stabil drift"   # act on whatever page is currently open
 */

const { createScopedSession, attachToExistingScopedSession } = require('./lib/scoped-browser-session');
const { prepareApprovalAndGoal, assertAllowedUrl } = require('./lib/nda-deployment-review');

const MAX_HOLD_OPEN_MS = 2 * 60 * 60 * 1000; // 2 hours safety cap
const ALLOWED_HOST = 'nda.ansatt.nav.no';

async function main() {
    let boardOverride;
    const args = process.argv.slice(2).filter((a) => {
        if (a.startsWith('--board=')) {
            boardOverride = a.slice('--board='.length);
            return false;
        }
        return true;
    });
    const [url, objective, keyResult, cdpPort] = args;
    if (!url || !objective) {
        console.error(
            "Usage: node prepare-review.js <deployment-url-or-'-'> <objective-label> [key-result-label] [cdp-port] [--board=<label>]",
        );
        process.exit(1);
    }

    const cdpEndpoint = `http://localhost:${cdpPort || '9222'}`;

    let session;
    let bootstrapped = false;
    try {
        session = await attachToExistingScopedSession({ cdpEndpoint, allowedHost: ALLOWED_HOST });
        console.log('Reusing existing scoped window.');
    } catch {
        bootstrapped = true;
        session = await createScopedSession({ cdpEndpoint, allowedHost: ALLOWED_HOST });
        console.log('No existing scoped window found — created a new one (bootstrap mode).');
        if (url === '-') {
            console.error('Cannot use "-" (current page) on a brand-new window — pass a real deployment URL.');
            process.exit(1);
        }
    }

    if (url !== '-') {
        await session.page.goto(url, { waitUntil: 'networkidle', timeout: 20000 });
    } else {
        assertAllowedUrl(session.page.url());
        console.log('Acting on already-loaded page:', session.page.url());
    }

    await prepareApprovalAndGoal(session.page, {
        board: boardOverride,
        objective,
        keyResult: keyResult || undefined,
    });

    console.log('Prepared: approval form revealed, goal selection made. Waiting for human review.');
    console.log('Neither "Godkjenn" nor "Legg til" have been clicked — please review and finish manually.');

    if (bootstrapped) {
        // This connection created the window, so it owns its lifetime:
        // deliberately do NOT close/disconnect — hold the process open so
        // the window and its pending selections remain visible, up to a
        // safety cap. Requires this script to be launched detached.
        await new Promise((resolve) => setTimeout(resolve, MAX_HOLD_OPEN_MS));
        console.log('Max hold-open time reached, disconnecting.');
    } else {
        // Reusing a window owned by another (already-running) process —
        // just disconnect; the window keeps living because that other
        // process is still holding its own connection open.
        await session.close();
        console.log('Disconnected (window remains open, owned by the original session).');
    }
}

main().catch((err) => {
    console.error('ERROR:', err.message);
    process.exit(1);
});
