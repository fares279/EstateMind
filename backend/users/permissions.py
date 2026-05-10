"""
Permission decorators and classes for plan-based access control.
Ensures backend enforces all plan restrictions regardless of frontend state.
"""

from functools import wraps
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import BasePermission


class RequiresPlan(BasePermission):
    """
    Base permission class for plan-based access.
    Subclass and override `required_plan` to enforce specific tiers.
    """
    required_plan = None  # Override in subclass: 'pro' or 'investor'
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if self.required_plan is None:
            return True
        
        user_plan = getattr(request.user, 'plan', 'free').lower()
        required_plan = self.required_plan.lower()
        
        # Plan hierarchy: free < pro < investor
        plan_levels = {'free': 0, 'pro': 1, 'investor': 2}
        
        user_level = plan_levels.get(user_plan, 0)
        required_level = plan_levels.get(required_plan, 0)
        
        return user_level >= required_level


class RequiresPro(RequiresPlan):
    """Require Pro plan or higher (Pro, Investor)"""
    required_plan = 'pro'


class RequiresInvestor(RequiresPlan):
    """Require Investor plan"""
    required_plan = 'investor'


def require_plan(required_plan):
    """
    Decorator for function-based views.
    Usage: @require_plan('pro') or @require_plan('investor')
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user or not request.user.is_authenticated:
                return Response(
                    {'error': 'Authentication required'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            user_plan = getattr(request.user, 'plan', 'free').lower()
            required_plan_lower = required_plan.lower()
            
            # Plan hierarchy: free < pro < investor
            plan_levels = {'free': 0, 'pro': 1, 'investor': 2}
            
            user_level = plan_levels.get(user_plan, 0)
            required_level = plan_levels.get(required_plan_lower, 0)
            
            if user_level < required_level:
                return Response(
                    {
                        'error': f'{required_plan.capitalize()} plan required to access this feature',
                        'required_plan': required_plan.capitalize(),
                        'current_plan': user_plan.capitalize(),
                        'upgrade_url': f'/upgrade?target_plan={required_plan}'
                    },
                    status=status.HTTP_403_FORBIDDEN
                )
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def require_pro(view_func):
    """
    Decorator for function-based views requiring Pro plan.
    Usage: @require_pro
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user or not request.user.is_authenticated:
            return Response(
                {'error': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        user_plan = getattr(request.user, 'plan', 'free').lower()
        plan_levels = {'free': 0, 'pro': 1, 'investor': 2}
        
        if plan_levels.get(user_plan, 0) < 1:  # 1 = pro
            return Response(
                {
                    'error': 'Pro plan required to access this feature',
                    'required_plan': 'Pro',
                    'current_plan': user_plan.capitalize(),
                    'upgrade_url': '/upgrade?target_plan=pro'
                },
                status=status.HTTP_403_FORBIDDEN
            )
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def require_investor(view_func):
    """
    Decorator for function-based views requiring Investor plan.
    Usage: @require_investor
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user or not request.user.is_authenticated:
            return Response(
                {'error': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        user_plan = getattr(request.user, 'plan', 'free').lower()
        plan_levels = {'free': 0, 'pro': 1, 'investor': 2}
        
        if plan_levels.get(user_plan, 0) < 2:  # 2 = investor
            return Response(
                {
                    'error': 'Investor plan required to access this feature',
                    'required_plan': 'Investor',
                    'current_plan': user_plan.capitalize(),
                    'upgrade_url': '/upgrade?target_plan=investor'
                },
                status=status.HTTP_403_FORBIDDEN
            )
        
        return view_func(request, *args, **kwargs)
    
    return wrapper
