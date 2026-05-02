---
name: notion-dedup
description: Use before creating or updating a Notion page via notion-create-pages or notion-update-page. Searches the target database for similar pages, asks the user before creating duplicates, and applies the supersession protocol (Superseded By / Superseded At / Status=superseded) when a page is replaced.
---

<!-- Body target: <=500 lines. Link to data/ or external/ for detail. -->

# Notion Dedup

## When to Activate

Use this skill:

- Before calling `notion-create-pages` or `notion-update-page` on any project
  database.
- When the user requests a Notion-bound action such as "Notion에 올려줘",
  "Notion 문서 만들어줘", "이거 업데이트해줘" and the target is Notion.
- When starting any multi-step Notion documentation job (e.g. syncing several
  pages at once).

Do NOT activate for:

- Read-only Notion queries (`notion-search`, `notion-fetch`).
- Adding comments to an existing page.
- Non-Notion markdown work in `docs/` or other local paths.

## Workflow

1. **Search the database first.** Before creating or heavily rewriting a page,
   run at least these three searches:
   - Title keywords: the core noun(s) of the planned title.
   - Same `Feature` tag as the planned page.
   - Active pages in the same `Layer` and `Doc Type`.

   Use `notion-search` / `notion-fetch` for this. Never proceed to create
   without performing the searches.

2. **Branch on results.**
   - **0 hits → safe to create.** Proceed to step 4.
   - **≥1 hit → stop and ask the user.** Present the match(es) with id, title,
     and status. Offer exactly three options:
     1. Update the existing page (body replacement).
     2. Create a new page and mark the existing one as superseded.
     3. Keep both (only if the user can describe the scope difference in one
        sentence).

3. **Execute the chosen branch.**
   - **(1) Update:** Replace the body only. Keep title, properties, and
     relations intact. No new page. Skip to step 5 with
     `action=page_updated`.
   - **(2) Supersede:** Do ALL of the following in the same task, in order:
     1. Create the new page; capture its id.
     2. Set the old page's `Superseded By` relation to the new page.
     3. Set the old page's `Superseded At` to today's date (YYYY-MM-DD).
     4. Set the old page's `Status` to `superseded`.

     Do NOT prepend `[대체됨]` or any marker to the old title. The relation
     and status fields are the canonical signal. Title prefixes only pollute
     search results.
   - **(3) Coexist:** Only if the user supplied a one-sentence scope
     difference. Otherwise fall back to (1) or (2). Record the rationale in
     the new page body.

4. **Ensure the database has the supersession properties.** If the target
   database lacks `Superseded By` (Relation, self-referential, max 1) or
   `Superseded At` (Date), add them once. Keep them hidden from the primary
   `기능별 문서` view; expose them only in filter views.

5. **Emit an audit event.** Append to `runtime/activity-log.jsonl` via
   `scripts/hooks/post-tool-use-log.py` or equivalent:

   ```json
   {"phase":"notion_sync","action":"page_updated","project":"<name>",
    "data":{"page_id":"<id>","title":"<title>"}}
   ```

   or

   ```json
   {"phase":"notion_sync","action":"page_superseded","project":"<name>",
    "data":{"old_page_id":"<old>","new_page_id":"<new>"}}
   ```

## Trigger Examples

- "CTF 인스턴스 관리 도구 최신 운영 정리 만들어줘" → search for existing
  "CTF 인스턴스 관리 도구" pages first.
- "이 문서 Notion에 올려" → search by title and Feature tag first.
- "운영 기능 정리 업데이트해줘" → confirm the existing page, then body-replace
  without creating a new one.

## Safety

- The supersession is incomplete until **all three** old-page fields
  (`Superseded By`, `Superseded At`, `Status=superseded`) are set. Halting
  between steps leaves the next session ambiguous.
- If Notion write permission is missing or a step fails, stop immediately.
  Do not leave a half-applied state. Report which step failed.
- Never mutate `Superseded By` or `Superseded At` on an already-superseded
  page (append-only semantics match the activity log).
- If the database schema cannot accept the new properties (e.g. shared DB
  with governance restrictions), escalate to the user instead of silently
  skipping.

## Failure Signals (Retroactive Fix Triggers)

The protocol is broken if any of these are observed:

- Two or more `Status=active` pages share the same `Feature` and describe
  the same scope.
- A new page exists but the old page's `Superseded By` is empty.
- An old page's body contains a "대체됨" / "superseded" sentence while its
  `Status` remains `active`.

When spotted, apply step 3 branch (2) retroactively: set the three old-page
fields and emit a `page_superseded` audit event dated today.

## References

- `../../../docs/NOTION_DOCUMENTATION_RULES.md` — "중복 방지 프로토콜"
  section (full rationale).
- `../../../docs/RUNTIME_EVENT_SCHEMA.md` — activity-log event shape.
- `../../../scripts/search-activity-log.py` — audit command, e.g.
  `python scripts/search-activity-log.py --phase notion_sync`.
