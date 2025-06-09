"""
Email Tools for Digital Assets Manager Agent
"""
import logging
import json
from typing import Dict, Any, List
from agents import function_tool
from .email_templates import get_available_templates, get_template, format_template

logger = logging.getLogger(__name__)

@function_tool
def email_template_selector(template_type: str, contact_name: str = "Valued Client", manager_name: str = "Digital Assets Manager") -> str:
    """
    Select and format an email template for response.
    
    Args:
        template_type: Type of email template to use (tariff_impact_analysis, event_reminder, portfolio_update, market_alert, meeting_request, client_onboarding)
        contact_name: Name of the contact/client
        manager_name: Name of the manager sending the email
        
    Returns:
        JSON string containing formatted email template
    """
    logger.info(f"Selecting email template: {template_type}")
    
    try:
        # Get available templates
        available_templates = get_available_templates()
        print(f"Available templates: {available_templates}")
        
        if template_type not in available_templates:
            error_result = {
                "success": False,
                "error": f"Template '{template_type}' not found. Available templates: {', '.join(available_templates)}",
                "available_templates": available_templates
            }
            return json.dumps(error_result, indent=2)
        
        # Set default values for common variables
        template_vars = {
            "ContactName": contact_name,
            "ManagerName": manager_name,
            "CompanyName": "AAS Digital Assets",
            "EmergencyContact": "+61-2-9000-0000",
            "EventDate": "23rd of May",
            "EventTime": "12pm to 2pm",
            "EventLocation": "Union, University & Schools Club, 25 Bent St, Sydney NSW 2000",
            "DressCode": "Jacket and Tie required for Men, Ladies if the equivalent",
            "CalendarLink": "[Calendar Link]",
            "Period": "Current Quarter",
            "PortfolioValue": "$250,000",
            "YTDPerformance": "+8.5%",
            "BenchmarkComparison": "Outperforming benchmark by 2.1%",
            "AlertType": "Market Volatility",
            "ImpactLevel": "Medium",
            "ClientName": contact_name,
            "MeetingPurpose": "Portfolio Review and Strategy Discussion",
            "Duration": "60 minutes",
            "MeetingFormat": "In-person or Video Call",
            "AccountNumber": "AAS-2025-001",
            "PortfolioType": "Balanced Growth Portfolio",
            "AdviserName": manager_name,
            "KeyHighlights": "Strong performance across all asset classes",
            "MarketCommentary": "Markets remain volatile but showing signs of stabilization",
            "Recommendations": "Maintain current allocation with minor rebalancing",
            "UpcomingActions": "Portfolio review scheduled for next quarter",
            "CurrentSituation": "Market experiencing increased volatility",
            "ActionsTaken": "Risk management protocols activated",
            "NextSteps": "Continue monitoring and will update as needed",
            "AffectedAssets": "Growth equities and emerging markets",
            "AlertReason": "significant market movements",
            "SuggestedDates": "Next Wednesday or Friday afternoon",
            "MeetingAgenda": "Portfolio performance review and strategy discussion",
            "PreparationNotes": "Please review your recent statements",
            "GettingStarted": "Your account is being set up and will be ready within 2 business days",
            "ImportantDocuments": "Account terms, investment policy statement, and welcome guide",
            "DirectPhone": "+61-2-9000-0001",
            "ManagerEmail": "manager@aasdigitalassets.com.au"
        }
        
        # Format the template
        formatted_email = format_template(template_type, **template_vars)
        
        result = {
            "success": True,
            "template_type": template_type,
            "contact_name": contact_name,
            "subject": formatted_email["subject"],
            "body": formatted_email["body"],
            "variables_used": template_vars
        }
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        logger.error(f"Error selecting email template: {e}")
        error_result = {
            "success": False,
            "error": str(e),
            "template_type": template_type
        }
        return json.dumps(error_result, indent=2)

@function_tool
def list_email_templates() -> str:
    """
    List all available email templates with descriptions.
    
    Returns:
        JSON string containing all available templates
    """
    logger.info("Listing all available email templates")
    
    templates_info = {
        "tariff_impact_analysis": "US tariff impact analysis and market update for clients",
        "event_reminder": "Reminder for upcoming AAS events and meetings",
        "portfolio_update": "Regular portfolio performance updates for clients",
        "market_alert": "Urgent market alerts and notifications",
        "meeting_request": "Request meetings for portfolio reviews",
        "client_onboarding": "Welcome new clients to digital assets management"
    }
    
    result = {
        "success": True,
        "available_templates": get_available_templates(),
        "templates_info": templates_info,
        "total_templates": len(templates_info)
    }
    
    return json.dumps(result, indent=2)

@function_tool
def analyze_email_content(email_content: str) -> str:
    """
    Analyze incoming email content to suggest appropriate response template.
    
    Args:
        email_content: Content of the incoming email
        
    Returns:
        JSON string with analysis and template suggestions
    """
    logger.info("Analyzing email content for template suggestion")
    
    email_lower = email_content.lower()
    
    # Keywords for different template types
    template_keywords = {
        "tariff_impact_analysis": ["tariff", "trade", "market impact", "economic", "inflation", "global", "australia", "us", "china"],
        "event_reminder": ["event", "lunch", "meeting", "reminder", "friday", "globalx", "aas", "calendar"],
        "portfolio_update": ["portfolio", "performance", "update", "investment", "return", "benchmark"],
        "market_alert": ["alert", "urgent", "immediate", "crisis", "emergency", "volatility", "crash"],
        "meeting_request": ["meeting", "call", "discuss", "schedule", "review", "appointment"],
        "client_onboarding": ["welcome", "new", "onboard", "account", "getting started", "first time"]
    }
    
    suggestions = []
    confidence_scores = {}
    
    for template_type, keywords in template_keywords.items():
        score = sum(1 for keyword in keywords if keyword in email_lower)
        if score > 0:
            confidence_scores[template_type] = score
            suggestions.append({
                "template_type": template_type,
                "confidence": score,
                "matched_keywords": [kw for kw in keywords if kw in email_lower]
            })
    
    # Sort by confidence
    suggestions.sort(key=lambda x: x["confidence"], reverse=True)
    
    result = {
        "success": True,
        "email_length": len(email_content),
        "suggested_templates": suggestions[:3],  # Top 3 suggestions
        "confidence_scores": confidence_scores,
        "analysis_summary": f"Found {len(suggestions)} potential template matches"
    }
    
    return json.dumps(result, indent=2)
