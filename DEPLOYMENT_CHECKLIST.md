# Production Deployment Checklist

## Pre-Deployment Verification

### ✅ Code Cleanup (Completed)
- [x] Removed Git repository and version control files
- [x] Removed IDE configuration folders (.vscode, .kiro)
- [x] Removed test artifacts (.hypothesis, .pytest_cache)
- [x] Removed Python cache (__pycache__)
- [x] Removed legacy code (campaign_orchestrator.py, lead_store.py, ai_studio_code.py)
- [x] Removed development scripts (start_livekit.sh, start_livekit.bat)
- [x] Removed frontend source files (kept only dist/)
- [x] Removed frontend build tools (node_modules, vite.config.js, package.json)
- [x] Updated imports to remove references to deleted files
- [x] Verified production readiness (35/35 checks passed)

### 📋 Environment Configuration
- [ ] Create `.env` file with production credentials
- [ ] Set `GEMINI_API_KEY` for Gemini Live API
- [ ] Configure `DATABASE_URL` for PostgreSQL (Neon or other)
- [ ] Configure `MONGODB_URI` for MongoDB Atlas
- [ ] Set `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` (if using LiveKit)
- [ ] Set `EXOTEL_API_KEY`, `EXOTEL_API_TOKEN`, `EXOTEL_SID` (if using Exotel)
- [ ] Configure `PUBLIC_URL` to your domain
- [ ] Set `CLIENT_ID` for multi-tenant support
- [ ] Configure agent persona (`AGENT_NAME`, `COMPANY_NAME`, `PRODUCT_NAME`)

### 🗄️ Database Setup
- [ ] PostgreSQL database created and accessible
- [ ] MongoDB database created and accessible
- [ ] Database credentials tested
- [ ] Network connectivity verified
- [ ] Firewall rules configured
- [ ] Connection pooling configured (PgBouncer recommended)

### 🔒 Security
- [ ] All secrets stored in environment variables (not in code)
- [ ] `.env` file permissions set to 600 (read/write owner only)
- [ ] SSL/TLS certificates obtained (Let's Encrypt recommended)
- [ ] CORS origins properly configured
- [ ] Rate limiting configured
- [ ] Input validation enabled on all endpoints
- [ ] Database connections encrypted
- [ ] API keys rotated from development

### 🚀 Server Setup
- [ ] Python 3.11+ installed
- [ ] Virtual environment created
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] Gunicorn installed for production server
- [ ] Process manager configured (systemd, supervisor, or PM2)
- [ ] Reverse proxy configured (Nginx or Apache)
- [ ] Log rotation configured
- [ ] Monitoring tools installed

### 🌐 Network & DNS
- [ ] Domain name configured
- [ ] DNS A/AAAA records pointing to server
- [ ] SSL certificate installed and auto-renewal configured
- [ ] Firewall rules configured (allow 80, 443; restrict 8000)
- [ ] WebSocket support enabled in reverse proxy
- [ ] Load balancer configured (if using multiple instances)

### 📊 Monitoring & Logging
- [ ] Application logging configured
- [ ] Log aggregation set up (optional: ELK, Datadog, etc.)
- [ ] Health check endpoint tested (`/health`)
- [ ] Uptime monitoring configured
- [ ] Error tracking configured (optional: Sentry)
- [ ] Performance monitoring configured
- [ ] Database monitoring enabled
- [ ] Alert rules configured

### 💾 Backup & Recovery
- [ ] PostgreSQL backup strategy implemented
- [ ] MongoDB backup strategy implemented
- [ ] Backup automation configured (daily recommended)
- [ ] Backup restoration tested
- [ ] Disaster recovery plan documented
- [ ] Data retention policy defined

### 🧪 Testing
- [ ] Health endpoint returns 200 OK
- [ ] Campaign upload endpoint tested
- [ ] Campaign start/pause/resume/stop tested
- [ ] Call handling tested (LiveKit or Exotel)
- [ ] Gemini API integration tested
- [ ] Database writes verified
- [ ] Frontend loads correctly
- [ ] WebSocket connections work
- [ ] Load testing performed (optional)

## Deployment Steps

### 1. Server Preparation
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.11+
sudo apt install python3.11 python3.11-venv python3-pip -y

# Create application directory
sudo mkdir -p /opt/voice_agent
sudo chown $USER:$USER /opt/voice_agent
```

### 2. Application Setup
```bash
# Copy application files
cd /opt/voice_agent
# Upload voice_agent/ directory here

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn
```

### 3. Environment Configuration
```bash
# Create .env file
nano .env
# Add all required environment variables

# Set permissions
chmod 600 .env
```

### 4. Database Initialization
```bash
# Test database connections
python -c "from config import DATABASE_URL, MONGODB_URI; print('PG:', DATABASE_URL); print('Mongo:', MONGODB_URI)"

# Initialize PostgreSQL schema (automatic on first run)
python -c "import pg_db; pg_db.init_db(); print('Database initialized')"
```

### 5. Process Manager (Systemd)
```bash
# Create systemd service
sudo nano /etc/systemd/system/voice-agent.service

# Add service configuration (see PRODUCTION_DEPLOYMENT.md)

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable voice-agent
sudo systemctl start voice-agent
sudo systemctl status voice-agent
```

### 6. Reverse Proxy (Nginx)
```bash
# Install Nginx
sudo apt install nginx -y

# Create site configuration
sudo nano /etc/nginx/sites-available/voice-agent

# Add configuration (see PRODUCTION_DEPLOYMENT.md)

# Enable site
sudo ln -s /etc/nginx/sites-available/voice-agent /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 7. SSL/TLS Setup
```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx -y

# Obtain certificate
sudo certbot --nginx -d your-domain.com

# Test auto-renewal
sudo certbot renew --dry-run
```

### 8. Verification
```bash
# Check service status
sudo systemctl status voice-agent

# Check logs
sudo journalctl -u voice-agent -f

# Test health endpoint
curl https://your-domain.com/health

# Test frontend
curl https://your-domain.com/frontend/

# Test API
curl https://your-domain.com/campaign/status
```

## Post-Deployment

### Monitoring
- [ ] Set up uptime monitoring (UptimeRobot, Pingdom, etc.)
- [ ] Configure alerting for service failures
- [ ] Monitor disk space usage
- [ ] Monitor database performance
- [ ] Track API usage and costs
- [ ] Review logs daily for errors

### Maintenance
- [ ] Schedule regular backups
- [ ] Plan for security updates
- [ ] Monitor dependency vulnerabilities
- [ ] Review and rotate API keys quarterly
- [ ] Update SSL certificates (auto-renewal should handle this)
- [ ] Review and optimize database queries
- [ ] Clean up old logs and data

### Scaling (When Needed)
- [ ] Add more worker processes
- [ ] Set up horizontal scaling with load balancer
- [ ] Implement Redis for session management
- [ ] Add database read replicas
- [ ] Optimize database indexes
- [ ] Implement caching layer
- [ ] Consider CDN for frontend assets

## Rollback Plan

If deployment fails:

1. **Stop the service**
   ```bash
   sudo systemctl stop voice-agent
   ```

2. **Restore previous version**
   ```bash
   cd /opt/voice_agent
   # Restore from backup
   ```

3. **Restore database** (if schema changed)
   ```bash
   psql $DATABASE_URL < backup.sql
   ```

4. **Restart service**
   ```bash
   sudo systemctl start voice-agent
   ```

## Support Contacts

- **Infrastructure**: [Your DevOps team]
- **Database**: [Your DBA team]
- **Application**: [Your dev team]
- **Security**: [Your security team]

## Documentation References

- [README.md](voice_agent/README.md) - Application overview and architecture
- [PRODUCTION_DEPLOYMENT.md](voice_agent/PRODUCTION_DEPLOYMENT.md) - Detailed deployment guide
- [CLEANUP_SUMMARY.md](CLEANUP_SUMMARY.md) - What was cleaned up and why

## Success Criteria

Deployment is successful when:
- ✅ Health endpoint returns 200 OK
- ✅ Frontend loads without errors
- ✅ Campaign can be created and started
- ✅ Calls can be placed and handled
- ✅ Database writes are persisted
- ✅ Logs show no critical errors
- ✅ SSL certificate is valid
- ✅ All monitoring alerts are green

---

**Last Updated**: [Current Date]
**Deployed By**: [Your Name]
**Environment**: Production
**Version**: 1.0.0
