# PyRinha 2025 - High-Performance Payment Processing System

A high-performance, distributed payment processing system built with Python and FastAPI for the [Rinha de Backend 2025 challenge](https://github.com/zanfranceschi/rinha-de-backend-2025/). This implementation demonstrates advanced backend engineering concepts including asynchronous processing, intelligent load balancing, health monitoring, and efficient data persistence under strict resource constraints.

## 🚀 Overview

PyRinha 2025 is my implementation of the Rinha de Backend 2025 challenge - a competitive programming contest focused on building high-performance backend systems. The challenge requires building a payment processing API that can handle thousands of concurrent requests while operating under strict resource limitations (1.5 CPU cores, 550MB RAM total).

This solution demonstrates advanced backend engineering concepts including asynchronous processing, intelligent load balancing, health monitoring, and efficient data persistence, all optimized for maximum performance within the contest constraints.

## 🏆 Rinha de Backend 2025 Challenge

This project is my solution to the [Rinha de Backend 2025](https://github.com/zanfranceschi/rinha-de-backend-2025/) - Brazil's premier backend performance competition. The challenge focuses on building systems that can handle massive concurrent loads while adhering to strict resource constraints.

### Challenge Requirements
- **Resource Limits**: Maximum 1.5 CPU cores and 550MB RAM across all services
- **High Concurrency**: Handle thousands of simultaneous payment requests
- **Fault Tolerance**: Graceful handling of external service failures
- **Performance**: Optimize for throughput and response times
- **Load Testing**: System must perform under K6 stress tests

### My Approach
- Intelligent resource allocation across services
- Async-first architecture for maximum concurrency
- Custom queue system optimized for the challenge constraints
- Strategic caching and database optimizations

## 🏗️ Architecture

The system follows a microservices architecture with the following components:

### Core Components

1. **Load Balancer (Nginx)**: Distributes incoming requests across multiple API instances
2. **API Instances**: Two FastAPI applications running in parallel for high availability
3. **Payment Processors**: External services (default and fallback) for payment processing
4. **Database**: PostgreSQL for persistent storage
5. **Cache**: Redis for performance optimization and health status caching
6. **Queue System**: Custom async queue for payment processing

### Architecture Diagram

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│   Client    │───▶│    Nginx     │───▶│   API 1/2   │
└─────────────┘    │ Load Balancer│    └─────────────┘
                   └──────────────┘           │
                                              ▼
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│   Redis     │◄───│ Health Check │───▶│  Processors │
│   Cache     │    │   Manager    │    │ (Def/Fall)  │
└─────────────┘    └──────────────┘    └─────────────┘
                                              │
┌─────────────┐    ┌──────────────┐          ▼
│ PostgreSQL  │◄───│ Payment Queue│◄─────────────────────
│  Database   │    │  & Workers   │
└─────────────┘    └──────────────┘
```

## 🛠️ Technologies Used

### Backend Framework
- **FastAPI**: Modern, fast web framework for building APIs with Python
- **Uvicorn**: ASGI server for running FastAPI applications
- **Pydantic**: Data validation and serialization

### Database & Caching
- **PostgreSQL**: Primary database for payment data persistence
- **SQLAlchemy**: ORM for database operations with connection pooling
- **Redis**: Caching layer for health status and performance optimization

### Networking & Communication
- **HTTPX**: Async HTTP client for external API communication
- **Nginx**: High-performance load balancer and reverse proxy

### Containerization & Orchestration
- **Docker**: Application containerization
- **Docker Compose**: Multi-container orchestration with resource limits

### Development Tools
- **UV**: Modern Python package manager for dependency management
- **Python 3.13**: Latest Python version with enhanced performance

## 🎯 Key Features

### 1. Intelligent Health Monitoring
- Real-time health checks for payment processors
- Automatic failover based on response times and availability
- Cached health status with periodic updates

### 2. Asynchronous Payment Processing
- Custom queue system with multiple worker threads
- Retry mechanism for failed payments
- Batch processing for database operations

### 3. High-Performance Database Operations
- Connection pooling for optimal database performance
- Batch inserts with fallback to individual operations
- Optimized PostgreSQL configuration for high throughput

### 4. Load Balancing & Scaling
- Nginx load balancer with keepalive connections
- Multiple API instances for horizontal scaling
- Resource limits for optimal memory usage

### 5. Fault Tolerance
- Automatic retry for failed operations
- Graceful degradation when services are unavailable
- Circuit breaker pattern for external service calls

## 📊 Performance Optimizations

### Database Layer
- **Batch Processing**: Groups multiple payments for efficient bulk inserts
- **Connection Pooling**: Reuses database connections to reduce overhead
- **Optimized Queries**: Uses SQLAlchemy for efficient database operations

### Caching Strategy
- **Health Status Caching**: Reduces external API calls for health checks
- **Redis Integration**: Fast in-memory caching for frequently accessed data

### Async Processing
- **Queue-Based Architecture**: Decouples request handling from processing
- **Multiple Workers**: Parallel processing of payment requests
- **Non-blocking Operations**: Maintains high throughput under load

## 🐳 Deployment

The application uses Docker Compose for easy deployment with the following services:

```yaml
services:
  - Load Balancer (Nginx) - 10MB RAM, 0.1 CPU
  - API Instance 1 & 2 - 120MB RAM each, 0.5 CPU each
  - PostgreSQL Database - 60MB RAM, 0.2 CPU
  - Redis Cache - 40MB RAM, 0.2 CPU
```

### Resource Allocation (Challenge Compliant)
```yaml
services:
  - Load Balancer (Nginx) - 10MB RAM, 0.1 CPU
  - API Instance 1 & 2 - 120MB RAM each, 0.5 CPU each  
  - PostgreSQL Database - 60MB RAM, 0.2 CPU
  - Redis Cache - 40MB RAM, 0.2 CPU
```

**Total: 350MB RAM, 1.4 CPU cores** (well within 550MB/1.5 CPU limits)

## 🔧 Configuration

### Environment Variables
- `DEFAULT_PAYMENT_PROCESSOR`: Primary payment processor URL
- `FALLBACK_PAYMENT_PROCESSOR`: Backup payment processor URL
- `DATABASE_URL`: PostgreSQL connection string

### Database Configuration
- Optimized for high-throughput operations
- Connection pooling with 10 base connections, 20 overflow
- Tuned PostgreSQL parameters for performance

## 📈 Monitoring & Observability

### Health Checks
- Automatic health monitoring of payment processors
- Response time tracking for intelligent routing
- Cached health status with 5-second refresh intervals

### Logging
- Structured logging for all operations
- Error tracking and monitoring
- Performance metrics collection

## 🚦 API Endpoints

### Payment Processing
- `POST /payments` - Queue payment for processing
- `GET /payments-summary` - Retrieve payment statistics
- `POST /purge-payments` - Clear all payment data (development)

## 🧪 Testing & Performance

### Load Testing
The system includes comprehensive load testing using K6, as required by the challenge:
```bash
make test WORKERS=250  # Run with 250 concurrent workers
```

### Performance Results
- **Throughput**: Handles 250+ concurrent requests efficiently
- **Memory Usage**: Stays well within 550MB limit under load
- **Response Times**: Optimized for sub-second response times
- **Fault Tolerance**: Graceful degradation when external services fail

### Challenge Compliance
- ✅ Resource constraints respected (350MB/1.4 CPU used of 550MB/1.5 CPU limit)
- ✅ All required endpoints implemented
- ✅ Proper error handling and edge cases covered
- ✅ Load testing integration with K6
- ✅ Docker containerization as specified

## 💡 Technical Highlights & Challenge Solutions

### Resource Optimization Strategies
1. **Memory-Efficient Architecture**: Custom buffering system to minimize memory footprint
2. **CPU Optimization**: Async-first design to maximize CPU utilization
3. **Database Tuning**: PostgreSQL configured for high-throughput, low-memory scenarios
4. **Smart Caching**: Redis used strategically to reduce database load

### Performance Engineering
1. **Batch Processing**: Groups database operations to reduce I/O overhead
2. **Connection Pooling**: Optimized pool sizes for the resource constraints
3. **Async Queue System**: Custom implementation optimized for the challenge requirements
4. **Load Balancing**: Nginx configured for maximum efficiency with minimal overhead

### Challenge-Specific Optimizations
1. **Intelligent Failover**: Health-based routing between payment processors
2. **Graceful Degradation**: System continues operating even under failure conditions
3. **Memory Management**: Careful buffer management to prevent OOM conditions
4. **Concurrent Processing**: Multiple worker pattern optimized for Python's GIL

## 🔄 Development & Challenge Participation

### Modern Python Tooling
- **UV**: Ultra-fast Python package manager for dependency management
- **Docker**: Containerization meeting challenge specifications
- **Make**: Simplified command execution for testing and deployment
- **Modular Architecture**: Clean separation of concerns for maintainability

### Why This Implementation Stands Out
1. **Python Performance**: Demonstrates that Python can compete in high-performance scenarios
2. **Resource Efficiency**: Achieves maximum performance within strict constraints
3. **Production Patterns**: Uses real-world architectural patterns and best practices
4. **Challenge Mastery**: Not just meeting requirements, but optimizing beyond them

## 🌟 Key Learnings & Achievements

This Rinha de Backend implementation showcases:
- **Systems Programming**: Deep understanding of resource management and optimization
- **Distributed Systems**: Proper handling of service communication and fault tolerance
- **Performance Engineering**: Optimization techniques for high-throughput scenarios
- **Modern Python**: Leveraging Python's async capabilities and modern tooling
- **Production Readiness**: Code quality and patterns suitable for production environments

The project demonstrates that with proper architecture and optimization techniques, Python can deliver exceptional performance even in resource-constrained environments, making it a valuable addition to any backend engineer's portfolio.

---

**Challenge Repository**: [Rinha de Backend 2025](https://github.com/zanfranceschi/rinha-de-backend-2025/)  
**Implementation**: Optimized for performance, built for scale, designed for reliability.