"""
User Profile views with token usage statistics
"""
import logging
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum, Count
from django.http import JsonResponse
import json

from .models import (
    UserProfile, TokenUsage, Document, TwinVersion, AgentConfiguration,
    DocumentShare, TwinVersionShare, AgentShare
)
from .usage_tracker import get_user_token_statistics

logger = logging.getLogger(__name__)


@login_required
def profile_view(request):
    """
    User profile view showing token usage statistics
    """
    try:
        # Get user profile
        profile, created = UserProfile.objects.get_or_create(user=request.user)
        
        # Get token usage statistics
        token_stats = get_user_token_statistics(request.user)
        
        # Get user's resources
        document_count = Document.objects.filter(user=request.user).count()
        twin_version_count = TwinVersion.objects.filter(user=request.user).count()
        agent_count = AgentConfiguration.objects.filter(user=request.user).count()
        
        # Prepare context for template
        context = {
            'user': request.user,
            'profile': profile,
            'token_stats': token_stats,
            'document_count': document_count,
            'twin_version_count': twin_version_count,
            'agent_count': agent_count,
            'daily_usage_dates': json.dumps(token_stats['daily']['dates']),
            'daily_usage_values': json.dumps(token_stats['daily']['values']),
        }
        
        return render(request, 'profile.html', context)
        
    except Exception as e:
        logger.error(f"Error loading profile: {str(e)}")
        # Fallback to simple profile
        return render(request, 'profile.html', {'user': request.user})


@login_required
def api_token_usage(request):
    """
    API endpoint for getting token usage statistics
    """
    try:
        days = int(request.GET.get('days', 30))
        stats = get_user_token_statistics(request.user, days)
        
        return JsonResponse(stats)
        
    except Exception as e:
        logger.error(f"Error getting token usage: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_user_resources(request):
    """
    API endpoint for getting user resource counts
    """
    try:
        # Get user's resource counts
        documents = Document.objects.filter(user=request.user)
        twin_versions = TwinVersion.objects.filter(user=request.user)
        agents = AgentConfiguration.objects.filter(user=request.user)
        
        # Get shared resource counts
        shared_documents = Document.objects.filter(shares__shared_with=request.user).count()
        shared_twin_versions = TwinVersion.objects.filter(shares__shared_with=request.user).count()
        shared_agents = AgentConfiguration.objects.filter(shares__shared_with=request.user).count()
        
        # Get public resource counts
        public_documents = Document.objects.filter(is_shared=True).exclude(user=request.user).count()
        public_twin_versions = TwinVersion.objects.filter(is_shared=True).exclude(user=request.user).count()
        public_agents = AgentConfiguration.objects.filter(is_shared=True).exclude(user=request.user).count()
        
        return JsonResponse({
            'own_resources': {
                'documents': documents.count(),
                'twin_versions': twin_versions.count(),
                'agents': agents.count(),
                'total': documents.count() + twin_versions.count() + agents.count(),
            },
            'shared_resources': {
                'documents': shared_documents,
                'twin_versions': shared_twin_versions,
                'agents': shared_agents,
                'total': shared_documents + shared_twin_versions + shared_agents,
            },
            'public_resources': {
                'documents': public_documents,
                'twin_versions': public_twin_versions,
                'agents': public_agents,
                'total': public_documents + public_twin_versions + public_agents,
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting user resources: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def set_token_limits(request):
    """
    API endpoint for setting token usage limits
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
        
    try:
        data = json.loads(request.body)
        profile = UserProfile.objects.get(user=request.user)
        
        # Update limits if provided
        if 'daily_limit' in data:
            profile.daily_token_limit = int(data['daily_limit'])
        
        if 'monthly_limit' in data:
            profile.monthly_token_limit = int(data['monthly_limit'])
            
        profile.save()
        
        return JsonResponse({
            'daily_limit': profile.daily_token_limit,
            'monthly_limit': profile.monthly_token_limit
        })
        
    except Exception as e:
        logger.error(f"Error setting token limits: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_shared_resources(request):
    """
    API endpoint for getting shared resources stats
    """
    try:
        # Get explicitly shared resources (shared directly with the user)
        shared_documents = Document.objects.filter(shares__shared_with=request.user).count()
        shared_twin_versions = TwinVersion.objects.filter(shares__shared_with=request.user).count()
        shared_agents = AgentConfiguration.objects.filter(shares__shared_with=request.user).count()
        
        # Get publicly shared resources (excluding user's own)
        public_documents = Document.objects.filter(is_shared=True).exclude(user=request.user).count()
        public_twin_versions = TwinVersion.objects.filter(is_shared=True).exclude(user=request.user).count()
        public_agents = AgentConfiguration.objects.filter(is_shared=True).exclude(user=request.user).count()
        
        return JsonResponse({
            'shared_with_me': {
                'documents': shared_documents,
                'twin_versions': shared_twin_versions,
                'agents': shared_agents,
                'total': shared_documents + shared_twin_versions + shared_agents
            },
            'public': {
                'documents': public_documents,
                'twin_versions': public_twin_versions,
                'agents': public_agents,
                'total': public_documents + public_twin_versions + public_agents
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting shared resources: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def profile_resources_view(request):
    """
    View for displaying user's resources and sharing information
    """
    try:
        # Get user's own resources
        own_documents = Document.objects.filter(user=request.user).count()
        own_twin_versions = TwinVersion.objects.filter(user=request.user).count()
        own_agents = AgentConfiguration.objects.filter(user=request.user).count()
        
        # Get shared resources (explicitly shared with the user)
        shared_documents = Document.objects.filter(shares__shared_with=request.user).count()
        shared_twin_versions = TwinVersion.objects.filter(shares__shared_with=request.user).count()
        shared_agents = AgentConfiguration.objects.filter(shares__shared_with=request.user).count()
        
        # Get publicly shared resources (excluding user's own)
        public_documents = Document.objects.filter(is_shared=True).exclude(user=request.user).count()
        public_twin_versions = TwinVersion.objects.filter(is_shared=True).exclude(user=request.user).count()
        public_agents = AgentConfiguration.objects.filter(is_shared=True).exclude(user=request.user).count()
        
        context = {
            'user': request.user,
            'own_resources': {
                'documents': own_documents,
                'twin_versions': own_twin_versions,
                'agents': own_agents,
                'total': own_documents + own_twin_versions + own_agents
            },
            'shared_resources': {
                'documents': shared_documents,
                'twin_versions': shared_twin_versions,
                'agents': shared_agents,
                'total': shared_documents + shared_twin_versions + shared_agents
            },
            'public_resources': {
                'documents': public_documents,
                'twin_versions': public_twin_versions,
                'agents': public_agents,
                'total': public_documents + public_twin_versions + public_agents
            }
        }
        
        return render(request, 'profile_resources.html', context)
        
    except Exception as e:
        logger.error(f"Error loading resources page: {str(e)}")
        return render(request, 'profile_resources.html', {'user': request.user})
