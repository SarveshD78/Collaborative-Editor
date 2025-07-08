from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import json
from .models import Document, DocumentPermission

# Add these new imports
from django.contrib.auth import login
from django import forms
from .ai_service import ai_assistant

# New Email Registration Form
class EmailUserCreationForm(forms.ModelForm):
    first_name = forms.CharField(max_length=30, required=True, help_text='Required.')
    last_name = forms.CharField(max_length=30, required=True, help_text='Required.')
    email = forms.EmailField(max_length=254, required=True, help_text='Required. Enter a valid email address.')
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput,
        help_text='Your password must contain at least 8 characters.'
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput,
        help_text='Enter the same password as before, for verification.'
    )

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'password1', 'password2')

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match")
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['email']  # Use email as username
        user.email = self.cleaned_data['email']
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user

def get_user_permission(user, document):
    """Get user's permission level for a document"""
    if document.created_by == user:
        return 'owner'
    
    try:
        perm = DocumentPermission.objects.get(document=document, user=user)
        return perm.permission_level
    except DocumentPermission.DoesNotExist:
        return None

def home(request):
    if request.user.is_authenticated:
        return redirect('documents:list')
    return render(request, 'documents/home.html')

@login_required
def document_list(request):
    # Documents user owns
    owned_docs = Document.objects.filter(created_by=request.user)
    
    # Documents shared with user
    shared_perms = DocumentPermission.objects.filter(user=request.user).select_related('document')
    
    documents = []
    
    # Add owned documents
    for doc in owned_docs:
        documents.append({
            'document': doc,
            'permission': 'owner',
            'icon': '👑'
        })
    
    # Add shared documents
    for perm in shared_perms:
        icon = '📝' if perm.permission_level == 'edit' else '👁️'
        documents.append({
            'document': perm.document,
            'permission': perm.permission_level,
            'icon': icon
        })
    
    return render(request, 'documents/list.html', {'documents': documents})

@login_required
def document_create(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        if title:
            document = Document.objects.create(
                title=title,
                created_by=request.user
            )
            messages.success(request, f'Document "{title}" created successfully!')
            return redirect('documents:edit', doc_id=document.id)
        else:
            messages.error(request, 'Title is required!')
    
    return render(request, 'documents/create.html')

@login_required
def document_edit(request, doc_id):
    document = get_object_or_404(Document, id=doc_id)
    user_permission = get_user_permission(request.user, document)
    
    if user_permission is None:
        messages.error(request, "You don't have access to this document")
        return redirect('documents:list')
    
    # Get collaborators for online indicator
    permissions = DocumentPermission.objects.filter(document=document).select_related('user')
    collaborators = []
    
    # Add owner
    collaborators.append({
        'user': document.created_by,
        'permission': 'owner',
        'icon': '👑'
    })
    
    # Add collaborators
    for perm in permissions:
        icon = '📝' if perm.permission_level == 'edit' else '👁️'
        collaborators.append({
            'user': perm.user,
            'permission': perm.permission_level,
            'icon': icon
        })
    
    context = {
        'document': document,
        'user_permission': user_permission,
        'collaborators': collaborators,
        'can_edit': user_permission in ['owner', 'edit']
    }
    return render(request, 'documents/edit.html', context)

@login_required
@require_POST
def document_save(request, doc_id):
    """AJAX endpoint for auto-saving document content"""
    document = get_object_or_404(Document, id=doc_id)
    user_permission = get_user_permission(request.user, document)
    
    if user_permission not in ['owner', 'edit']:
        return JsonResponse({'success': False, 'error': 'No edit permission'})
    
    try:
        data = json.loads(request.body)
        old_content = document.content
        new_content = data.get('content', '')
        
        document.content = new_content
        document.save()
        
        # Check if content actually changed
        content_changed = old_content != new_content
        
        return JsonResponse({
            'success': True, 
            'last_updated': document.updated_at.strftime('%H:%M:%S'),
            'content_changed': content_changed,
            'updated_by': request.user.first_name or request.user.email
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def manage_permissions(request, doc_id):
    document = get_object_or_404(Document, id=doc_id)
    
    # Only owner can manage permissions
    if document.created_by != request.user:
        messages.error(request, "Only the owner can manage permissions")
        return redirect('documents:edit', doc_id=doc_id)
    
    if request.method == 'POST':
        email = request.POST.get('email')  # Changed from username to email
        permission_level = request.POST.get('permission_level')
        
        try:
            user = User.objects.get(email=email)  # Look up by email
            
            if user == document.created_by:
                messages.error(request, 'Cannot add document owner as collaborator')
                return redirect('documents:manage_permissions', doc_id=doc_id)
            
            # Create or update permission
            perm, created = DocumentPermission.objects.get_or_create(
                document=document,
                user=user,
                defaults={
                    'permission_level': permission_level,
                    'granted_by': request.user
                }
            )
            
            if not created:
                perm.permission_level = permission_level
                perm.save()
                messages.success(request, f'Updated {user.first_name or user.email} permission to {permission_level}')
            else:
                messages.success(request, f'Added {user.first_name or user.email} with {permission_level} permission')
            
        except User.DoesNotExist:
            messages.error(request, 'User with this email not found')
    
    # Get current permissions
    permissions = DocumentPermission.objects.filter(document=document).select_related('user')
    
    return render(request, 'documents/manage_permissions.html', {
        'document': document,
        'permissions': permissions
    })

# Updated register function - replace the existing one
def register(request):
    if request.method == 'POST':
        form = EmailUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Specify the backend when logging in
            login(request, user, backend='documents.backends.EmailBackend')
            messages.success(request, f'Welcome {user.first_name}! Your account has been created.')
            return redirect('documents:list')
    else:
        form = EmailUserCreationForm()
    
    return render(request, 'registration/register.html', {'form': form})



@login_required
@require_POST
def get_ai_suggestions(request, doc_id):
    """Get AI writing suggestions for document content"""
    document = get_object_or_404(Document, id=doc_id)
    user_permission = get_user_permission(request.user, document)
    
    # Check if user has access to the document
    if user_permission is None:
        return JsonResponse({'error': 'No access to document'}, status=403)
    
    try:
        data = json.loads(request.body)
        text = data.get('text', '')
        
        if not text.strip():
            return JsonResponse({'suggestions': [], 'stats': {}})
        
        # Get AI suggestions (free)
        suggestions = ai_assistant.get_grammar_suggestions(text)
        
        # Get writing stats
        stats = ai_assistant.get_writing_stats(text)
        
        return JsonResponse({
            'success': True,
            'suggestions': suggestions,
            'stats': stats,
            'text_length': len(text)
        })
        
    except Exception as e:
        print(f"AI Error: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to get AI suggestions',
            'suggestions': [],
            'stats': {}
        })