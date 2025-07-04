"""
Migration to make resources user-centric and add usage tracking
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('digital_twin_app', '0006_setup_site'),
    ]

    operations = [
        # Update TwinVersion model - add is_shared field
        migrations.AddField(
            model_name='twinversion',
            name='is_shared',
            field=models.BooleanField(default=False, help_text='Whether this twin version is shared with other users'),
        ),
        # Add sharing fields to Document
        migrations.AddField(
            model_name='document',
            name='is_shared',
            field=models.BooleanField(default=False, help_text='Whether this document is shared with other users'),
        ),
        # Rename uploaded_by to user for consistency
        migrations.RenameField(
            model_name='document',
            old_name='uploaded_by',
            new_name='user',
        ),
        # Rename created_by to user for consistency
        migrations.RenameField(
            model_name='twinversion',
            old_name='created_by',
            new_name='user',
        ),
        # Add is_shared field to AgentConfiguration (we're keeping created_by)
        migrations.AddField(
            model_name='agentconfiguration',
            name='is_shared',
            field=models.BooleanField(default=False, help_text='Whether this agent is shared with other users'),
        ),
        # Add is_shared field to AgentConfiguration
        migrations.AddField(
            model_name='agentconfiguration',
            name='is_shared',
            field=models.BooleanField(default=False, help_text='Whether this agent is shared with other users'),
        ),
        # Create TokenUsage model
        migrations.CreateModel(
            name='TokenUsage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('tokens_used', models.IntegerField()),
                ('input_tokens', models.IntegerField(default=0)),
                ('output_tokens', models.IntegerField(default=0)),
                ('resource_type', models.CharField(choices=[
                    ('agent', 'Agent'), 
                    ('document', 'Document'),
                    ('twin_version', 'Twin Version'),
                    ('chat', 'Chat'),
                    ('other', 'Other')
                ], max_length=20)),
                ('resource_id', models.CharField(blank=True, max_length=100, null=True)),
                ('operation', models.CharField(max_length=50)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='token_usage', to='auth.user')),
            ],
            options={
                'ordering': ['-timestamp'],
                'indexes': [
                    models.Index(fields=['user', 'timestamp'], name='token_user_ts_idx'),
                    models.Index(fields=['resource_type', 'resource_id'], name='token_res_type_id_idx'),
                ],
            },
        ),
        # Create DocumentUsage model
        migrations.CreateModel(
            name='DocumentUsage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('operation', models.CharField(max_length=50)),
                ('tokens_used', models.IntegerField(default=0)),
                ('document', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='usage_records', to='digital_twin_app.document')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='document_usage', to='auth.user')),
            ],
            options={
                'ordering': ['-timestamp'],
                'indexes': [models.Index(fields=['user', 'timestamp'], name='doc_usage_user_ts_idx')],
            },
        ),
        # Create AgentUsage model
        migrations.CreateModel(
            name='AgentUsage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('operation', models.CharField(max_length=50)),
                ('tokens_used', models.IntegerField(default=0)),
                ('input_tokens', models.IntegerField(default=0)),
                ('output_tokens', models.IntegerField(default=0)),
                ('agent', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='usage_records', to='digital_twin_app.agentconfiguration')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='agent_usage', to='auth.user')),
            ],
            options={
                'ordering': ['-timestamp'],
                'indexes': [models.Index(fields=['user', 'timestamp'], name='agent_usage_user_ts_idx')],
            },
        ),
        # Add sharing relationship tables
        migrations.CreateModel(
            name='DocumentShare',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('document', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='shares', to='digital_twin_app.document')),
                ('shared_with', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='shared_documents', to='auth.user')),
            ],
            options={
                'unique_together': {('document', 'shared_with')},
            },
        ),
        migrations.CreateModel(
            name='TwinVersionShare',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('twin_version', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='shares', to='digital_twin_app.twinversion')),
                ('shared_with', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='shared_twin_versions', to='auth.user')),
            ],
            options={
                'unique_together': {('twin_version', 'shared_with')},
            },
        ),
        migrations.CreateModel(
            name='AgentShare',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('agent', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='shares', to='digital_twin_app.agentconfiguration')),
                ('shared_with', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='shared_agents', to='auth.user')),
            ],
            options={
                'unique_together': {('agent', 'shared_with')},
            },
        ),
    ]
