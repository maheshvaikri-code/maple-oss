"""
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
"""


# setup.py
# Creator: Mahesh Vaikri

from setuptools import setup, find_packages

# Read the README file
try:
    with open("README.md", "r", encoding="utf-8") as fh:
        long_description = fh.read()
except FileNotFoundError:
    long_description = "MAPLE: Multi Agent Protocol Language Engine - Advanced multi-agent communication framework"

# Production dependencies
install_requires = [
    # Core dependencies (always required)
    "python-dateutil>=2.8.0",
    "typing-extensions>=4.0.0",
    
    # Security dependencies
    "PyJWT>=2.8.0",
    "cryptography>=41.0.0",
    
    # Optional performance dependencies
    "psutil>=5.9.0",  # For system monitoring
]

# Optional dependencies for different broker backends
extras_require = {
    # NATS broker support
    "nats": [
        "nats-py>=2.3.0",
        "asyncio-nats-client>=0.11.0"
    ],
    
    # RabbitMQ broker support (future)
    "rabbitmq": [
        "pika>=1.3.0",
        "kombu>=5.3.0"
    ],
    
    # Kafka broker support (future) 
    "kafka": [
        "kafka-python>=2.0.0",
        "aiokafka>=0.8.0"
    ],
    
    # Development and testing
    "dev": [
        "pytest>=7.0.0",
        "pytest-asyncio>=0.21.0",
        "pytest-cov>=4.0.0",
        "black>=23.0.0",
        "flake8>=6.0.0",
        "mypy>=1.0.0",
        "pre-commit>=3.0.0"
    ],
    
    # Performance and monitoring
    "monitoring": [
        "prometheus-client>=0.17.0",
        "opentelemetry-api>=1.20.0",
        "opentelemetry-sdk>=1.20.0"
    ],
    
    # Documentation
    "docs": [
        "sphinx>=7.0.0",
        "sphinx-rtd-theme>=1.3.0",
        "myst-parser>=2.0.0"
    ],
    
    # All optional dependencies
    "all": [
        # NATS
        "nats-py>=2.3.0",
        "asyncio-nats-client>=0.11.0",
        # RabbitMQ
        "pika>=1.3.0", 
        "kombu>=5.3.0",
        # Kafka
        "kafka-python>=2.0.0",
        "aiokafka>=0.8.0",
        # Monitoring
        "prometheus-client>=0.17.0",
        "opentelemetry-api>=1.20.0",
        "opentelemetry-sdk>=1.20.0",
        # Development
        "pytest>=7.0.0",
        "pytest-asyncio>=0.21.0",
        "pytest-cov>=4.0.0"
    ]
}

setup(
    name="maple-oss",
    version="1.0.0",
    author="Mahesh Vaikri",
    author_email="mahesh.vaikri@example.com",
    description="MAPLE: Multi Agent Protocol Language Engine - Advanced multi-agent communication framework",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/mahesh-vaikri/maple",
    project_urls={
        "Bug Tracker": "https://github.com/mahesh-vaikri/maple/issues",
        "Documentation": "https://maple-protocol.org/docs",
        "Source Code": "https://github.com/mahesh-vaikri/maple",
        "Research Paper": "https://maple-protocol.org/research"
    },
    packages=find_packages(),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: AGPL 3.0 License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Distributed Computing",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Internet :: WWW/HTTP :: Message Boards",
        "Topic :: Communications",
    ],
    python_requires=">=3.8",
    install_requires=install_requires,
    extras_require=extras_require,
    include_package_data=True,
    package_data={
        "maple": [
            "py.typed",  # Type hints marker
        ],
        "": [
            "LICENSE",
            "README.md",
            "CHANGELOG.md",
            "ATTRIBUTION.md"
        ]
    },
    entry_points={
        "console_scripts": [
            "maple-demo=maple.tools.demo:main",
            "maple-test=tests.comprehensive_test_suite:main",
            "maple-bench=maple.tools.benchmark:main",
        ],
    },
    keywords=[
        "agent", "multi-agent", "protocol", "communication", "AI", "distributed",
        "message-passing", "resource-management", "security", "NATS", "microservices",
        "mahesh-vaikri", "maple", "agent-communication", "production-ready"
    ],
    zip_safe=False,  # Required for proper typing support
)
