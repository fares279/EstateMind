from django.db import models
from django.utils import timezone


class EmbeddingCollectionVersion(models.Model):
    """
    Registry of all ChromaDB collection versions.
    Each version corresponds to a specific embedding model.
    Collections are never overwritten — each upgrade creates a new version.
    """
    collection_name = models.CharField(max_length=100, unique=True)
    domain = models.CharField(max_length=50)
    embedding_model = models.CharField(max_length=200)
    embedding_version = models.CharField(max_length=20)
    total_passages = models.IntegerField(default=0)
    indexed_date = models.DateField(default=timezone.now)
    recall_at_5 = models.FloatField(null=True, blank=True)
    status = models.CharField(max_length=20, default='indexing')
    is_active = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"{self.collection_name} ({self.domain}) [{self.status}]"
