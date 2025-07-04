# User-Centric Resource Management in Digital Twin

## Overview

The Digital Twin application implements a comprehensive user-centric resource management system, ensuring that all documents, twin versions, and agents are associated with specific users. This system enables user-level ownership, resource sharing between users, and detailed usage tracking.

## Features

### User-Centric Resources

All primary resources in the Digital Twin application are now user-centric:

- **Documents**: Each document is associated with the user who uploaded it
- **Twin Versions**: Each twin version is owned by a specific user
- **Agent Configurations**: Each agent configuration is created by a specific user

### Resource Sharing

Users can share their resources with other users:

- **Public Sharing**: Resources can be marked as publicly shared using the `is_shared` flag
- **Private Sharing**: Resources can be shared with specific users through the sharing relationship tables:
  - `DocumentShare`
  - `TwinVersionShare`
  - `AgentShare`

### Usage Tracking

The system tracks detailed resource usage on a per-user basis:

- **Token Usage**: All token usage is tracked, including input/output tokens
- **Document Usage**: Document access and operations are tracked
- **Agent Usage**: Agent execution and operations are tracked

## Implementation Details

### Database Models

1. **User Resource Models**:
   - Document, TwinVersion, and AgentConfiguration models include user foreign keys and sharing flags

2. **Sharing Relationship Tables**:
   - DocumentShare, TwinVersionShare, and AgentShare models define sharing relationships between users

3. **Usage Tracking Models**:
   - TokenUsage, DocumentUsage, and AgentUsage models track resource utilization

### Access Control

1. **Permission Decorators**:
   - Custom decorators enforce user-level access control for all resource operations
   - Example: `@check_document_access`, `@check_twin_version_access`, etc.

2. **Middleware**:
   - ResourceAccessMiddleware enforces access control at the middleware level
   - Automatically validates resource access for API endpoints

### User Interface

1. **Resource Management**:
   - UI allows users to view, manage, and share their resources
   - Clear indication of ownership and sharing status for resources

2. **Usage Statistics**:
   - Profile page displays detailed token usage statistics
   - Resource usage breakdown by type and operation

## Usage

### Managing Resources

1. **Viewing Resources**:
   - The DMS (Document Management System) page displays user's own resources
   - Shared resources are clearly marked

2. **Sharing Resources**:
   - Use the "Share" button on resource cards to share with other users
   - Toggle "Public" to make resources available to all users

### Tracking Usage

1. **Profile Page**:
   - Visit the Profile page to see detailed token usage statistics
   - Daily, monthly, and all-time usage breakdown

2. **Resource Analytics**:
   - Resource-specific analytics show usage patterns and token consumption

## API Reference

The application provides several API endpoints for managing user-centric resources:

- `GET /api/twin-versions/` - List twin versions accessible to the user
- `GET /api/documents/` - List documents accessible to the user
- `POST /api/documents/<uuid:document_id>/share/` - Share a document with another user
- `GET /api/profile/token-usage/` - Get token usage statistics
- `GET /api/profile/resources/` - Get user resource counts

## Testing

Run the included test suite to verify the user-centric system:

```bash
python manage.py test digital_twin_app.test_user_centric
```
