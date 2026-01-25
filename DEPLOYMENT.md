# Unified Deployment Workflow — Railway.app

This guide explains how to deploy both the frontend and backend of RepoPilot AI as separate services within a single Railway project.

## 1. Project Creation
1. Go to [Railway.app](https://railway.app) and create a new project.
2. Select **Deploy from GitHub repo** and choose your `repopilot` repository.

## 2. Service Configuration

### Backend Service
1. In your Railway project, click **New** -> **GitHub Repo** (if not already added).
2. Go to the **Settings** tab of the service.
3. Set the **Root Directory** to `/backend`.
4. Set the **Service Name** to `repopilot-backend`.
5. In the **Deploy** tab, keep the default start command from `backend/railway.json` (`python run.py`).
6. In the **Variables** tab, add the following:
   - `GEMINI_API_KEY`: Your Google Gemini API Key.
   - `DATA_DIR`: `/app/data`
   - Do **not** set `PORT`; Railway injects a numeric value automatically.

### Frontend Service
1. Click **New** -> **GitHub Repo** again and select the same repository.
2. Go to the **Settings** tab of this new service.
3. Set the **Root Directory** to `/frontend`.
4. Set the **Service Name** to `repopilot-frontend`.
5. In the **Variables** tab, add the following:
   - `NEXT_PUBLIC_API_URL`: The public URL of your backend service (e.g., `https://repopilot-backend.up.railway.app`).
   - `NODE_ENV`: `production`

## 3. Deployment
- Railway will automatically detect the `Dockerfile` in each subdirectory and build the services.
- Once both builds are complete, you can access your application via the provided `repopilot-frontend` URL.

## 4. Verification
Run the following command locally to verify the backend is responsive:
```bash
curl https://<your-backend-url>/health
```
