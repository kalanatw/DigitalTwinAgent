"""
Permission decorators and mixins for user-centric resource access.

This module provides decorators for checking access permissions to various
resources including documents, twin versions, and agent configurations.
"""

import functools
import logging
from typing import Callable

from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from .models import AgentConfiguration, Document, TwinVersion

logger = logging.getLogger(__name__)


def check_document_access(view_func: Callable) -> Callable:
    """
    Decorator to verify user has access to the requested document.

    This decorator should be applied after @login_required to ensure
    the user is authenticated before checking document access permissions.

    Args:
        view_func: The view function to wrap

    Returns:
        Wrapped view function with document access checking

    Access Rules:
    - User owns the document
    - Document is publicly shared (is_shared=True)
    - Document is specifically shared with the user via DocumentShare
    """

    @functools.wraps(view_func)
    def wrapper(request, document_id, *args, **kwargs):
        document = get_object_or_404(Document, id=document_id)

        # Check if user owns the document
        if document.uploaded_by == request.user:
            return view_func(request, document_id, *args, **kwargs)

        # Check if document is shared and accessible
        if document.is_shared:
            # Public share
            return view_func(request, document_id, *args, **kwargs)

        # Check if specifically shared with this user via DocumentShare
        if document.shares.filter(shared_with=request.user).exists():
            return view_func(request, document_id, *args, **kwargs)

        # Access denied
        logger.warning(
            f"Access denied: User {request.user.username} attempted to access "
            f"document {document_id} without permission"
        )
        return JsonResponse({"error": "Access denied"}, status=403)

    return wrapper


def check_twin_version_access(view_func: Callable) -> Callable:
    """
    Decorator to verify user has access to the requested twin version.

    This decorator should be applied after @login_required to ensure
    the user is authenticated before checking twin version access permissions.

    Args:
        view_func: The view function to wrap

    Returns:
        Wrapped view function with twin version access checking

    Access Rules:
    - User owns the twin version
    - Twin version is publicly shared (is_shared=True)
    - Twin version is specifically shared with the user via TwinVersionShare
    """

    @functools.wraps(view_func)
    def wrapper(request, twin_version_id, *args, **kwargs):
        twin_version = get_object_or_404(TwinVersion, id=twin_version_id)

        # Check if user owns the twin version
        if twin_version.user == request.user:
            return view_func(request, twin_version_id, *args, **kwargs)

        # Check if twin version is shared and accessible
        if twin_version.is_shared:
            # Public share
            return view_func(request, twin_version_id, *args, **kwargs)

        # Check if specifically shared with this user via TwinVersionShare
        if twin_version.shares.filter(shared_with=request.user).exists():
            return view_func(request, twin_version_id, *args, **kwargs)

        # Access denied
        logger.warning(
            f"Access denied: User {request.user.username} attempted to access "
            f"twin version {twin_version_id} without permission"
        )
        return JsonResponse({"error": "Access denied"}, status=403)

    return wrapper


def check_agent_access(view_func: Callable) -> Callable:
    """
    Decorator to verify user has access to the requested agent configuration.

    This decorator should be applied after @login_required to ensure
    the user is authenticated before checking agent access permissions.

    Args:
        view_func: The view function to wrap

    Returns:
        Wrapped view function with agent access checking

    Access Rules:
    - User owns the agent configuration
    - Agent is publicly shared (is_shared=True)
    - Agent is specifically shared with the user via AgentShare
    """

    @functools.wraps(view_func)
    def wrapper(request, agent_id, *args, **kwargs):
        agent = get_object_or_404(AgentConfiguration, id=agent_id)

        # Check if user owns the agent
        if agent.user == request.user:
            return view_func(request, agent_id, *args, **kwargs)

        # Check if agent is shared and accessible
        if agent.is_shared:
            # Public share
            return view_func(request, agent_id, *args, **kwargs)

        # Check if specifically shared with this user via AgentShare
        if agent.shares.filter(shared_with=request.user).exists():
            return view_func(request, agent_id, *args, **kwargs)

        # Access denied
        logger.warning(
            f"Access denied: User {request.user.username} attempted to access "
            f"agent {agent_id} without permission"
        )
        return JsonResponse({"error": "Access denied"}, status=403)

    return wrapper
