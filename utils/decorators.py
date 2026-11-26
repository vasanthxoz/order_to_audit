from functools import wraps
from flask import flash, redirect, url_for, abort
from flask_login import current_user


def role_required(*roles):
    """Restrict route access to users having one of the specified role names."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("login"))
            if current_user.role_name not in roles:
                flash("Access denied: insufficient permissions for your role.", "danger")
                return abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator
