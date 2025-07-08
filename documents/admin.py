from django.contrib import admin
from .models import Document, DocumentPermission

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'created_by', 'created_at', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['title', 'content']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(DocumentPermission)
class DocumentPermissionAdmin(admin.ModelAdmin):
    list_display = ['document', 'user', 'permission_level', 'granted_by', 'granted_at']
    list_filter = ['permission_level', 'granted_at']
    search_fields = ['document__title', 'user__username']