# Digital Twin Assistant

A comprehensive Django/FastAPI application that implements an agentic AI workflow using the OpenAI Agents Python SDK. This application features an agent that can chat about digital twins with access to sensor data and system monitoring capabilities.

## 🚀 Features

- **AI-Powered Agent**: Uses OpenAI Agents SDK for intelligent conversations about digital twin systems
- **Real-time Sensor Data**: Access to temperature, pressure, humidity, vibration, power consumption, and flow rate data
- **System Monitoring**: Monitor motors, pumps, controllers, and network components
- **Redis Caching**: High-performance caching for faster response times
- **Dual API**: Both Django REST Framework and FastAPI endpoints
- **Modern UI**: Responsive web interface with real-time chat functionality
- **Comprehensive Logging**: Detailed logging at each step of agent execution
- **Google OAuth Integration**: Secure authentication with Google accounts

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Django/       │    │   OpenAI        │
│   (Alpine.js)   │◄──►│   FastAPI       │◄──►│   Agents SDK    │
│                 │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   Redis Cache   │
                       │   + SQLite DB   │
                       └─────────────────┘
```

## 📋 Requirements

- Python 3.8+
- Redis server
- OpenAI API key
- Google OAuth credentials (optional, for Google login)

## 🛠️ Installation

### Quick Setup

```bash
# Clone or create the project directory
cd Digital_Twin

# Make setup script executable
chmod +x setup.sh

# Run setup script
./setup.sh
```

### Manual Setup

1. **Create virtual environment**:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Environment configuration**:
```bash
cp .env.example .env
# Edit .env file with your settings
```

4. **Database setup**:
```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser  # Optional
```

5. **Start Redis**:
```bash
redis-server
```

## 🚀 Running the Application

### Development Mode

```bash
# Start the integrated server (Django + FastAPI)
python main.py
```

### Alternative: Django Only

```bash
python manage.py runserver
```

### Alternative: FastAPI Only

```bash
uvicorn digital_twin_app.views:fastapi_app --reload --port 8001
```

## 🌐 Access Points

- **Main Application**: http://localhost:8000/
- **Chat Interface**: http://localhost:8000/chat/
- **FastAPI Documentation**: http://localhost:8000/api/docs
- **Django Admin**: http://localhost:8000/django/admin/
- **Health Check**: http://localhost:8000/health

## 🔧 Configuration

### Environment Variables (.env)

```env
OPENAI_API_KEY=your_openai_api_key_here
REDIS_URL=redis://localhost:6379/0
DEBUG=True
SECRET_KEY=your_secret_key_here
ALLOWED_HOSTS=localhost,127.0.0.1
LOG_LEVEL=INFO
OPENAI_MODEL=gpt-4-turbo-preview
AGENT_MAX_TURNS=20
AGENT_TIMEOUT=30
```

## 🤖 Agent Capabilities

The Digital Twin Agent can:

1. **Retrieve Sensor Data**:
   - Temperature, pressure, humidity
   - Vibration, power consumption, flow rate
   - Data from multiple locations (main_facility, secondary_unit, warehouse)

2. **System Status Monitoring**:
   - Motor status and performance
   - Pump operations and metrics
   - Controller diagnostics
   - Network component status

3. **Intelligent Conversations**:
   - Explain digital twin concepts
   - Analyze system performance
   - Provide operational insights
   - Answer technical questions

## 📊 API Endpoints

### FastAPI Endpoints

- `POST /api/chat` - Send message to agent
- `GET /api/health` - Service health check
- `GET /api/sessions/{session_id}/history` - Get conversation history
- `DELETE /api/sessions/{session_id}` - Clear session
- `GET /api/tools/sensor-data` - Direct sensor data access
- `GET /api/tools/system-status` - Direct system status access

### Django REST Framework

- `POST /api/drf-chat/` - Alternative chat endpoint
- `GET /admin/` - Django admin interface

## 🛠️ Tools

### SensorDataTool

Retrieves sensor readings with the following parameters:
- `sensor_type`: temperature, pressure, humidity, vibration, power_consumption, flow_rate, or "all"
- `location`: main_facility, secondary_unit, warehouse

### SystemStatusTool

Monitors system components:
- `system_component`: motors, pumps, controllers, network, or "all"

## 📝 Usage Examples

### Chat Interface

1. Visit http://localhost:8000/
2. Ask questions like:
   - "Show me all sensor data from the main facility"
   - "What is the current system status?"
   - "Explain what a digital twin is"
   - "Are there any warnings in the vibration sensors?"

### API Usage

```python
import requests

# Send a chat message
response = requests.post('http://localhost:8000/api/chat', json={
    'message': 'Show me temperature readings',
    'session_id': 'my_session_123'
})

print(response.json())
```

### Direct Tool Access

```python
# Get sensor data directly
response = requests.get('http://localhost:8000/api/tools/sensor-data?sensor_type=temperature&location=main_facility')
print(response.json())
```

## 📊 Logging

The application provides comprehensive logging:

- **Application logs**: `logs/app.log`
- **Agent logs**: `logs/agent.log`
- **Tool logs**: `logs/tools.log`
- **Debug logs**: `logs/debug.log`

## 🧪 Testing

```bash
# Run tests
python -m pytest

# Run specific tests
python -m pytest tests/test_agent.py

# With coverage
python -m pytest --cov=digital_twin_app
```

## 🔒 Security Considerations

- Set strong `SECRET_KEY` in production
- Configure `ALLOWED_HOSTS` appropriately
- Use environment variables for sensitive data
- Enable HTTPS in production
- Implement rate limiting for API endpoints

## 🚀 Deployment

### Docker (Optional)

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["python", "main.py"]
```

### Production Considerations

- Use PostgreSQL instead of SQLite
- Configure Redis persistence
- Set up proper logging aggregation
- Implement monitoring and alerting
- Use reverse proxy (nginx)
- Configure SSL/TLS

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

## 🆘 Troubleshooting

### Common Issues

1. **OpenAI API Key Error**:
   - Ensure your API key is set in `.env`
   - Check API key permissions

2. **Redis Connection Error**:
   - Start Redis server: `redis-server`
   - Check Redis configuration

3. **Port Already in Use**:
   - Change port in `main.py`
   - Kill existing processes: `lsof -ti:8000 | xargs kill`

4. **Import Errors**:
   - Activate virtual environment
   - Install all requirements: `pip install -r requirements.txt`

### Getting Help

- Check the logs in the `logs/` directory
- Review the FastAPI documentation at `/api/docs`
- Ensure all services are running (Redis, Django, FastAPI)

## 🔗 Related Links

- [OpenAI Agents SDK](https://github.com/openai/openai-agents-python)
- [Django Documentation](https://docs.djangoproject.com/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Redis Documentation](https://redis.io/documentation)

## 🔐 Google OAuth Setup

This application supports authentication via Google OAuth. To enable it:

1. **Create Google OAuth credentials**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a project and enable the Google OAuth API
   - Create OAuth client credentials with this redirect URI:
     `http://localhost:8000/accounts/google/login/callback/`

2. **Configure the application**:
   - Save your credentials in `google_oauth_config.json` (see `GOOGLE_OAUTH_README.md` for details)
   - Run the setup script: `python setup_google_oauth.py`
   - Run migrations: `python manage.py migrate`

3. **Try it out**:
   - Visit the login page at `/login/`
   - Click "Continue with Google"

For detailed instructions, see `GOOGLE_OAUTH_README.md`
