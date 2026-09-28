# ROB-5 Vite preview requirements

## App location and runtime

The frontend lives in `frontend/` as a standalone React + TypeScript application
served by Vite. It owns its package manifest, TypeScript settings, Vite config,
source files, and public preview assets. It must not require the Python backend to
start or render the ROB-5 review screen.

From the repository root:

```bash
cd frontend
npm install
npm run dev
```

The development server binds to `127.0.0.1` and uses Vite's default port `5173`.
The review page is available at `http://127.0.0.1:5173/`. A host override may be
passed through Vite when the preview needs to be opened outside the local machine.

## Fixture loading

The checked-in source of truth remains `fixtures/manifest.v1.json`. Vite exposes
it to the frontend through a development-only alias named `@fixture/manifest`.
The application imports the JSON through that alias so there is one fixture to
maintain and no copied contract data under `frontend/`.

The frontend defines a TypeScript `VideoManifest` type matching the v1 Pydantic
contract and validates the small set of runtime invariants required for safe
rendering. The fixture itself remains unchanged.

## Local media adapter

The fixture contains API-relative production media URLs. When the frontend is
running in fixture-preview mode and a URL matches the fixture video source route,
the client resolves it to `/demo/warehouse-walkthrough.mp4`. Other URLs remain
unchanged. This mapping belongs in a single preview adapter; components receive a
normal playable URL and do not branch on fixture IDs.

The local asset is a clearly synthetic preview clip checked in at:

```text
frontend/public/demo/warehouse-walkthrough.mp4
```

It is 60 seconds long so the media clock matches the fixture's score domain. The
clip should be small enough for repository use, contain no private or licensed
footage, and include a visible `Fixture preview` marker. It illustrates warehouse
motion and timeline position; it does not claim to depict the events described by
the analysis prompts.

Evidence-frame URLs are not resolved in ROB-5 because evidence cards belong to
ROB-6.

## Configuration boundary

- Fixture mode is the default for the standalone ROB-5 preview.
- A future API mode may load a manifest URL and use its media URLs directly.
- The media adapter changes URL resolution only; it never edits IDs, timestamps,
  scores, preset details, or schema version.
- Vite serves source modules and local public assets. It does not mock job or
  upload endpoints.

## Missing-media behavior

If the local clip is missing or cannot be decoded, the page still renders the
fixture metadata and score timeline. The video frame shows `Preview video
unavailable`, names the expected local asset, and offers one reload action. It
must not substitute unrelated remote footage or imply that the score series was
calculated from another clip.

## Implementation deliverables

- `frontend/package.json` with React, React DOM, TypeScript, and Vite scripts.
- TypeScript/Vite configuration scoped to `frontend/`.
- The v1 manifest type and fixture loader.
- A single fixture media URL adapter.
- A compact 60-second local preview clip.
- README instructions for starting the Vite development server.
