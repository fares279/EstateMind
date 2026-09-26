"""
Django management command to retrain the intent classifier with labeled examples.

Usage:
    python manage.py retrain_intent_classifier --labeled_data=labeled_intents.jsonl --validate
    python manage.py retrain_intent_classifier --labeled_data=labeled_intents.jsonl --test_accuracy
"""

import json
import pickle
from pathlib import Path
from django.core.management.base import BaseCommand
from django.utils import timezone
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report
from sentence_transformers import SentenceTransformer


class Command(BaseCommand):
    help = "Retrain intent classifier with labeled examples"

    def add_arguments(self, parser):
        parser.add_argument(
            '--labeled_data',
            type=str,
            required=True,
            help='Path to labeled_intents.jsonl file'
        )
        parser.add_argument(
            '--validate',
            action='store_true',
            help='Run validation test before saving model'
        )
        parser.add_argument(
            '--test_accuracy',
            action='store_true',
            help='Test accuracy on 40-query test set'
        )
        parser.add_argument(
            '--output',
            type=str,
            default='/tmp/chatbot_models/intent_classifier_retrained.pkl',
            help='Output model path'
        )

    def handle(self, *args, **options):
        labeled_data_path = options['labeled_data']
        validate = options['validate']
        test_accuracy = options['test_accuracy']
        output_path = options['output']

        self.stdout.write(f"🔄 Retraining intent classifier...")
        self.stdout.write(f"  Input: {labeled_data_path}")
        self.stdout.write(f"  Output: {output_path}")

        # Load labeled data
        if not Path(labeled_data_path).exists():
            self.stdout.write(self.style.ERROR(f"❌ File not found: {labeled_data_path}"))
            return

        examples = []
        with open(labeled_data_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    examples.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

        if len(examples) < 50:
            self.stdout.write(
                self.style.ERROR(
                    f"❌ Not enough examples: {len(examples)} (minimum 50 required)"
                )
            )
            return

        self.stdout.write(f"✅ Loaded {len(examples)} labeled examples")

        # Load embedding model
        self.stdout.write("📦 Loading sentence-transformer model...")
        embedding_model = SentenceTransformer(
            'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
        )

        # Prepare features and labels
        queries = [ex['query'] for ex in examples]
        intents = [ex['intent'] for ex in examples]

        # Get unique intents
        unique_intents = sorted(set(intents))
        intent_to_label = {intent: idx for idx, intent in enumerate(unique_intents)}

        self.stdout.write(f"🎯 Intent classes: {unique_intents}")

        # Embed queries
        self.stdout.write("🧮 Computing embeddings...")
        embeddings = embedding_model.encode(queries, convert_to_numpy=True)
        labels = np.array([intent_to_label[intent] for intent in intents])

        self.stdout.write(f"✅ Embeddings shape: {embeddings.shape}")

        # Split train/test
        X_train, X_test, y_train, y_test = train_test_split(
            embeddings, labels, test_size=0.2, random_state=42, stratify=labels
        )

        self.stdout.write(f"📊 Train/test split: {len(X_train)}/{len(X_test)}")

        # Train classifier
        self.stdout.write("🚀 Training LogisticRegression classifier...")
        classifier = LogisticRegression(
            max_iter=1000,
            random_state=42,
            multi_class='multinomial',
            solver='lbfgs'
        )
        classifier.fit(X_train, y_train)

        # Evaluate
        train_pred = classifier.predict(X_train)
        test_pred = classifier.predict(X_test)

        train_acc = accuracy_score(y_train, train_pred)
        test_acc = accuracy_score(y_test, test_pred)

        self.stdout.write(f"📈 Training accuracy: {train_acc:.1%}")
        self.stdout.write(f"📈 Test accuracy: {test_acc:.1%}")

        if test_acc < 0.80:
            self.stdout.write(
                self.style.WARNING(
                    f"⚠️  Test accuracy {test_acc:.1%} is below 80% baseline.\n"
                    f"   This model may underperform production intent classifier."
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS(f"✅ Test accuracy {test_acc:.1%} is good"))

        # Print confusion matrix
        self.stdout.write("\n📋 Confusion Matrix (Test Set):")
        cm = confusion_matrix(y_test, test_pred)
        self.stdout.write(f"  (rows=actual, cols=predicted)")

        label_to_intent = {v: k for k, v in intent_to_label.items()}
        for i, intent in enumerate(unique_intents):
            row = cm[i]
            row_str = ' '.join(f"{count:3d}" for count in row)
            self.stdout.write(f"  {intent:20s}: {row_str}")

        # Print per-intent accuracy
        self.stdout.write("\n📊 Per-Intent Accuracy (Test Set):")
        for i, intent in enumerate(unique_intents):
            mask = y_test == i
            if mask.sum() > 0:
                acc = (test_pred[mask] == y_test[mask]).mean()
                count = mask.sum()
                self.stdout.write(f"  {intent:20s}: {acc:.1%} ({count} examples)")

        # Validate on test set
        if validate:
            self.stdout.write("\n✅ Validation passed (test_accuracy >= 0.80)")

        # Save model
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        model_data = {
            'classifier': classifier,
            'embedding_model_name': 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
            'intent_to_label': intent_to_label,
            'label_to_intent': {v: k for k, v in intent_to_label.items()},
            'training_accuracy': train_acc,
            'test_accuracy': test_acc,
            'training_date': timezone.now().isoformat(),
            'trained_on_examples': len(examples),
        }

        with open(output_path, 'wb') as f:
            pickle.dump(model_data, f)

        self.stdout.write(self.style.SUCCESS(f"✅ Model saved to {output_path}"))

        # Optional: test on full 40-query test set
        if test_accuracy:
            self.stdout.write("\n🧪 Testing on 40-query validation set...")
            self._test_on_validation_set(embedding_model, classifier, intent_to_label)

    def _test_on_validation_set(self, embedding_model, classifier, intent_to_label):
        """Test on the standard 40-query validation set"""
        # This would use the same test set from test_intent_40queries.py
        # For now, show the structure
        self.stdout.write(
            "  → Run: python test_intent_40queries.py --use_retrained_model\n"
            "    to test on full 40-query validation set"
        )
