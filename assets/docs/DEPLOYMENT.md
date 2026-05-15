# Deployment Guide

Build and deploy the scheduler bot using Docker and GitHub Actions.

## How It Works

1. **GitHub Actions** automatically builds a Docker image when you push code
2. **Image is pushed** to GitHub Container Registry (ghcr.io)
3. **You pull and run** the image in your infrastructure (Kubernetes, Docker Compose, etc.)

## Step 1: Prepare Your Repository

Ensure you have:
- A GitHub account with this repository
- GitHub Actions enabled (automatic, no setup needed)
- A `.github/workflows/docker-build-push.yml` file that builds the image

The workflow builds images for both ARM64 (Raspberry Pi) and AMD64 (x86).

## Step 2: Deploy Code to GitHub

```bash
git add -A
git commit -m "Deploy scheduler bot"
git push origin main
```

GitHub Actions will automatically:
1. Build Docker image
2. Run tests
3. Push to `ghcr.io/YOUR_USERNAME/scheduler-discord-bot:latest`

Monitor the build:
- Go to your GitHub repository
- Click **Actions** tab
- Watch the workflow complete (usually 3-5 minutes)

## Step 3: Authenticate with Container Registry

On the machine where you'll run the bot:

```bash
# Create a GitHub Personal Access Token
# https://github.com/settings/tokens
# Give it 'read:packages' scope

export CR_PAT=your_github_token
echo $CR_PAT | docker login ghcr.io -u YOUR_USERNAME --password-stdin
```

## Step 4: Configure Environment

Create or update `.env`:

```env
BOT_TOKEN=your_bot_token_here
TZ=Europe/London
```

## Step 5: Run the Container

### Option A: Docker Run

```bash
docker run -d \
  --name scheduler_bot \
  --restart unless-stopped \
  -e BOT_TOKEN=${BOT_TOKEN} \
  -e TZ=${TZ} \
  -v scheduler_data:/app/db \
  -v scheduler_logs:/app/logs \
  ghcr.io/YOUR_USERNAME/scheduler-discord-bot:latest

# View logs
docker logs -f scheduler_bot
```

### Option B: Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  scheduler-bot:
    image: ghcr.io/YOUR_USERNAME/scheduler-discord-bot:latest
    container_name: scheduler_bot
    restart: unless-stopped
    environment:
      BOT_TOKEN: ${BOT_TOKEN}
      TZ: ${TZ}
    volumes:
      - scheduler_data:/app/db
      - scheduler_logs:/app/logs
    healthcheck:
      test: ["CMD", "python", "-c", "import sys; sys.exit(0)"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  scheduler_data:
  scheduler_logs:
```

Then:

```bash
docker-compose up -d
docker-compose logs -f
```

### Option C: Kubernetes

Create `deployment.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: scheduler-config
data:
  TZ: "Europe/London"

---
apiVersion: v1
kind: Secret
metadata:
  name: scheduler-secret
type: Opaque
stringData:
  BOT_TOKEN: "your_bot_token_here"

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: scheduler-bot
spec:
  replicas: 1
  selector:
    matchLabels:
      app: scheduler-bot
  template:
    metadata:
      labels:
        app: scheduler-bot
    spec:
      containers:
      - name: scheduler-bot
        image: ghcr.io/YOUR_USERNAME/scheduler-discord-bot:latest
        imagePullPolicy: Always
        env:
        - name: TZ
          valueFrom:
            configMapKeyRef:
              name: scheduler-config
              key: TZ
        - name: BOT_TOKEN
          valueFrom:
            secretKeyRef:
              name: scheduler-secret
              key: BOT_TOKEN
        volumeMounts:
        - name: data
          mountPath: /app/db
        - name: logs
          mountPath: /app/logs
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          exec:
            command:
            - python
            - -c
            - "import sys; sys.exit(0)"
          initialDelaySeconds: 30
          periodSeconds: 10
      imagePullSecrets:
      - name: ghcr-secret
      volumes:
      - name: data
        emptyDir: {}
      - name: logs
        emptyDir: {}
```

Deploy:

```bash
kubectl apply -f deployment.yaml
kubectl logs -f deployment/scheduler-bot
```

## Step 6: Verify Deployment

```bash
# Check container is running
docker ps | grep scheduler_bot

# View logs
docker logs scheduler_bot

# Should see: "✅ Synced 5 slash command(s) with Discord"
```

## Step 7: Update When New Code Is Pushed

When you push new code to GitHub:

1. GitHub Actions builds new image automatically
2. Pull the new image:

```bash
docker pull ghcr.io/YOUR_USERNAME/scheduler-discord-bot:latest

# If using Docker Compose
docker-compose up -d

# Or if using docker run
docker stop scheduler_bot
docker rm scheduler_bot
# Run again with docker run command above
```

## Troubleshooting

### Image won't pull
- Verify token: `docker login ghcr.io`
- Check token has `read:packages` scope
- Verify username is correct in image URL

### Bot won't start
- Check logs: `docker logs scheduler_bot`
- Verify `BOT_TOKEN` is set and valid
- Confirm privileged intents are enabled in Discord Portal

### Database issues
- Ensure volume has write permissions: `docker exec scheduler_bot ls -la /app/db`
- Check disk space: `docker exec scheduler_bot df -h`

### High resource usage
- Set memory limit: `-m 512m` in docker run
- Or in compose: `memory: 512M`

## Environment Variables

| Variable | Required | Notes |
|----------|----------|-------|
| BOT_TOKEN | Yes | Bot token from Discord Portal |
| TZ | No | Timezone (default: Europe/London) |

## Image Details

- **Base**: `python:3.12-alpine`
- **Platforms**: `linux/arm64` (Raspberry Pi), `linux/amd64` (x86)
- **Size**: ~150MB
- **User**: Non-root for security

## Database

Data is stored in:
- Container: `/app/db/database.db`
- Volume: `scheduler_data` (persist across restarts)

Back up your data:

```bash
docker cp scheduler_bot:/app/db ./backup-$(date +%Y%m%d)
```
