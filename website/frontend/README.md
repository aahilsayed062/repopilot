# RepoPilot Website Frontend

Next.js frontend for repository architecture analysis.

## Run Locally

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

## Environment

- `NEXT_PUBLIC_API_URL` (optional): explicit backend base URL.
- `BACKEND_URL` (optional): server-side rewrite target for `/api/:path*`.

If both are missing, local fallback is `http://localhost:8001`.

## Main Routes

- `/` landing page
- `/analyze` repository analyzer
- `/dashboard` advanced workflow UI

## Notes

- Analyze page has live loading percentage + progress bar.
- `next.config.ts` uses `.next-runtime` locally and default `.next` on Vercel.
