#!/usr/bin/env python
"""
Script to add ColPali agent template to the database
"""
import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'digital_twin.settings')
django.setup()

from digital_twin_app.models import AgentTemplate

def add_colpali_template():
    """Add ColPali agent template to the database"""
    
    # Check if template already exists
    if AgentTemplate.objects.filter(name='ColPali Visual Agent').exists():
        print("ColPali Visual Agent template already exists")
        return
    
    # Create ColPali template
    template = AgentTemplate.objects.create(
        name='ColPali Visual Agent',
        description='Advanced visual document analysis agent using ColPali embeddings and Gemini API for image understanding',
        instructions_template='''You are a ColPali Visual Agent specialized in analyzing document images and extracting information from visual content.

Your capabilities include:
1. Visual document analysis using ColPali image embeddings
2. Understanding tabular data, charts, and layouts in document images
3. Retrieving relevant document pages based on visual similarity
4. Generating responses based on visual content analysis using Gemini API

You excel at:
- Analyzing complex document layouts and structures
- Understanding tables, charts, and visual elements in documents
- Providing accurate responses based on visual document content
- Handling multilingual documents with visual cues

You use advanced visual retrieval to find the most relevant document images and then analyze them to provide comprehensive answers.''',
        system_context_template='Visual document analysis and retrieval system using ColPali embeddings and Gemini API',
        default_tools=[],  # ColPali uses its own visual processing pipeline
        default_capabilities=[
            'Visual document analysis',
            'Image-based search',
            'Multimodal responses', 
            'Document understanding',
            'Table and chart analysis'
        ],
        recommended_model='colpali',
        recommended_temperature=0.7,
        is_system_template=True
    )
    
    print(f"Created ColPali Visual Agent template with ID: {template.id}")

if __name__ == '__main__':
    add_colpali_template()
