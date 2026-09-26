"""
Django management command to export labeled intent examples for fine-tuning.
Used to prepare training data for intent classifier improvements.

Usage:
    python manage.py export_labeled_intents --min_feedback=50 --output=labeled_intents.jsonl
    python manage.py export_labeled_intents --min_feedback=200 --output=labeled_intents.jsonl
"""

import json
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from estatemind.assistants.chatbot.models import ChatbotResponseLog


class Command(BaseCommand):
    help = "Export labeled intent examples from feedback for fine-tuning"

    def add_arguments(self, parser):
        parser.add_argument(
            '--min_feedback',
            type=int,
            default=50,
            help='Minimum number of feedback examples required to export (default: 50)'
        )
        parser.add_argument(
            '--output',
            type=str,
            default='labeled_intents.jsonl',
            help='Output file path (default: labeled_intents.jsonl)'
        )
        parser.add_argument(
            '--only_feedback',
            action='store_true',
            help='Only export examples with user feedback (thumbs_up/down)'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=None,
            help='Only export feedback from last N days (default: all)'
        )

    def handle(self, *args, **options):
        min_feedback = options['min_feedback']
        output_file = options['output']
        only_feedback = options['only_feedback']
        days = options['days']

        self.stdout.write(f"Exporting labeled intent examples...")
        self.stdout.write(f"  Min feedback threshold: {min_feedback}")
        self.stdout.write(f"  Output file: {output_file}")
        self.stdout.write(f"  Only feedback: {only_feedback}")

        # Build query
        query = ChatbotResponseLog.objects.all()

        if only_feedback:
            query = query.exclude(user_feedback__isnull=True)

        if days:
            cutoff_date = timezone.now() - timedelta(days=days)
            query = query.filter(created_at__gte=cutoff_date)
            self.stdout.write(f"  Date range: last {days} days")

        total_count = query.count()
        self.stdout.write(f"Total matching records: {total_count}")

        # Check minimum threshold
        if total_count < min_feedback:
            self.stdout.write(
                self.style.WARNING(
                    f"⚠️  Only {total_count} examples available, but {min_feedback} required.\n"
                    f"   Please collect more feedback before fine-tuning.\n"
                    f"   Current collection rate: {total_count} examples"
                )
            )
            return

        # Export to JSONL
        with open(output_file, 'w', encoding='utf-8') as f:
            for log in query:
                # Convert to training format
                example = {
                    "query": log.query,
                    "intent": log.intent,
                    "confidence": float(log.intent_confidence or 0.0),
                    "user_feedback": log.user_feedback,
                    "user_approved": log.user_feedback == "thumbs_up",
                    "response_quality": float(log.overall_quality_score or 0.0),
                    "timestamp": log.created_at.isoformat() if log.created_at else None,
                }
                f.write(json.dumps(example, ensure_ascii=False) + '\n')

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Exported {total_count} examples to {output_file}\n"
                f"   Next step: python train_intent_classifier_finetuned.py --labeled_data={output_file}"
            )
        )

        # Print statistics
        feedback_counts = query.values('user_feedback').counts()
        self.stdout.write("\nFeedback breakdown:")
        for feedback_type, count in feedback_counts.items():
            percent = (count / total_count) * 100
            status = "👍" if feedback_type == "thumbs_up" else "👎"
            self.stdout.write(f"  {status} {feedback_type}: {count} ({percent:.1f}%)")

        # Print intent breakdown
        intent_counts = query.values('intent').counts()
        self.stdout.write("\nIntent breakdown:")
        for intent, count in intent_counts.items():
            percent = (count / total_count) * 100
            self.stdout.write(f"  {intent}: {count} ({percent:.1f}%)")

        # Print quality breakdown
        good_count = query.filter(overall_quality_score__gte=0.85).count()
        acceptable_count = query.filter(
            overall_quality_score__gte=0.70,
            overall_quality_score__lt=0.85
        ).count()
        poor_count = query.filter(overall_quality_score__lt=0.70).count()

        self.stdout.write("\nQuality breakdown:")
        self.stdout.write(f"  Good (≥0.85): {good_count} ({100*good_count/total_count:.1f}%)")
        self.stdout.write(f"  Acceptable (0.70-0.85): {acceptable_count} ({100*acceptable_count/total_count:.1f}%)")
        self.stdout.write(f"  Poor (<0.70): {poor_count} ({100*poor_count/total_count:.1f}%)")
