"use strict";

/**
 * nda-deployment-review.js
 *
 * Shared helpers for the "review an NDA deployment's unapproved commits"
 * workflow. Built on top of scoped-browser-session.js, which already
 * restricts the agent to the nda.ansatt.nav.no origin only.
 *
 * This module adds a second, path-level restriction on top of that:
 * the agent may only act on deployment pages matching
 *   https://nda.ansatt.nav.no/team/tpts/env/prod-gcp/app/<repo>/deployments/*
 *
 * GitHub commit content is intentionally NOT fetched via the browser —
 * it is fetched separately via the `gh` CLI / GitHub API, so the browser
 * session never needs to navigate outside nda.ansatt.nav.no.
 */

const ALLOWED_URL_PATTERN =
  /^https:\/\/nda\.ansatt\.nav\.no\/team\/tpts\/env\/prod-gcp\/app\/[^/]+\/deployments\/[^/?#]+/;

function assertAllowedUrl(url) {
  if (!ALLOWED_URL_PATTERN.test(url)) {
    throw new Error(
      `Refusing to act on URL outside the allowed scope ` +
        `(https://nda.ansatt.nav.no/team/tpts/env/prod-gcp/app/<repo>/deployments/*): ${url}`,
    );
  }
}

/**
 * True if the current deployment page has no "Godkjenn manuelt" button —
 * i.e. there are no (more) unapproved commits pending manual review on
 * this page (either everything was already approved, or there simply
 * weren't any unapproved commits to begin with).
 *
 * Requires POSITIVE evidence either way — either the pending button or
 * the "Manuelt godkjent" confirmation heading must actually be present
 * — rather than treating mere *absence* of the pending button as proof
 * of approval. A page that hasn't finished rendering yet (e.g. right
 * after a client-side "Neste" navigation, before the app has hydrated
 * this section) also has neither element present, which previously
 * caused a real bug: auto-advance-on-completion.js raced straight
 * through dozens of still-unreviewed deployments because a half-loaded
 * page looked indistinguishable from an already-approved one.
 */
async function isAlreadyApproved(page) {
  assertAllowedUrl(page.url());
  const pendingButton = page.getByRole("button", { name: "Godkjenn manuelt" });
  const approvedHeading = page.getByRole("heading", {
    name: "Manuelt godkjent",
  });
  try {
    await Promise.race([
      pendingButton.first().waitFor({ state: "attached", timeout: 8000 }),
      approvedHeading.first().waitFor({ state: "attached", timeout: 8000 }),
    ]);
  } catch {
    // Neither showed up within the timeout — page may still be
    // loading, or its shape is unexpected. Don't claim "approved".
    return false;
  }
  return (await pendingButton.count()) === 0;
}

/**
 * True if the current deployment page already has a Mål linked AND
 * actually saved — i.e. the "Endringsopphav" section no longer shows
 * the placeholder "Ingen kobling til mål." text, AND the "Knytt til
 * mål" panel itself is closed (showing the final read-only summary,
 * not the open edit form). Combined with isAlreadyApproved(), this
 * detects that a human has finished BOTH final submit steps on the
 * page (see auto-advance-on-completion.js).
 *
 * The second check (panel closed) is essential and was missing in an
 * earlier version — a real bug that caused auto-advance-on-completion.js
 * (and, transitively, the continuous review loop) to advance past
 * pages the instant prepare-review.js opened the panel and made a
 * selection, well before the human clicked the final "Legg til" to
 * actually save it. Opening the panel replaces the "Ingen kobling til
 * mål." placeholder text with the live edit form (Tavle/Mål/
 * Nøkkelresultat selects + its own "Legg til" button), so checking for
 * the placeholder's absence alone is not proof anything was actually
 * saved — it's equally true the instant the panel is opened with
 * nothing chosen yet. Only the fully-closed, saved state shows the
 * read-only "Registrert av <navn>" summary instead of the form.
 *
 * Like isAlreadyApproved(), this first waits for positive evidence that
 * the "Endringsopphav" section has actually rendered, rather than
 * treating the mere absence of the placeholder text (also true on a
 * still-loading page) as proof the goal is linked.
 */
async function isGoalLinked(page) {
  assertAllowedUrl(page.url());
  try {
    await page
      .getByRole("heading", { name: "Endringsopphav" })
      .first()
      .waitFor({ state: "attached", timeout: 8000 });
  } catch {
    return false;
  }
  const unlinkedCount = await page.getByText("Ingen kobling til mål").count();
  if (unlinkedCount > 0) {
    return false;
  }
  // The placeholder is gone, but that's also true while the panel is
  // open mid-edit (unsaved). Only a fully-closed panel (no visible
  // Tavle select) means the goal is genuinely saved rather than just
  // being worked on.
  const panelOpenCount = await boardSelectLocator(page).count();
  return panelOpenCount === 0;
}

/**
 * Clicks the "Neste" (next) button/link to move from the current
 * deployment page to the next one in the filtered list, and waits for
 * the resulting navigation. Throws if no "Neste" control is found (e.g.
 * already on the last page of the filtered list).
 */
async function goToNextDeployment(page) {
  assertAllowedUrl(page.url());

  const nesteControl = page
    .getByRole("button", { name: /neste/i })
    .or(page.getByRole("link", { name: /neste/i }));
  if ((await nesteControl.count()) === 0) {
    throw new Error(
      'No "Neste" button/link found — may already be on the last page of the filtered list.',
    );
  }

  await Promise.all([
    page.waitForURL(ALLOWED_URL_PATTERN, { timeout: 20000 }).catch(() => {}),
    nesteControl.first().click(),
  ]);
  await page
    .waitForLoadState("networkidle", { timeout: 20000 })
    .catch(() => {});
  assertAllowedUrl(page.url());
  // Give the app's client-side-hydrated content a chance to actually
  // render before handing control back to a caller that may
  // immediately check isAlreadyApproved()/isGoalLinked() — networkidle
  // alone doesn't guarantee that.
  await page
    .getByRole("heading", { name: "Endringsopphav" })
    .first()
    .waitFor({ state: "attached", timeout: 10000 })
    .catch(() => {});
}

/**
 * Extracts the list of unapproved commits (from the itemized
 * "Ikke-godkjente commits (N)" alert box) and the full
 * Tavle -> Mål -> Nøkkelresultat goal hierarchy, without submitting or
 * changing anything persistent. Opens the "Knytt til mål" panel to read
 * the hierarchy (harmless client-side toggle), then leaves the page
 * alone — caller is expected to close this session normally afterwards.
 */
/**
 * Locates the Tavle (board) <select> in the "Knytt til mål" form.
 *
 * NOT `page.locator('select').first()` — the page also has an
 * always-present, normally-hidden <select name="deviation_follow_up_role">
 * belonging to an unrelated "registrer avvik" dialog elsewhere in the
 * layout. Which of the two mounts first in DOM order is a client-side
 * rendering race (observed in practice: sometimes the deviation select
 * "wins" `.first()`, especially right after `goToNextDeployment()`),
 * so `.first()` occasionally grabbed the wrong, hidden select and then
 * timed out trying to select an option on it. Scope by the board
 * select's own distinctive placeholder option ("Velg tavle…") instead,
 * which uniquely and stably identifies it regardless of DOM order.
 */
function boardSelectLocator(page) {
  return page
    .locator("select")
    .filter({ has: page.locator("option", { hasText: "Velg tavle" }) });
}

/**
 * Locates the "Avbryt" (cancel) button that belongs specifically to the
 * "Knytt til mål" panel/form — NOT `page.getByRole('button', { name:
 * 'Avbryt' })` on its own, which can also match an unrelated "Avbryt"
 * button belonging to the "Godkjenn manuelt" approval form when both
 * are open simultaneously (a very common state once prepare-review.js
 * has run). Clicking the wrong one silently left the goal panel open
 * with a corrupted selection instead of actually cancelling it. Scoped
 * to the enclosing <form> that also contains the board select, which
 * uniquely isolates the goal panel's own cancel button.
 */
function goalPanelCancelButton(page) {
  return page
    .locator("form")
    .filter({ has: boardSelectLocator(page) })
    .getByRole("button", { name: "Avbryt" });
}

/**
 * Reads just the unapproved-commit list for the current page — no side
 * effects, does not touch the "Knytt til mål" panel at all. Safe to call
 * repeatedly (e.g. every few seconds while polling for a page change) at
 * no cost to the human's in-progress goal selection.
 *
 * This is split out from extractReviewData() specifically because that
 * function's hierarchy-reading step is NOT side-effect-free — it opens
 * the goal-linking panel and cycles the board/objective/key-result
 * selects to enumerate every option, visibly changing the current
 * selection each time. Calling extractReviewData() on every poll tick
 * (as an earlier version of wait-for-next-review.js did) made the goal
 * selection flicker/reset in front of the human every few seconds.
 */
async function extractCommits(page) {
  assertAllowedUrl(page.url());

  // --- Unapproved commits list ------------------------------------------
  // The itemized box looks like:
  //   <li><a href=".../commit/<sha>">shortsha</a> - <message><br>
  //       <p class="aksel-detail">av <span>Author Name</span> • PR status</p></li>
  // Author is extracted from the <span> inside p.aksel-detail rather
  // than via text-regex, since commit messages can themselves contain
  // the Norwegian word "av" (e.g. "journalføring av innstillingsbrev"),
  // which previously caused false-positive matches.
  const commits = await page.evaluate(() => {
    const items = Array.from(document.querySelectorAll("li"));
    const results = [];
    for (const li of items) {
      const link = li.querySelector('a[href*="/commit/"]');
      if (!link) continue;

      const detailP = li.querySelector("p.aksel-detail");
      let author = null;
      if (detailP) {
        const span = detailP.querySelector("span");
        if (span) {
          // Bot authors (e.g. Dependabot) are wrapped in a tag <span>.
          author = (span.textContent || "").trim() || null;
        } else {
          // Human authors are plain text: "av <Author Name> [• PR status]".
          // Safe to regex here (unlike on the full commit message) since
          // this element only ever contains "av <author> [• ...]".
          const m = (detailP.textContent || "").match(
            /^av\s+([^•]+?)\s*(?:•|$)/,
          );
          author = m ? m[1].trim() : null;
        }
      }

      let messageText = li.textContent || "";
      if (detailP) {
        const detailText = detailP.textContent || "";
        if (messageText.endsWith(detailText)) {
          messageText = messageText.slice(
            0,
            messageText.length - detailText.length,
          );
        }
      }
      // Strip the leading "<sha> - " prefix (sha is duplicated via link.textContent).
      messageText = messageText.replace(/^\s*\S+\s*-\s*/, "").trim();

      results.push({
        sha: link.textContent.trim(),
        url: link.href,
        message: messageText,
        author,
      });
    }
    return results;
  });

  // The page shows unapproved commits in two places (a general summary
  // alert box and an itemized "Ikke-godkjente commits (N)" box), so the
  // same sha can appear twice above. Dedupe by sha, preferring whichever
  // duplicate has a resolved author and the longer message text.
  const commitsBySha = new Map();
  for (const c of commits) {
    const existing = commitsBySha.get(c.sha);
    if (!existing) {
      commitsBySha.set(c.sha, c);
      continue;
    }
    const better =
      (c.author && !existing.author) ||
      (c.author === existing.author &&
        c.message.length > existing.message.length)
        ? c
        : existing;
    commitsBySha.set(c.sha, better);
  }
  let dedupedCommits = Array.from(commitsBySha.values());

  // --- Fallback: single-PR deployment page (no itemized commits list) --
  // Some deployments are flagged unapproved for a different reason than
  // "several individually-listed unverified commits" — e.g. a single
  // squash-merged PR whose only problem is "Pull requesten har ingen
  // godkjent code review" (missing an independent reviewer, i.e. the
  // four-eyes principle). That page shows one commit via a "Commit SHA"
  // detail field and a page-title <h1> instead of an <li>-based list, so
  // the loop above finds nothing. Only kick in when there IS still an
  // unapproved commit to review (isAlreadyApproved would be false) but
  // the itemized-list scan came up empty.
  if (
    dedupedCommits.length === 0 &&
    (await page.getByRole("button", { name: "Godkjenn manuelt" }).count()) > 0
  ) {
    const fallback = await page.evaluate(() => {
      function labelValue(label) {
        const el = Array.from(document.querySelectorAll("p.aksel-detail")).find(
          (e) => e.textContent.trim() === label,
        );
        if (!el) return null;
        const link = el.parentElement?.querySelector('a[href*="github.com"]');
        return (
          (link
            ? link.textContent
            : el.parentElement?.textContent.replace(label, "")
          ).trim() || null
        );
      }

      const commitLink = document.querySelector('a[href*="/commit/"]');
      if (!commitLink) return null;

      const h1 = document.querySelector("h1");
      return {
        sha: commitLink.textContent.trim(),
        url: commitLink.href,
        message: h1 ? h1.textContent.trim() : "",
        author:
          labelValue("Merget av") ||
          labelValue("PR Opprettet av") ||
          labelValue("Deployer"),
      };
    });
    if (fallback) {
      dedupedCommits = [fallback];
    }
  }

  return dedupedCommits;
}

async function extractReviewData(page) {
  assertAllowedUrl(page.url());

  const dedupedCommits = await extractCommits(page);

  // --- Goal hierarchy (Tavle -> Mål -> Nøkkelresultat) -------------------
  const goalButton = page.getByRole("button", { name: "Knytt til mål" });
  if ((await goalButton.count()) === 0) {
    throw new Error(
      '"Knytt til mål" button not found on page — page structure may have changed.',
    );
  }
  // "Knytt til mål" is a TOGGLE, not a plain "open" button — if the
  // panel is already open (e.g. a previous prepare-review.js call left
  // it open for the human to finish), clicking it again would close it
  // instead. Only click if the board select isn't already present.
  //
  // If the panel WAS already open, that means someone (a human, or an
  // earlier prepare-review.js call) already made a real, pending,
  // unsaved selection here — this function must not disturb it. The
  // hierarchy walk below re-selects every board/objective option in
  // turn purely to enumerate what's available, which would otherwise
  // silently overwrite that in-progress selection with whatever the
  // LAST enumerated option happens to be. This is a real bug that
  // happened live: calling extract-review-data.js a second time on an
  // already-prepared page (e.g. just to "check" it) changed its goal
  // from the correct, already-logged choice to the last option in the
  // list. Capture the original selection first so it can be restored.
  const panelWasAlreadyOpen = (await boardSelectLocator(page).count()) > 0;
  let originalSelection = null;
  if (panelWasAlreadyOpen) {
    originalSelection = await page.evaluate(() => {
      const selectValue = (name) => {
        const el = document.querySelector(`select[name="${name}"]`);
        return el ? el.value : "";
      };
      const boardEl = Array.from(document.querySelectorAll("select")).find(
        (s) =>
          Array.from(s.options).some((o) =>
            o.textContent.includes("Velg tavle"),
          ),
      );
      return {
        board: boardEl ? boardEl.value : "",
        objective: selectValue("objective_id"),
        keyResult: selectValue("key_result_id"),
      };
    });
  } else {
    await goalButton.first().click();
  }
  // A fixed wait here was unreliable — the board select can take longer
  // than 500ms to mount after the click. Wait for actual positive
  // evidence (the select itself attaching) instead, with a longer
  // bounded timeout.
  await boardSelectLocator(page)
    .first()
    .waitFor({ state: "attached", timeout: 8000 });

  const boardSelect = boardSelectLocator(page);
  const boardOptions = (await boardSelect.locator("option").allTextContents())
    .map((s) => s.trim())
    .filter((s) => s && !/^velg /i.test(s));

  const hierarchy = [];
  for (const board of boardOptions) {
    await boardSelect.selectOption({ label: board });
    await page.waitForTimeout(300);

    const objectiveSelect = page.locator("select[name=objective_id]");
    const objectiveOptions = (
      await objectiveSelect.locator("option").allTextContents()
    )
      .map((s) => s.trim())
      .filter((s) => s && !/^velg /i.test(s));

    const objectives = [];
    for (const objective of objectiveOptions) {
      await objectiveSelect.selectOption({ label: objective });
      await page.waitForTimeout(300);

      const krSelect = page.locator("select[name=key_result_id]");
      const krOptions = (await krSelect.locator("option").allTextContents())
        .map((s) => s.trim())
        .filter(Boolean);

      objectives.push({ objective, keyResults: krOptions });
    }
    hierarchy.push({ board, objectives });
  }

  if (panelWasAlreadyOpen) {
    // Restore exactly what was selected before we started reading the
    // hierarchy, and leave the panel open — it's someone else's
    // pending, unsaved work, not ours to close or discard.
    if (originalSelection.board) {
      await boardSelect.selectOption({ value: originalSelection.board });
      await page.waitForTimeout(300);
    }
    if (originalSelection.objective) {
      await page
        .locator("select[name=objective_id]")
        .selectOption({ value: originalSelection.objective });
      await page.waitForTimeout(300);
    }
    if (originalSelection.keyResult) {
      await page
        .locator("select[name=key_result_id]")
        .selectOption({ value: originalSelection.keyResult });
    }
  } else {
    // We're the ones who opened it purely to read the hierarchy — safe
    // to collapse back to neutral. Scoped specifically to the goal
    // panel's own cancel button (see goalPanelCancelButton doc comment)
    // rather than the page's first "Avbryt", which can belong to the
    // separate "Godkjenn manuelt" approval form instead.
    const cancelButton = goalPanelCancelButton(page);
    if (await cancelButton.count()) {
      await cancelButton
        .first()
        .click()
        .catch(() => {});
    }
  }

  return { commits: dedupedCommits, hierarchy };
}

/**
 * Performs the real, supervised actions:
 *  - clicks "Godkjenn manuelt" to reveal the approval form
 *    (does NOT click the final "Godkjenn" button)
 *  - clicks "Knytt til mål", selects the given board/objective/key result
 *    (does NOT click the final "Legg til" button)
 *
 * Leaves the page in this pending state for a human to review and
 * finalize manually.
 */
async function prepareApprovalAndGoal(
  page,
  { board, objective, keyResult, comment, link },
) {
  assertAllowedUrl(page.url());

  // --- Reveal the manual-approval form (do not submit it) ---------------
  const approveManualButton = page.getByRole("button", {
    name: "Godkjenn manuelt",
  });
  if (await approveManualButton.count()) {
    await approveManualButton.first().click();
    await page.waitForTimeout(500);
  }

  // --- Open goal-linking form and make selections (do not submit) -------
  const goalButton = page.getByRole("button", { name: "Knytt til mål" });
  // "Knytt til mål" is a TOGGLE — only click it if the panel isn't
  // already open (e.g. extractReviewData's read of the hierarchy, or a
  // previous call, left it open), or clicking again would close it.
  if ((await boardSelectLocator(page).count()) === 0) {
    await goalButton.first().click();
  }
  // Same rationale as extractReviewData: wait for the board select to
  // actually attach instead of a fixed timeout, since it can take
  // longer than 500ms to mount and a too-short wait causes a spurious
  // "No Tavle options found" error under load.
  await boardSelectLocator(page)
    .first()
    .waitFor({ state: "attached", timeout: 8000 });

  const boardSelect = boardSelectLocator(page);
  if (board) {
    await boardSelect.selectOption({ label: board });
  } else {
    // No board given (e.g. team only has one Tavle, and its label is
    // period-specific — "Team Tiltakspenger - T1 2026" today, but that
    // changes every term) — auto-pick the (first) real option instead
    // of hardcoding a label that will go stale.
    const boardOptions = (await boardSelect.locator("option").allTextContents())
      .map((s) => s.trim())
      .filter((s) => s && !/^velg /i.test(s));
    if (boardOptions.length === 0) {
      throw new Error('No Tavle options found in the "Knytt til mål" form.');
    }
    if (boardOptions.length > 1) {
      throw new Error(
        `Multiple Tavle options found (${boardOptions.join(", ")}) — pass an explicit board to disambiguate.`,
      );
    }
    await boardSelect.selectOption({ label: boardOptions[0] });
  }
  await page.waitForTimeout(300);

  const objectiveSelect = page.locator("select[name=objective_id]");
  await objectiveSelect.selectOption({ label: objective });
  await page.waitForTimeout(300);

  if (keyResult) {
    const krSelect = page.locator("select[name=key_result_id]");
    await krSelect.selectOption({ label: keyResult });
    await page.waitForTimeout(200);
  }

  if (link) {
    await page
      .getByLabel(/^Lenke/i)
      .fill(link)
      .catch(() => {});
  }
  if (comment) {
    await page
      .getByLabel(/^Kommentar/i)
      .fill(comment)
      .catch(() => {});
  }

  // Deliberately leave both "Godkjenn" and "Legg til" un-clicked.
}

module.exports = {
  ALLOWED_URL_PATTERN,
  assertAllowedUrl,
  isAlreadyApproved,
  isGoalLinked,
  goToNextDeployment,
  extractCommits,
  extractReviewData,
  prepareApprovalAndGoal,
  boardSelectLocator,
  goalPanelCancelButton,
};
