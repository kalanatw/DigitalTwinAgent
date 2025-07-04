#!/bin/bash

# Digital Twin Application Setup Script

echo "🚀 Setting up Digital Twin Application..."

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "📚 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Copy environment file
echo "⚙️ Setting up environment..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "✅ Created .env file from .env.example"
    echo "⚠️  Please edit .env file with your OpenAI API key and other settings"
else
    echo "✅ .env file already exists"
fi

# Run Django migrations
echo "🗄️ Setting up database..."
python manage.py makemigrations
python manage.py migrate

# Create superuser (optional)
echo "👤 Creating superuser (optional)..."
echo "You can skip this step by pressing Ctrl+C"
python manage.py createsuperuser || echo "Skipped superuser creation"

# Create logs directory
mkdir -p logs

echo "✅ Base setup complete!"

# Configure Google OAuth (if config file exists)
if [ -f google_oauth_config.json ]; then
    echo "🔐 Setting up Google OAuth..."
    python setup_google_oauth.py
else
    echo "⚠️ No google_oauth_config.json found. Skipping Google OAuth setup."
    echo "To enable Google login, create this file with your OAuth credentials."
    echo "See GOOGLE_OAUTH_README.md for details."
fi

echo ""
echo "📋 Next steps:"
echo "1. Edit .env file with your OpenAI API key"
echo "2. Start Redis server: redis-server"
echo "3. Run the application: python main.py"
echo ""
echo "🌐 Application will be available at:"
echo "   - Main app: http://localhost:8000/"
echo "   - FastAPI docs: http://localhost:8000/api/docs"
echo "   - Django admin: http://localhost:8000/admin/"
echo ""
echo "🔑 Login options:"
echo "   - Default user: username 'admin', password 'admin'"
echo "   - Google OAuth (if configured)"
