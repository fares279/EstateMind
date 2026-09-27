"""Reward model for legal answers, trained on thumbs up/down feedback.

Same approach and thresholds as the chatbot's RLHFRewardModel (logistic
regression on multilingual sentence embeddings, retrained only once enough
balanced feedback exists and only kept when cross-validated AUC is useful);
only the training rows and the artifact location differ.
"""
from typing import Dict, List

from config.paths import ARTIFACTS_DIR
from estatemind.assistants.chatbot.services.reward_model import RLHFRewardModel


class LegalRewardModel(RLHFRewardModel):
    MODEL_ARTIFACT_DIR = str(ARTIFACTS_DIR / 'legal')

    def _labeled_examples(self) -> List[Dict]:
        from estatemind.assistants.legal.models import LegalResponseLog

        return [
            {'query': r['question'], 'response': r['answer'], 'user_feedback': r['user_feedback']}
            for r in LegalResponseLog.objects.filter(user_feedback__isnull=False)
            .exclude(answer='')
            .values('question', 'answer', 'user_feedback')
        ]
