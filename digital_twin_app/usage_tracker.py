"""
Utility functions for user-centric resource management and usage tracking
"""
import logging
from django.utils import timezone
from django.db.models import Sum, Count
from .models import UserProfile, TokenUsage, DocumentUsage, AgentUsage
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)


def record_token_usage(user, tokens_used, input_tokens=0, output_tokens=0, 
                      resource_type=None, resource_id=None, operation=None):
    """
    Record token usage for a specific user
    
    Args:
        user (User): Django User object
        tokens_used (int): Total tokens used
        input_tokens (int): Input tokens used (optional)
        output_tokens (int): Output tokens used (optional)
        resource_type (str): Type of resource ('agent', 'document', etc.)
        resource_id (str): ID of the resource
        operation (str): Type of operation performed
    """
    try:
        if not user or not isinstance(user, User):
            logger.warning(f"Invalid user provided for token usage tracking: {user}")
            return
            
        # Record token usage
        TokenUsage.objects.create(
            user=user,
            tokens_used=tokens_used,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            resource_type=resource_type or 'other',
            resource_id=str(resource_id) if resource_id else None,
            operation=operation or 'usage'
        )
        
        # Update user profile totals
        profile, created = UserProfile.objects.get_or_create(user=user)
        profile.total_tokens_used += tokens_used
        profile.total_input_tokens += input_tokens
        profile.total_output_tokens += output_tokens
        profile.save(update_fields=[
            'total_tokens_used', 
            'total_input_tokens', 
            'total_output_tokens',
            'updated_at'
        ])
        
        logger.debug(
            f"Token usage recorded for {user.username}: {tokens_used} tokens "
            f"({input_tokens} input, {output_tokens} output)"
        )
        
    except Exception as e:
        logger.error(f"Failed to record token usage: {str(e)}")


def record_document_usage(user, document, operation, tokens_used=0):
    """
    Record document usage for a specific user and document
    
    Args:
        user (User): Django User object
        document (Document): Document object
        operation (str): Type of operation performed
        tokens_used (int): Tokens used for this operation
    """
    try:
        DocumentUsage.objects.create(
            user=user,
            document=document,
            operation=operation,
            tokens_used=tokens_used
        )
        
        # Also record in general token usage
        if tokens_used > 0:
            record_token_usage(
                user=user,
                tokens_used=tokens_used,
                resource_type='document',
                resource_id=document.id,
                operation=operation
            )
            
        logger.debug(
            f"Document usage recorded: {user.username}, doc: {document.title}, "
            f"operation: {operation}, tokens: {tokens_used}"
        )
            
    except Exception as e:
        logger.error(f"Failed to record document usage: {str(e)}")


def record_agent_usage(user, agent, operation, tokens_used=0, input_tokens=0, output_tokens=0):
    """
    Record agent usage for a specific user and agent
    
    Args:
        user (User): Django User object
        agent (AgentConfiguration): Agent object
        operation (str): Type of operation performed
        tokens_used (int): Total tokens used
        input_tokens (int): Input tokens used
        output_tokens (int): Output tokens used
    """
    try:
        AgentUsage.objects.create(
            user=user,
            agent=agent,
            operation=operation,
            tokens_used=tokens_used,
            input_tokens=input_tokens,
            output_tokens=output_tokens
        )
        
        # Also record in general token usage
        record_token_usage(
            user=user,
            tokens_used=tokens_used,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            resource_type='agent',
            resource_id=agent.id,
            operation=operation
        )
            
        logger.debug(
            f"Agent usage recorded: {user.username}, agent: {agent.name}, "
            f"operation: {operation}, tokens: {tokens_used}"
        )
            
    except Exception as e:
        logger.error(f"Failed to record agent usage: {str(e)}")


def get_user_token_statistics(user, days=30):
    """
    Get token usage statistics for a user over the specified period
    
    Args:
        user (User): Django User object
        days (int): Number of days to look back
    
    Returns:
        dict: Token usage statistics
    """
    try:
        since_date = timezone.now() - timezone.timedelta(days=days)
        
        # Get profile stats
        profile = UserProfile.objects.get(user=user)
        
        # Recent usage
        recent_usage = TokenUsage.objects.filter(
            user=user,
            timestamp__gte=since_date
        ).aggregate(
            total=Sum('tokens_used'),
            input_total=Sum('input_tokens'),
            output_total=Sum('output_tokens')
        )
        
        # Usage by resource type
        resource_usage = TokenUsage.objects.filter(
            user=user,
            timestamp__gte=since_date
        ).values('resource_type').annotate(
            total=Sum('tokens_used')
        ).order_by('-total')
        
        # Daily usage for charts
        daily_usage = get_daily_usage(user, days)
        
        return {
            'total_all_time': profile.total_tokens_used,
            'total_recent': recent_usage['total'] or 0,
            'input_recent': recent_usage['input_total'] or 0,
            'output_recent': recent_usage['output_total'] or 0,
            'by_resource': list(resource_usage),
            'daily': daily_usage,
            'days': days
        }
        
    except Exception as e:
        logger.error(f"Failed to get user token statistics: {str(e)}")
        return {
            'total_all_time': 0,
            'total_recent': 0,
            'input_recent': 0,
            'output_recent': 0,
            'by_resource': [],
            'daily': {'dates': [], 'values': []},
            'days': days
        }


def get_daily_usage(user, days=30):
    """
    Get daily token usage for charting
    
    Args:
        user (User): Django User object
        days (int): Number of days to look back
        
    Returns:
        dict: With dates and values lists for charting
    """
    try:
        since_date = timezone.now() - timezone.timedelta(days=days)
        
        # Initialize all days with zero values
        dates = []
        values = []
        for i in range(days, 0, -1):
            date = timezone.now() - timezone.timedelta(days=i)
            dates.append(date.strftime('%Y-%m-%d'))
            values.append(0)
        
        # Get actual data
        daily_data = TokenUsage.objects.filter(
            user=user, 
            timestamp__gte=since_date
        ).extra({
            'date': "DATE(timestamp)"
        }).values('date').annotate(
            total=Sum('tokens_used')
        ).order_by('date')
        
        # Update values with actual data
        date_map = {date: i for i, date in enumerate(dates)}
        for entry in daily_data:
            date_str = entry['date'].strftime('%Y-%m-%d')
            if date_str in date_map:
                values[date_map[date_str]] = entry['total']
                
        return {
            'dates': dates,
            'values': values
        }
        
    except Exception as e:
        logger.error(f"Failed to get daily usage data: {str(e)}")
        return {'dates': [], 'values': []}


def check_user_token_limits(user):
    """
    Check if a user has exceeded their token usage limits
    
    Args:
        user (User): Django User object
        
    Returns:
        tuple: (has_exceeded, limit_type)
    """
    try:
        profile = UserProfile.objects.get(user=user)
        
        # Check daily limit
        today = timezone.now().date()
        daily_usage = TokenUsage.objects.filter(
            user=user, 
            timestamp__date=today
        ).aggregate(total=Sum('tokens_used'))['total'] or 0
        
        if daily_usage >= profile.daily_token_limit:
            return True, "daily"
            
        # Check monthly limit
        thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
        monthly_usage = TokenUsage.objects.filter(
            user=user, 
            timestamp__gte=thirty_days_ago
        ).aggregate(total=Sum('tokens_used'))['total'] or 0
        
        if monthly_usage >= profile.monthly_token_limit:
            return True, "monthly"
            
        return False, None
        
    except Exception as e:
        logger.error(f"Failed to check token limits: {str(e)}")
        return False, None
