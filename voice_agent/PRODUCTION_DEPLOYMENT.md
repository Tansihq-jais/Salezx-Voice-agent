# Production Deployment Guide

## Overview
This is a production-ready deployment of the Sales Voice Agent with all development artifacts removed.

## What Was Cleaned Up

### Removed Files/Folders:
- ✅ `.git/` - Git repository (not needed in production)
- ✅ `.vscode/`, `.kiro/` - IDE configuration folders
- ✅ `.hypothesis/`, `.pytest_cache/` - Test artifacts and caches
- ✅ `__pycache__/` - Python bytecode cache
- ✅ `.gitignore`, `.env.example` - Git-related files
- ✅ `ai_studio_code.py` - Demo/example code
- ✅ `campaign_orchestrator.py` - Legacy in-memory orchestrator (replaced by `campaign_orchestrator_pg.py`)
- ✅ `lead_store.py` - Legacy in-memory lead store (replaced by PostgreSQL)
- ✅ `start_livekit.sh`, `start_livekit.bat` - Development startup scripts
- ✅ `frontend/src/`, `frontend/node_modules/` - Frontend source files (built version in `dist/`)
- ✅ `frontend/package.json`, `frontend/vite.config.js` - Frontend build configs
- ✅ `frontend/UI_REDESIGN.md`, `frontend/README.md` - Development documentation

### Kept Files (Production Essentials):
- ✅ All Python backend modules
- ✅ `frontend/dist/` - Built frontend assets
- ✅ `requirements.txt` - Python dependencies
- ✅ `README.md` - Main documentation
- ✅ `.env` - Environment configuration (ensure secrets are properly set)

## Production Architecture

### Database Layer:
- **PostgreSQL** (`pg_db.py`) - Campaigns, contacts, call results
- **MongoDB** (`db.py`) - Lead info, call insights, billing records

### Core Components:
- `main.py` - FastAPI server with all endpoints
- `campaign_orchestrator_pg.py` - Campaign management with PostgreSQL persistence
- `livekit_handler.py` - LiveKit integration (recommended)
- `exotel_handler.py` - Exotel integration (legacy)
- `gemini_bridge.py` - Gemini Live API integration
- `billing.py` - Tiered billing system
- `call_insights.py` - Post-call analysis

## Deployment Steps

### 1. Environment Setup
Ensure `.env` file has all required variables:
```bash
# Gemini AI
GEMINI_API_KEY=your_key_here
USE_VERTEX_AI=false

# LiveKit (Recommended)
USE_LIVEKIT=true
LIVEKIT_URL=wss://your-livekit-server.com
LIVEKIT_API_KEY=your_key
LIVEKIT_API_SECRET=your_secret

# Exotel (Legacy)
EXOTEL_API_KEY=your_key
EXOTEL_API_TOKEN=your_token
EXOTEL_SID=your_sid
EXOTEL_CALLER_ID=your_number

# Databases
DATABASE_URL=postgresql://user:pass@host:5432/dbname
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/dbname

# Server
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
PUBLIC_URL=https://your-domain.com
CLIENT_ID=your_client_id

# Agent Persona
AGENT_NAME=Priya
COMPANY_NAME=TechVision Solutions
PRODUCT_NAME=CloudPro CRM
```

### 2. Install Dependencies
```bash
cd voice_agent
pip install -r requirements.txt
```

### 3. Initialize Database
The PostgreSQL schema is automatically initialized on startup via `pg_db.init_db()`.

### 4. Run with Production Server
Use a production WSGI/ASGI server like Gunicorn with Uvicorn workers:

```bash
# Install production server
pip install gunicorn

# Run with multiple workers
gunicorn main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 300 \
  --access-logfile - \
  --error-logfile -
```

### 5. Process Management
Use a process manager like systemd, supervisor, or PM2:

#### Systemd Example:
```ini
[Unit]
Description=Sales Voice Agent
After=network.target

[Service]
Type=notify
User=www-data
WorkingDirectory=/opt/voice_agent
Environment="PATH=/opt/voice_agent/venv/bin"
ExecStart=/opt/voice_agent/venv/bin/gunicorn main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
Restart=always

[Install]
WantedBy=multi-user.target
```

### 6. Reverse Proxy (Nginx)
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
    }

    # Serve frontend static files
    location /frontend/ {
        alias /opt/voice_agent/frontend/dist/;
        try_files $uri $uri/ /index.html;
    }
}
```

### 7. SSL/TLS
Use Let's Encrypt with certbot:
```bash
certbot --nginx -d your-domain.com
```

## Monitoring & Logging

### Application Logs
The application uses Python's logging module. Configure log level via environment:
```bash
export LOG_LEVEL=INFO
```

### Health Check Endpoint
```bash
curl https://your-domain.com/health
```

### Metrics to Monitor:
- Active campaigns
- Call success rate
- Average call duration
- API response times
- Database connection pool
- Memory usage
- CPU usage

## Scaling Considerations

### Horizontal Scaling:
- Run multiple instances behind a load balancer
- Use Redis for shared session state if needed
- Ensure DATABASE_URL points to a connection pooler (PgBouncer)

### Database Optimization:
- Enable PostgreSQL connection pooling
- Add indexes for frequently queried fields
- Monitor slow queries
- Set up read replicas for analytics

### Cost Optimization:
- Use LiveKit instead of Exotel (96% cost savings)
- Implement call duration limits
- Monitor Gemini API usage
- Cache frequently accessed data

## Security Checklist

- [ ] All secrets in environment variables (not in code)
- [ ] SSL/TLS enabled
- [ ] Database connections encrypted
- [ ] CORS properly configured
- [ ] Rate limiting enabled
- [ ] Input validation on all endpoints
- [ ] Regular security updates
- [ ] Firewall rules configured
- [ ] Backup strategy in place

## Backup Strategy

### Database Backups:
```bash
# PostgreSQL
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql

# MongoDB
mongodump --uri="$MONGODB_URI" --out=backup_$(date +%Y%m%d)
```

### Automated Backups:
Set up daily backups via cron or cloud provider tools.

## Troubleshooting

### Common Issues:

1. **Database Connection Errors**
   - Check DATABASE_URL and MONGODB_URI
   - Verify network connectivity
   - Check firewall rules

2. **Gemini API Errors**
   - Verify GEMINI_API_KEY
   - Check API quota limits
   - Monitor rate limits

3. **LiveKit Connection Issues**
   - Verify LIVEKIT_URL, API_KEY, API_SECRET
   - Check WebSocket connectivity
   - Review LiveKit server logs

4. **High Memory Usage**
   - Reduce worker count
   - Implement connection pooling
   - Monitor for memory leaks

## Support

For issues or questions:
- Check logs: `journalctl -u voice-agent -f`
- Review README.md for architecture details
- Monitor health endpoint: `/health`
