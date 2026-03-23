# app/main_routes.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, current_app, jsonify, session
from flask_login import login_required, current_user
from app import db
from app.models import User, Team, TeamMember, Coaching, Workshop, workshop_participants, Project, AssignedCoaching
from app.forms import CoachingForm, ProjectLeaderNoteForm, PasswordChangeForm, WorkshopForm, AssignedCoachingForm
from app.utils import role_required, ROLE_ADMIN, ROLE_BETRIEBSLEITER, ROLE_PROJEKTLEITER, ROLE_QM, ROLE_SALESCOACH, ROLE_TRAINER, ROLE_TEAMLEITER, ROLE_ABTEILUNGSLEITER, ARCHIV_TEAM_NAME
from sqlalchemy import desc, func, or_, and_
from datetime import datetime, timedelta, timezone
import sqlalchemy
from calendar import monthrange

bp = Blueprint('main', __name__)

# ... (all existing helper functions remain unchanged) ...

# ... (existing routes up to workshop_dashboard) ...

# --- Assigned Coachings (Zugewiesene Coachings) ---
@bp.route('/assigned-coachings')
@login_required
def assigned_coachings():
    page = request.args.get('page', 1, type=int)
    project_filter = get_visible_project_id()

    if current_user.role in [ROLE_ADMIN, ROLE_BETRIEBSLEITER, ROLE_PROJEKTLEITER]:
        if current_user.role in [ROLE_ADMIN, ROLE_BETRIEBSLEITER]:
            query = AssignedCoaching.query
        else:
            query = AssignedCoaching.query.filter_by(project_leader_id=current_user.id)
    else:
        query = AssignedCoaching.query.filter_by(coach_id=current_user.id)

    if project_filter:
        query = query.join(TeamMember).join(Team).filter(Team.project_id == project_filter)

    assignments = query.order_by(AssignedCoaching.deadline.asc(), AssignedCoaching.created_at.desc()).paginate(page=page, per_page=10, error_out=False)

    view_type = 'pl' if current_user.role in [ROLE_ADMIN, ROLE_BETRIEBSLEITER, ROLE_PROJEKTLEITER] else 'coach'

    all_projects = None
    if current_user.role in [ROLE_ADMIN, ROLE_BETRIEBSLEITER]:
        all_projects = Project.query.order_by(Project.name).all()
    elif current_user.role == ROLE_ABTEILUNGSLEITER:
        all_projects = current_user.projects.order_by(Project.name).all()
    else:
        all_projects = [Project.query.get(project_filter)] if project_filter else []

    return render_template('main/assigned_coachings.html',
                           assignments=assignments,
                           view_type=view_type,
                           all_projects=all_projects,
                           current_project_filter=project_filter,
                           config=current_app.config)


@bp.route('/assigned-coachings/create', methods=['GET', 'POST'])
@login_required
@role_required([ROLE_ADMIN, ROLE_BETRIEBSLEITER, ROLE_PROJEKTLEITER])
def create_assigned_coaching():
    project_filter = get_visible_project_id()
    form = AssignedCoachingForm(project_id=project_filter)

    if form.validate_on_submit():
        member = TeamMember.query.get(form.team_member_id.data)
        member_coachings = Coaching.query.filter_by(team_member_id=member.id).all()
        current_avg_score = 0
        if member_coachings:
            current_avg_score = sum(c.overall_score for c in member_coachings) / len(member_coachings)

        assigned = AssignedCoaching(
            project_leader_id=current_user.id,
            coach_id=form.coach_id.data,
            team_member_id=form.team_member_id.data,
            deadline=form.deadline.data,
            expected_coaching_count=form.expected_coaching_count.data,
            desired_performance_note=form.desired_performance_note.data,
            current_performance_note_at_assign=current_avg_score,
            status='pending'
        )
        db.session.add(assigned)
        db.session.commit()
        flash('Coaching-Aufgabe erfolgreich zugewiesen.', 'success')
        return redirect(url_for('main.assigned_coachings'))

    for field, errors in form.errors.items():
        for error in errors:
            flash(f"Fehler im Feld '{getattr(form, field).label.text}': {error}", 'danger')

    return render_template('main/create_assigned_coaching.html',
                           form=form,
                           config=current_app.config)


@bp.route('/assigned-coachings/<int:assignment_id>/accept', methods=['POST'])
@login_required
def accept_assigned_coaching(assignment_id):
    assignment = AssignedCoaching.query.get_or_404(assignment_id)
    if assignment.coach_id != current_user.id:
        flash('Sie sind nicht der zugewiesene Coach für diese Aufgabe.', 'danger')
        return redirect(url_for('main.assigned_coachings'))

    if assignment.status != 'pending':
        flash('Diese Aufgabe kann nicht mehr angenommen werden.', 'warning')
        return redirect(url_for('main.assigned_coachings'))

    assignment.status = 'accepted'
    db.session.commit()
    flash('Coaching-Aufgabe angenommen. Sie können jetzt Coachings für dieses Mitglied durchführen.', 'success')
    return redirect(url_for('main.assigned_coachings'))


@bp.route('/assigned-coachings/<int:assignment_id>/reject', methods=['POST'])
@login_required
def reject_assigned_coaching(assignment_id):
    assignment = AssignedCoaching.query.get_or_404(assignment_id)
    if assignment.coach_id != current_user.id:
        flash('Sie sind nicht der zugewiesene Coach für diese Aufgabe.', 'danger')
        return redirect(url_for('main.assigned_coachings'))

    if assignment.status != 'pending':
        flash('Diese Aufgabe kann nicht mehr abgelehnt werden.', 'warning')
        return redirect(url_for('main.assigned_coachings'))

    assignment.status = 'rejected'
    db.session.commit()
    flash('Coaching-Aufgabe abgelehnt.', 'info')
    return redirect(url_for('main.assigned_coachings'))


@bp.route('/assigned-coachings/<int:assignment_id>/report')
@login_required
def assigned_coaching_report(assignment_id):
    assignment = AssignedCoaching.query.get_or_404(assignment_id)
    if assignment.project_leader_id != current_user.id and current_user.role not in [ROLE_ADMIN, ROLE_BETRIEBSLEITER]:
        abort(403)

    coachings = assignment.coachings.order_by(Coaching.coaching_date).all()
    final_avg_score = 0
    if coachings:
        final_avg_score = sum(c.overall_score for c in coachings) / len(coachings)

    report = {
        'assignment': assignment,
        'coachings': coachings,
        'final_avg_score': round(final_avg_score, 2),
        'start_note': assignment.current_performance_note_at_assign,
        'target_note': assignment.desired_performance_note,
        'coachings_done': len(coachings),
        'coachings_expected': assignment.expected_coaching_count,
        'deadline': assignment.deadline,
        'status': assignment.status
    }

    return render_template('main/assigned_coaching_report.html', report=report, config=current_app.config)


@bp.route('/api/member_current_score', methods=['GET'])
@login_required
def get_member_current_score():
    member_id = request.args.get('member_id', type=int)
    if not member_id:
        return jsonify({'error': 'No member_id'}), 400
    member = TeamMember.query.get_or_404(member_id)
    coachings = Coaching.query.filter_by(team_member_id=member_id).all()
    avg_score = 0
    if coachings:
        avg_score = sum(c.overall_score for c in coachings) / len(coachings)
    return jsonify({'score': round(avg_score, 2)})


# ... (rest of existing routes like profile, edit_coaching, etc., unchanged) ...
