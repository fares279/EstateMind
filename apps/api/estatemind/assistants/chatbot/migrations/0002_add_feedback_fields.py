"""
Django migration to add feedback_text field to ChatbotResponseLog.
This allows storing user's optional feedback comments for better context.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chatbot', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatbotresponselog',
            name='feedback_text',
            field=models.TextField(
                null=True,
                blank=True,
                help_text='Optional user feedback text accompanying thumbs_up/down'
            ),
        ),
        migrations.AddField(
            model_name='chatbotresponselog',
            name='intent_confidence',
            field=models.FloatField(
                null=True,
                blank=True,
                help_text='Confidence score of intent classification'
            ),
        ),
        migrations.AddField(
            model_name='chatbotresponselog',
            name='secondary_intent',
            field=models.CharField(
                max_length=50,
                null=True,
                blank=True,
                help_text='Secondary intent if classification was ambiguous'
            ),
        ),
        migrations.AddField(
            model_name='chatbotresponselog',
            name='extraction_metadata',
            field=models.JSONField(
                default=dict,
                blank=True,
                help_text='Extracted entities (location, property_type, timeframe)'
            ),
        ),
        migrations.AddIndex(
            model_name='chatbotresponselog',
            index=models.Index(
                fields=['user_feedback', 'created_at'],
                name='feedback_date_idx'
            ),
        ),
    ]
