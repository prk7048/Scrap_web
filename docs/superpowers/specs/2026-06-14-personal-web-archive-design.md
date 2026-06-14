# Personal Web Archive Design

Date: 2026-06-14

## Goal

Build a personal web archive that collects saved links from scattered places, preserves readable copies before pages disappear, makes them searchable, and gradually organizes them with AI.

The first product should be useful as a standalone web app. OpenClaw should integrate later as a chat-based operator that calls the app through limited APIs, not as the core storage or processing engine.

## Problem

Saved articles and links are scattered across browser bookmarks, KakaoTalk "send to myself", YouTube saved lists, and the FM Korea site save area. Some saved content later disappears. Even when content remains available, it is hard to find, classify, and revisit across many topics.

The system should solve four problems:

1. Capture links quickly from multiple entry points.
2. Preserve page content deeply enough that deleted pages remain usable.
3. Search and browse saved content by topic, status, text, source, and date.
4. Use AI to classify, summarize, and recommend content without making the whole app dependent on an autonomous agent.

## Product Shape

The app is a personal web application accessed from a browser. It should run locally during early use and later run 24/7 on an Ubuntu machine or home server through Docker Compose.

Remote access should use Tailscale rather than exposing the service directly to the public internet. The app should still have its own single administrator account with long-lived login sessions.

### Main Screen

The main screen is centered on viewing saved content.

- Top area: global search and a URL save button.
- Left sidebar: an AI-generated topic tree.
- Center area: AI-recommended article cards by default.
- Category mode: clicking a topic in the left sidebar replaces the recommendation feed with the saved items in that topic.
- Status visibility: cards should show capture, classification, summary, and failure states.

The topic tree should feel like an AI-generated interest map, not a manually maintained folder system. The user can approve, rename, merge, or delete proposed topics.

### Recommendation Feed

The central recommendation feed should use newsfeed-like cards.

Each card should include:

- Title
- Source
- Saved date
- Short summary
- AI recommendation reason
- Topic and tag labels
- Processing status
- Quick actions such as open, archive, hide from recommendations, or retry failed capture

The recommendation criteria can combine recent saves, stale but important items, topic continuity, related items, and AI judgment.

### Detail Screen

The item detail screen should use tabs:

- Body: cleaned extracted text for reading.
- Original: saved HTML snapshot.
- Snapshot: screenshot and PDF when available.
- AI: summary, tags, recommendation reason, and related items.
- Meta: original URL, normalized URL, source, saved time, processing status, and failure logs.

Notes and highlights are out of scope for the first version. They should be considered after preservation and search are reliable.

## Capture Sources

The app should eventually support:

- In-app single URL save.
- Multi-URL paste.
- Chrome/Edge extension for saving the current page.
- Browser bookmark file import.
- KakaoTalk text paste with URL extraction.
- YouTube saved-list import.
- FM Korea saved-area import.
- OpenClaw command-based save.

The MVP should include:

- In-app single URL save.
- Multi-URL paste.
- Chrome/Edge extension for saving the current page.
- URL normalization and duplicate prevention.
- Capture queue and retry support.

Bookmark import and KakaoTalk URL extraction should follow soon after the MVP. YouTube saved-list import and FM Korea saved-area import should be later dedicated integrations.

## Capture And Preservation Flow

All capture sources should converge on a single `save_url` pipeline.

1. Receive a URL.
2. Normalize the URL.
3. Resolve redirects where practical.
4. Check for duplicates by normalized URL.
5. Create or return an item in the inbox.
6. Enqueue background processing.
7. Fetch metadata.
8. Extract readable body text.
9. Save the original HTML snapshot.
10. Capture a screenshot.
11. Generate or store a PDF when useful.
12. Run lightweight AI classification and summary tasks.
13. Auto-classify high-confidence items.
14. Move low-confidence items to the classification-needed state.
15. Make processed items eligible for the recommendation feed.

The user-facing save action should return quickly. Expensive work should run in the background.

## Preservation Policy

General web pages should store:

- Original URL
- Normalized URL
- Title
- Source/domain
- Saved timestamp
- Metadata
- Extracted body text
- Original HTML snapshot
- Screenshot
- PDF when useful or when other preservation methods fail

Community posts should preserve body text, relevant comments when feasible, HTML, and screenshot. Site-specific handling can improve over time.

YouTube items should not store video files. They should store:

- URL
- Title
- Channel
- Thumbnail
- Description
- Transcript or captions when available
- Summary

PDF and document items should store the original file and extracted text.

## Failure Handling

Failure handling is a core requirement.

If full capture fails, the app should retain the best available partial result. A URL-only item is still better than losing the save.

Failure states should include:

- Metadata fetch failed
- Body extraction failed
- HTML snapshot failed
- Screenshot failed
- PDF generation failed
- AI processing failed
- Site requires login or special handling

The app should include a failed-saves view with:

- Failure reason
- Last attempt time
- Retry action
- Processing log summary

The preservation fallback order should be:

1. Metadata and URL.
2. Extracted text.
3. HTML snapshot.
4. Screenshot.
5. PDF.

This order describes attempts, not strict dependencies. The system should keep whichever artifacts succeed.

## Duplicate Handling

The MVP duplicate policy is simple: the same normalized URL should create only one item.

Normalization should remove common tracking parameters, normalize trailing slashes where safe, and resolve short links to final URLs when practical. YouTube URL variants should normalize to a canonical video URL when possible.

If a user saves an already saved URL, the app should show the existing item and update a last-seen or save-attempt timestamp. Version history for changed pages is out of scope for the first version.

## Data Model

The core entity is `Item`.

An item should store:

- ID
- Original URL
- Normalized URL
- Source/domain
- Title
- Description
- Saved timestamp
- Last processed timestamp
- Capture status
- Classification status
- AI summary
- AI recommendation reason
- Readable body text
- Topic IDs
- Tag IDs
- Artifact references

Artifacts should be stored on the filesystem rather than inside the database. The database should store artifact metadata and paths.

Artifact types include:

- HTML snapshot
- Screenshot image
- PDF
- YouTube transcript
- Original PDF or document file
- Extracted text file when useful

The first deployment should use Postgres for metadata and search. Files should live under a structured local data directory.

## Search

First-version search should cover:

- Title
- URL
- Body text
- Source/domain
- Saved date
- Topic
- Tag
- Processing status
- Failure status

Postgres full-text search is sufficient for the first version. Semantic search, natural-language search, and RAG should be added after the basic archive is reliable.

## AI Behavior

AI should assist organization but not be required for core preservation.

AI tasks include:

- Summary generation
- Topic and tag suggestion
- Auto-classification with confidence
- Low-confidence classification queueing
- Related-item discovery
- Recommendation feed generation

Processing policy:

- Immediate: metadata extraction, body extraction, basic topic candidates.
- Deferred: summary, tags, duplicate hints, relatedness hints.
- Nightly: embeddings, topic clustering, recommendation recalculation.
- Manual: user-requested reports, topic digests, and deeper analysis.

The system should support both local models and external AI APIs through configuration. Sensitive or high-volume work can use local models; higher-quality summaries or complex reasoning can use external providers.

## OpenClaw Role

OpenClaw should be an operator layer, not the app's core.

The archive app should expose limited APIs that OpenClaw can call. OpenClaw should not access the database or data directory directly.

Initial OpenClaw-oriented commands can include:

- `save_url`
- `recommend_today`
- `retry_failed`
- `classify_inbox`
- `summarize_week`

OpenClaw is well suited for chat-based operation from mobile or messaging channels. The archive app remains the source of truth for storage, processing, permissions, and logs.

This design follows OpenClaw's documented shape as a self-hosted gateway for messaging channels, sessions, tool use, and agent routing: https://docs.openclaw.ai/

## Authentication And Access

Remote access should be through Tailscale. The application should also require a single administrator login.

The first version should support:

- One administrator account.
- Password login.
- Long-lived sessions.
- Logout.
- Session invalidation from the admin settings page.

Device registration is intentionally out of scope because it adds friction when using new devices.

## Backup

Automatic backup is required from the first version.

The first backup target is a local backup folder. Later versions can sync that folder to NAS, cloud storage, or another machine.

Backups should include:

- Postgres database dump.
- File artifact directory.
- App configuration.
- Backup manifest.

The app should show backup success, failure, last run time, and retained backup count. The first retention policy should keep the most recent N backups, configurable by the administrator.

## Technical Architecture

Recommended stack:

- Frontend: Vite React.
- Backend: Python FastAPI.
- Worker: Python worker process using a Postgres-backed job table for the MVP.
- Browser capture: Playwright.
- Database: Postgres.
- File storage: local data directory.
- Deployment: Docker Compose.
- Remote access: Tailscale.
- Browser extension: Chrome/Edge extension calling the backend API.
- AI: configurable local and external providers.

The system should be split into these components:

- Web frontend
- Backend API
- Capture worker
- AI worker
- Database
- File artifact store
- Browser extension
- Backup job
- Later OpenClaw integration

## MVP Scope

The MVP must include:

- Single administrator login.
- In-app single URL save.
- Multi-URL paste.
- Chrome/Edge extension for current-page save.
- URL normalization.
- Duplicate prevention by normalized URL.
- Capture queue.
- Body text extraction.
- HTML snapshot storage.
- Screenshot storage.
- Failure state tracking and retry.
- Saved item list.
- Initial AI topic tree.
- Initial AI recommendation card feed.
- Basic keyword and filter search.
- Local backup folder with scheduled backup.

The MVP may use simple versions of AI classification and recommendation, but the UI should be shaped around the long-term model: topic tree on the left, recommendation feed in the center, and item detail tabs.

## Post-MVP Scope

Post-MVP features:

- Bookmark HTML import.
- KakaoTalk text paste URL extraction.
- YouTube saved-list import.
- FM Korea saved-area import.
- YouTube transcript and summary improvements.
- Semantic search.
- RAG over the archive.
- OpenClaw command API.
- Notes and highlights.
- Page version history.
- NAS and cloud backup integrations.
- Advanced storage cleanup and artifact size controls.

## Non-Goals For The First Version

The first version should not include:

- Multiple user accounts.
- Public internet exposure without Tailscale.
- Device registration.
- Notes and highlights.
- Video file storage for YouTube.
- Full automatic import from every source.
- Page version history.
- A fully autonomous OpenClaw-managed archive.

## Success Criteria

The first version is successful when:

1. A user can save one or many URLs quickly.
2. The system preserves enough content that a deleted page remains readable.
3. Failed saves are visible and retryable.
4. Saved items are searchable by title, URL, body text, topic, source, date, and status.
5. The main screen shows saved content with a usable topic tree and recommendation cards.
6. A Chrome or Edge extension can save the current page.
7. Backups run automatically to a local backup folder.
8. The app can run locally during development and be moved to Ubuntu with Docker Compose.
