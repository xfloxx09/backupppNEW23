# app/models.py
print("<<<< START models.py (ARCHIV-HISTORIE) GELADEN >>>>")

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager
from datetime import datetime, timezone
from app.roles import ROLE_ADMIN, ROLE_BETRIEBSLEITER, ROLE_ABTEILUNGSLEITER

team_leaders = db.Table('team_leaders',
    db.Column('team_id', db.Integer, db.ForeignKey('teams.id', ondelete='CASCADE'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
)

workshop_participants = db.Table('workshop_participants',
    db.Column('workshop_id', db.Integer, db.ForeignKey('workshops.id', ondelete='CASCADE'), primary_key=True),
    db.Column('team_member_id', db.Integer, db.ForeignKey('team_members.id', ondelete='CASCADE'), primary_key=True),
    db.Column('individual_rating', db.Integer, nullable=True),
    db.Column('original_team_id', db.Integer, db.ForeignKey('teams.id'), nullable=True)
)

user_projects = db.Table('user_projects',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('project_id', db.Integer, db.ForeignKey('projects.id'), primary_key=True)
)

class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.utcnow())

    users = db.relationship('User', backref='project_ref', lazy='dynamic')
    teams = db.relationship('Team', backref='project_ref', lazy='dynamic')
    workshops = db.relationship('Workshop', backref='project_ref', lazy='dynamic')
    coachings = db.relationship('Coaching', backref='project_ref', lazy='dynamic')

    def __repr__(self):
        return f'<Project {self.name}>'

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True, nullable=False)
    email = db.Column(db.String(120), index=True, unique=False, nullable=True)
    password_hash = db.Column(db.String(256), nullable=True)
    role = db.Column(db.String(20), nullable=False, default='Teammitglied')
    team_id_if_leader = db.Column(db.Integer, db.ForeignKey('teams.id', name='fk_user_team_id_if_leader'), nullable=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)

    coachings_done = db.relationship('Coaching', foreign_keys='Coaching.coach_id', backref='coach', lazy='dynamic')
    teams_led = db.relationship('Team', secondary=team_leaders, back_populates='leaders', lazy='dynamic')
    workshops_given = db.relationship('Workshop', backref='coach', lazy='dynamic')
    projects = db.relationship('Project', secondary=user_projects, backref='users_with_access', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

    @property
    def has_multiple_projects(self):
        if self.role not in [ROLE_ADMIN, ROLE_BETRIEBSLEITER, ROLE_ABTEILUNGSLEITER]:
            return False
        if self.role == ROLE_ABTEILUNGSLEITER:
            return self.projects.count() > 1
        else:
            from app.models import Project
            return Project.query.count() > 1

    def get_allowed_project_ids(self):
        if self.role in [ROLE_ADMIN, ROLE_BETRIEBSLEITER]:
            from app.models import Project
            return [p.id for p in Project.query.all()]
        elif self.role == ROLE_ABTEILUNGSLEITER:
            return [p.id for p in self.projects]
        else:
            return [self.project_id] if self.project_id else []

@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))

class Team(db.Model):
    __tablename__ = 'teams'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    team_leader_id = db.Column(db.Integer, db.ForeignKey('users.id', name='fk_team_team_leader_id'), nullable=True)
    team_leader = db.relationship(
        'User',
        foreign_keys=[team_leader_id],
        backref=db.backref('led_team_obj', uselist=False, lazy='joined')
    )
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)

    members = db.relationship('TeamMember', backref='team', lazy='dynamic', foreign_keys='TeamMember.team_id')
    leaders = db.relationship('User', secondary=team_leaders, back_populates='teams_led', lazy='dynamic')

    def __repr__(self):
        return f'<Team {self.name}>'

class TeamMember(db.Model):
    __tablename__ = 'team_members'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id', name='fk_teammember_team_id'), nullable=False)
    coachings_received = db.relationship('Coaching', backref='team_member_coached', lazy='dynamic')
    workshops_attended = db.relationship('Workshop', secondary=workshop_participants,
                                         backref=db.backref('participants', lazy='dynamic'),
                                         lazy='dynamic')

    original_team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=True)
    original_project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=True)

    original_team = db.relationship('Team', foreign_keys=[original_team_id])
    original_project = db.relationship('Project', foreign_keys=[original_project_id])

    def __repr__(self):
        return f'<TeamMember {self.name} (Team ID: {self.team_id})>'

class Coaching(db.Model):
    __tablename__ = 'coachings'
    id = db.Column(db.Integer, primary_key=True)
    team_member_id = db.Column(db.Integer, db.ForeignKey('team_members.id', name='fk_coaching_team_member_id'), nullable=False)
    coach_id = db.Column(db.Integer, db.ForeignKey('users.id', name='fk_coaching_coach_id'), nullable=False)
    coaching_date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.utcnow())
    coaching_style = db.Column(db.String(50), nullable=True)
    tcap_id = db.Column(db.String(50), nullable=True)
    coaching_subject = db.Column(db.String(50), nullable=True)
    coach_notes = db.Column(db.Text, nullable=True)

    leitfaden_begruessung = db.Column(db.String(10), default="k.A.", nullable=True)
    leitfaden_legitimation = db.Column(db.String(10), default="k.A.", nullable=True)
    leitfaden_pka = db.Column(db.String(10), default="k.A.", nullable=True)
    leitfaden_kek = db.Column(db.String(10), default="k.A.", nullable=True)
    leitfaden_angebot = db.Column(db.String(10), default="k.A.", nullable=True)
    leitfaden_zusammenfassung = db.Column(db.String(10), default="k.A.", nullable=True)
    leitfaden_kzb = db.Column(db.String(10), default="k.A.", nullable=True)

    performance_mark = db.Column(db.Integer, nullable=True)
    time_spent = db.Column(db.Integer, nullable=True)
    project_leader_notes = db.Column(db.Text, nullable=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=True)
    assigned_coaching_id = db.Column(db.Integer, db.ForeignKey('assigned_coachings.id', name='fk_coachings_assigned_coaching'), nullable=True)

    team = db.relationship('Team', foreign_keys=[team_id])

    @property
    def leitfaden_fields_list(self):
        return [
            ("Begrüßung", self.leitfaden_begruessung),
            ("Legitimation", self.leitfaden_legitimation),
            ("PKA", self.leitfaden_pka),
            ("KEK", self.leitfaden_kek),
            ("Angebot", self.leitfaden_angebot),
            ("Zusammenfassung", self.leitfaden_zusammenfassung),
            ("KZB", self.leitfaden_kzb)
        ]

    @property
    def leitfaden_counts(self):
        ja_count = 0
        nein_count = 0
        ka_count = 0
        for _, value in self.leitfaden_fields_list:
            if value == "Ja":
                ja_count += 1
            elif value == "Nein":
                nein_count += 1
            elif value == "k.A.":
                ka_count += 1
        return {'ja': ja_count, 'nein': nein_count, 'ka': ka_count}

    @property
    def leitfaden_erfuellung_display(self):
        counts = self.leitfaden_counts
        ja = counts['ja']
        nein = counts['nein']
        ka = counts['ka']
        total_relevant = ja + nein
        if total_relevant == 0:
            return f"N/A ({ka} k.A.)" if ka > 0 else "N/A"
        return f"{ja}/{total_relevant} ({ka} k.A.)"

    @property
    def leitfaden_erfuellung_prozent(self):
        counts = self.leitfaden_counts
        ja = counts['ja']
        nein = counts['nein']
        total_relevant = ja + nein
        if total_relevant == 0:
            return 0.0
        return (ja / total_relevant) * 100

    @property
    def overall_score(self):
        if self.performance_mark is None:
            return 0.0
        performance_percentage = (float(self.performance_mark) / 10.0) * 100.0
        return round(performance_percentage, 2)

    def __repr__(self):
        return f'<Coaching {self.id} for TeamMember {self.team_member_id} on {self.coaching_date}>'

class Workshop(db.Model):
    __tablename__ = 'workshops'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    coach_id = db.Column(db.Integer, db.ForeignKey('users.id', name='fk_workshop_coach_id'), nullable=False)
    workshop_date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.utcnow())
    overall_rating = db.Column(db.Integer, nullable=True)
    time_spent = db.Column(db.Integer, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)

    def __repr__(self):
        return f'<Workshop {self.id}: {self.title}>'


class AssignedCoaching(db.Model):
    __tablename__ = 'assigned_coachings'
    id = db.Column(db.Integer, primary_key=True)
    project_leader_id = db.Column(db.Integer, db.ForeignKey('users.id', name='fk_assigned_coachings_project_leader'), nullable=False)
    coach_id = db.Column(db.Integer, db.ForeignKey('users.id', name='fk_assigned_coachings_coach'), nullable=False)
    team_member_id = db.Column(db.Integer, db.ForeignKey('team_members.id', name='fk_assigned_coachings_team_member'), nullable=False)
    deadline = db.Column(db.DateTime, nullable=False)
    expected_coaching_count = db.Column(db.Integer, nullable=False, default=1)
    desired_performance_note = db.Column(db.Integer, nullable=True)
    current_performance_note_at_assign = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='pending')
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.utcnow())
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.utcnow(), onupdate=lambda: datetime.utcnow())

    project_leader = db.relationship('User', foreign_keys=[project_leader_id], backref='assigned_coachings_as_pl')
    coach = db.relationship('User', foreign_keys=[coach_id], backref='assigned_coachings_as_coach')
    team_member = db.relationship('TeamMember', backref='assigned_coachings')
    coachings = db.relationship('Coaching', backref='assigned_coaching', lazy='dynamic')

    @property
    def progress(self):
        completed = self.coachings.count()
        if self.expected_coaching_count == 0:
            return 0
        return min(100, int((completed / self.expected_coaching_count) * 100))

    @property
    def is_overdue(self):
        # Use naive UTC datetime to compare with deadline (which is stored as naive)
        return datetime.utcnow() > self.deadline and self.status not in ['completed', 'expired']

    def __repr__(self):
        return f'<AssignedCoaching {self.id} to {self.coach.username} for {self.team_member.name}>'

print("<<<< ENDE models.py (ARCHIV-HISTORIE) GELADEN >>>>")
