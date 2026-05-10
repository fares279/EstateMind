from django.db import models
from django.core.validators import EmailValidator, RegexValidator


class Participant(models.Model):
    """Campaign participant for #Aaref_Bledek"""
    ROLE_CHOICES = [
        ('learner', 'Learner'),
        ('contributor', 'Contributor'),
        ('volunteer', 'Research Volunteer'),
        ('ambassador', 'Community Ambassador'),
    ]

    phone_regex = RegexValidator(
        regex=r'^\+?2?1?6?\d{8}$',
        message='Enter a valid Tunisian phone number.'
    )

    full_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True, validators=[EmailValidator()])
    phone = models.CharField(validators=[phone_regex], max_length=25)
    region = models.CharField(max_length=100)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    motivation = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Participants'

    def __str__(self):
        return f"{self.full_name} — {self.get_role_display()}"
