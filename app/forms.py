# app/forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField, SelectMultipleField, IntegerField, TextAreaField, DateTimeField
from wtforms.validators import DataRequired, EqualTo, ValidationError, Length, NumberRange, Optional
from app.models import User, Team, TeamMember, Project
from app.utils import ARCHIV_TEAM_NAME, ROLE_TEAMLEITER, ROLE_ADMIN, ROLE_BETRIEBSLEITER, ROLE_ABTEILUNGSLEITER

class LoginForm(FlaskForm):
    username = StringField('Benutzername', validators=[DataRequired("Benutzername ist erforderlich.")])
    password = PasswordField('Passwort', validators=[DataRequired("Passwort ist erforderlich.")])
    remember_me = BooleanField('Angemeldet bleiben')
    submit = SubmitField('Anmelden')

class RegistrationForm(FlaskForm):
    username = StringField('Benutzername', validators=[DataRequired("Benutzername ist erforderlich."), Length(min=3, max=64)])
    email = StringField('E-Mail (Optional)')
    password = PasswordField('Passwort', validators=[DataRequired("Passwort ist erforderlich."), Length(min=6)])
    password2 = PasswordField(
        'Passwort wiederholen',
        validators=[DataRequired("Passwortwiederholung ist erforderlich."), EqualTo('password', message='Passwörter müssen übereinstimmen.')]
    )
    role = SelectField('Rolle', choices=[
        ('Teamleiter', 'Teamleiter'),
        ('Qualitätsmanager', 'Qualitäts-Coach'),
        ('SalesCoach', 'Sales-Coach'),
        ('Trainer', 'Trainer'),
        ('Projektleiter', 'AL/PL'),
        ('Admin', 'Admin'),
        ('Betriebsleiter', 'Betriebsleiter'),
        ('Abteilungsleiter', 'Abteilungsleiter')
    ], validators=[DataRequired("Rolle ist erforderlich.")])
    team_ids = SelectMultipleField('Zugeordnete Teams (nur für Teamleiter)', coerce=int, choices=[])
    project_id = SelectField('Projekt', coerce=int, choices=[])
    project_ids = SelectMultipleField('Zugeordnete Projekte (nur für Abteilungsleiter)', coerce=int, choices=[])
    submit = SubmitField('Benutzer registrieren/aktualisieren')

    def __init__(self, original_username=None, *args, **kwargs):
        super(RegistrationForm, self).__init__(*args, **kwargs)
        self.original_username = original_username
        active_teams = Team.query.filter(Team.name != ARCHIV_TEAM_NAME).order_by(Team.name).all()
        self.team_ids.choices = [(t.id, t.name) for t in active_teams]
        all_projects = Project.query.order_by(Project.name).all()
        self.project_id.choices = [(p.id, p.name) for p in all_projects]
        self.project_ids.choices = [(p.id, p.name) for p in all_projects]

    def validate_username(self, username_field):
        query = User.query.filter(User.username == username_field.data)
        if self.original_username and self.original_username == username_field.data:
            return
        user = query.first()
        if user:
            raise ValidationError('Dieser Benutzername ist bereits vergeben.')

    def validate_project_id(self, field):
        # For roles other than Abteilungsleiter, we need project_id
        if self.role.data != 'Abteilungsleiter' and not field.data:
            raise ValidationError('Projekt ist erforderlich.')
        # For Abteilungsleiter, project_id is optional, but we validate project_ids
        if self.role.data == 'Abteilungsleiter' and not self.project_ids.data:
            raise ValidationError('Mindestens ein Projekt muss ausgewählt werden.')

    def validate_project_ids(self, field):
        if self.role.data == 'Abteilungsleiter' and not field.data:
            raise ValidationError('Mindestens ein Projekt muss ausgewählt werden.')

class TeamForm(FlaskForm):
    name = StringField('Team Name', validators=[DataRequired(), Length(min=3, max=100)])
    team_leaders = SelectMultipleField('Teamleiter', coerce=int, choices=[])
    project_id = SelectField('Projekt', coerce=int, choices=[])
    submit = SubmitField('Team erstellen/aktualisieren')

    def __init__(self, original_name=None, *args, **kwargs):
        super(TeamForm, self).__init__(*args, **kwargs)
        self.original_name = original_name
        possible_leaders = User.query.filter(User.role == ROLE_TEAMLEITER).order_by(User.username).all()
        self.team_leaders.choices = [(u.id, u.username) for u in possible_leaders]
        self.project_id.choices = [(p.id, p.name) for p in Project.query.order_by(Project.name).all()]

    def validate_name(self, name_field):
        if self.original_name and self.original_name.strip().upper() == name_field.data.strip().upper():
            return
        if Team.query.filter(Team.name.ilike(name_field.data)).first():
            raise ValidationError('Ein Team mit diesem Namen existiert bereits.')
        if name_field.data.strip().upper() == ARCHIV_TEAM_NAME:
            raise ValidationError(f'Der Teamname "{ARCHIV_TEAM_NAME}" ist für das System reserviert.')

class TeamMemberForm(FlaskForm):
    name = StringField('Name des Teammitglieds', validators=[DataRequired(), Length(min=2, max=100)])
    team_id = SelectField('Team', coerce=int, validators=[DataRequired("Team ist erforderlich.")], choices=[])
    submit = SubmitField('Teammitglied erstellen/aktualisieren')

    def __init__(self, *args, **kwargs):
        super(TeamMemberForm, self).__init__(*args, **kwargs)
        active_teams = Team.query.filter(Team.name != ARCHIV_TEAM_NAME).order_by(Team.name).all()
        if active_teams:
            self.team_id.choices = [(t.id, t.name) for t in active_teams]
        else:
            self.team_id.choices = [("", "Bitte zuerst Teams erstellen")]

LEITFADEN_CHOICES = [('Ja', 'Ja'), ('Nein', 'Nein'), ('k.A.', 'k.A.')]
COACHING_SUBJECT_CHOICES = [
    ('', '--- Bitte wählen ---'),
    ('Sales', 'Sales'),
    ('Qualität', 'Qualität'),
    ('Allgemein', 'Allgemein')
]

class CoachingForm(FlaskForm):
    team_member_id = SelectField(
        'Teammitglied',
        coerce=int,
        validators=[DataRequired("Teammitglied ist erforderlich.")],
        choices=[]
    )
    coaching_style = SelectField('Coaching Stil', choices=[('Side-by-Side', 'Side-by-Side'), ('TCAP', 'TCAP')], validators=[DataRequired("Coaching-Stil ist erforderlich.")])
    tcap_id = StringField('T-CAP ID (falls TCAP gewählt)')
    coaching_subject = SelectField('Coaching Thema', choices=COACHING_SUBJECT_CHOICES, validators=[DataRequired("Coaching-Thema ist erforderlich.")])
    leitfaden_begruessung = SelectField('Begrüßung', choices=LEITFADEN_CHOICES, default='k.A.')
    leitfaden_legitimation = SelectField('Legitimation', choices=LEITFADEN_CHOICES, default='k.A.')
    leitfaden_pka = SelectField('PKA', choices=LEITFADEN_CHOICES, default='k.A.')
    leitfaden_kek = SelectField('KEK', choices=LEITFADEN_CHOICES, default='k.A.')
    leitfaden_angebot = SelectField('Angebot', choices=LEITFADEN_CHOICES, default='k.A.')
    leitfaden_zusammenfassung = SelectField('Zusammenfassung', choices=LEITFADEN_CHOICES, default='k.A.')
    leitfaden_kzb = SelectField('KZB', choices=LEITFADEN_CHOICES, default='k.A.')
    performance_mark = IntegerField('Performance Note (0-10)', validators=[DataRequired("Performance Note ist erforderlich."), NumberRange(min=0, max=10)])
    time_spent = IntegerField('Zeitaufwand (Minuten)', validators=[DataRequired("Zeitaufwand ist erforderlich."), NumberRange(min=1)])
    coach_notes = TextAreaField('Notizen des Coaches', validators=[Length(max=2000)])
    submit = SubmitField('Coaching speichern')

    def __init__(self, current_user_role=None, current_user_team_ids=None, *args, **kwargs):
        super(CoachingForm, self).__init__(*args, **kwargs)
        self.current_user_role = current_user_role
        self.current_user_team_ids = current_user_team_ids if current_user_team_ids is not None else []

    def update_team_member_choices(self, exclude_archiv=False, project_id=None):
        generated_choices = []
        query = TeamMember.query.join(Team, TeamMember.team_id == Team.id)

        if project_id:
            query = query.filter(Team.project_id == project_id)

        if self.current_user_role == ROLE_TEAMLEITER and self.current_user_team_ids:
            query = query.filter(TeamMember.team_id.in_(self.current_user_team_ids))
        elif self.current_user_role not in [ROLE_ADMIN, ROLE_BETRIEBSLEITER]:
            pass

        if exclude_archiv:
            query = query.filter(Team.name != ARCHIV_TEAM_NAME)

        members = query.order_by(TeamMember.name).all()
        for m in members:
            generated_choices.append((m.id, f"{m.name} ({m.team.name})"))
        self.team_member_id.choices = generated_choices

class PasswordChangeForm(FlaskForm):
    old_password = PasswordField('Aktuelles Passwort', validators=[DataRequired("Bitte aktuelles Passwort eingeben.")])
    new_password = PasswordField('Neues Passwort', validators=[DataRequired("Neues Passwort ist erforderlich."), Length(min=6)])
    confirm_password = PasswordField('Neues Passwort wiederholen', validators=[DataRequired("Bitte wiederholen."), EqualTo('new_password', message='Passwörter müssen übereinstimmen.')])
    submit = SubmitField('Passwort ändern')

class WorkshopForm(FlaskForm):
    title = StringField('Workshop-Thema', validators=[DataRequired("Bitte ein Thema angeben."), Length(max=200)])
    team_member_ids = SelectMultipleField('Teilnehmer', coerce=int, validators=[DataRequired("Mindestens ein Teilnehmer erforderlich.")], choices=[])
    overall_rating = IntegerField('Gesamtbewertung (0-10)', validators=[DataRequired(), NumberRange(min=0, max=10)])
    time_spent = IntegerField('Zeitaufwand (Minuten)', validators=[DataRequired(), NumberRange(min=1)])
    notes = TextAreaField('Notizen', validators=[Length(max=2000)])
    submit = SubmitField('Workshop speichern')

    def __init__(self, current_user_role=None, current_user_team_ids=None, *args, **kwargs):
        super(WorkshopForm, self).__init__(*args, **kwargs)
        self.current_user_role = current_user_role
        self.current_user_team_ids = current_user_team_ids if current_user_team_ids is not None else []

    def update_participant_choices(self, project_id=None):
        generated_choices = []
        query = TeamMember.query.join(Team, TeamMember.team_id == Team.id)

        if project_id:
            query = query.filter(Team.project_id == project_id)

        if self.current_user_role == ROLE_TEAMLEITER and self.current_user_team_ids:
            query = query.filter(TeamMember.team_id.in_(self.current_user_team_ids))

        query = query.filter(Team.name != ARCHIV_TEAM_NAME)

        members = query.order_by(TeamMember.name).all()
        for m in members:
            generated_choices.append((m.id, f"{m.name} ({m.team.name})"))
        self.team_member_ids.choices = generated_choices

    def validate_team_member_ids(self, field):
        if len(field.data) < 2:
            raise ValidationError('Es müssen mindestens zwei Teilnehmer ausgewählt werden.')

class ProjectLeaderNoteForm(FlaskForm):
    notes = TextAreaField('PL/QM Notiz',
                          validators=[DataRequired("Die Notiz darf nicht leer sein."),
                                      Length(max=2000)])

class ProjectForm(FlaskForm):
    name = StringField('Projektname', validators=[DataRequired(), Length(min=3, max=100)])
    description = TextAreaField('Beschreibung', validators=[Length(max=500)])
    submit = SubmitField('Projekt speichern')

class AssignedCoachingForm(FlaskForm):
    coach_id = SelectField('Coach', coerce=int, validators=[DataRequired("Coach ist erforderlich.")], choices=[])
    team_member_id = SelectField('Teammitglied', coerce=int, validators=[DataRequired("Teammitglied ist erforderlich.")], choices=[])
    deadline = DateTimeField('Deadline', format='%Y-%m-%d %H:%M', validators=[DataRequired("Deadline ist erforderlich.")])
    expected_coaching_count = IntegerField('Anzahl erwarteter Coachings', validators=[DataRequired("Anzahl ist erforderlich."), NumberRange(min=1, max=50)], default=1)
    desired_performance_note = IntegerField('Gewünschte Performance Note (0-10)', validators=[Optional(), NumberRange(min=0, max=10)], default=None)
    submit = SubmitField('Coaching zuweisen')

    def __init__(self, project_id=None, *args, **kwargs):
        super(AssignedCoachingForm, self).__init__(*args, **kwargs)
        if project_id:
            # Coaches: users with roles that can coach
            coach_roles = ['Teamleiter', 'Qualitätsmanager', 'SalesCoach', 'Trainer', 'Admin', 'Betriebsleiter']
            coaches = User.query.filter(User.role.in_(coach_roles)).order_by(User.username).all()
            self.coach_id.choices = [(u.id, f"{u.username} ({u.role})") for u in coaches]

            # Team members: from the given project, excluding archiv
            # Use explicit relationship to avoid ambiguous foreign keys
            members = TeamMember.query.join(TeamMember.team).filter(
                Team.project_id == project_id,
                Team.name != ARCHIV_TEAM_NAME
            ).order_by(TeamMember.name).all()
            self.team_member_id.choices = [(m.id, f"{m.name} ({m.team.name})") for m in members]
