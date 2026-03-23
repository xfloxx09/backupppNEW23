# app/admin.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, session
from flask_login import login_required, current_user
from sqlalchemy import desc, or_, false
from app import db
from app.models import User, Team, TeamMember, Coaching, Workshop, workshop_participants, Project
from app.forms import RegistrationForm, TeamForm, TeamMemberForm, CoachingForm, WorkshopForm, ProjectForm
from app.utils import role_required, ROLE_ADMIN, ROLE_BETRIEBSLEITER, ROLE_TEAMLEITER, ROLE_ABTEILUNGSLEITER, get_or_create_archiv_team, ARCHIV_TEAM_NAME
from app.main_routes import calculate_date_range, get_month_name_german
from datetime import datetime, timezone

bp = Blueprint('admin', __name__)

@bp.route('/')
@login_required
@role_required([ROLE_ADMIN, ROLE_BETRIEBSLEITER])
def panel():
    page_users = request.args.get('page_users', 1, type=int)
    page_teams = request.args.get('page_teams', 1, type=int)
    page_members = request.args.get('page_members', 1, type=int)
    page_archiv = request.args.get('page_archiv', 1, type=int)
    
    # Filter-Parameter
    user_project_filter = request.args.get('user_project', type=int)
    user_role_filter = request.args.get('user_role', default='', type=str)
    user_search = request.args.get('user_search', default='', type=str).strip()
    
    team_project_filter = request.args.get('team_project', type=int)
    team_search = request.args.get('team_search', default='', type=str).strip()
    
    member_project_filter = request.args.get('member_project', type=int)
    member_team_filter = request.args.get('member_team', type=int)
    member_search = request.args.get('member_search', default='', type=str).strip()
    
    archiv_project_filter = request.args.get('archiv_project', type=int)
    archiv_team_filter = request.args.get('archiv_team', type=int)
    archiv_search = request.args.get('archiv_search', default='', type=str).strip()

    # --- Flags, ob Filter aktiv sind ---
    user_filter_active = any([user_project_filter, user_role_filter, user_search])
    team_filter_active = any([team_project_filter, team_search])
    member_filter_active = any([member_project_filter, member_team_filter, member_search])
    archiv_filter_active = any([archiv_project_filter, archiv_team_filter, archiv_search])

    # --- Benutzer Query ---
    users_query = User.query
    if not user_filter_active:
        users_query = users_query.filter(false())
    else:
        if user_project_filter:
            users_query = users_query.filter(User.project_id == user_project_filter)
        if user_role_filter:
            users_query = users_query.filter(User.role == user_role_filter)
        if user_search:
            users_query = users_query.filter(
                or_(
                    User.username.ilike(f'%{user_search}%'),
                    User.email.ilike(f'%{user_search}%')
                )
            )
    users_paginated = users_query.order_by(User.username).paginate(page=page_users, per_page=20, error_out=False)

    # --- Teams Query ---
    teams_query = Team.query.filter(Team.name != ARCHIV_TEAM_NAME)
    if not team_filter_active:
        teams_query = teams_query.filter(false())
    else:
        if team_project_filter:
            teams_query = teams_query.filter(Team.project_id == team_project_filter)
        if team_search:
            teams_query = teams_query.filter(Team.name.ilike(f'%{team_search}%'))
    teams_paginated = teams_query.order_by(Team.name).paginate(page=page_teams, per_page=20, error_out=False)

    # --- Aktive Teammitglieder Query ---
    members_query = TeamMember.query.join(Team, TeamMember.team_id == Team.id).filter(Team.name != ARCHIV_TEAM_NAME)
    if not member_filter_active:
        members_query = members_query.filter(false())
    else:
        if member_project_filter:
            members_query = members_query.filter(Team.project_id == member_project_filter)
        if member_team_filter:
            members_query = members_query.filter(TeamMember.team_id == member_team_filter)
        if member_search:
            members_query = members_query.filter(TeamMember.name.ilike(f'%{member_search}%'))
    members_paginated = members_query.order_by(TeamMember.name).paginate(page=page_members, per_page=20, error_out=False)

    # --- Archivierte Mitglieder Query ---
    archiv_team = get_or_create_archiv_team()
    archiv_query = TeamMember.query.filter_by(team_id=archiv_team.id)
    if not archiv_filter_active:
        archiv_query = archiv_query.filter(false())
    else:
        if archiv_project_filter:
            archiv_query = archiv_query.filter(TeamMember.original_project_id == archiv_project_filter)
        if archiv_team_filter:
            archiv_query = archiv_query.filter(TeamMember.original_team_id == archiv_team_filter)
        if archiv_search:
            archiv_query = archiv_query.filter(TeamMember.name.ilike(f'%{archiv_search}%'))
    archiv_paginated = archiv_query.order_by(TeamMember.name).paginate(page=page_archiv, per_page=20, error_out=False)

    # Listen für Filter-Dropdowns
    all_projects = Project.query.order_by(Project.name).all()
    all_teams = Team.query.filter(Team.name != ARCHIV_TEAM_NAME).order_by(Team.name).all()
    all_roles = [role for role, _ in RegistrationForm.role.kwargs['choices']]

    return render_template('admin/admin_panel.html', title='Admin Panel',
                           users_paginated=users_paginated,
                           teams_paginated=teams_paginated,
                           members_paginated=members_paginated,
                           archiv_paginated=archiv_paginated,
                           all_projects=all_projects,
                           all_teams=all_teams,
                           all_roles=all_roles,
                           filter_params={
                               'user_project': user_project_filter,
                               'user_role': user_role_filter,
                               'user_search': user_search,
                               'team_project': team_project_filter,
                               'team_search': team_search,
                               'member_project': member_project_filter,
                               'member_team': member_team_filter,
                               'member_search': member_search,
                               'archiv_project': archiv_project_filter,
                               'archiv_team': archiv_team_filter,
                               'archiv_search': archiv_search
                           },
                           user_filter_active=user_filter_active,
                           team_filter_active=team_filter_active,
                           member_filter_active=member_filter_active,
                           archiv_filter_active=archiv_filter_active,
                           config=current_app.config)

# --- Projekt Management ---
@bp.route('/projects')
@login_required
@role_required([ROLE_ADMIN, ROLE_BETRIEBSLEITER])
def manage_projects():
    projects = Project.query.order_by(Project.name).all()
    return render_template('admin/manage_projects.html', projects=projects)

@bp.route('/projects/create', methods=['GET', 'POST'])
@login_required
@role_required([ROLE_ADMIN, ROLE_BETRIEBSLEITER])
def create_project():
    form = ProjectForm()
    if form.validate_on_submit():
        project = Project(name=form.name.data, description=form.description.data)
        db.session.add(project)
        db.session.commit()
        flash('Projekt erfolgreich erstellt.', 'success')
        return redirect(url_for('admin.manage_projects'))
    return render_template('admin/create_project.html', form=form)

@bp.route('/projects/edit/<int:project_id>', methods=['GET', 'POST'])
@login_required
@role_required([ROLE_ADMIN, ROLE_BETRIEBSLEITER])
def edit_project(project_id):
    project = Project.query.get_or_404(project_id)
    form = ProjectForm(obj=project)
    if form.validate_on_submit():
        project.name = form.name.data
        project.description = form.description.data
        db.session.commit()
        flash('Projekt aktualisiert.', 'success')
        return redirect(url_for('admin.manage_projects'))
    return render_template('admin/edit_project.html', form=form, project=project)

@bp.route('/projects/delete/<int:project_id>', methods=['POST'])
@login_required
@role_required([ROLE_ADMIN, ROLE_BETRIEBSLEITER])
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    if project.users.count() > 0 or project.teams.count() > 0 or project.workshops.count() > 0 or project.coachings.count() > 0:
        flash('Projekt kann nicht gelöscht werden, da noch Benutzer, Teams, Workshops oder Coachings zugeordnet sind.', 'danger')
        return redirect(url_for('admin.manage_projects'))
    db.session.delete(project)
    db.session.commit()
    flash('Projekt gelöscht.', 'success')
    return redirect(url_for('admin.manage_projects'))

# --- User Management ---
@bp.route('/users/create', methods=['GET', 'POST'])
@login_required
@role_required([ROLE_ADMIN, ROLE_BETRIEBSLEITER])
def create_user():
    form = RegistrationForm()
    if form.validate_on_submit():
        try:
            # Abteilungsleiter: set project_id to first selected project, otherwise None (but column is NOT NULL, so fallback to a dummy? We'll use first selected project)
            if form.role.data == ROLE_ABTEILUNGSLEITER:
                primary_project_id = form.project_ids.data[0] if form.project_ids.data else None
                if primary_project_id is None:
                    flash('Mindestens ein Projekt muss ausgewählt werden.', 'danger')
                    return render_template('admin/create_user.html', title='Benutzer erstellen', form=form, config=current_app.config)
                user = User(
                    username=form.username.data,
                    email=form.email.data if form.email.data else None,
                    role=form.role.data,
                    project_id=primary_project_id
                )
            else:
                user = User(
                    username=form.username.data,
                    email=form.email.data if form.email.data else None,
                    role=form.role.data,
                    project_id=form.project_id.data
                )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.flush()

            # Teamleiter: assign teams
            if user.role == ROLE_TEAMLEITER and form.team_ids.data:
                selected_teams = Team.query.filter(Team.id.in_(form.team_ids.data)).all()
                user.teams_led = selected_teams
            else:
                user.teams_led = []

            # Abteilungsleiter: assign all selected projects (including the primary)
            if user.role == ROLE_ABTEILUNGSLEITER and form.project_ids.data:
                selected_projects = Project.query.filter(Project.id.in_(form.project_ids.data)).all()
                user.projects = selected_projects
            else:
                user.projects = []

            db.session.commit()
            flash('Benutzer erfolgreich erstellt!', 'success')
            return redirect(url_for('admin.panel'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"FEHLER beim Erstellen des Benutzers: {str(e)}")
            flash(f'Fehler beim Erstellen des Benutzers: {str(e)}', 'danger')
    elif request.method == 'POST':
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Fehler im Feld '{form[field].label.text if hasattr(form[field], 'label') else field}': {error}", 'danger')
    return render_template('admin/create_user.html', title='Benutzer erstellen', form=form, config=current_app.config)

@bp.route('/users/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
@role_required([ROLE_ADMIN, ROLE_BETRIEBSLEITER])
def edit_user(user_id):
    user_to_edit = User.query.get_or_404(user_id)
    form = RegistrationForm(obj=user_to_edit, original_username=user_to_edit.username)

    if not form.password.data:
        form.password.validators = []
        form.password2.validators = []

    if form.validate_on_submit():
        try:
            user_to_edit.username = form.username.data
            user_to_edit.email = form.email.data if form.email.data else None
            user_to_edit.role = form.role.data

            # Handle project assignment based on role
            if user_to_edit.role == ROLE_ABTEILUNGSLEITER:
                # Set project_id to the first selected project (required for NOT NULL)
                primary_project_id = form.project_ids.data[0] if form.project_ids.data else None
                if primary_project_id is None:
                    flash('Mindestens ein Projekt muss ausgewählt werden.', 'danger')
                    return render_template('admin/edit_user.html', title='Benutzer bearbeiten', form=form, user=user_to_edit, config=current_app.config)
                user_to_edit.project_id = primary_project_id
                # Assign all selected projects
                selected_projects = Project.query.filter(Project.id.in_(form.project_ids.data)).all()
                user_to_edit.projects = selected_projects
            else:
                user_to_edit.project_id = form.project_id.data
                user_to_edit.projects = []  # clear any previous project assignments

            if form.password.data:
                user_to_edit.set_password(form.password.data)

            # Teamleiter: assign teams
            if user_to_edit.role == ROLE_TEAMLEITER and form.team_ids.data:
                selected_teams = Team.query.filter(Team.id.in_(form.team_ids.data)).all()
                user_to_edit.teams_led = selected_teams
            else:
                user_to_edit.teams_led = []

            db.session.commit()
            flash('Benutzer erfolgreich aktualisiert!', 'success')
            return redirect(url_for('admin.panel'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"FEHLER beim Aktualisieren des Benutzers: {str(e)}")
            flash(f'Fehler beim Aktualisieren des Benutzers: {str(e)}', 'danger')
    elif request.method == 'GET':
        form.username.data = user_to_edit.username
        form.email.data = user_to_edit.email
        form.role.data = user_to_edit.role
        form.team_ids.data = [team.id for team in user_to_edit.teams_led.all()]
        if user_to_edit.role != ROLE_ABTEILUNGSLEITER:
            form.project_id.data = user_to_edit.project_id
        else:
            form.project_ids.data = [p.id for p in user_to_edit.projects]
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Fehler im Feld '{form[field].label.text if hasattr(form[field], 'label') else field}': {error}", 'danger')

    return render_template('admin/edit_user.html', title='Benutzer bearbeiten', form=form, user=user_to_edit, config=current_app.config)

@bp.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
@role_required([ROLE_ADMIN, ROLE_BETRIEBSLEITER])
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.username == 'admin' or user.id == current_user.id:
        flash('Dieser Benutzer kann nicht gelöscht werden.', 'danger')
        return redirect(url_for('admin.panel'))

    try:
        user.teams_led = []
        Coaching.query.filter_by(coach_id=user_id).update({"coach_id": None})
        db.session.delete(user)
        db.session.commit()
        flash('Benutzer gelöscht.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Fehler beim Löschen von User ID {user_id}: {e}")
        flash(f'Fehler beim Löschen des Benutzers. Es könnten noch verbundene Daten existieren (z.B. Coachings). Details im Log.', 'danger')
    return redirect(url_for('admin.panel'))

# --- Team Management ---
@bp.route('/teams/create', methods=['GET', 'POST'])
@login_required
@role_required([ROLE_ADMIN, ROLE_BETRIEBSLEITER])
def create_team():
    form = TeamForm()
    all_team_leaders = User.query.filter(User.role == ROLE_TEAMLEITER).order_by(User.username).all()
    if form.validate_on_submit():
        if form.name.data.strip().upper() == ARCHIV_TEAM_NAME:
            flash(f'Der Teamname "{ARCHIV_TEAM_NAME}" ist für das System reserviert.', 'danger')
            return render_template('admin/create_team.html', title='Team erstellen', form=form, config=current_app.config)
        try:
            team = Team(
                name=form.name.data,
                project_id=form.project_id.data
            )
            db.session.add(team)
            db.session.flush()

            if form.team_leaders.data:
                leaders = User.query.filter(User.id.in_(form.team_leaders.data), User.role == ROLE_TEAMLEITER).all()
                team.leaders = leaders
            else:
                team.leaders = []

            db.session.commit()
            flash('Team erfolgreich erstellt!', 'success')
            return redirect(url_for('admin.panel'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Fehler beim Erstellen des Teams: {e}")
            flash(f'Fehler beim Erstellen des Teams: {str(e)}', 'danger')
    return render_template('admin/create_team.html', title='Team erstellen', form=form, all_team_leaders=all_team_leaders, config=current_app.config)

@bp.route('/teams/edit/<int:team_id>', methods=['GET', 'POST'])
@login_required
@role_required([ROLE_ADMIN, ROLE_BETRIEBSLEITER])
def edit_team(team_id):
    team_to_edit = Team.query.get_or_404(team_id)
    form = TeamForm(obj=team_to_edit, original_name=team_to_edit.name)

    if team_to_edit.name == ARCHIV_TEAM_NAME and request.method == 'GET':
        flash('Das ARCHIV-Team kann nicht bearbeitet werden.', 'info')
        form.name.render_kw = {'readonly': True}
        form.team_leaders.render_kw = {'disabled': True}
        form.project_id.render_kw = {'disabled': True}

    if form.validate_on_submit():
        if team_to_edit.name == ARCHIV_TEAM_NAME:
            flash('Das ARCHIV-Team kann nicht geändert werden.', 'danger')
            return redirect(url_for('admin.edit_team', team_id=team_id))

        try:
            team_to_edit.name = form.name.data
            team_to_edit.project_id = form.project_id.data

            if form.team_leaders.data:
                leaders = User.query.filter(User.id.in_(form.team_leaders.data), User.role == ROLE_TEAMLEITER).all()
                team_to_edit.leaders = leaders
            else:
                team_to_edit.leaders = []

            db.session.commit()
            flash('Team erfolgreich aktualisiert!', 'success')
            return redirect(url_for('admin.panel'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Fehler beim Bearbeiten des Teams {team_id}: {e}")
            flash(f'Fehler beim Bearbeiten des Teams: {str(e)}', 'danger')

    elif request.method == 'GET':
        form.name.data = team_to_edit.name
        form.team_leaders.data = [leader.id for leader in team_to_edit.leaders.all()]
        form.project_id.data = team_to_edit.project_id

    return render_template('admin/edit_team.html', title='Team bearbeiten', form=form, team=team_to_edit, config=current_app.config)

@bp.route('/teams/delete/<int:team_id>', methods=['POST'])
@login_required
@role_required([ROLE_ADMIN, ROLE_BETRIEBSLEITER])
def delete_team(team_id):
    team = Team.query.get_or_404(team_id)
    if team.name == ARCHIV_TEAM_NAME:
        flash('Das ARCHIV-Team kann nicht gelöscht werden.', 'danger')
        return redirect(url_for('admin.panel'))
    if team.members.count() > 0:
        flash('Team kann nicht gelöscht werden, da ihm noch Mitglieder zugeordnet sind. Verschieben Sie die Mitglieder zuerst ins Archiv.', 'danger')
        return redirect(url_for('admin.panel'))

    try:
        team.leaders = []
        db.session.delete(team)
        db.session.commit()
        flash('Team gelöscht.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Fehler beim Löschen von Team ID {team_id}: {e}")
        flash('Fehler beim Löschen des Teams.', 'danger')
    return redirect(url_for('admin.panel'))

# --- Team Member Management ---
@bp.route('/teammembers/create', methods=['GET', 'POST'])
@login_required
@role_required([ROLE_ADMIN, ROLE_BETRIEBSLEITER])
def create_team_member():
    form = TeamMemberForm()
    projects = Project.query.order_by(Project.name).all()
    all_teams = Team.query.filter(Team.name != ARCHIV_TEAM_NAME).order_by(Team.name).all()
    if form.validate_on_submit():
        try:
            team = Team.query.get(form.team_id.data)
            if not team:
                flash('Team nicht gefunden.', 'danger')
                return redirect(url_for('admin.create_team_member'))
            member = TeamMember(name=form.name.data, team_id=form.team_id.data)
            db.session.add(member)
            db.session.commit()
            flash('Teammitglied erfolgreich erstellt!', 'success')
            return redirect(url_for('admin.panel'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Fehler beim Erstellen des Teammitglieds: {e}")
            flash(f'Fehler beim Erstellen des Teammitglieds: {str(e)}', 'danger')
    return render_template('admin/create_team_member.html', title='Teammitglied erstellen',
                           form=form, projects=projects, all_teams=all_teams, config=current_app.config)

@bp.route('/teammembers/edit/<int:member_id>', methods=['GET', 'POST'])
@login_required
@role_required([ROLE_ADMIN, ROLE_BETRIEBSLEITER])
def edit_team_member(member_id):
    member = TeamMember.query.get_or_404(member_id)
    form = TeamMemberForm(obj=member)
    projects = Project.query.order_by(Project.name).all()
    all_teams = Team.query.filter(Team.name != ARCHIV_TEAM_NAME).order_by(Team.name).all()
    if form.validate_on_submit():
        try:
            member.name = form.name.data
            member.team_id = form.team_id.data
            db.session.commit()
            flash('Teammitglied erfolgreich aktualisiert!', 'success')
            return redirect(url_for('admin.edit_team', team_id=member.team_id))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Fehler beim Bearbeiten des Teammitglieds {member_id}: {e}")
            flash(f'Fehler beim Bearbeiten des Teammitglieds: {str(e)}', 'danger')
    elif request.method == 'GET':
        form.team_id.data = member.team_id
    return render_template('admin/edit_team_member.html', title='Teammitglied bearbeiten',
                           form=form, member=member, projects=projects, all_teams=all_teams, config=current_app.config)

@bp.route('/teammembers/<int:member_id>/move-to-archiv', methods=['POST'])
@login_required
@role_required([ROLE_ADMIN, ROLE_BETRIEBSLEITER])
def move_to_archiv(member_id):
    member_to_move = TeamMember.query.get_or_404(member_id)
    original_team_id = member_to_move.team_id
    original_team_name = member_to_move.team.name
    archiv_team = get_or_create_archiv_team()
    if member_to_move.team_id == archiv_team.id:
        flash(f'{member_to_move.name} ist bereits im Archiv.', 'info')
        return redirect(url_for('admin.panel'))
    try:
        member_to_move.original_team_id = member_to_move.team_id
        member_to_move.original_project_id = member_to_move.team.project_id
        member_to_move.team_id = archiv_team.id
        db.session.commit()
        flash(f'Mitglied "{member_to_move.name}" wurde von Team "{original_team_name}" ins ARCHIV verschoben.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Fehler beim Verschieben von Mitglied {member_id} ins Archiv: {e}")
        flash('Fehler beim Verschieben des Mitglieds ins Archiv.', 'danger')
    return redirect(url_for('admin.edit_team', team_id=original_team_id))

@bp.route('/teammembers/delete-permanent/<int:member_id>', methods=['POST'])
@login_required
@role_required([ROLE_ADMIN, ROLE_BETRIEBSLEITER])
def delete_team_member_permanently(member_id):
    member = TeamMember.query.get_or_404(member_id)
    member_name = member.name
    
    try:
        Coaching.query.filter_by(team_member_id=member_id).delete()
        db.session.execute(workshop_participants.delete().where(workshop_participants.c.team_member_id == member_id))
        db.session.delete(member)
        db.session.commit()
        flash(f'Mitglied "{member_name}" wurde endgültig gelöscht.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Fehler beim endgültigen Löschen von Mitglied {member_id}: {e}")
        flash(f'Fehler beim Löschen: {str(e)}', 'danger')
    
    return redirect(url_for('admin.panel'))

# --- Coaching Management (Admin) ---
@bp.route('/manage_coachings', methods=['GET', 'POST'])
@login_required
@role_required([ROLE_ADMIN, ROLE_BETRIEBSLEITER])
def manage_coachings():
    page = request.args.get('page', 1, type=int)
    period_filter_arg = request.args.get('period', 'all')
    team_filter_arg = request.args.get('team', 'all')
    team_member_filter_arg = request.args.get('teammember', 'all')
    coach_filter_arg = request.args.get('coach', 'all')
    search_term = request.args.get('search', default="", type=str).strip()
    project_filter = request.args.get('project', type=int) or session.get('active_project')

    coachings_query = Coaching.query \
        .join(TeamMember, Coaching.team_member_id == TeamMember.id) \
        .join(User, Coaching.coach_id == User.id, isouter=True) \
        .join(Team, TeamMember.team_id == Team.id)

    if team_filter_arg == 'all':
        coachings_query = coachings_query.filter(Team.name != ARCHIV_TEAM_NAME)

    if project_filter:
        coachings_query = coachings_query.filter(Coaching.project_id == project_filter)

    start_date, end_date = calculate_date_range(period_filter_arg)
    if start_date:
        coachings_query = coachings_query.filter(Coaching.coaching_date >= start_date)
    if end_date:
        coachings_query = coachings_query.filter(Coaching.coaching_date <= end_date)

    if team_filter_arg and team_filter_arg.isdigit():
        coachings_query = coachings_query.filter(TeamMember.team_id == int(team_filter_arg))
    if team_member_filter_arg and team_member_filter_arg.isdigit():
        coachings_query = coachings_query.filter(Coaching.team_member_id == int(team_member_filter_arg))
    if coach_filter_arg and coach_filter_arg.isdigit():
        coachings_query = coachings_query.filter(Coaching.coach_id == int(coach_filter_arg))

    if search_term:
        search_pattern = f"%{search_term}%"
        coachings_query = coachings_query.filter(
            or_(
                TeamMember.name.ilike(search_pattern),
                User.username.ilike(search_pattern),
                Team.name.ilike(search_pattern),
                Coaching.coaching_subject.ilike(search_pattern),
                Coaching.coaching_style.ilike(search_pattern),
                Coaching.tcap_id.ilike(search_pattern),
                Coaching.coach_notes.ilike(search_pattern),
                Coaching.project_leader_notes.ilike(search_pattern)
            )
        )

    if request.method == 'POST':
        if 'delete_selected' in request.form:
            coaching_ids_to_delete = request.form.getlist('coaching_ids')
            if coaching_ids_to_delete:
                try:
                    coaching_ids_to_delete_int = [int(id_str) for id_str in coaching_ids_to_delete]
                    deleted_count = Coaching.query.filter(Coaching.id.in_(coaching_ids_to_delete_int)).delete(synchronize_session='fetch')
                    db.session.commit()
                    flash(f'{deleted_count} Coaching(s) erfolgreich gelöscht.', 'success')
                except ValueError:
                    flash('Ungültige Coaching-IDs zum Löschen ausgewählt.', 'danger')
                except Exception as e:
                    db.session.rollback()
                    current_app.logger.error(f"Fehler beim Löschen von Coachings: {e}")
                    flash(f'Fehler beim Löschen der Coachings: {str(e)}', 'danger')
                return redirect(url_for('admin.manage_coachings', page=page, period=period_filter_arg, team=team_filter_arg, teammember=team_member_filter_arg, coach=coach_filter_arg, search=search_term))
            else:
                flash('Keine Coachings zum Löschen ausgewählt.', 'info')

    coachings_paginated = coachings_query.order_by(desc(Coaching.coaching_date))\
        .paginate(page=page, per_page=15, error_out=False)

    all_teams = Team.query.order_by(Team.name).all()
    all_team_members = TeamMember.query.order_by(TeamMember.name).all()
    all_coaches = User.query.filter(User.coachings_done.any()).distinct().order_by(User.username).all()
    all_projects = Project.query.order_by(Project.name).all()

    now_dt = datetime.now(timezone.utc)
    current_year_val = now_dt.year
    previous_year_val = current_year_val - 1
    month_options_for_filter = []
    for m_num in range(12, 0, -1):
        month_options_for_filter.append({'value': f"{previous_year_val}-{m_num:02d}", 'text': f"{get_month_name_german(m_num)} {previous_year_val}"})
    for m_num in range(now_dt.month, 0, -1):
        month_options_for_filter.append({'value': f"{current_year_val}-{m_num:02d}", 'text': f"{get_month_name_german(m_num)} {current_year_val}"})

    return render_template('admin/manage_coachings.html',
                           title='Coachings Verwalten',
                           coachings_paginated=coachings_paginated,
                           all_teams=all_teams,
                           all_team_members=all_team_members,
                           all_coaches=all_coaches,
                           all_projects=all_projects,
                           month_options=month_options_for_filter,
                           current_period_filter=period_filter_arg,
                           current_team_id_filter=team_filter_arg,
                           current_teammember_id_filter=team_member_filter_arg,
                           current_coach_id_filter=coach_filter_arg,
                           current_search_term=search_term,
                           current_project_filter=project_filter,
                           config=current_app.config,
                           ARCHIV_TEAM_NAME=ARCHIV_TEAM_NAME)

@bp.route('/coaching/<int:coaching_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required([ROLE_ADMIN, ROLE_BETRIEBSLEITER])
def edit_coaching_entry(coaching_id):
    coaching_to_edit = Coaching.query.get_or_404(coaching_id)
    form = CoachingForm(obj=coaching_to_edit, current_user_role=current_user.role, current_user_team_ids=[])
    form.update_team_member_choices(exclude_archiv=False, project_id=coaching_to_edit.project_id)

    if form.validate_on_submit():
        try:
            form.populate_obj(coaching_to_edit)
            db.session.commit()
            flash(f'Coaching ID {coaching_id} erfolgreich aktualisiert!', 'success')
            return redirect(url_for('admin.manage_coachings'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating coaching ID {coaching_id}: {e}")
            flash(f'Fehler beim Aktualisieren von Coaching ID {coaching_id}.', 'danger')
    elif request.method == 'GET':
        form.team_member_id.data = coaching_to_edit.team_member_id

    tcap_js_for_edit = """document.addEventListener('DOMContentLoaded', function() {
    var styleSelect = document.getElementById('coaching_style');
    var tcapField = document.getElementById('tcap_id_field');
    var tcapInput = document.getElementById('tcap_id');
    function toggleTcapField() {
        if (styleSelect && tcapField && tcapInput) {
            if (styleSelect.value === 'TCAP') {
                tcapField.style.display = '';
                tcapInput.required = true;
            } else {
                tcapField.style.display = 'none';
                tcapInput.required = false;
            }
        }
    }
    if (styleSelect && tcapField && tcapInput) {
        styleSelect.addEventListener('change', toggleTcapField);
        toggleTcapField();
    }
});"""
    return render_template('main/add_coaching.html',
                            title=f'Coaching ID {coaching_id} bearbeiten',
                            form=form,
                            is_edit_mode=True,
                            coaching=coaching_to_edit,
                            tcap_js=tcap_js_for_edit,
                            config=current_app.config)

@bp.route('/coaching/<int:coaching_id>/delete', methods=['POST'])
@login_required
@role_required([ROLE_ADMIN, ROLE_BETRIEBSLEITER])
def delete_coaching_entry(coaching_id):
    coaching = Coaching.query.get_or_404(coaching_id)
    try:
        db.session.delete(coaching)
        db.session.commit()
        flash(f'Coaching ID {coaching_id} erfolgreich gelöscht.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Fehler beim Löschen von Coaching ID {coaching_id}: {e}")
        flash(f'Fehler beim Löschen von Coaching ID {coaching_id}.', 'danger')
    return redirect(url_for('admin.manage_coachings'))

# --- Workshop Management (Admin) ---
@bp.route('/manage_workshops', methods=['GET', 'POST'])
@login_required
@role_required([ROLE_ADMIN, ROLE_BETRIEBSLEITER])
def manage_workshops():
    page = request.args.get('page', 1, type=int)
    period_filter_arg = request.args.get('period', 'all')
    search_term = request.args.get('search', default="", type=str).strip()
    project_filter = request.args.get('project', type=int) or session.get('active_project')

    workshops_query = Workshop.query
    if project_filter:
        workshops_query = workshops_query.filter(Workshop.project_id == project_filter)

    start_date, end_date = calculate_date_range(period_filter_arg)
    if start_date:
        workshops_query = workshops_query.filter(Workshop.workshop_date >= start_date)
    if end_date:
        workshops_query = workshops_query.filter(Workshop.workshop_date <= end_date)

    if search_term:
        search_pattern = f"%{search_term}%"
        workshops_query = workshops_query.filter(
            or_(
                Workshop.title.ilike(search_pattern),
                Workshop.notes.ilike(search_pattern),
                User.username.ilike(search_pattern)
            )
        ).join(User, Workshop.coach_id == User.id)

    if request.method == 'POST':
        if 'delete_selected' in request.form:
            workshop_ids_to_delete = request.form.getlist('workshop_ids')
            if workshop_ids_to_delete:
                try:
                    workshop_ids_to_delete_int = [int(id_str) for id_str in workshop_ids_to_delete]
                    db.session.execute(workshop_participants.delete().where(workshop_participants.c.workshop_id.in_(workshop_ids_to_delete_int)))
                    deleted_count = Workshop.query.filter(Workshop.id.in_(workshop_ids_to_delete_int)).delete(synchronize_session='fetch')
                    db.session.commit()
                    flash(f'{deleted_count} Workshop(s) erfolgreich gelöscht.', 'success')
                except ValueError:
                    flash('Ungültige Workshop-IDs zum Löschen ausgewählt.', 'danger')
                except Exception as e:
                    db.session.rollback()
                    current_app.logger.error(f"Fehler beim Löschen von Workshops: {e}")
                    flash(f'Fehler beim Löschen der Workshops: {str(e)}', 'danger')
                return redirect(url_for('admin.manage_workshops', page=page, period=period_filter_arg, search=search_term))
            else:
                flash('Keine Workshops zum Löschen ausgewählt.', 'info')

    workshops_paginated = workshops_query.order_by(desc(Workshop.workshop_date))\
        .paginate(page=page, per_page=15, error_out=False)

    now_dt = datetime.now(timezone.utc)
    current_year_val = now_dt.year
    previous_year_val = current_year_val - 1
    month_options_for_filter = []
    for m_num in range(12, 0, -1):
        month_options_for_filter.append({'value': f"{previous_year_val}-{m_num:02d}", 'text': f"{get_month_name_german(m_num)} {previous_year_val}"})
    for m_num in range(now_dt.month, 0, -1):
        month_options_for_filter.append({'value': f"{current_year_val}-{m_num:02d}", 'text': f"{get_month_name_german(m_num)} {current_year_val}"})

    all_projects = Project.query.order_by(Project.name).all()

    return render_template('admin/manage_workshops.html',
                           title='Workshops Verwalten',
                           workshops_paginated=workshops_paginated,
                           month_options=month_options_for_filter,
                           current_period_filter=period_filter_arg,
                           current_search_term=search_term,
                           current_project_filter=project_filter,
                           all_projects=all_projects,
                           config=current_app.config,
                           workshop_participants=workshop_participants,
                           db=db)

@bp.route('/workshop/<int:workshop_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required([ROLE_ADMIN, ROLE_BETRIEBSLEITER])
def edit_workshop_entry(workshop_id):
    workshop_to_edit = Workshop.query.get_or_404(workshop_id)
    form = WorkshopForm(obj=workshop_to_edit, current_user_role=current_user.role, current_user_team_ids=[])
    form.update_participant_choices(project_id=workshop_to_edit.project_id)

    existing_participant_ids = [p.id for p in workshop_to_edit.participants]
    form.team_member_ids.data = existing_participant_ids

    if form.validate_on_submit():
        try:
            workshop_to_edit.title = form.title.data
            workshop_to_edit.overall_rating = form.overall_rating.data
            workshop_to_edit.time_spent = form.time_spent.data
            workshop_to_edit.notes = form.notes.data

            workshop_to_edit.participants = []
            db.session.flush()

            for member_id in form.team_member_ids.data:
                individual_rating_key = f'individual_rating_{member_id}'
                individual_rating = request.form.get(individual_rating_key, type=int)
                member = TeamMember.query.get(member_id)
                original_team_id = member.team_id if member else None

                if individual_rating is not None and 0 <= individual_rating <= 10:
                    stmt = workshop_participants.insert().values(
                        workshop_id=workshop_to_edit.id,
                        team_member_id=member_id,
                        individual_rating=individual_rating,
                        original_team_id=original_team_id
                    )
                    db.session.execute(stmt)
                else:
                    flash(f'Ungültige Bewertung für Teilnehmer ID {member_id}', 'danger')
                    db.session.rollback()
                    return redirect(url_for('admin.edit_workshop_entry', workshop_id=workshop_id))

            db.session.commit()
            flash(f'Workshop ID {workshop_id} erfolgreich aktualisiert!', 'success')
            return redirect(url_for('admin.manage_workshops'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating workshop ID {workshop_id}: {e}")
            flash(f'Fehler beim Aktualisieren von Workshop ID {workshop_id}.', 'danger')
    elif request.method == 'GET':
        pass

    existing_ratings = {}
    for participant in workshop_to_edit.participants:
        rating = db.session.query(workshop_participants.c.individual_rating).filter_by(
            workshop_id=workshop_id, team_member_id=participant.id).scalar()
        existing_ratings[participant.id] = rating

    return render_template('main/add_workshop.html',
                           title=f'Workshop ID {workshop_id} bearbeiten',
                           form=form,
                           is_edit_mode=True,
                           workshop=workshop_to_edit,
                           existing_ratings=existing_ratings,
                           config=current_app.config)

@bp.route('/workshop/<int:workshop_id>/delete', methods=['POST'])
@login_required
@role_required([ROLE_ADMIN, ROLE_BETRIEBSLEITER])
def delete_workshop_entry(workshop_id):
    workshop = Workshop.query.get_or_404(workshop_id)
    try:
        db.session.delete(workshop)
        db.session.commit()
        flash(f'Workshop ID {workshop_id} erfolgreich gelöscht.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Fehler beim Löschen von Workshop ID {workshop_id}: {e}")
        flash(f'Fehler beim Löschen von Workshop ID {workshop_id}.', 'danger')
    return redirect(url_for('admin.manage_workshops'))
