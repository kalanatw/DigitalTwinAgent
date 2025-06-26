"""
Management command to create default user
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Create default user for the application'

    def handle(self, *args, **options):
        username = 'kalana'
        password = 'kalana123'
        email = 'kalana@example.com'
        
        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.SUCCESS(f'Default user "{username}" already exists'))
        else:
            user = User.objects.create_user(username=username, email=email, password=password)
            self.stdout.write(self.style.SUCCESS(f'Successfully created default user "{username}"'))
