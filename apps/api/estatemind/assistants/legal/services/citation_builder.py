from dataclasses import dataclass


@dataclass
class Citation:
    source_id: str
    law_name: str
    article: str
    passage_text: str
    similarity: float
    rank: int

    @property
    def confidence_label(self) -> str:
        if self.similarity >= 0.85:
            return 'HIGH'
        if self.similarity >= 0.65:
            return 'MEDIUM'
        return 'LOW'

    @property
    def trust_message(self) -> str:
        if self.similarity >= 0.85:
            return f"Strong match (similarity {self.similarity:.2f}) — highly relevant source"
        if self.similarity >= 0.65:
            return f"Moderate match (similarity {self.similarity:.2f}) — review source for full context"
        return f"Weak match (similarity {self.similarity:.2f}) — use with caution"

    def to_dict(self) -> dict:
        return {
            'source_id': self.source_id,
            'law_name': self.law_name,
            'article': self.article,
            'similarity': self.similarity,
            'confidence_label': self.confidence_label,
            'trust_message': self.trust_message,
            'rank': self.rank,
            'passage_excerpt': (self.passage_text[:300] + '...') if len(self.passage_text) > 300 else self.passage_text,
        }
