# 🚀 MAPLE n8n Integration - Production Launch Guide

**Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)**

This guide provides step-by-step instructions for launching the MAPLE n8n integration package in production environments.

---

## 📋 Pre-Launch Checklist

### ✅ **Technical Requirements**
- [ ] Node.js 16+ installed
- [ ] npm 8+ installed  
- [ ] n8n installed (`npm install -g n8n`)
- [ ] Docker (optional, for containerized deployment)
- [ ] SSL certificates (for production HTTPS)

### ✅ **Environment Setup**
- [ ] Production server configured
- [ ] DNS records configured (maple.yourdomain.com)
- [ ] Firewall rules configured (ports 8080, 3000, 9090)
- [ ] SSL certificates installed
- [ ] Environment variables set

### ✅ **Package Validation**
- [ ] All tests passing (`npm test`)
- [ ] Build successful (`npm run build`)
- [ ] Linting passed (`npm run lint`)
- [ ] Security audit clean (`npm audit`)

---

## 🎯 Launch Sequences

### **Option 1: Quick Development Launch (60 seconds)**

```bash
# Clone and setup
git clone https://github.com/mahesh-vaikri/maple-n8n-nodes
cd maple-n8n-nodes

# Install and launch
npm install
node launch.js

# That's it! MAPLE is running on localhost:8080
```

### **Option 2: Production Deployment**

#### **Step 1: Server Setup**
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Node.js 18 LTS
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# Install PM2 for process management
sudo npm install -g pm2

# Create maple user
sudo useradd -m -s /bin/bash maple
sudo usermod -aG sudo maple
```

#### **Step 2: Clone and Build**
```bash
# Switch to maple user
sudo su - maple

# Clone repository
git clone https://github.com/mahesh-vaikri/maple-n8n-nodes
cd maple-n8n-nodes

# Install dependencies
npm install

# Build production package
npm run build

# Run tests
npm test
```

#### **Step 3: Configure Production Environment**
```bash
# Copy production config
cp config/maple-config.json config/production.json

# Edit configuration
nano config/production.json

# Set environment variables
export NODE_ENV=production
export MAPLE_CONFIG_PATH=/home/maple/maple-n8n-nodes/config/production.json
export JWT_SECRET="your-super-secret-jwt-key"
```

#### **Step 4: SSL Setup**
```bash
# Install Let's Encrypt
sudo apt install certbot

# Generate SSL certificate
sudo certbot certonly --standalone -d maple.yourdomain.com

# Copy certificates
sudo cp /etc/letsencrypt/live/maple.yourdomain.com/fullchain.pem ssl/cert.pem
sudo cp /etc/letsencrypt/live/maple.yourdomain.com/privkey.pem ssl/key.pem
sudo chown maple:maple ssl/*.pem
```

#### **Step 5: Start Production Services**
```bash
# Start with PM2
pm2 start launch.js --name "maple-server"
pm2 start demo/start-maple-broker.js --name "maple-broker"

# Save PM2 configuration
pm2 save
pm2 startup

# Check status
pm2 status
```

### **Option 3: Docker Deployment**

#### **Create Docker Compose File**
```yaml
# docker-compose.yml
version: '3.8'

services:
  maple-server:
    build: .
    ports:
      - "8080:8080"
      - "3000:3000"
      - "9090:9090"
    environment:
      - NODE_ENV=production
      - MAPLE_CONFIG_PATH=/app/config/production.json
    volumes:
      - ./config:/app/config
      - ./logs:/app/logs
      - ./ssl:/app/ssl
    restart: unless-stopped
    
  maple-db:
    image: postgres:13
    environment:
      - POSTGRES_DB=maple
      - POSTGRES_USER=maple
      - POSTGRES_PASSWORD=secure_password
    volumes:
      - maple_db_data:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  maple_db_data:
```

#### **Deploy with Docker**
```bash
# Build and start
docker-compose up -d

# Check logs
docker-compose logs -f maple-server

# Scale if needed
docker-compose up -d --scale maple-server=3
```

### **Option 4: Kubernetes Deployment**

#### **Apply Kubernetes Manifests**
```bash
# Create namespace
kubectl create namespace maple-system

# Apply configurations
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml

# Check deployment
kubectl get pods -n maple-system
kubectl get services -n maple-system
```

---

## 🔍 Post-Launch Verification

### **Health Checks**
```bash
# Check all endpoints
curl https://maple.yourdomain.com/health
curl https://maple.yourdomain.com/metrics
curl https://maple.yourdomain.com/api/status

# Test WebSocket connection
wscat -c wss://maple.yourdomain.com
```

### **Performance Tests**
```bash
# Run performance benchmarks
npm run test:performance

# Load testing
npm run test:load

# Stress testing  
npm run test:stress
```

### **Security Verification**
```bash
# Security audit
npm audit

# SSL verification
openssl s_client -connect maple.yourdomain.com:443

# Authentication test
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" https://maple.yourdomain.com/api/secure
```

---

## 📊 Monitoring Setup

### **Prometheus Metrics**
```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'maple'
    static_configs:
      - targets: ['maple.yourdomain.com:9090']
```

### **Grafana Dashboard**
```bash
# Import MAPLE dashboard
curl -X POST \
  http://grafana.yourdomain.com/api/dashboards/db \
  -H 'Content-Type: application/json' \
  -d @grafana/maple-dashboard.json
```

### **Log Aggregation**
```bash
# Configure log shipping to ELK Stack
echo 'filebeat.inputs:
- type: log
  paths:
    - /home/maple/maple-n8n-nodes/logs/*.log
  fields:
    service: maple
    environment: production' > /etc/filebeat/filebeat.yml
```

---

## 🛡️ Security Hardening

### **Firewall Configuration**
```bash
# Ubuntu UFW
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw allow 8080/tcp  # MAPLE API
sudo ufw enable
```

### **Rate Limiting**
```nginx
# nginx.conf
http {
    limit_req_zone $binary_remote_addr zone=maple:10m rate=10r/s;
    
    server {
        location /api/ {
            limit_req zone=maple burst=20 nodelay;
            proxy_pass http://localhost:8080;
        }
    }
}
```

### **DDoS Protection**
```bash
# Install fail2ban
sudo apt install fail2ban

# Configure MAPLE protection
echo '[maple-dos]
enabled = true
port = 8080
filter = maple-dos
logpath = /home/maple/maple-n8n-nodes/logs/maple-prod.log
maxretry = 10
bantime = 600' > /etc/fail2ban/jail.d/maple.conf
```

---

## 🔧 Troubleshooting

### **Common Issues**

#### **Port Already in Use**
```bash
# Find process using port
sudo lsof -i :8080

# Kill process
sudo kill -9 <PID>

# Or change port in config
nano config/production.json
```

#### **SSL Certificate Issues**
```bash
# Verify certificate
openssl x509 -in ssl/cert.pem -text -noout

# Check certificate expiry
openssl x509 -in ssl/cert.pem -noout -dates

# Renew Let's Encrypt
sudo certbot renew
```

#### **Performance Issues**
```bash
# Check system resources
htop
df -h
free -m

# Monitor MAPLE processes
pm2 monit

# Check logs
tail -f logs/maple-prod.log
```

#### **Database Connection Issues**
```bash
# Test database connection
psql -h localhost -U maple -d maple -c "SELECT version();"

# Check database logs
sudo tail -f /var/log/postgresql/postgresql-13-main.log
```

---

## 📈 Scaling Strategies

### **Horizontal Scaling**
```bash
# Add more server instances
pm2 start launch.js --name "maple-server-2" --env production

# Load balancer configuration (nginx)
upstream maple_backend {
    server 127.0.0.1:8080;
    server 127.0.0.1:8081;
    server 127.0.0.1:8082;
}
```

### **Vertical Scaling**
```bash
# Increase resource limits
pm2 start launch.js --name "maple-server" --max-memory-restart 2G

# Update system resources
# - Increase RAM
# - Add CPU cores
# - Improve disk I/O
```

### **Database Scaling**
```bash
# PostgreSQL read replicas
# Redis caching layer
# Connection pooling
```

---

## 🎯 Launch Success Metrics

### **Performance Targets**
- ✅ **Message Processing**: > 300K msg/sec
- ✅ **Response Time**: < 50ms average
- ✅ **Uptime**: > 99.9%
- ✅ **Error Rate**: < 0.1%

### **Functionality Targets**
- ✅ **Agent Registration**: < 100ms
- ✅ **Resource Allocation**: < 200ms
- ✅ **Security Validation**: < 10ms
- ✅ **Health Checks**: All passing

### **User Experience Targets**
- ✅ **n8n Node Installation**: < 60 seconds
- ✅ **First Workflow**: < 5 minutes
- ✅ **Demo Completion**: < 10 minutes
- ✅ **Documentation**: 100% complete

---

## 🎉 Launch Complete!

### **Verification Checklist**
- [ ] All services running
- [ ] Health checks passing
- [ ] Performance targets met
- [ ] Security validated
- [ ] Monitoring active
- [ ] Documentation complete
- [ ] Support channels ready

### **Next Steps**
1. **Monitor** system performance for first 24 hours
2. **Collect** user feedback and usage metrics
3. **Iterate** based on real-world usage
4. **Scale** as demand grows
5. **Enhance** with additional features

**🏆 Congratulations! MAPLE n8n Integration is successfully launched!**

**Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)**  
**MAPLE - Multi Agent Protocol Language Engine**

---
