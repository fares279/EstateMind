"""How an investor score was produced, stated in every scoring response.

The seven trained investor models the scorer can load are not present in
this deployment (no artifacts, no training code), so scores come from fixed
rules and zone market averages. Responses say so instead of implying AI/ML.
"""
RULE_BASED = 'rule_based'
ML_MODELS = 'ml_models'

NOTES = {
    RULE_BASED: 'Scores come from fixed rules applied to zone market averages, not from trained models.',
    ML_MODELS: 'Scores come from trained investor models.',
}


def describe(models_loaded: list | None) -> dict:
    method = ML_MODELS if models_loaded else RULE_BASED
    return {'scoring_method': method, 'scoring_note': NOTES[method], 'models_used': list(models_loaded or [])}
