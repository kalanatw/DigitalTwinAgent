"""
Logging Configuration for Digital Twin Application
"""
import logging
import logging.config
import os
from datetime import datetime

# Create logs directory if it doesn't exist
log_dir = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(log_dir, exist_ok=True)

# Logging configuration
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'detailed': {
            'format': '{levelname} {asctime} [{name}] {pathname}:{lineno} - {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
        'simple': {
            'format': '{levelname} {asctime} {name} - {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
        'agent': {
            'format': '[AGENT] {asctime} {levelname} - {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'formatter': 'simple',
            'stream': 'ext://sys.stdout'
        },
        'file_debug': {
            'class': 'logging.FileHandler',
            'level': 'DEBUG',
            'formatter': 'detailed',
            'filename': os.path.join(log_dir, 'debug.log'),
            'mode': 'a',
        },
        'file_app': {
            'class': 'logging.FileHandler',
            'level': 'INFO',
            'formatter': 'simple',
            'filename': os.path.join(log_dir, 'app.log'),
            'mode': 'a',
        },
        'file_agent': {
            'class': 'logging.FileHandler',
            'level': 'INFO',
            'formatter': 'agent',
            'filename': os.path.join(log_dir, 'agent.log'),
            'mode': 'a',
        },
        'file_tools': {
            'class': 'logging.FileHandler',
            'level': 'INFO',
            'formatter': 'detailed',
            'filename': os.path.join(log_dir, 'tools.log'),
            'mode': 'a',
        }
    },
    'loggers': {
        'digital_twin_app': {
            'handlers': ['console', 'file_app', 'file_debug'],
            'level': 'INFO',
            'propagate': False,
        },
        'digital_twin_app.agent': {
            'handlers': ['console', 'file_agent', 'file_debug'],
            'level': 'INFO',
            'propagate': False,
        },
        'digital_twin_app.tools': {
            'handlers': ['console', 'file_tools', 'file_debug'],
            'level': 'INFO',
            'propagate': False,
        },
        'agents': {
            'handlers': ['console', 'file_agent'],
            'level': 'INFO',
            'propagate': False,
        },
        'uvicorn': {
            'handlers': ['console', 'file_app'],
            'level': 'INFO',
            'propagate': False,
        },
        'fastapi': {
            'handlers': ['console', 'file_app'],
            'level': 'INFO',
            'propagate': False,
        }
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    }
}

def setup_logging():
    """Setup logging configuration."""
    logging.config.dictConfig(LOGGING_CONFIG)
    
    # Log startup message
    logger = logging.getLogger('digital_twin_app')
    logger.info("="*50)
    logger.info("Digital Twin Application Starting")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    logger.info("="*50)

if __name__ == "__main__":
    setup_logging()
