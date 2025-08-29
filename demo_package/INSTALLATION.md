<img width="358" height="358" alt="maple358" src="https://github.com/user-attachments/assets/299615b3-7c74-4344-9aff-5346b8f62c24" />

<img width="358" height="358" alt="mapleagents-358" src="https://github.com/user-attachments/assets/e78a2d4f-837a-4f72-919a-366cbe4c3eb5" />

# MAPLE Installation Guide

**Creator: Mahesh Vaikri**

This guide provides complete instructions for installing and setting up MAPLE (Multi Agent Protocol Language Engine) for demonstrations and development.

## 📋 Prerequisites

### System Requirements
- **Operating System**: Windows 10+, macOS 10.14+, or Linux (Ubuntu 18.04+)
- **Python**: Version 3.8 or higher
- **Memory**: 4GB RAM minimum, 8GB recommended
- **Storage**: 2GB available disk space
- **Network**: Internet connection for downloads

### Hardware Recommendations
- **CPU**: Multi-core processor (Intel i5/AMD Ryzen 5 or better)
- **RAM**: 8GB for full demo experience
- **Storage**: SSD for better performance
- **Network**: Stable connection for broker communication

## 🚀 Quick Installation

### Option 1: Demo Package (Recommended for Evaluation)
```bash
# Download the MAPLE demo package
git clone <repository-url>
cd MAPLE-OSS-IMPL/maple-oss

# Install in development mode
pip install -e .

# Verify installation
python -c "import maple; print('MAPLE installed successfully!')"

# Run setup verification
cd demo_package
python setup_demo.py
```

### Option 2: Production Installation
```bash
# Install from PyPI (when available)
pip install maple-oss

# Or install from source
pip install git+<repository-url>
```

### Option 3: Docker Installation (Coming Soon)
```bash
# Pull official MAPLE image
docker pull maple/agent-protocol:latest

# Run demo container
docker run -p 8888:8888 maple/agent-protocol:latest
```

## 🔧 Detailed Setup Instructions

### Step 1: Python Environment Setup

#### On Windows:
```cmd
# Check Python version
python --version

# If Python < 3.8, download from python.org
# Recommended: Use Python 3.10+ for best performance

# Create virtual environment (recommended)
python -m venv maple-env
maple-env\Scripts\activate

# Upgrade pip
python -m pip install --upgrade pip
```

#### On macOS:
```bash
# Check Python version
python3 --version

# Install via Homebrew (if needed)
brew install python@3.10

# Create virtual environment
python3 -m venv maple-env
source maple-env/bin/activate

# Upgrade pip
python -m pip install --upgrade pip
```

#### On Linux (Ubuntu/Debian):
```bash
# Install Python 3.10 if not available
sudo apt update
sudo apt install python3.10 python3.10-venv python3.10-dev

# Create virtual environment
python3.10 -m venv maple-env
source maple-env/bin/activate

# Upgrade pip
python -m pip install --upgrade pip
```

### Step 2: MAPLE Installation

#### From Source (Development/Demo):
```bash
# Clone repository
git clone <repository-url>
cd MAPLE-OSS-IMPL/maple-oss

# Install dependencies
pip install -r requirements.txt

# Install MAPLE in development mode
pip install -e .

# Install optional dependencies
pip install psutil  # For system monitoring
pip install cryptography  # For advanced encryption
pip install nats-py  # For NATS broker support
```

#### Package Installation:
```bash
# Core MAPLE installation
pip install maple-oss

# With optional features
pip install maple-oss[full]  # All optional dependencies
pip install maple-oss[crypto]  # Cryptography features
pip install maple-oss[monitoring]  # System monitoring
pip install maple-oss[nats]  # NATS broker support
```

### Step 3: Verification and Testing

#### Basic Verification:
```bash
# Test basic import
python -c "import maple; print(f'MAPLE {maple.__version__} ready!')"

# Run setup verification
cd demo_package
python setup_demo.py
```

#### Comprehensive Testing:
```bash
# Run test suite
cd MAPLE-OSS-IMPL/maple-oss
python -m pytest tests/ -v

# Run performance benchmarks
python tests/performance_tests.py

# Run comprehensive test suite
python tests/comprehensive_test_suite.py
```

## 🎯 Demo Package Setup

### Interactive Launcher:
```bash
cd demo_package
python launch_demos.py
```

### Individual Demos:
```bash
# Quick 2-minute demo
python quick_demo.py

# Complete 15-minute demonstration
python maple_demo.py

# Focused feature examples
python examples/resource_management_example.py
python examples/secure_link_example.py
python examples/performance_comparison_example.py

# Web dashboard
python web_dashboard.py
```

## 🔧 Configuration

### Environment Variables:
```bash
# Optional configuration
export MAPLE_LOG_LEVEL=INFO
export MAPLE_BROKER_URL=localhost:8080
export MAPLE_SECURITY_LEVEL=HIGH
export MAPLE_PERFORMANCE_MODE=OPTIMIZED
```

### Configuration File (maple.conf):
```ini
[maple]
log_level = INFO
broker_url = localhost:8080
security_level = HIGH
performance_mode = OPTIMIZED

[security]
require_authentication = true
require_links = false
default_encryption = AES256-GCM

[performance]
message_buffer_size = 10000
agent_pool_size = 100
enable_metrics = true

[demos]
auto_cleanup = true
save_results = true
web_dashboard_port = 8888
```

## 🐛 Troubleshooting

### Common Issues:

#### "Module 'maple' not found"
```bash
# Solution 1: Install/reinstall MAPLE
pip install -e .

# Solution 2: Check Python path
python -c "import sys; print(sys.path)"

# Solution 3: Virtual environment
source maple-env/bin/activate  # Linux/macOS
maple-env\Scripts\activate     # Windows
```

#### "Permission denied" errors
```bash
# Linux/macOS: Fix permissions
chmod +x demo_package/*.py
sudo chown -R $USER:$USER .

# Windows: Run as administrator or check antivirus
```

#### "Port already in use" (Web dashboard)
```bash
# Find process using port
lsof -i :8888  # Linux/macOS
netstat -ano | findstr :8888  # Windows

# Kill process or use different port
python web_dashboard.py --port 9999
```

#### Import errors for optional dependencies
```bash
# Install missing dependencies
pip install psutil cryptography nats-py

# Or install all optional features
pip install maple-oss[full]
```

#### Performance issues
```bash
# Check system resources
python -c "import psutil; print(f'CPU: {psutil.cpu_count()}, RAM: {psutil.virtual_memory().total//1024**3}GB')"

# Use performance mode
export MAPLE_PERFORMANCE_MODE=OPTIMIZED

# Reduce demo complexity
python quick_demo.py  # Instead of full demo
```

### Debug Mode:
```bash
# Enable debug logging
export MAPLE_LOG_LEVEL=DEBUG
python maple_demo.py

# Or in Python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### System Diagnostics:
```bash
# Run comprehensive diagnostics
python setup_demo.py

# Check dependencies
pip list | grep -E "(maple|psutil|cryptography|nats)"

# System information
python -c "
import platform, sys
print(f'OS: {platform.system()} {platform.release()}')
print(f'Python: {sys.version}')
print(f'Architecture: {platform.machine()}')
"
```

## 🚀 Advanced Setup

### Development Environment:
```bash
# Install development dependencies
pip install -e .[dev]

# Install pre-commit hooks
pre-commit install

# Run linting and formatting
black src/
flake8 src/
mypy src/
```

### Production Deployment:
```bash
# Production configuration
export MAPLE_ENV=production
export MAPLE_BROKER_URL=your-broker-cluster
export MAPLE_SECURITY_LEVEL=MAXIMUM

# Install production dependencies
pip install maple-oss[production]

# Run health checks
python -m maple.health_check
```

### Container Deployment:
```dockerfile
# Dockerfile example
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN pip install -e .

EXPOSE 8080 8888
CMD ["python", "demo_package/web_dashboard.py"]
```

## 📊 Performance Optimization

### System Tuning:
```bash
# Increase file descriptor limits (Linux)
ulimit -n 65536

# Configure Python for performance
export PYTHONOPTIMIZE=1
export PYTHONDONTWRITEBYTECODE=1

# Use optimized Python build
# Consider PyPy for CPU-intensive workloads
```

### MAPLE Configuration:
```python
# High-performance configuration
from maple import Config, PerformanceConfig

config = Config(
    performance=PerformanceConfig(
        connection_pool_size=100,
        max_concurrent_requests=1000,
        serialization_format="msgpack",  # Faster than JSON
        batch_size=100,
        batch_timeout="10ms"
    )
)
```

## 📚 Next Steps

### After Installation:
1. **Run Quick Demo**: `python quick_demo.py`
2. **Explore Examples**: Check `examples/` directory
3. **Read Documentation**: Browse `README.md` files
4. **Try Web Dashboard**: `python web_dashboard.py`
5. **Run Full Demo**: `python maple_demo.py`

### For Development:
1. **Study Source Code**: Explore `src/maple/` directory
2. **Run Tests**: `python -m pytest tests/`
3. **Check Examples**: Implement your own agents
4. **Contribute**: Fork repository and submit PRs

### For Production:
1. **Performance Testing**: Benchmark in your environment
2. **Security Review**: Configure security settings
3. **Integration Planning**: Design agent architecture
4. **Monitoring Setup**: Configure logging and metrics

## 🆘 Support

### Getting Help:
- **Documentation**: Check README.md and examples
- **Issues**: Report bugs and feature requests
- **Discussions**: Join community discussions
- **Enterprise**: Contact for commercial support

### Contact Information:
- **Creator**: Mahesh Vaikri
- **Project**: MAPLE (Multi Agent Protocol Language Engine)
- **License**: AGPL 3.0
- **Status**: Production Ready v1.0.0

---

## ✅ Installation Checklist

- [ ] Python 3.8+ installed
- [ ] Virtual environment created and activated
- [ ] MAPLE package installed (`pip install -e .`)
- [ ] Optional dependencies installed
- [ ] Basic import test passed (`import maple`)
- [ ] Setup verification completed (`python setup_demo.py`)
- [ ] Quick demo runs successfully (`python quick_demo.py`)
- [ ] Demo launcher works (`python launch_demos.py`)
- [ ] Web dashboard accessible (if needed)
- [ ] Performance benchmarks completed
- [ ] Documentation reviewed

🎉 **Installation Complete!** You're ready to explore MAPLE's revolutionary capabilities!

**Creator: Mahesh Vaikri | MAPLE v1.0.0 | Revolutionary Multi-Agent Communication**

```
Copyright (C) 2025 Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

This file is part of MAPLE - Multi Agent Protocol Language Engine. 

MAPLE - Multi Agent Protocol Language Engine is free software: you can redistribute it and/or 
modify it under the terms of the GNU Affero General Public License as published by the Free Software 
Foundation, either version 3 of the License, or (at your option) any later version. 
MAPLE - Multi Agent Protocol Language Engine is distributed in the hope that it will be useful, 
but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A 
PARTICULAR PURPOSE. See the GNU Affero General Public License for more details. You should have 
received a copy of the GNU Affero General Public License along with MAPLE - Multi Agent Protocol 
Language Engine. If not, see <https://www.gnu.org/licenses/>.
```
