'use strict';

/**
 * scoped-browser-session.js
 *
 * Creates an ISOLATED, ORIGIN-LOCKED Playwright browser context for a
 * supervised AI agent to drive, without ever handling the human's
 * credentials and without being able to silently reuse the human's
 * shared internal SSO session against any site other than an explicit
 * allowlist.
 *
 * Two independent layers of defense are used together, since either one
 * alone is insufficient:
 *
 *   1. Cookie scoping — only cookies that are actually valid for the
 *      allowed host (exact-domain or applicable parent-domain cookies)
 *      are copied into a brand-new, otherwise-empty browser context.
 *      Identity-provider cookies (e.g. Microsoft/Azure AD, ID-porten)
 *      are never copied, so the agent's context cannot silently
 *      re-authenticate ("SSO") into a different internal application.
 *
 *   2. Origin allowlist enforcement — every network request in the new
 *      context is intercepted; anything whose hostname does not exactly
 *      match the allowed host is aborted and logged. This is the actual
 *      enforcement boundary: even if a cookie needed by the allowed app
 *      also happens to be valid for a shared parent domain (e.g. an
 *      ingress-level "forwardauth" cookie on ".ansatt.nav.no"), the
 *      agent still cannot reach any other host, because the request
 *      itself never leaves the browser.
 *
 * All allowed and blocked requests are appended as JSON lines to an
 * audit log for after-the-fact review.
 *
 * This module does NOT use MCP — it is a plain Node.js script driven
 * via playwright-core, connecting to an already-running, already
 * human-authenticated browser over the Chrome DevTools Protocol (CDP).
 * See ../start-agent-session.sh for how that browser is started.
 */

const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright-core');

/**
 * @param {object} opts
 * @param {string} opts.cdpEndpoint   e.g. "http://localhost:9222"
 * @param {string} opts.allowedHost   exact hostname the agent may reach,
 *                                    e.g. "nda.ansatt.nav.no"
 * @param {string} [opts.auditLogPath] path to a JSONL audit log file.
 *                                     Defaults to
 *                                     "<this dir>/audit-logs/<timestamp>.jsonl"
 * @returns {Promise<{browser: import('playwright-core').Browser,
 *                     context: import('playwright-core').BrowserContext,
 *                     page: import('playwright-core').Page,
 *                     close: () => Promise<void>}>}
 */
async function createScopedSession(opts) {
    const { cdpEndpoint, allowedHost } = opts;
    if (!cdpEndpoint) throw new Error('cdpEndpoint is required');
    if (!allowedHost) throw new Error('allowedHost is required');

    const auditLogPath = opts.auditLogPath || defaultAuditLogPath();
    fs.mkdirSync(path.dirname(auditLogPath), { recursive: true });
    const auditLog = (entry) => {
        fs.appendFileSync(
            auditLogPath,
            JSON.stringify({ timestamp: new Date().toISOString(), ...entry }) + '\n',
        );
    };

    // --- Connect to the human's already-authenticated browser ------------
    const browser = await chromium.connectOverCDP(cdpEndpoint);
    const sourceContext = browser.contexts()[0];
    if (!sourceContext) {
        throw new Error('No existing browser context found at ' + cdpEndpoint);
    }

    // --- Layer 1: copy only cookies applicable to the allowed host -------
    const allCookies = await sourceContext.cookies();
    const scopedCookies = allCookies.filter((c) => cookieAppliesToHost(c.domain, allowedHost));

    auditLog({
        event: 'session_created',
        allowedHost,
        totalCookiesSeen: allCookies.length,
        cookiesCopied: scopedCookies.map((c) => ({ domain: c.domain, name: c.name })),
    });

    // Fresh, isolated context — shares nothing with the human's real profile
    // except the explicitly copied cookies above.
    // `viewport: null` disables Playwright's default fixed 1280x720
    // viewport emulation, so the page renders at the real window's
    // actual size instead of being letterboxed/framed inside it (the
    // normal behavior when attaching to a real, human-sized browser
    // window over CDP rather than a Playwright-launched headless one).
    const context = await browser.newContext({ viewport: null });

    // Marks every document loaded in this context so that a *later*,
    // independent CDP connection can positively identify this as a
    // scoped context (see attachToExistingScopedSession below) rather
    // than accidentally matching the human's real, unscoped profile
    // context purely by hostname — which would silently defeat the
    // origin-allowlist protection.
    await context.addInitScript(() => {
        window.__ndaScopedSession = true;
    });
    if (scopedCookies.length > 0) {
        await context.addCookies(scopedCookies);
    }

    // --- Layer 2: hard network-level origin allowlist ---------------------
    await context.route('**/*', (route) => {
        const url = route.request().url();
        let hostname;
        try {
            hostname = new URL(url).hostname;
        } catch {
            hostname = '';
        }

        if (hostname === allowedHost) {
            auditLog({ event: 'request_allowed', url });
            route.continue();
        } else {
            auditLog({ event: 'request_blocked', url, hostname });
            route.abort('blockedbyclient');
        }
    });

    const page = await context.newPage();

    const close = async () => {
        auditLog({ event: 'session_closed' });
        await context.close();
        await browser.close(); // disconnects only; does not kill the human's browser
    };

    return { browser, context, page, close, auditLogPath };
}

/**
 * Attaches to an ALREADY-OPEN scoped context/window (previously created
 * by createScopedSession and still held open by whatever process
 * created it) instead of creating a brand-new one — so a human can keep
 * reusing a single scoped window across an entire review session
 * (navigating it themselves between deployment pages) rather than
 * accumulating a new browser window per script invocation.
 *
 * Only reads/reuses existing state; never calls `browser.newContext()`
 * or `context.newPage()`. `close()` on the returned handle only
 * disconnects this CDP connection — it must NOT close the context,
 * since this connection didn't create it (the original creating
 * connection is what keeps it alive; see createScopedSession above and
 * the "Reusing a single scoped window" section in README.md).
 *
 * @param {object} opts
 * @param {string} opts.cdpEndpoint
 * @param {string} opts.allowedHost  used only to pick the right existing
 *                                   context/page if more than one scoped
 *                                   context happens to still be open.
 * @returns {Promise<{browser, context, page, close}>}
 * @throws if no existing scoped context/page can be found.
 */
async function attachToExistingScopedSession(opts) {
    const { cdpEndpoint, allowedHost } = opts;
    if (!cdpEndpoint) throw new Error('cdpEndpoint is required');
    if (!allowedHost) throw new Error('allowedHost is required');

    const browser = await chromium.connectOverCDP(cdpEndpoint);
    const contexts = browser.contexts();

    // Note: unlike at initial connection (where contexts()[0] is the
    // human's real default profile context), a fresh connection made
    // *after* a scoped context already exists tends to only reliably
    // enumerate the CDP-created (scoped) contexts — not the human's
    // original default profile context. So we don't assume any fixed
    // index; we scan every context/page and match by hostname AND by
    // the __ndaScopedSession marker injected via addInitScript in
    // createScopedSession, to positively rule out ever attaching to the
    // human's real, unscoped profile context even if it happens to also
    // be sitting on a page for the same host.
    let found = null;
    for (const ctx of contexts) {
        for (const p of ctx.pages()) {
            try {
                if (new URL(p.url()).hostname !== allowedHost) continue;
                const isScoped = await p.evaluate(() => window.__ndaScopedSession === true).catch(() => false);
                if (isScoped) {
                    found = { context: ctx, page: p };
                    break;
                }
            } catch {
                // ignore pages with unparsable/blank URLs (e.g. about:blank)
            }
        }
        if (found) break;
    }

    if (!found) {
        await browser.close();
        throw new Error(
            `No existing scoped browser window found for host "${allowedHost}". ` +
            `Start one first with a script built on createScopedSession() ` +
            `(e.g. prepare-review.js), or use createScopedSession() directly ` +
            `if you want a brand-new window instead.`,
        );
    }

    const close = async () => {
        // Only disconnects this CDP session. Since this connection did not
        // create the context (no newContext()/newPage() calls happened
        // here), Playwright has no reason to dispose it on close — the
        // window keeps living as long as its original creating process
        // stays connected.
        await browser.close();
    };

    return { browser, context: found.context, page: found.page, close };
}

/**
 * Determines whether a cookie set for `cookieDomain` would actually be
 * sent by a browser for requests to `host` — i.e. cookieDomain is either
 * an exact match, or a valid parent domain of host (per RFC 6265 domain
 * matching, ignoring the leading dot Chrome sometimes prepends).
 */
function cookieAppliesToHost(cookieDomain, host) {
    const d = cookieDomain.replace(/^\./, '');
    return host === d || host.endsWith('.' + d);
}

function defaultAuditLogPath() {
    const stamp = new Date().toISOString().replace(/[:.]/g, '-');
    return path.join(__dirname, '..', 'audit-logs', `session-${stamp}.jsonl`);
}

module.exports = { createScopedSession, attachToExistingScopedSession, cookieAppliesToHost };
