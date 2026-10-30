# Deploying without Render: Hugging Face Spaces + MongoDB Atlas (both free tiers)

The root `Dockerfile` builds the React app and serves it from the FastAPI process, so the site and `/api/v1` share one
origin. That matters: the refresh cookie is `SameSite=Strict`, so a frontend and API on different domains would break login.

**Status:** the serving code is covered by a unit test and was exercised locally with uvicorn (SPA routes, assets, API 404,
path traversal). The Docker image itself and a real Hugging Face / Atlas deployment have **not** been built or run by the author
(no Docker or outside network in the build environment). Treat the first deploy as a test.

## Steps
1. **MongoDB Atlas**: create a free M0 cluster, a database user, and under Network Access allow `0.0.0.0/0`
   (Spaces have no fixed IP). Copy the `mongodb+srv://...` URI.
2. **Hugging Face**: New Space, SDK **Docker**, blank. Push this repository to it, but make the Space's `README.md`
   the contents of `deploy/huggingface/SPACE_README.md` (it holds the `sdk: docker` / `app_port: 7860` header).
3. Space **Settings, Variables and secrets** (put anything sensitive under *Secrets*):

| Name | Value |
|---|---|
| `APP_ENV` | `production` |
| `APP_SECRET_KEY` | random string, 32+ chars (secret) |
| `MONGO_URI` | your Atlas URI (secret) |
| `GROQ_API_KEY` | your Groq key (secret) |
| `EMBEDDING_PROVIDER` | `google` (needs `GOOGLE_API_KEY`, secret) or `hash` for a lexical-only demo |
| `VECTOR_STORE_PROVIDER` | `mongo` |
| `CORS_ORIGINS` | `https://<your-space>.hf.space` |
| `RAZORPAY_*` | optional; leave empty to run without payments |

4. Wait for the build, then open `https://<your-space>.hf.space/ready`. `{"status":"ready"}` means the database and
   indexes are fine. The first request after the free Space sleeps is slow.

Other Docker hosts (Railway, Fly.io, Koyeb) work with the same image: they set `PORT`, which the container honours.
Razorpay webhooks need the public URL `https://<host>/api/v1/billing/webhook` configured in the Razorpay dashboard.

## Render (optional)
`render.yaml` is a Blueprint for the same Docker image: New > Blueprint > pick the repo > fill the secret prompts
(`MONGO_URI`, `GROQ_API_KEY`, `GOOGLE_API_KEY`, `CORS_ORIGINS`, Razorpay keys). `APP_SECRET_KEY` is generated for you. Set
`CORS_ORIGINS` to the service URL. It has not been run on Render by the author.

## Other places that are not Render
- **Any Docker host** (your own VPS, Koyeb, Railway, Fly.io): build the root `Dockerfile`, set the same variables, point the host's health check at `/health`.
- **Local or VPS with Docker Compose:** copy `.env.example` to `.env`, fill in your keys, run `docker compose up --build`, open `http://localhost:7860`. (`docker-compose.yml` was written but not run: no Docker was available while building.)
