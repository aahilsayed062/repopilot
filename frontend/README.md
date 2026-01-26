# 🎨 RepoPilot Frontend

The Next.js user interface for **RepoPilot** - the engineering tool that navigates your codebase.

## 🚀 Quick Start

```bash
# Install dependencies
npm install

# Run development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) to start chatting.

## 🏗️ Structure

- `src/app/page.tsx`: Main chat interface & state logic.
- `src/app/layout.tsx`: Global styles & metadata.
- `next.config.ts`: Proxy configuration for backend API.

## 🔧 Configuration

The frontend connects to the backend via `NEXT_PUBLIC_API_URL` (or proxies `/api` to `localhost:8001` in dev).

---
Part of the [RepoPilot](https://github.com/yourusername/repopilot) monorepo.
