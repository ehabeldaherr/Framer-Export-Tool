# 🚀 Free Deployment Guide for Framer Export Tool

This guide walks you through deploying your **Framer Export Tool** online for **free** so anyone on the internet can use it.

---

## 🏆 Option 1: Render.com (Recommended — Simplest Setup)

Render gives you a free public web service with an HTTPS URL (`https://your-tool.onrender.com`).

### Step 1: Push your code to GitHub
1. Open PowerShell or Terminal in this folder.
2. Initialize and push your repository to your GitHub account:
   ```bash
   git add .
   git commit -m "Initial commit for deployment"
   git branch -M main
   # Create a new repository on https://github.com/new (make it Public or Private)
   git remote add origin https://github.com/<YOUR_USERNAME>/<YOUR_REPOSITORY_NAME>.git
   git push -u origin main
   ```

### Step 2: Deploy on Render
1. Go to [Render.com](https://render.com) and sign up / log in with your GitHub account.
2. Click **New +** in the top right and select **Web Service**.
3. Choose **Build and deploy from a Git repository**.
4. Select your Framer Export Tool repository from the list.
5. Fill in the details:
   - **Name**: `framer-export-tool` (or any name you prefer)
   - **Region**: Choose the closest region (e.g. Frankfurt, Oregon, Singapore)
   - **Branch**: `main`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn --worker-class gthread --workers 1 --threads 8 --timeout 180 app:app`
   - **Instance Type**: Select **Free** ($0/month)
6. Click **Deploy Web Service**.

> Render will build the app and give you a live URL (e.g., `https://framer-export-tool.onrender.com`).
> Note: Free Render instances sleep when idle and wake up in ~30–45s when someone visits the page.

---

## ⚡ Option 2: Hugging Face Spaces (24/7 Always Active, Never Sleeps)

If you don't want the 30-second cold start from Render, Hugging Face Spaces provides **2 vCPU + 16 GB RAM completely free** with no credit card required.

### Step 1: Create a Space on Hugging Face
1. Go to [Hugging Face](https://huggingface.co/) and create a free account.
2. Click your profile picture -> **New Space**.
3. Space details:
   - **Space Name**: `framer-export-tool`
   - **License**: `mit` (or choose another)
   - **Space SDK**: Choose **Docker** -> **Blank**
   - **Space hardware**: `Free (CPU basic · 2 vCPU · 16 GB)`
   - Set visibility to **Public**.
4. Click **Create Space**.

### Step 2: Push your code
Hugging Face provides a Git remote URL for your space. In your local folder:
```bash
git remote add space https://huggingface.co/spaces/<YOUR_USERNAME>/<YOUR_SPACE_NAME>
git push space main
```
> Hugging Face will detect the `Dockerfile`, build the container, and launch your app with a public shareable URL!

---

## 📦 What was configured for deployment:
- **`requirements.txt`**: Added `gunicorn` for high-performance production WSGI serving and removed unused packages.
- **`Procfile`**: Multi-threaded Gunicorn worker configuration (`--worker-class gthread --threads 8`) to support live Server-Sent Events (SSE) streaming logs without blocking other users.
- **`Dockerfile`**: Self-contained container configuration for Hugging Face Spaces, Koyeb, or Docker-based platforms.
- **`render.yaml`**: Automatic blueprint configuration for Render.com.
- **`.gitignore`**: Excludes internal test exports, temporary files, and caches from being uploaded to GitHub.
