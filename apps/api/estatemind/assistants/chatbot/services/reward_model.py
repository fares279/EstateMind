"""
RLHF Reward Model: trains on user feedback to improve response reranking.
Lightweight logistic regression on sentence-embeddings.
Trained only when sufficient labeled data accumulated (≥200 examples).
"""

import logging
import numpy as np
from typing import Optional, Dict, List
import pickle
import os
from datetime import datetime, timedelta

from config.paths import ARTIFACTS_DIR

logger = logging.getLogger(__name__)


class RLHFRewardModel:
    """
    Lightweight reward model trained on user feedback (thumbs_up/thumbs_down).
    Input: (query, response) text pair
    Output: predicted quality score [0, 1]
    
    Training data: ChatbotResponseLog rows where user_feedback is not null
    """
    
    MINIMUM_TRAINING_EXAMPLES = 200
    MIN_THUMBS_UP = 100
    MIN_THUMBS_DOWN = 100
    MIN_AUC = 0.60
    MODEL_ARTIFACT_DIR = str(ARTIFACTS_DIR / 'chatbot')
    
    def __init__(self):
        self.classifier = None
        self.is_trained = False
        self.model_version = None
        self.trained_at = None
        self.training_examples_count = 0
        self._load_model_if_available()
    
    def _load_model_if_available(self):
        """
        Attempts to load a pre-trained model from disk.
        """
        try:
            if not os.path.exists(self.MODEL_ARTIFACT_DIR):
                return
            
            model_path = os.path.join(self.MODEL_ARTIFACT_DIR, 'reward_model.pkl')
            meta_path = os.path.join(self.MODEL_ARTIFACT_DIR, 'reward_model_meta.pkl')
            
            if os.path.exists(model_path) and os.path.exists(meta_path):
                with open(model_path, 'rb') as f:
                    self.classifier = pickle.load(f)
                
                with open(meta_path, 'rb') as f:
                    meta = pickle.load(f)
                    self.model_version = meta.get('version')
                    self.trained_at = meta.get('trained_at')
                    self.training_examples_count = meta.get('training_examples')
                
                self.is_trained = True
                logger.info(f'Loaded reward model v{self.model_version} '
                           f'({self.training_examples_count} examples)')
        except Exception as e:
            logger.warning(f'Failed to load reward model: {e}')
    
    def predict_quality(self, query: str, response: str) -> float:
        """
        Predicts quality score for a (query, response) pair.
        Returns 0.5 (neutral) if model not trained yet.
        """
        
        if not self.is_trained:
            return 0.5  # neutral until trained
        
        try:
            # Encode concatenated query + response
            combined = f"Query: {query} Response: {response}"
            embedding = self._encode(combined)
            
            # Binary classification: thumbs_up (1) vs thumbs_down (0)
            score = float(self.classifier.predict_proba([embedding])[0][1])
            return min(1.0, max(0.0, score))
            
        except Exception as e:
            logger.error(f'Reward model prediction error: {e}')
            return 0.5  # fallback to neutral on error
    
    def train(self) -> Dict:
        """
        Trains the reward model on accumulated feedback data.
        Called by Celery Beat task monthly.
        
        Returns training metadata including success/failure status.
        """
        
        labeled_list = self._labeled_examples()
        
        thumbs_up_count = sum(1 for x in labeled_list if x['user_feedback'] == 'thumbs_up')
        thumbs_down_count = sum(1 for x in labeled_list if x['user_feedback'] == 'thumbs_down')
        total_count = len(labeled_list)
        
        if total_count < self.MINIMUM_TRAINING_EXAMPLES:
            logger.info(
                f'Reward model training skipped: only {total_count} '
                f'labeled examples (need {self.MINIMUM_TRAINING_EXAMPLES}). '
                f'Thumbs up: {thumbs_up_count}, down: {thumbs_down_count}'
            )
            return {
                'status': 'skipped',
                'reason': 'insufficient_data',
                'total_examples': total_count,
                'thumbs_up': thumbs_up_count,
                'thumbs_down': thumbs_down_count,
                'needed': self.MINIMUM_TRAINING_EXAMPLES
            }
        
        # Check for balanced classes
        if thumbs_up_count < self.MIN_THUMBS_UP or thumbs_down_count < self.MIN_THUMBS_DOWN:
            logger.warning(
                f'Reward model training skipped: imbalanced feedback. '
                f'Thumbs up: {thumbs_up_count} (need {self.MIN_THUMBS_UP}), '
                f'down: {thumbs_down_count} (need {self.MIN_THUMBS_DOWN})'
            )
            return {
                'status': 'skipped',
                'reason': 'imbalanced_classes',
                'thumbs_up': thumbs_up_count,
                'thumbs_down': thumbs_down_count,
                'min_required': self.MIN_THUMBS_UP
            }
        
        # Encode all examples
        X = []
        y = []
        
        for example in labeled_list:
            try:
                combined = f"Query: {example['query']} Response: {example['response']}"
                embedding = self._encode(combined)
                X.append(embedding)
                y.append(1 if example['user_feedback'] == 'thumbs_up' else 0)
            except Exception as e:
                logger.warning(f'Error encoding example: {e}')
                continue
        
        if len(X) < self.MINIMUM_TRAINING_EXAMPLES:
            logger.warning(f'After encoding, only {len(X)} valid examples')
            return {
                'status': 'failed',
                'reason': 'insufficient_valid_examples',
                'valid_count': len(X)
            }
        
        X = np.array(X)
        y = np.array(y)
        
        try:
            from sklearn.linear_model import LogisticRegression
            from sklearn.model_selection import cross_val_score
            
            classifier = LogisticRegression(
                max_iter=1000,
                class_weight='balanced'  # handle class imbalance
            )
            
            # Cross-validation to check if model is actually learning
            cv_scores = cross_val_score(
                classifier, X, y, cv=5, scoring='roc_auc'
            )
            mean_auc = float(cv_scores.mean())
            
            if mean_auc < self.MIN_AUC:
                logger.warning(
                    f'Reward model AUC {mean_auc:.2f} is below threshold '
                    f'{self.MIN_AUC}. Model may not be useful. Keeping previous version.'
                )
                return {
                    'status': 'rejected',
                    'reason': 'low_auc',
                    'auc': mean_auc,
                    'min_auc': self.MIN_AUC,
                    'examples': len(X)
                }
            
            # Train on full dataset
            classifier.fit(X, y)
            
            # Save to disk
            os.makedirs(self.MODEL_ARTIFACT_DIR, exist_ok=True)
            
            model_path = os.path.join(self.MODEL_ARTIFACT_DIR, 'reward_model.pkl')
            meta_path = os.path.join(self.MODEL_ARTIFACT_DIR, 'reward_model_meta.pkl')
            
            with open(model_path, 'wb') as f:
                pickle.dump(classifier, f)
            
            version = datetime.now().strftime('%Y%m%d_%H%M%S')
            with open(meta_path, 'wb') as f:
                pickle.dump({
                    'version': version,
                    'trained_at': datetime.now(),
                    'training_examples': len(X),
                    'thumbs_up': int(y.sum()),
                    'thumbs_down': len(y) - int(y.sum()),
                    'auc': mean_auc
                }, f)
            
            self.classifier = classifier
            self.is_trained = True
            self.model_version = version
            self.trained_at = datetime.now()
            self.training_examples_count = len(X)
            
            logger.info(
                f'Reward model trained successfully: '
                f'{len(X)} examples, AUC {mean_auc:.3f}, '
                f'v{version}'
            )
            
            return {
                'status': 'trained',
                'version': version,
                'training_examples': len(X),
                'cross_val_auc': mean_auc,
                'thumbs_up_count': int(y.sum()),
                'thumbs_down_count': len(y) - int(y.sum())
            }
            
        except Exception as e:
            logger.error(f'Reward model training failed: {e}')
            return {
                'status': 'failed',
                'reason': str(e)
            }
    
    def _labeled_examples(self) -> List[Dict]:
        """Rows with user feedback, as dicts with 'query', 'response', 'user_feedback'."""
        from estatemind.assistants.chatbot.models import ChatbotResponseLog

        return list(
            ChatbotResponseLog.objects.filter(user_feedback__isnull=False)
            .values('query', 'response', 'user_feedback')
        )

    def _encode(self, text: str) -> np.ndarray:
        """
        Encodes text to embedding using sentence-transformers.
        Uses the same multilingual model as intent classifier.
        """
        try:
            from estatemind.assistants.shared_models import INTENT_MODEL, get_sentence_model

            if not hasattr(self, '_encoder'):
                self._encoder = get_sentence_model(INTENT_MODEL)
            
            embedding = self._encoder.encode(text, convert_to_numpy=True)
            return embedding
            
        except Exception as e:
            logger.error(f'Encoding error: {e}')
            # Return random embedding as fallback (model will work but be useless)
            return np.random.randn(384)
