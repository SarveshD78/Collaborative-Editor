from django.contrib.auth.models import User
from django.db import models

class Document(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_documents')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.title

class DocumentPermission(models.Model):
    PERMISSION_CHOICES = [
        ('view', 'Can View'),
        ('edit', 'Can Edit'),
    ]
    
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='permissions')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    permission_level = models.CharField(max_length=10, choices=PERMISSION_CHOICES)
    granted_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='granted_permissions')
    granted_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['document', 'user']
    
    def __str__(self):
        return f"{self.user.username} - {self.permission_level} on {self.document.title}"