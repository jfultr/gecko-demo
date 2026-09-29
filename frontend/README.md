# Gecko Demo frontend

Video upload and review screens built with React, TypeScript, and Vite.

```bash
npm install
npm run dev
```

Open <http://127.0.0.1:5173/>. To use the real upload and processing flow, run
the full Docker Compose stack from the repository root. It proxies `/api` to
the backend and starts the worker. The **View demo analysis** button uses the
repository fixture at `../fixtures/manifest.v1.json` and the local
`public/demo/warehouse-walkthrough.mp4` clip, so that preview works without
the backend. When running the frontend separately, set `VITE_API_TARGET` to
the reachable backend origin. Set `VITE_MAX_UPLOAD_BYTES` to match
`APP_MAX_UPLOAD_BYTES` if the backend uses a nondefault upload limit.

Use `npm run build` to produce a static build in `dist/`.
