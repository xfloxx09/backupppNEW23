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

# --- HILFSFUNKTIONEN ---
def get_month_name_german(month_number):
    months_german = {1:"Januar",2:"Februar",3:"März",4:"April",5:"Mai",6:"Juni",7:"Juli",8:"August",9:"September",10:"Oktober",11:"November",12:"Dezember"}
    return months_german.get(month_number, "")

def calculate_date_range(period_filter_str=None):
    now = datetime.now(timezone.utc); start_date, end_date = None, None
    if not period_filter_str or period_filter_str == 'all': return None, None
    if period_filter_str == '7days': start_date=(now-timedelta(days=6)).replace(hour=0,minute=0,second=0,microsecond=0); end_date=now.replace(hour=23,minute=59,second=59,microsecond=999999)
    elif period_filter_str == '30days': start_date=(now-timedelta(days=29)).replace(hour=0,minute=0,second=0,microsecond=0); end_date=now.replace(hour=23,minute=59,second=59,microsecond=999999)
    elif period_filter_str == 'current_quarter':
        c_month=now.month; yr=now.year
        if 1<=c_month<=3: start_date,end_date=datetime(yr,1,1,0,0,0,tzinfo=timezone.utc),datetime(yr,3,monthrange(yr,3)[1],23,59,59,999999,tzinfo=timezone.utc)
        elif 4<=c_month<=6: start_date,end_date=datetime(yr,4,1,0,0,0,tzinfo=timezone.utc),datetime(yr,6,monthrange(yr,6)[1],23,59,59,999999,tzinfo=timezone.utc)
        elif 7<=c_month<=9: start_date,end_date=datetime(yr,7,1,0,0,0,tzinfo=timezone.utc),datetime(yr,9,monthrange(yr,9)[1],23,59,59,999999,tzinfo=timezone.utc)
        else: start_date,end_date=datetime(yr,10,1,0,0,0,tzinfo=timezone.utc),datetime(yr,12,monthrange(yr,12)[1],23,59,59,999999,tzinfo=timezone.utc)
    elif period_filter_str == 'current_year': yr=now.year; start_date,end_date=datetime(yr,1,1,0,0,0,tzinfo=timezone.utc),datetime(yr,12,monthrange(yr,12)[1],23,59,59,999999,tzinfo=timezone.utc)
    elif '-' in period_filter_str and len(period_filter_str)==7:
        try:
            y_s,m_s=period_filter_str.split('-'); yr=int(y_s); m_i=int(m_s)
            if 1<=m_i<=12:
                start_date=datetime(yr,m_i,1,0,0,0,tzinfo=timezone.utc)
                end_date=datetime(yr,m_i,monthrange(yr,m_i)[1],23,59,59,999999,tzinfo=timezone.utc)
        except ValueError:
            pass
    return start_date,end_date

def get_filtered_coachings_subquery(period_filter_str=None, project_id=None):
    q = db.session.query(
        Coaching.id.label("coaching_id_sq"),
        Coaching.team_id.label("team_id_sq"),
        Coaching.performance_mark.label("performance_mark_sq"),
        Coaching.time_spent.label("time_spent_sq"),
        Coaching.coaching_subject.label("coaching_subject_sq")
    )
    s_d,e_d = calculate_date_range(period_filter_str)
    if s_d: q = q.filter(Coaching.coaching_date >= s_d)
    if e_d: q = q.filter(Coaching.coaching_date <= e_d)
    if project_id:
        q = q.filter(Coaching.project_id == project_id)
    return q.subquery('filtered_coachings_sq')

def get_performance_data_for_charts(period_filter_str=None, selected_team_id_str=None, project_id=None):
    sq = get_filtered_coachings_subquery(period_filter_str, project_id)
    q = db.session.query(
        Team.id.label('team_id'),
        Team.name.label('team_name'),
        func.coalesce(func.avg(sq.c.performance_mark_sq), 0).label('avg_perf_mark'),
        func.coalesce(func.sum(sq.c.time_spent_sq), 0).label('total_time'),
        func.coalesce(func.count(sq.c.coaching_id_sq), 0).label('num_coachings')
    ).select_from(Team)\
     .outerjoin(sq, Team.id == sq.c.team_id_sq)

    q = q.filter(Team.name != ARCHIV_TEAM_NAME)

    if project_id:
        q = q.filter(Team.project_id == project_id)

    if selected_team_id_str and selected_team_id_str.isdigit():
        q = q.filter(Team.id == int(selected_team_id_str))

    res = q.group_by(Team.id, Team.name).having(func.count(sq.c.coaching_id_sq) > 0).order_by(Team.name).all()
    avg_perf_pcnt = [round(r.avg_perf_mark * 10, 2) if r.avg_perf_mark is not None else 0 for r in res]
    total_time_spent_values_list = [r.total_time for r in res]

    return {
        'labels': [r.team_name for r in res],
        'avg_performance_values': avg_perf_pcnt,
        'total_time_spent_values': total_time_spent_values_list,
        'coachings_done_values': [r.num_coachings for r in res]
    }

def get_coaching_subject_distribution(period_filter_str=None, selected_team_id_str=None, project_id=None):
    sq = get_filtered_coachings_subquery(period_filter_str, project_id)
    q = db.session.query(
        sq.c.coaching_subject_sq.label('subject'),
        func.count(sq.c.coaching_id_sq).label('count')
    ).select_from(sq).filter(sq.c.coaching_subject_sq.isnot(None)).filter(sq.c.coaching_subject_sq != '')

    q = q.join(Team, sq.c.team_id_sq == Team.id)\
         .filter(Team.name != ARCHIV_TEAM_NAME)

    if project_id:
        q = q.filter(Team.project_id == project_id)

    if selected_team_id_str and selected_team_id_str.isdigit():
        q = q.filter(Team.id == int(selected_team_id_str))

    res = q.group_by(sq.c.coaching_subject_sq).order_by(desc('count')).all()
    return {'labels':[r.subject for r in res if r.subject],'values':[r.count for r in res if r.subject]}

def get_visible_project_id():
    if current_user.role in [ROLE_ADMIN, ROLE_BETRIEBSLEITER, ROLE_ABTEILUNGSLEITER]:
        return request.args.get('project', type=int) or session.get('active_project')
    else:
        return current_user.project_id

def update_assignment_progress(assignment_id):
    """Update assignment status based on completed coachings count."""
    assignment = AssignedCoaching.query.get(assignment_id)
    if assignment and assignment.status in ['accepted', 'in_progress', 'pending']:
        completed = assignment.coachings.count()
        if completed >= assignment.expected_coaching_count:
            assignment.status = 'completed'
        elif completed > 0:
            assignment.status = 'in_progress'
        db.session.commit()

# --- ROUTEN ---

@bp.route('/')
@bp.route('/index')
@login_required
def index():
    return render_template('main/index_choice.html', config=current_app.config)

@bp.route('/coaching-dashboard')
@login_required
def coaching_dashboard():
    page = request.args.get('page', 1, type=int)
    period_arg = request.args.get('period', 'all')
    team_arg = request.args.get('team', "all")
    search_arg = request.args.get('search', default="", type=str).strip()
    member_filter = request.args.get('member_id', type=int)
    project_filter = get_visible_project_id()

    # --- Globale Statistiken (mit allen Filtern) ---
    global_base = Coaching.query.join(Team, Coaching.team_id == Team.id).filter(Team.name != ARCHIV_TEAM_NAME)

    if project_filter:
        global_base = global_base.filter(Coaching.project_id == project_filter)

    if member_filter:
        global_base = global_base.filter(Coaching.team_member_id == member_filter)

    if team_arg and team_arg.isdigit():
        global_base = global_base.filter(Coaching.team_id == int(team_arg))

    gs_d, ge_d = calculate_date_range(period_arg)
    if gs_d: global_base = global_base.filter(Coaching.coaching_date >= gs_d)
    if ge_d: global_base = global_base.filter(Coaching.coaching_date <= ge_d)

    if search_arg:
        global_base = global_base.join(TeamMember, Coaching.team_member_id == TeamMember.id)\
                                   .join(User, Coaching.coach_id == User.id, isouter=True)\
                                   .filter(or_(
                                       TeamMember.name.ilike(f"%{search_arg}%"),
                                       User.username.ilike(f"%{search_arg}%"),
                                       Coaching.coaching_subject.ilike(f"%{search_arg}%")
                                   ))

    filtered_ids_subquery = global_base.with_entities(Coaching.id).distinct().subquery()
    global_total_coachings = global_base.distinct().count()
    total_time = db.session.query(func.sum(Coaching.time_spent)).filter(Coaching.id.in_(filtered_ids_subquery)).scalar() or 0
    global_time_display = f"{total_time//60} Std. {total_time%60} Min. ({total_time} Min.)"

    list_q = Coaching.query.join(TeamMember, Coaching.team_member_id == TeamMember.id)\
                           .join(Team, TeamMember.team_id == Team.id)\
                           .join(User, Coaching.coach_id == User.id, isouter=True)\
                           .filter(Team.name != ARCHIV_TEAM_NAME)

    if project_filter:
        list_q = list_q.filter(Coaching.project_id == project_filter)

    if member_filter:
        list_q = list_q.filter(Coaching.team_member_id == member_filter)

    ls_d, le_d = calculate_date_range(period_arg)
    if ls_d: list_q = list_q.filter(Coaching.coaching_date >= ls_d)
    if le_d: list_q = list_q.filter(Coaching.coaching_date <= le_d)

    if current_user.role == ROLE_TEAMLEITER:
        led_team_ids = [team.id for team in current_user.teams_led]
        if not led_team_ids:
            flash("Sie leiten derzeit kein Team.", "warning")
            list_q = list_q.filter(sqlalchemy.sql.false())
        else:
            tm_ids = TeamMember.query.filter(TeamMember.team_id.in_(led_team_ids)).all()
            tm_ids_list = [m.id for m in tm_ids]
            if not tm_ids_list:
                list_q = list_q.filter(Coaching.coach_id == current_user.id)
            else:
                list_q = list_q.filter(or_(Coaching.team_member_id.in_(tm_ids_list), Coaching.coach_id == current_user.id))
    elif team_arg and team_arg.isdigit():
        list_q = list_q.filter(TeamMember.team_id == int(team_arg))

    if search_arg:
        list_q = list_q.filter(or_(
            TeamMember.name.ilike(f"%{search_arg}%"),
            User.username.ilike(f"%{search_arg}%"),
            Coaching.coaching_subject.ilike(f"%{search_arg}%")
        ))

    total_filtered_list = list_q.count()
    coachings_page = list_q.order_by(desc(Coaching.coaching_date)).paginate(page=page, per_page=10, error_out=False)

    chart_perf = get_performance_data_for_charts(period_arg, team_arg, project_filter)
    chart_subj = get_coaching_subject_distribution(period_arg, team_arg, project_filter)

    all_teams_query = Team.query.filter(Team.name != ARCHIV_TEAM_NAME)
    if project_filter:
        all_teams_query = all_teams_query.filter(Team.project_id == project_filter)
    all_teams_dd = all_teams_query.order_by(Team.name).all()

    query = db.session.query(
        func.date_trunc('month', Coaching.coaching_date).label('month'),
        func.count(Coaching.id).label('count')
    )
    if project_filter:
        query = query.filter(Coaching.project_id == project_filter)
    all_months_query = query.group_by('month').order_by(desc('month')).all()

    month_options = []
    for row in all_months_query:
        dt = row.month
        if dt:
            month_options.append({
                'value': dt.strftime('%Y-%m'),
                'text': f"{get_month_name_german(dt.month)} {dt.year}",
                'count': row.count
            })

    all_projects = None
    if current_user.role in [ROLE_ADMIN, ROLE_BETRIEBSLEITER, ROLE_ABTEILUNGSLEITER]:
        if current_user.role == ROLE_ABTEILUNGSLEITER:
            all_projects = current_user.projects.order_by(Project.name).all()
        else:
            all_projects = Project.query.order_by(Project.name).all()

    return render_template('main/index.html',
                           title='Coaching - Dashboard',
                           coachings_paginated=coachings_page,
                           total_coachings=total_filtered_list,
                           chart_labels=chart_perf['labels'],
                           chart_avg_performance_mark_percentage=chart_perf['avg_performance_values'],
                           chart_total_time_spent=chart_perf['total_time_spent_values'],
                           chart_coachings_done=chart_perf['coachings_done_values'],
                           subject_chart_labels=chart_subj['labels'],
                           subject_chart_values=chart_subj['values'],
                           all_teams_for_filter=all_teams_dd,
                           current_period_filter=period_arg,
                           current_team_id_filter=team_arg,
                           current_search_term=search_arg,
                           global_total_coachings_count=global_total_coachings,
                           global_time_coached_display=global_time_display,
                           month_options=month_options,
                           all_projects=all_projects,
                           current_project_filter=project_filter,
                           config=current_app.config)

@bp.route('/team_view', methods=['GET'])
@login_required
@role_required([ROLE_TEAMLEITER, ROLE_ADMIN, ROLE_BETRIEBSLEITER, ROLE_PROJEKTLEITER, ROLE_QM, ROLE_SALESCOACH, ROLE_TRAINER, ROLE_ABTEILUNGSLEITER])
def team_view():
    selected_team_object = None
    team_coachings_list_for_display = []
    team_members_stats = []
    view_team_id_arg = request.args.get('team_id', type=int)
    project_filter = get_visible_project_id()
    page_title = "Team Ansicht"

    if current_user.role == ROLE_TEAMLEITER and not view_team_id_arg:
        led_team_ids = [team.id for team in current_user.teams_led]
        if not led_team_ids:
            flash("Sie leiten derzeit kein Team.", "warning")
            return redirect(url_for('main.index'))
        selected_team_object = Team.query.get(led_team_ids[0])
        if selected_team_object:
            page_title = f"Mein Team: {selected_team_object.name}"
        else:
            flash("Zugewiesenes Team nicht gefunden.", "danger")
            return redirect(url_for('main.index'))
    elif view_team_id_arg:
        if current_user.role not in [ROLE_ADMIN, ROLE_BETRIEBSLEITER, ROLE_PROJEKTLEITER, ROLE_ABTEILUNGSLEITER, ROLE_QM, ROLE_SALESCOACH, ROLE_TRAINER]:
            abort(403)
        selected_team_object = Team.query.get(view_team_id_arg)
        if selected_team_object:
            page_title = f"Team Ansicht: {selected_team_object.name}"
    else:
        if current_user.role in [ROLE_ADMIN, ROLE_BETRIEBSLEITER, ROLE_PROJEKTLEITER, ROLE_ABTEILUNGSLEITER, ROLE_QM, ROLE_SALESCOACH, ROLE_TRAINER]:
            teams_query = Team.query.filter(Team.name != ARCHIV_TEAM_NAME)
            if project_filter:
                teams_query = teams_query.filter(Team.project_id == project_filter)
            selected_team_object = teams_query.order_by(Team.name).first()
            if selected_team_object:
                page_title = f"Team Ansicht: {selected_team_object.name}"

    if not selected_team_object:
        flash("Kein Team zum Anzeigen ausgewählt oder vorhanden.", "info")
        all_teams_for_selection = []
        if current_user.role in [ROLE_ADMIN, ROLE_BETRIEBSLEITER, ROLE_PROJEKTLEITER, ROLE_ABTEILUNGSLEITER, ROLE_QM, ROLE_SALESCOACH, ROLE_TRAINER]:
            teams_query = Team.query.filter(Team.name != ARCHIV_TEAM_NAME)
            if project_filter:
                teams_query = teams_query.filter(Team.project_id == project_filter)
            all_teams_for_selection = teams_query.order_by(Team.name).all()
        return render_template('main/team_view.html', title="Team Auswählen", team=None, all_teams_list=all_teams_for_selection, team_members_performance=[], team_coachings=[], config=current_app.config)

    team_member_ids_in_selected_team = [member.id for member in selected_team_object.members]
    if team_member_ids_in_selected_team:
        team_coachings_list_for_display = Coaching.query.filter(Coaching.team_member_id.in_(team_member_ids_in_selected_team)).order_by(desc(Coaching.coaching_date)).limit(10).all()

    for member in selected_team_object.members.all():
        member_coachings_list = Coaching.query.filter_by(team_member_id=member.id).all()
        avg_score_val = sum(c.overall_score for c in member_coachings_list) / len(member_coachings_list) if member_coachings_list else 0.0
        leitfaden_adherences_percentages = [c.leitfaden_erfuellung_prozent for c in member_coachings_list if c.leitfaden_erfuellung_prozent is not None]
        avg_leitfaden_adherence_val = sum(leitfaden_adherences_percentages) / len(leitfaden_adherences_percentages) if leitfaden_adherences_percentages else 0.0
        total_coaching_time_minutes_val = sum(c.time_spent for c in member_coachings_list if c.time_spent is not None)
        hours = total_coaching_time_minutes_val // 60; minutes = total_coaching_time_minutes_val % 60
        formatted_time_str = f"{hours} Std. {minutes} Min."
        team_members_stats.append({'id': member.id, 'name': member.name, 'avg_score': round(avg_score_val, 2), 'avg_leitfaden_adherence': round(avg_leitfaden_adherence_val, 1), 'total_coachings': len(member_coachings_list), 'raw_total_coaching_time': total_coaching_time_minutes_val, 'formatted_total_coaching_time': formatted_time_str})

    all_teams_for_dropdown = []
    if current_user.role in [ROLE_ADMIN, ROLE_BETRIEBSLEITER, ROLE_PROJEKTLEITER, ROLE_ABTEILUNGSLEITER, ROLE_QM, ROLE_SALESCOACH, ROLE_TRAINER]:
        teams_query = Team.query.filter(Team.name != ARCHIV_TEAM_NAME)
        if project_filter:
            teams_query = teams_query.filter(Team.project_id == project_filter)
        all_teams_for_dropdown = teams_query.order_by(Team.name).all()

    return render_template('main/team_view.html',
                           title=page_title, team=selected_team_object,
                           team_coachings=team_coachings_list_for_display,
                           team_members_performance=team_members_stats,
                           all_teams_list=all_teams_for_dropdown,
                           config=current_app.config)

@bp.route('/coaching/add', methods=['GET', 'POST'])
@login_required
@role_required([ROLE_TEAMLEITER, ROLE_QM, ROLE_SALESCOACH, ROLE_TRAINER, ROLE_ADMIN, ROLE_BETRIEBSLEITER])
def add_coaching():
    if current_user.role == ROLE_TEAMLEITER:
        user_team_ids = [team.id for team in current_user.teams_led]
    else:
        user_team_ids = []

    form = CoachingForm(current_user_role=current_user.role, current_user_team_ids=user_team_ids)

    if current_user.role in [ROLE_ADMIN, ROLE_BETRIEBSLEITER, ROLE_ABTEILUNGSLEITER]:
        selected_project_id = request.args.get('project', type=int) or session.get('active_project') or current_user.project_id
        if current_user.role == ROLE_ABTEILUNGSLEITER and selected_project_id not in current_user.get_allowed_project_ids():
            allowed = current_user.get_allowed_project_ids()
            selected_project_id = allowed[0] if allowed else None
    else:
        selected_project_id = current_user.project_id

    form.update_team_member_choices(exclude_archiv=True, project_id=selected_project_id)

    # --- Pre-populate assignment choices on POST before validation ---
    if request.method == 'POST':
        team_member_id = request.form.get('team_member_id', type=int)
        if team_member_id:
            form.update_assignment_choices(team_member_id, current_user.id)

    if form.validate_on_submit():
        try:
            member = TeamMember.query.get(form.team_member_id.data)
            team_id = member.team_id if member else None

            coaching = Coaching(
                team_member_id=form.team_member_id.data,
                coach_id=current_user.id,
                coaching_style=form.coaching_style.data,
                tcap_id=form.tcap_id.data if form.coaching_style.data == 'TCAP' and form.tcap_id.data else None,
                coaching_subject=form.coaching_subject.data,
                coach_notes=form.coach_notes.data if form.coach_notes.data else None,
                leitfaden_begruessung=form.leitfaden_begruessung.data,
                leitfaden_legitimation=form.leitfaden_legitimation.data,
                leitfaden_pka=form.leitfaden_pka.data,
                leitfaden_kek=form.leitfaden_kek.data,
                leitfaden_angebot=form.leitfaden_angebot.data,
                leitfaden_zusammenfassung=form.leitfaden_zusammenfassung.data,
                leitfaden_kzb=form.leitfaden_kzb.data,
                performance_mark=form.performance_mark.data,
                time_spent=form.time_spent.data,
                project_id=selected_project_id,
                team_id=team_id
            )
            if form.assigned_coaching_id.data and form.assigned_coaching_id.data != 0:
                coaching.assigned_coaching_id = form.assigned_coaching_id.data

            db.session.add(coaching)
            db.session.commit()

            if coaching.assigned_coaching_id:
                update_assignment_progress(coaching.assigned_coaching_id)

            flash('Coaching erfolgreich gespeichert!', 'success')
            return redirect(url_for('main.coaching_dashboard'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Add coaching error: {e}")
            flash(f'Fehler: {str(e)}', 'danger')
    elif request.method == 'POST':
        # On POST with validation errors, re-populate assignment choices for re-rendering
        if form.team_member_id.data:
            form.update_assignment_choices(form.team_member_id.data, current_user.id)
        for field, errors in form.errors.items():
            flash(f"Fehler '{form[field].label.text}': {'; '.join(errors)}", 'danger')

    tcap_js = "document.addEventListener('DOMContentLoaded',function(){var s=document.getElementById('coaching_style'),t=document.getElementById('tcap_id_field'),i=document.getElementById('tcap_id');function o(){if(s&&t&&i)if(s.value==='TCAP'){t.style.display='';i.required=!0}else{t.style.display='none';i.required=!1;i.value=''}}s&&t&&i&&(s.addEventListener('change',o),o())});"
    return render_template('main/add_coaching.html', title='Coaching hinzufügen', form=form, tcap_js=tcap_js, is_edit_mode=False, config=current_app.config)

@bp.route('/workshop/add', methods=['GET', 'POST'])
@login_required
@role_required([ROLE_TEAMLEITER, ROLE_QM, ROLE_SALESCOACH, ROLE_TRAINER, ROLE_ADMIN, ROLE_BETRIEBSLEITER])
def add_workshop():
    if current_user.role == ROLE_TEAMLEITER:
        user_team_ids = [team.id for team in current_user.teams_led]
    else:
        user_team_ids = []

    form = WorkshopForm(current_user_role=current_user.role, current_user_team_ids=user_team_ids)

    if current_user.role in [ROLE_ADMIN, ROLE_BETRIEBSLEITER, ROLE_ABTEILUNGSLEITER]:
        selected_project_id = request.args.get('project', type=int) or session.get('active_project') or current_user.project_id
        if current_user.role == ROLE_ABTEILUNGSLEITER and selected_project_id not in current_user.get_allowed_project_ids():
            allowed = current_user.get_allowed_project_ids()
            selected_project_id = allowed[0] if allowed else None
    else:
        selected_project_id = current_user.project_id

    form.update_participant_choices(project_id=selected_project_id)

    if form.validate_on_submit():
        try:
            workshop = Workshop(
                title=form.title.data,
                coach_id=current_user.id,
                overall_rating=form.overall_rating.data,
                time_spent=form.time_spent.data,
                notes=form.notes.data if form.notes.data else None,
                project_id=selected_project_id
            )
            db.session.add(workshop)
            db.session.flush()

            for member_id in form.team_member_ids.data:
                individual_rating_key = f'individual_rating_{member_id}'
                individual_rating = request.form.get(individual_rating_key, type=int)
                member = TeamMember.query.get(member_id)
                original_team_id = member.team_id if member else None

                if individual_rating is not None and 0 <= individual_rating <= 10:
                    stmt = workshop_participants.insert().values(
                        workshop_id=workshop.id,
                        team_member_id=member_id,
                        individual_rating=individual_rating,
                        original_team_id=original_team_id
                    )
                    db.session.execute(stmt)
                else:
                    flash(f'Ungültige Bewertung für Teilnehmer ID {member_id}', 'danger')
                    db.session.rollback()
                    return redirect(url_for('main.add_workshop'))

            db.session.commit()
            flash('Workshop erfolgreich gespeichert!', 'success')
            return redirect(url_for('main.workshop_dashboard'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Add workshop error: {e}")
            flash(f'Fehler: {str(e)}', 'danger')
    elif request.method == 'POST':
        for field, errors in form.errors.items():
            field_label = getattr(form, field).label.text if hasattr(getattr(form, field), 'label') else field
            flash(f"Fehler '{field_label}': {'; '.join(errors)}", 'danger')

    return render_template('main/add_workshop.html', title='Workshop hinzufügen', form=form, is_edit_mode=False, config=current_app.config)

@bp.route('/workshop/<int:workshop_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_workshop(workshop_id):
    workshop_to_edit = Workshop.query.get_or_404(workshop_id)

    if not (current_user.id == workshop_to_edit.coach_id or current_user.role in [ROLE_ADMIN, ROLE_BETRIEBSLEITER]):
        flash('Sie haben keine Berechtigung, diesen Workshop zu bearbeiten.', 'danger')
        abort(403)

    if current_user.role not in [ROLE_ADMIN, ROLE_BETRIEBSLEITER] and current_user.project_id != workshop_to_edit.project_id:
        abort(403)

    if current_user.role == ROLE_TEAMLEITER:
        user_team_ids = [team.id for team in current_user.teams_led]
    else:
        user_team_ids = []

    form = WorkshopForm(obj=workshop_to_edit, current_user_role=current_user.role, current_user_team_ids=user_team_ids)
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
                    return redirect(url_for('main.edit_workshop', workshop_id=workshop_id))

            db.session.commit()
            flash('Workshop erfolgreich aktualisiert!', 'success')
            return redirect(url_for('main.workshop_dashboard'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Edit workshop error: {e}")
            flash(f'Fehler: {str(e)}', 'danger')

    existing_ratings = {}
    for participant in workshop_to_edit.participants:
        rating = db.session.query(workshop_participants.c.individual_rating).filter_by(
            workshop_id=workshop_id, team_member_id=participant.id).scalar()
        existing_ratings[participant.id] = rating

    return render_template('main/add_workshop.html',
                           title=f'Workshop bearbeiten',
                           form=form,
                           is_edit_mode=True,
                           workshop=workshop_to_edit,
                           existing_ratings=existing_ratings,
                           config=current_app.config)

@bp.route('/workshop-dashboard', methods=['GET'])
@login_required
@role_required([ROLE_TEAMLEITER, ROLE_QM, ROLE_SALESCOACH, ROLE_TRAINER, ROLE_ADMIN, ROLE_BETRIEBSLEITER, ROLE_PROJEKTLEITER, ROLE_ABTEILUNGSLEITER])
def workshop_dashboard():
    page = request.args.get('page', 1, type=int)
    period_arg = request.args.get('period', 'all')
    project_filter = get_visible_project_id()

    workshops_query = Workshop.query
    if project_filter:
        workshops_query = workshops_query.filter(Workshop.project_id == project_filter)

    start_date, end_date = calculate_date_range(period_arg)
    if start_date:
        workshops_query = workshops_query.filter(Workshop.workshop_date >= start_date)
    if end_date:
        workshops_query = workshops_query.filter(Workshop.workshop_date <= end_date)

    total_workshops = workshops_query.count()
    total_time = workshops_query.with_entities(func.sum(Workshop.time_spent)).scalar() or 0
    avg_rating = workshops_query.with_entities(func.avg(Workshop.overall_rating)).scalar() or 0

    workshops_paginated = workshops_query.order_by(desc(Workshop.workshop_date)).paginate(page=page, per_page=10, error_out=False)

    query = db.session.query(
        func.date_trunc('month', Workshop.workshop_date).label('month'),
        func.count(Workshop.id).label('count')
    )
    if project_filter:
        query = query.filter(Workshop.project_id == project_filter)
    all_months_query = query.group_by('month').order_by(desc('month')).all()

    month_options = []
    for row in all_months_query:
        dt = row.month
        if dt:
            month_options.append({
                'value': dt.strftime('%Y-%m'),
                'text': f"{get_month_name_german(dt.month)} {dt.year}",
                'count': row.count
            })

    all_projects = None
    if current_user.role in [ROLE_ADMIN, ROLE_BETRIEBSLEITER, ROLE_ABTEILUNGSLEITER]:
        if current_user.role == ROLE_ABTEILUNGSLEITER:
            all_projects = current_user.projects.order_by(Project.name).all()
        else:
            all_projects = Project.query.order_by(Project.name).all()

    return render_template('main/workshop_dashboard.html',
                           title='Workshop-Dashboard',
                           total_workshops=total_workshops,
                           total_time=total_time,
                           avg_rating=round(avg_rating, 1),
                           workshops_paginated=workshops_paginated,
                           current_period_filter=period_arg,
                           month_options=month_options,
                           all_projects=all_projects,
                           current_project_filter=project_filter,
                           config=current_app.config,
                           workshop_participants=workshop_participants,
                           db=db)

@bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = PasswordChangeForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.old_password.data):
            flash('Das aktuelle Passwort ist falsch.', 'danger')
            return redirect(url_for('main.profile'))
        current_user.set_password(form.new_password.data)
        db.session.commit()
        flash('Ihr Passwort wurde erfolgreich geändert.', 'success')
        return redirect(url_for('main.profile'))
    return render_template('main/profile.html', title='Profil', form=form, config=current_app.config)

@bp.route('/coaching/<int:coaching_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_coaching(coaching_id):
    coaching_to_edit = Coaching.query.get_or_404(coaching_id)

    if not (current_user.id == coaching_to_edit.coach_id or current_user.role in [ROLE_ADMIN, ROLE_BETRIEBSLEITER]):
        flash('Sie haben keine Berechtigung, dieses Coaching zu bearbeiten.', 'danger')
        abort(403)

    if current_user.role not in [ROLE_ADMIN, ROLE_BETRIEBSLEITER] and current_user.project_id != coaching_to_edit.project_id:
        abort(403)

    if current_user.role == ROLE_TEAMLEITER:
        user_team_ids = [team.id for team in current_user.teams_led]
    else:
        user_team_ids = []

    form = CoachingForm(obj=coaching_to_edit, current_user_role=current_user.role, current_user_team_ids=user_team_ids)
    form.update_team_member_choices(exclude_archiv=False, project_id=coaching_to_edit.project_id)

    # --- Pre-populate assignment choices on POST before validation ---
    if request.method == 'POST':
        team_member_id = request.form.get('team_member_id', type=int)
        if team_member_id:
            form.update_assignment_choices(team_member_id, current_user.id)

    if form.validate_on_submit():
        try:
            form.populate_obj(coaching_to_edit)
            if coaching_to_edit.coaching_style != 'TCAP':
                coaching_to_edit.tcap_id = None
            db.session.commit()
            if coaching_to_edit.assigned_coaching_id:
                update_assignment_progress(coaching_to_edit.assigned_coaching_id)
            flash('Coaching erfolgreich aktualisiert!', 'success')
            return redirect(request.args.get('next') or url_for('main.index'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Update coaching ID {coaching_id} error: {e}")
            flash(f'Fehler: {str(e)}', 'danger')
    elif request.method == 'GET':
        form.team_member_id.data = coaching_to_edit.team_member_id
        form.update_assignment_choices(coaching_to_edit.team_member_id, coaching_to_edit.coach_id)
    else:
        # On validation errors, re-populate assignment choices for re-rendering
        if form.team_member_id.data:
            form.update_assignment_choices(form.team_member_id.data, current_user.id)

    tcap_js = """document.addEventListener('DOMContentLoaded',function(){var s=document.getElementById('coaching_style'),t=document.getElementById('tcap_id_field'),i=document.getElementById('tcap_id');function o(){if(s&&t&&i)if(s.value==='TCAP'){t.style.display='';i.required=!0}else{t.style.display='none';i.required=!1}}s&&t&&i&&(s.addEventListener('change'),o())});"""
    return render_template('main/add_coaching.html',
                           title=f'Coaching ID {coaching_to_edit.id} Bearbeiten',
                           form=form,
                           is_edit_mode=True,
                           coaching=coaching_to_edit,
                           coaching_id_being_edited=coaching_to_edit.id,
                           tcap_js=tcap_js,
                           config=current_app.config)

@bp.route('/coaching_review_dashboard', methods=['GET', 'POST'])
@login_required
@role_required([ROLE_PROJEKTLEITER, ROLE_QM, ROLE_ABTEILUNGSLEITER, ROLE_ADMIN, ROLE_BETRIEBSLEITER])
def pl_qm_dashboard():
    page = request.args.get('page', 1, type=int)
    selected_team_id_filter_str = request.args.get('team_id_filter', None)
    project_filter = get_visible_project_id()

    coachings_query = Coaching.query.join(TeamMember, Coaching.team_member_id == TeamMember.id)\
                                     .join(Team, TeamMember.team_id == Team.id)\
                                     .filter(Team.name != ARCHIV_TEAM_NAME)

    if project_filter:
        coachings_query = coachings_query.filter(Coaching.project_id == project_filter)

    coachings_paginated = coachings_query.order_by(desc(Coaching.coaching_date)).paginate(page=page, per_page=10, error_out=False)
    note_form = ProjectLeaderNoteForm()
    title = "Notizen Dashboard"
    if current_user.role == ROLE_QM:
        title = "Quality Coach Dashboard"
    elif current_user.role == ROLE_PROJEKTLEITER:
        title = "Projektleiter Dashboard"
    elif current_user.role == ROLE_ABTEILUNGSLEITER:
        title = "Abteilungsleiter Dashboard"
    elif current_user.role in [ROLE_ADMIN, ROLE_BETRIEBSLEITER]:
        title = "Dashboard (Alle Projekte)"

    if request.method == 'POST' and 'submit_note' in request.form:
        form_val = ProjectLeaderNoteForm(request.form)
        coaching_id_str = request.form.get('coaching_id')
        if not coaching_id_str or not coaching_id_str.isdigit():
            flash("Gültige Coaching-ID fehlt.", 'danger')
        elif form_val.validate():
            try:
                coaching = Coaching.query.get_or_404(int(coaching_id_str))
                if current_user.role not in [ROLE_ADMIN, ROLE_BETRIEBSLEITER] and coaching.project_id != project_filter:
                    abort(403)
                coaching.project_leader_notes = form_val.notes.data
                db.session.commit()
                flash(f'Notiz für Coaching ID {coaching_id_str} gespeichert.', 'success')
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Note save error: {e}")
                flash('Fehler Notizspeicherung.', 'danger')
        else:
            for f, errs in form_val.errors.items():
                flash(f"Validierungsfehler '{form_val[f].label.text}': {'; '.join(errs)}", 'danger')
        return redirect(url_for('main.pl_qm_dashboard',
                                page=request.args.get('page', 1, type=int),
                                team_id_filter=selected_team_id_filter_str))

    # Team-Statistiken (for Top/Flop)
    all_teams_data = []
    teams_query = Team.query.filter(Team.name != ARCHIV_TEAM_NAME)
    if project_filter:
        teams_query = teams_query.filter(Team.project_id == project_filter)
    for team_obj_stat_loop in teams_query.all():
        stats = db.session.query(
            func.coalesce(func.avg(Coaching.performance_mark * 10.0), 0).label('avg_perf'),
            func.coalesce(func.sum(Coaching.time_spent), 0).label('total_time'),
            func.coalesce(func.count(Coaching.id), 0).label('num_coachings')
        ).join(TeamMember, Coaching.team_member_id == TeamMember.id)\
         .filter(TeamMember.team_id == team_obj_stat_loop.id).first()
        all_teams_data.append({
            'id': team_obj_stat_loop.id, 'name': team_obj_stat_loop.name,
            'num_coachings': stats.num_coachings if stats else 0,
            'avg_score': round(stats.avg_perf, 2) if stats else 0,
            'total_time': stats.total_time if stats else 0
        })
    sorted_data = sorted(all_teams_data, key=lambda x: (x.get('avg_score', 0), x.get('num_coachings', 0)), reverse=True)
    top_3 = sorted_data[:3]
    teams_c = [t for t in all_teams_data if t.get('num_coachings', 0) > 0]
    flop_3 = sorted(teams_c, key=lambda x: (x.get('avg_score', 0), -x.get('num_coachings', 0)))[:3] if teams_c else []

    all_teams_for_filter_dropdown = teams_query.order_by(Team.name).all()
    selected_team_object_for_cards = None
    members_data_for_cards = []

    if selected_team_id_filter_str and selected_team_id_filter_str.isdigit():
        selected_team_id = int(selected_team_id_filter_str)
        selected_team_object_for_cards = Team.query.get(selected_team_id)
        if selected_team_object_for_cards:
            if current_user.role not in [ROLE_ADMIN, ROLE_BETRIEBSLEITER] and selected_team_object_for_cards.project_id != project_filter:
                abort(403)
            for member in selected_team_object_for_cards.members.all():
                member_coachings_list = Coaching.query.filter_by(team_member_id=member.id).all()
                avg_score_val = sum(c.overall_score for c in member_coachings_list) / len(member_coachings_list) if member_coachings_list else 0.0
                leitfaden_adherences_percentages = [
                    c.leitfaden_erfuellung_prozent for c in member_coachings_list if c.leitfaden_erfuellung_prozent is not None
                ]
                avg_leitfaden_adherence_val = sum(leitfaden_adherences_percentages) / len(leitfaden_adherences_percentages) if leitfaden_adherences_percentages else 0.0
                total_coaching_time_minutes_val = sum(c.time_spent for c in member_coachings_list if c.time_spent is not None)
                hours = total_coaching_time_minutes_val // 60
                minutes = total_coaching_time_minutes_val % 60
                formatted_time_str = f"{hours} Std. {minutes} Min."
                members_data_for_cards.append({
                    'id': member.id, 'name': member.name,
                    'avg_score': round(avg_score_val, 2),
                    'avg_leitfaden_adherence': round(avg_leitfaden_adherence_val, 1),
                    'total_coachings': len(member_coachings_list),
                    'raw_total_coaching_time': total_coaching_time_minutes_val,
                    'formatted_total_coaching_time': formatted_time_str
                })

    # Overall stats for the project
    overall_stats = db.session.query(
        func.count(Coaching.id).label('total_coachings'),
        func.coalesce(func.sum(Coaching.time_spent), 0).label('total_time'),
        func.coalesce(func.avg(Coaching.performance_mark * 10.0), 0).label('avg_score')
    ).join(TeamMember, Coaching.team_member_id == TeamMember.id)\
     .join(Team, TeamMember.team_id == Team.id)\
     .filter(Team.name != ARCHIV_TEAM_NAME)
    if project_filter:
        overall_stats = overall_stats.filter(Coaching.project_id == project_filter)
    overall_stats = overall_stats.first()

    total_coachings_overall = overall_stats.total_coachings if overall_stats else 0
    total_time_overall = overall_stats.total_time if overall_stats else 0
    avg_score_overall = round(overall_stats.avg_score, 1) if overall_stats else 0

    # Team stats for table
    teams_stats = []
    teams_query_table = Team.query.filter(Team.name != ARCHIV_TEAM_NAME)
    if project_filter:
        teams_query_table = teams_query_table.filter(Team.project_id == project_filter)
    for team in teams_query_table.all():
        stats = db.session.query(
            func.count(Coaching.id).label('num_coachings'),
            func.coalesce(func.avg(Coaching.performance_mark * 10.0), 0).label('avg_score'),
            func.coalesce(func.sum(Coaching.time_spent), 0).label('total_time')
        ).join(TeamMember, Coaching.team_member_id == TeamMember.id)\
         .filter(TeamMember.team_id == team.id).first()
        if stats.num_coachings > 0:
            teams_stats.append({
                'id': team.id,
                'name': team.name,
                'num_coachings': stats.num_coachings,
                'avg_score': round(stats.avg_score, 1),
                'total_time': stats.total_time
            })
    teams_stats.sort(key=lambda x: (-x['avg_score'], -x['num_coachings']))

    # Chart data for all teams
    chart_data = get_performance_data_for_charts(period_filter_str='all', selected_team_id_str=None, project_id=project_filter)
    chart_labels = chart_data['labels']
    chart_avg_performance_values = chart_data['avg_performance_values']

    subject_data = get_coaching_subject_distribution(period_filter_str='all', selected_team_id_str=None, project_id=project_filter)
    subject_labels = subject_data['labels']
    subject_values = subject_data['values']

    return render_template('main/projektleiter_dashboard.html',
                           title=title,
                           coachings_paginated=coachings_paginated,
                           note_form=note_form,
                           top_3_teams=top_3,
                           flop_3_teams=flop_3,
                           all_teams_for_filter=all_teams_for_filter_dropdown,
                           selected_team_id_filter=selected_team_id_filter_str,
                           selected_team_object_for_cards=selected_team_object_for_cards,
                           members_data_for_cards=members_data_for_cards,
                           total_coachings_overall=total_coachings_overall,
                           total_time_overall=total_time_overall,
                           avg_score_overall=avg_score_overall,
                           teams_stats=teams_stats,
                           chart_labels=chart_labels,
                           chart_avg_performance_values=chart_avg_performance_values,
                           subject_labels=subject_labels,
                           subject_values=subject_values,
                           config=current_app.config)

# --- Assigned Coachings (Zugewiesene Coachings) ---
@bp.route('/assigned-coachings')
@login_required
def assigned_coachings():
    page = request.args.get('page', 1, type=int)
    project_filter = get_visible_project_id()

    if current_user.role in [ROLE_ADMIN, ROLE_BETRIEBSLEITER, ROLE_PROJEKTLEITER]:
        view_type = 'pl'
        if current_user.role in [ROLE_ADMIN, ROLE_BETRIEBSLEITER]:
            query = AssignedCoaching.query
        else:
            query = AssignedCoaching.query.filter_by(project_leader_id=current_user.id)
        if project_filter:
            query = query.join(AssignedCoaching.team_member).join(TeamMember.team).filter(Team.project_id == project_filter)
    else:
        view_type = 'coach'
        query = AssignedCoaching.query.filter_by(coach_id=current_user.id)

    assignments = query.order_by(AssignedCoaching.deadline.asc(), AssignedCoaching.created_at.desc()).paginate(page=page, per_page=10, error_out=False)

    all_projects = []
    if current_user.role in [ROLE_ADMIN, ROLE_BETRIEBSLEITER]:
        all_projects = Project.query.order_by(Project.name).all()
    elif current_user.role == ROLE_ABTEILUNGSLEITER:
        all_projects = current_user.projects.order_by(Project.name).all()

    return render_template('main/assigned_coachings.html',
                           assignments=assignments,
                           view_type=view_type,
                           all_projects=all_projects,
                           current_project_filter=project_filter if view_type == 'pl' else None,
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


@bp.route('/assigned-coachings/<int:assignment_id>/cancel', methods=['POST'])
@login_required
def cancel_assigned_coaching(assignment_id):
    assignment = AssignedCoaching.query.get_or_404(assignment_id)
    if assignment.project_leader_id != current_user.id and current_user.role not in [ROLE_ADMIN, ROLE_BETRIEBSLEITER]:
        flash('Sie haben keine Berechtigung, diese Aufgabe zu stornieren.', 'danger')
        return redirect(url_for('main.assigned_coachings'))
    if assignment.status in ['completed', 'expired', 'cancelled']:
        flash('Diese Aufgabe kann nicht mehr storniert werden.', 'warning')
        return redirect(url_for('main.assigned_coachings'))
    assignment.status = 'cancelled'
    db.session.commit()
    flash('Coaching-Aufgabe wurde storniert.', 'success')
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


@bp.route('/api/available_assignments', methods=['GET'])
@login_required
def available_assignments():
    member_id = request.args.get('member_id', type=int)
    if not member_id:
        return jsonify({'assignments': []})
    assignments = AssignedCoaching.query.filter(
        AssignedCoaching.team_member_id == member_id,
        AssignedCoaching.coach_id == current_user.id,
        AssignedCoaching.status.in_(['pending', 'accepted', 'in_progress'])
    ).all()
    assignment_list = [{'id': a.id, 'deadline': a.deadline.strftime('%d.%m.%y'), 'progress': a.progress} for a in assignments]
    return jsonify({'assignments': assignment_list})


@bp.route('/api/member_current_score', methods=['GET'])
@login_required
def get_member_current_score():
    member_id = request.args.get('member_id', type=int)
    if not member_id:
        return jsonify({'error': 'No member_id'}), 400
    member = TeamMember.query.get_or_404(member_id)
    coachings = Coaching.query.filter_by(team_member_id=member.id).all()
    avg_score = 0
    if coachings:
        avg_score = sum(c.overall_score for c in coachings) / len(coachings)
    return jsonify({'score': round(avg_score, 2)})


@bp.route('/api/member_coaching_trend', methods=['GET'])
@login_required
def get_member_coaching_trend():
    team_member_id_str = request.args.get('team_member_id')
    count_str = request.args.get('count', '10')
    if not team_member_id_str:
        return jsonify({"error": "Team Member ID (team_member_id) is required"}), 400
    try:
        team_member_id = int(team_member_id_str)
    except ValueError:
        return jsonify({"error": "Invalid Team Member ID format"}), 400
    member = TeamMember.query.get_or_404(team_member_id)
    if current_user.role not in [ROLE_ADMIN, ROLE_BETRIEBSLEITER] and member.team.project_id != current_user.project_id:
        return jsonify({"error": "Access denied"}), 403

    query = Coaching.query.filter_by(team_member_id=team_member_id).order_by(Coaching.coaching_date.desc())
    if count_str.lower() != 'all':
        try:
            count = int(count_str)
            if count <= 0:
                return jsonify({"error": "Count must be a positive integer or 'all'"}), 400
            query = query.limit(count)
        except ValueError:
            return jsonify({"error": "Invalid count format"}), 400
    recent_coachings = query.all()
    recent_coachings.reverse()
    if not recent_coachings:
        return jsonify({"labels": [], "scores": [], "dates": []})
    labels = []
    scores = []
    dates = []
    for i, coaching in enumerate(recent_coachings):
        labels.append(f"Coaching {i+1}")
        scores.append(coaching.overall_score if coaching.overall_score is not None else 0)
        dates.append(coaching.coaching_date.strftime('%d.%m.%y'))
    return jsonify({"labels": labels, "scores": scores, "dates": dates})


@bp.route('/set-project/<int:project_id>')
@login_required
def set_project(project_id):
    if current_user.role not in [ROLE_ADMIN, ROLE_BETRIEBSLEITER, ROLE_ABTEILUNGSLEITER]:
        abort(403)
    project = Project.query.get_or_404(project_id)
    if current_user.role == ROLE_ABTEILUNGSLEITER:
        if project not in current_user.projects:
            abort(403)
    session['active_project'] = project_id
    flash(f'Aktives Projekt gewechselt zu {project.name}', 'success')
    return redirect(request.referrer or url_for('main.index'))
