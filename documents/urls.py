from django.urls import path
from . import views

app_name = 'documents'

urlpatterns = [
    path('', views.home, name='home'),
    path('documents/', views.document_list, name='list'),
    path('documents/create/', views.document_create, name='create'),
    path('documents/<int:doc_id>/', views.document_edit, name='edit'),
    path('documents/<int:doc_id>/save/', views.document_save, name='save'),
    path('documents/<int:doc_id>/permissions/', views.manage_permissions, name='manage_permissions'),
    path('documents/<int:doc_id>/ai-suggestions/', views.get_ai_suggestions, name='ai_suggestions'),  # ← FIXED: Added 'documents/' prefix
    path('register/', views.register, name='register'),
]