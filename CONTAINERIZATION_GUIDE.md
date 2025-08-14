# AI Video Editor - Containerization Guide

## Overview

This guide documents the complete migration from S3-hosted vanilla JavaScript frontend to a fully containerized React application running alongside the backend on the same infrastructure.

## Migration Summary

### Before (Legacy Architecture)
- **Frontend**: Vanilla JavaScript hosted on Amazon S3 static website
- **Backend**: Flask API + Celery workers on EC2
- **Communication**: Frontend calls `http://awscloudops.in:5000` API endpoint
- **Deployment**: Manual S3 upload for frontend, manual EC2 deployment for backend

### After (Containerized Architecture)
- **Frontend**: React TypeScript app served by nginx in container
- **Backend**: Flask API with Gunicorn in container
- **Worker**: Celery worker in dedicated container
- **Redis**: Dedicated Redis container for message broker
- **Orchestration**: Docker Compose for multi-container management

## Framework Selection: React

**Decision**: React with TypeScript was chosen over Vue.js and Svelte.

**Justification**:
- **Complexity Analysis**: The original frontend had 14 functions and 24 async operations, indicating moderate complexity
- **TypeScript Support**: Excellent TypeScript integration for better maintainability
- **Ecosystem**: Mature ecosystem with extensive libraries (WaveSurfer.js integration)
- **Audio Visualization**: Strong support for complex audio visualization requirements
- **Team Familiarity**: Widely adopted with extensive documentation and community support

**Alternatives Considered**:
- **Vue.js**: Good option but smaller ecosystem for audio processing libraries
- **Svelte**: Excellent performance but less mature ecosystem for complex audio/video workflows

## Container Architecture

### 1. Frontend Container (`Dockerfile.frontend`)
```dockerfile
# Multi-stage build for React frontend
FROM node:18-alpine AS build
WORKDIR /app
COPY frontend-react/package*.json ./
RUN npm ci
COPY frontend-react/ ./
RUN npm run build

# Production stage with nginx
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

**Features**:
- Multi-stage build for optimized production image
- nginx for production-ready static file serving
- Custom nginx configuration for API proxying
- Optimized build process with npm ci

### 2. Backend API Container (`Dockerfile.api`)
```dockerfile
FROM python:3.12-slim
WORKDIR /usr/src/app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py main_editor.py tasks.py audio_analyzer.py bedrock_director.py video_analyzer.py reel_assembler.py ./
RUN pip install --no-cache-dir gunicorn
EXPOSE 5000
CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:5000", "app:app"]
```

**Features**:
- Production-ready Gunicorn WSGI server
- All required Python modules included
- Optimized for container networking
- Environment variable configuration

### 3. Celery Worker Container (`Dockerfile.worker`)
```dockerfile
FROM python:3.12-slim
WORKDIR /usr/src/app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY tasks.py main_editor.py audio_analyzer.py bedrock_director.py video_analyzer.py reel_assembler.py ./
ENV CELERY_BROKER_URL="redis://redis:6379/0"
ENV CELERY_RESULT_BACKEND="redis://redis:6379/0"
CMD ["celery", "-A", "tasks.celery_app", "worker", "--loglevel=info"]
```

**Features**:
- Dedicated worker for background video processing
- Redis connectivity via container networking
- All video processing modules included
- Configurable logging levels

### 4. Redis Container
```yaml
redis:
  image: redis:7-alpine
  container_name: ai-editor-redis
  ports:
    - "6380:6379"
  volumes:
    - redis_data:/data
  restart: unless-stopped
```

**Features**:
- Official Redis Alpine image for minimal footprint
- Persistent data storage with named volumes
- External port mapping for debugging (6380:6379)
- Automatic restart policy

## Docker Compose Configuration

### Service Dependencies
```yaml
services:
  redis:     # Base service - no dependencies
  api:       # depends_on: redis
  worker:    # depends_on: redis, api
  frontend:  # depends_on: api
```

### Environment Variables
```yaml
environment:
  - S3_INPUT_BUCKET=${S3_INPUT_BUCKET:-ai-edit-input-bucket}
  - S3_OUTPUT_BUCKET=${S3_OUTPUT_BUCKET:-ai-edit-output-bucket}
  - S3_REGION=${S3_REGION:-ap-south-1}
  - AWS_REGION=${AWS_REGION:-ap-south-1}
  - CELERY_BROKER_URL=redis://redis:6379/0
  - CELERY_RESULT_BACKEND=redis://redis:6379/0
  - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
  - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
```

### Networking
- **Custom Network**: `ai-editor-network` for inter-container communication
- **Service Discovery**: Containers communicate using service names (e.g., `redis:6379`)
- **Port Mapping**: External access via localhost ports

## Frontend Migration Details

### Component Architecture
```
src/
├── components/
│   ├── AudioUpload.tsx      # File upload with progress
│   ├── VideoUpload.tsx      # Multiple video file handling
│   ├── AudioSelector.tsx    # WaveSurfer.js integration
│   └── JobStatus.tsx        # Real-time status polling
├── config/
│   └── api.ts              # Environment-based API configuration
├── types/
│   └── index.ts            # TypeScript interfaces
└── App.tsx                 # Main application component
```

### Key Migrations
1. **File Upload**: Converted from vanilla JS XMLHttpRequest to React hooks with TypeScript
2. **Audio Visualization**: Migrated WaveSurfer.js integration to React component lifecycle
3. **State Management**: Replaced global variables with React state and props
4. **API Communication**: Centralized API configuration with environment variables
5. **Error Handling**: Improved error boundaries and user feedback

### Preserved Functionality
- ✅ File upload with progress tracking
- ✅ Audio segment selection with WaveSurfer.js
- ✅ Real-time job status polling
- ✅ AI suggestion handling
- ✅ Manual/AI mode toggling
- ✅ Download functionality

## Environment Configuration

### Development (.env)
```bash
# Local development configuration
REACT_APP_API_BASE_URL=http://localhost:5000
AWS_ACCESS_KEY_ID=your_dev_key
AWS_SECRET_ACCESS_KEY=your_dev_secret
S3_INPUT_BUCKET=ai-edit-input-bucket-dev
S3_OUTPUT_BUCKET=ai-edit-output-bucket-dev
```

### Production (.env.production)
```bash
# Production configuration
REACT_APP_API_BASE_URL=http://api:5000
AWS_ACCESS_KEY_ID=your_prod_key
AWS_SECRET_ACCESS_KEY=your_prod_secret
S3_INPUT_BUCKET=ai-edit-input-bucket
S3_OUTPUT_BUCKET=ai-edit-output-bucket
```

## Testing Strategy

### 1. Container Health Checks
```bash
# Verify all containers are running
docker-compose ps

# Check container logs
docker-compose logs api
docker-compose logs worker
docker-compose logs frontend
docker-compose logs redis
```

### 2. API Connectivity Tests
```python
# test_containerized_workflow.py
def test_api_health():
    response = requests.get(f"{API_BASE_URL}/generate-download-url?s3_key=test")
    assert response.status_code == 200

def test_upload_url_generation():
    payload = {"filename": "test.mp3", "fileType": "audio/mpeg"}
    response = requests.post(f"{API_BASE_URL}/generate-upload-url", json=payload)
    assert response.status_code == 200
    assert 'uploadUrl' in response.json()
```

### 3. End-to-End Workflow Tests
- File upload through React frontend
- Audio analysis and segment suggestion
- Video processing job creation
- Real-time status updates
- Final video download

## Performance Optimizations

### Frontend Optimizations
- **Multi-stage Docker build** for minimal production image size
- **nginx gzip compression** for faster asset delivery
- **React production build** with code splitting and minification
- **Efficient re-renders** with proper React hooks usage

### Backend Optimizations
- **Gunicorn multi-worker** setup for concurrent request handling
- **Container resource limits** to prevent resource exhaustion
- **Redis connection pooling** for efficient message broker usage
- **Optimized Python imports** to reduce container startup time

### Container Optimizations
- **Alpine Linux base images** for minimal footprint
- **Layer caching** for faster rebuilds during development
- **Named volumes** for persistent data storage
- **Health checks** for automatic container recovery

## Deployment Strategies

### Local Development
```bash
# Start all services with hot reload
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up --build

# Individual service development
docker-compose up redis api worker  # Backend only
docker-compose up frontend          # Frontend only
```

### Production Deployment
```bash
# Production startup with optimized settings
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# Health monitoring
docker-compose ps
docker-compose logs -f
```

### Scaling Considerations
```yaml
# Scale workers for high load
docker-compose up --scale worker=3

# Load balancer configuration for multiple API instances
docker-compose up --scale api=2
```

## Security Considerations

### Container Security
- **Non-root user** execution in containers
- **Minimal base images** to reduce attack surface
- **Environment variable** management for secrets
- **Network isolation** between services

### API Security
- **CORS configuration** for frontend-backend communication
- **Input validation** for file uploads
- **AWS IAM roles** for secure S3 access
- **Rate limiting** for API endpoints

## Monitoring and Logging

### Container Logs
```bash
# Centralized logging
docker-compose logs -f --tail=100

# Service-specific logs
docker-compose logs -f api
docker-compose logs -f worker
```

### Health Monitoring
```yaml
# Health check configuration
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
```

### Performance Metrics
- Container resource usage monitoring
- API response time tracking
- Video processing job duration
- Redis queue depth monitoring

## Troubleshooting Guide

### Common Issues

1. **Container Startup Failures**
   ```bash
   # Check container logs
   docker-compose logs <service_name>
   
   # Rebuild specific container
   docker-compose build <service_name>
   ```

2. **API Import Errors**
   ```bash
   # Verify all Python modules are copied
   docker exec -it ai-editor-api ls -la
   
   # Test imports manually
   docker exec -it ai-editor-api python -c "import audio_analyzer"
   ```

3. **Redis Connection Issues**
   ```bash
   # Test Redis connectivity
   docker exec -it ai-editor-redis redis-cli ping
   
   # Check network connectivity
   docker exec -it ai-editor-worker ping redis
   ```

4. **Frontend Build Failures**
   ```bash
   # Check Node.js version compatibility
   docker run --rm node:18-alpine node --version
   
   # Verify package.json dependencies
   docker exec -it ai-editor-frontend npm list
   ```

### Performance Issues

1. **Slow Container Startup**
   - Use Docker layer caching
   - Optimize Dockerfile instruction order
   - Use .dockerignore to exclude unnecessary files

2. **High Memory Usage**
   - Set container memory limits
   - Monitor with `docker stats`
   - Optimize Python worker processes

3. **Network Latency**
   - Use container networking instead of host networking
   - Optimize nginx configuration
   - Enable gzip compression

## Migration Checklist

### Pre-Migration
- ✅ Backup existing S3 frontend files
- ✅ Document current API endpoints
- ✅ Test existing functionality
- ✅ Prepare AWS credentials

### Migration Steps
- ✅ Create React TypeScript application
- ✅ Migrate vanilla JS components to React
- ✅ Create Docker containers for all services
- ✅ Configure Docker Compose orchestration
- ✅ Set up nginx reverse proxy
- ✅ Configure environment variables
- ✅ Test containerized workflow

### Post-Migration
- ✅ Verify all functionality works
- ✅ Performance testing
- ✅ Documentation updates
- ✅ Deployment scripts creation
- ✅ Monitoring setup

## Future Enhancements

### Potential Improvements
1. **Kubernetes Deployment**: Migrate from Docker Compose to Kubernetes for production scalability
2. **CI/CD Pipeline**: Automated testing and deployment pipeline
3. **Monitoring Stack**: Prometheus + Grafana for comprehensive monitoring
4. **Load Balancing**: nginx load balancer for multiple API instances
5. **Database Integration**: PostgreSQL for persistent job history and user management

### Scalability Considerations
- Horizontal scaling of Celery workers
- Redis Cluster for high availability
- CDN integration for frontend assets
- Microservices architecture for complex workflows

## Conclusion

The containerization migration successfully transforms the AI Video Editor from a mixed S3/EC2 deployment to a fully containerized, orchestrated application. This provides:

- **Improved Developer Experience**: Consistent development environment across teams
- **Enhanced Maintainability**: Modern React codebase with TypeScript
- **Better Deployment**: Simplified deployment with Docker Compose
- **Increased Reliability**: Container health checks and restart policies
- **Future-Proof Architecture**: Foundation for Kubernetes and microservices migration

The migration preserves all existing functionality while providing a solid foundation for future enhancements and scaling requirements.
