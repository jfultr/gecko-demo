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
the backend. A separate `npm run dev` session also proxies `/api`, targeting
`http://127.0.0.1:8000` by default. If the Gecko API uses another host port,
set `VITE_API_TARGET` in `frontend/.env.local` (for example,
`VITE_API_TARGET=http://127.0.0.1:8001`) and restart Vite. Set
`VITE_MAX_UPLOAD_BYTES` to match `APP_MAX_UPLOAD_BYTES` if the backend uses a
nondefault upload limit.

Use `npm run build` to produce a static build in `dist/`.
