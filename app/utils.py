# app/utils.py

from functools import wraps
from flask_login import current_user
from flask import abort
from .roles import *  # Import all constants

def role_required(role_name_or_list):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return abort(401)
            required_roles = []
            if isinstance(role_name_or_list, str):
                required_roles.append(role_name_or_list)
            elif isinstance(role_name_or_list, list):
                required_roles = role_name_or_list
            else:
                return abort(500)
            if current_user.role not in required_roles:
                return abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def get_or_create_archiv_team():
    # Import inside function to avoid circular import
    from .models import db, Team
    archiv_team = Team.query.filter_by(name=ARCHIV_TEAM_NAME).first()
    if not archiv_team:
        print(f"INFO: Erstelle das spezielle Team: {ARCHIV_TEAM_NAME}")
        archiv_team = Team(name=ARCHIV_TEAM_NAME)
        db.session.add(archiv_team)
        db.session.commit()
    return archiv_team

def user_can_access_project(user, project_id):
    if user.role in [ROLE_ADMIN, ROLE_BETRIEBSLEITER]:
        return True
    return user.project_id == project_id
