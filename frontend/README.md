# Gecko Demo frontend

Standalone ROB-5 review screen built with React, TypeScript, and Vite.

```bash
npm install
npm run dev
```

Open <http://127.0.0.1:5173/>. The app imports the repository fixture at
`../fixtures/manifest.v1.json` and maps its source-video route to the local
`public/demo/warehouse-walkthrough.mp4` fixture clip. It does not require the
upload flow or backend API.

Use `npm run build` to produce a static build in `dist/`.
