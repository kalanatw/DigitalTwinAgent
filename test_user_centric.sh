#!/bin/bash
# Test script for user-centric resource management

echo "====================================================="
echo "Testing User-Centric Resource Management"
echo "====================================================="

# Activate virtual environment if exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run migrations
echo "Running migrations..."
python manage.py migrate

# Run the test
echo "Running user-centric resource tests..."
python manage.py test digital_twin_app.test_user_centric

# Run specific tests
echo "Testing resource sharing..."
python manage.py test digital_twin_app.test_user_centric.UserCentricResourcesTest.test_resource_sharing

echo "Testing token usage tracking..."
python manage.py test digital_twin_app.test_user_centric.UserCentricResourcesTest.test_token_usage_tracking

echo "====================================================="
echo "Test complete"
echo "====================================================="
