"""
Email Templates for Digital Assets Manager
"""

EMAIL_TEMPLATES = {
    "tariff_impact_analysis": {
        "subject": "US Tariff Impact Analysis - Market Update",
        "template": """
Dear {ContactName},

Please find attached our article regarding the recent tariffs announced by the United States. 

The aim of the article is to provide a high-level overview of the tariffs and what this potentially means to Australia and the global economy. 

Simplistically the negative share market reaction can be explained by the fact that tariffs increase the cost of goods which mean less goods are consumed.

Which in turn is likely to have negative implications for global economic growth. 

**Key points to note:**

• The U.S. has introduced broad tariff increases, applying a 10% base tariff to most imported goods — including those from Australia.

• Certain countries face even higher tariffs 

• For example Chinese imports to the U.S. will face a total tariff of 64% (including a new 34% retaliatory tariff).

• On average, tariffs on goods imported to the U.S. have increased from 2% last year to around 25% today.

• U.S. inflation is expected to increase by approximately 2.5% as a direct result of the tariffs.

• The direct Impact on Australia is expected to be limited — only 5% of Australia's exports go to the U.S. (compared to 37% to China and 15% to Japan).

• However, slower global economic growth — particularly in Asia — may indirectly affect demand for Australian exports.

• The tariff program adds complexity and uncertainty to investment markets (which markets don't like).

**Market Impact Summary:**

• The Australian share market (ASX/S&P 200) has fallen 7.1% since it's peak on 14th February 2025.

• U.S. and Japanese share markets have experienced larger falls over the same period.

• European, U.K., and Chinese markets have been more resilient.

• Bond markets have strengthened, with lower interest rate expectations supporting defensive investments like infrastructure.

**Looking Forward:**

• There is still an expectation that the new US government will introduce policies more supportive of company earnings.

• There is scope for most major economies to engage in easing of monetary policy

• Over the last 12 months there has been a growing disconnect between share market performance and the real economy 

• The full affect of the tariffs could take a while to play out

If you have any questions about this article and how the US tariffs may affect your portfolio please do not hesitate to contact us. 

Kind regards,
{ManagerName}
Digital Assets Manager
{CompanyName}
        """
    },
    
    "event_reminder": {
        "subject": "AAS & Global Lunch This Friday",
        "template": """
Hi {AdviserName},

Just a reminder of AAS' Adviser Lunch and Learn on Friday with GlobalX.

**Event Details:**
• **Date:** {EventDate}
• **Time:** {EventTime}
• **Location:** {EventLocation}
• **Dress Code:** {DressCode}

To add this event to your calendar, please click this link: {CalendarLink}

Please inform me of any dietary requirements if you have not already done so.

Look forward to it!

Regards,
{ManagerName}
Digital Assets Manager
{CompanyName}
        """
    },
    
    "portfolio_update": {
        "subject": "Portfolio Performance Update - {Period}",
        "template": """
Dear {ContactName},

I hope this email finds you well. I'm writing to provide you with your portfolio performance update for {Period}.

**Portfolio Summary:**
• Total Portfolio Value: {PortfolioValue}
• Performance YTD: {YTDPerformance}
• Benchmark Comparison: {BenchmarkComparison}

**Key Highlights:**
{KeyHighlights}

**Market Commentary:**
{MarketCommentary}

**Recommendations:**
{Recommendations}

**Upcoming Actions:**
{UpcomingActions}

Please don't hesitate to reach out if you have any questions or would like to schedule a call to discuss your portfolio in detail.

Best regards,
{ManagerName}
Digital Assets Manager
{CompanyName}
        """
    },
    
    "market_alert": {
        "subject": "Market Alert - {AlertType}",
        "template": """
Dear {ContactName},

I wanted to reach out immediately regarding {AlertReason}.

**Market Alert Details:**
• **Alert Type:** {AlertType}
• **Impact Level:** {ImpactLevel}
• **Affected Assets:** {AffectedAssets}

**Current Situation:**
{CurrentSituation}

**Immediate Actions Taken:**
{ActionsTaken}

**Recommendations:**
{Recommendations}

**Next Steps:**
{NextSteps}

I will continue monitoring the situation closely and will provide updates as they become available.

Please contact me immediately if you have any urgent concerns.

Best regards,
{ManagerName}
Digital Assets Manager
{CompanyName}
Emergency Contact: {EmergencyContact}
        """
    },
    
    "meeting_request": {
        "subject": "Portfolio Review Meeting - {ClientName}",
        "template": """
Dear {ContactName},

I hope you're doing well. I would like to schedule our regular portfolio review meeting to discuss your investment performance and strategy.

**Proposed Meeting Details:**
• **Purpose:** {MeetingPurpose}
• **Duration:** {Duration}
• **Format:** {MeetingFormat}
• **Suggested Dates:** {SuggestedDates}

**Meeting Agenda:**
{MeetingAgenda}

**Preparation Required:**
{PreparationNotes}

Please let me know which time works best for you, or feel free to suggest alternative dates.

Looking forward to our discussion.

Best regards,
{ManagerName}
Digital Assets Manager
{CompanyName}
        """
    },
    
    "client_onboarding": {
        "subject": "Welcome to Digital Assets Management",
        "template": """
Dear {ContactName},

Welcome to our Digital Assets Management services! We're thrilled to have you as our client and look forward to helping you achieve your investment goals.

**Your Account Details:**
• **Account Number:** {AccountNumber}
• **Portfolio Type:** {PortfolioType}
• **Assigned Manager:** {ManagerName}

**Getting Started:**
{GettingStarted}

**Next Steps:**
{NextSteps}

**Important Documents:**
{ImportantDocuments}

**Contact Information:**
• **Direct Phone:** {DirectPhone}
• **Email:** {ManagerEmail}
• **Emergency Contact:** {EmergencyContact}

Please don't hesitate to reach out if you have any questions. We're here to support you every step of the way.

Welcome aboard!

Best regards,
{ManagerName}
Digital Assets Manager
{CompanyName}
        """
    }
}

def get_template(template_type: str) -> dict:
    """
    Get a specific email template.
    
    Args:
        template_type: Type of template to retrieve
        
    Returns:
        Dictionary containing subject and template
    """
    return EMAIL_TEMPLATES.get(template_type, {
        "subject": "Digital Assets Communication",
        "template": "Dear {ContactName},\n\nThank you for your email. I will review your message and get back to you shortly.\n\nBest regards,\n{ManagerName}\nDigital Assets Manager"
    })

def get_available_templates() -> list:
    """
    Get list of available template types.
    
    Returns:
        List of available template names
    """
    return list(EMAIL_TEMPLATES.keys())

def format_template(template_type: str, **kwargs) -> dict:
    """
    Format a template with provided variables.
    
    Args:
        template_type: Type of template to format
        **kwargs: Variables to fill in the template
        
    Returns:
        Dictionary with formatted subject and body
    """
    template_data = get_template(template_type)
    
    try:
        formatted_subject = template_data["subject"].format(**kwargs)
        formatted_body = template_data["template"].format(**kwargs)
        
        return {
            "subject": formatted_subject,
            "body": formatted_body,
            "template_type": template_type
        }
    except KeyError as e:
        return {
            "subject": "Digital Assets Communication",
            "body": f"Error formatting template: Missing variable {e}",
            "template_type": template_type,
            "error": str(e)
        }
