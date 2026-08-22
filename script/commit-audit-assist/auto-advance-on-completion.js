#!/usr/bin/env node
'use strict';

/**
 * auto-advance-on-completion.js
 *
 * Polls the currently-open scoped nda.ansatt.nav.no window and, as soon
 * as the human has clicked BOTH final buttons on the current deployment
 * page ("Godkjenn" and "Legg til" — i.e. the commit is fully approved
 * AND a Mål is linked), automatically clicks "Neste" to advance to the
 * next deployment in the filtered list.
 *
 * This does NOT do any review work itself, and it never touches either
 * final submit button — it only reads state (isAlreadyApproved /
 * isGoalLinked) and, once both are already true, clicks the read-only
 * "Neste" navigation control. Ask the agent for "next" as usual once
 * you want it to actually review/prepare the (now-current) page.
 *
 * Requires a scoped window to already exist (attach/reuse only — never
 * creates or closes the window). Must be launched detached, since it
 * holds its CDP connection open for as long as you want polling to
 * continue:
 *
 *   nohup node auto-advance-on-completion.js [cdp-port] [poll-interval-ms] \
 *     > /tmp/auto-advance.log 2>&1 &
 *   disown
 *
 * Stop it whenever you like with `kill <pid>` (find the pid via
 * `pgrep -f auto-advance-on-completion.js` or your shell's job control).
 * It also stops on its own if the current page navigates away from the
 * allowed deployment-URL scope, or if there's no "Neste" control left
 * (last page of the filtered list).
 */

const { attachToExistingScopedSession } = require('./lib/scoped-browser-session');
const {
    isAlreadyApproved,
    isGoalLinked,
    goToNextDeployment,
    ALLOWED_URL_PATTERN,
} = require('./lib/nda-deployment-review');

const ALLOWED_HOST = 'nda.ansatt.nav.no';
const DEFAULT_POLL_INTERVAL_MS = 3000;

async function main() {
    const cdpPort = process.argv[2] || '9222';
    const pollIntervalMs = Number(process.argv[3]) || DEFAULT_POLL_INTERVAL_MS;
    const cdpEndpoint = `http://localhost:${cdpPort}`;

    const session = await attachToExistingScopedSession({ cdpEndpoint, allowedHost: ALLOWED_HOST });
    console.log(`Attached to existing scoped window. Polling every ${pollIntervalMs}ms.`);

    let stopping = false;
    const stop = () => {
        stopping = true;
    };
    process.on('SIGINT', stop);
    process.on('SIGTERM', stop);

    // Circuit breaker: a real human finishing a review realistically
    // takes at least some tens of seconds. If this script ever advances
    // several times in a row within a short window, that's a strong
    // signal something is wrong with detection (as happened once before
    // — see the note in lib/nda-deployment-review.js) rather than
    // genuine rapid-fire completions, so stop and let a person look.
    const recentAdvanceTimestamps = [];
    const CIRCUIT_BREAKER_COUNT = 4;
    const CIRCUIT_BREAKER_WINDOW_MS = 60000;

    while (!stopping) {
        try {
            const url = session.page.url();
            if (!ALLOWED_URL_PATTERN.test(url)) {
                console.log(`Current page is no longer in the allowed scope (${url}) — stopping.`);
                break;
            }

            const [approved, goalLinked] = await Promise.all([
                isAlreadyApproved(session.page),
                isGoalLinked(session.page),
            ]);

            if (approved && goalLinked) {
                // Double-check after a short delay before acting — cheap
                // extra protection against any remaining transient/
                // still-rendering false positive.
                await new Promise((resolve) => setTimeout(resolve, 1500));
                const [stillApproved, stillGoalLinked] = await Promise.all([
                    isAlreadyApproved(session.page),
                    isGoalLinked(session.page),
                ]);
                if (session.page.url() === url && stillApproved && stillGoalLinked) {
                    console.log(`[${new Date().toISOString()}] Finished (approved + goal linked): ${url}`);

                    const now = Date.now();
                    recentAdvanceTimestamps.push(now);
                    while (recentAdvanceTimestamps.length && now - recentAdvanceTimestamps[0] > CIRCUIT_BREAKER_WINDOW_MS) {
                        recentAdvanceTimestamps.shift();
                    }
                    if (recentAdvanceTimestamps.length >= CIRCUIT_BREAKER_COUNT) {
                        console.log(
                            `Circuit breaker tripped: advanced ${recentAdvanceTimestamps.length} times within ` +
                            `${CIRCUIT_BREAKER_WINDOW_MS / 1000}s — this is far faster than a real review, so ` +
                            `something is likely wrong with detection. Stopping without advancing further.`,
                        );
                        break;
                    }

                    try {
                        await goToNextDeployment(session.page);
                        console.log('Advanced to:', session.page.url());
                    } catch (err) {
                        console.log(`Could not advance (${err.message}) — stopping.`);
                        break;
                    }
                }
            }
        } catch (err) {
            // Transient errors (e.g. page mid-navigation) shouldn't kill
            // the whole poller — log and retry on the next tick.
            console.error('Poll error, will retry:', err.message);
        }

        await new Promise((resolve) => setTimeout(resolve, pollIntervalMs));
    }

    await session.close();
    console.log('Stopped.');
}

main().catch((err) => {
    console.error('ERROR:', err.message);
    process.exit(1);
});
