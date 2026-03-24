# app/__init__.py
print("<<<< START __init__.py wird GELADEN >>>>")

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from config import Config
import os
from datetime import datetime, timezone
import pytz
from sqlalchemy import inspect, text

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = "Bitte melden Sie sich an, um auf diese Seite zuzugreifen."
login_manager.login_message_category = "info"

migrate = Migrate()

def create_app(config_class=Config):
    print("<<<< create_app() WIRD AUFGERUFEN (__init__.py) >>>>")
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    print("<<<< db.init_app() VORBEI (__init__.py) >>>>")
    login_manager.init_app(app)
    migrate.init_app(app, db)

    # --- Migration: ensure necessary columns and tables exist ---
    with app.app_context():
        print("--- Running automatic migrations ---")
        inspector = inspect(db.engine)
        conn = db.engine.connect()

        # 1. coachings.team_id
        columns_coachings = [col['name'] for col in inspector.get_columns('coachings')]
        if 'team_id' not in columns_coachings:
            print("⚠️ Spalte 'team_id' in coachings fehlt – wird hinzugefügt...")
            conn.execute(text('ALTER TABLE coachings ADD COLUMN team_id INTEGER REFERENCES teams(id)'))
            conn.commit()
            print("✅ Spalte 'team_id' in coachings hinzugefügt.")
        else:
            print("✅ Spalte 'team_id' in coachings existiert bereits.")

        # 2. Für bestehende Coachings die team_id nachtragen (falls NULL)
        conn.execute(text('''
            UPDATE coachings
            SET team_id = team_members.team_id
            FROM team_members
            WHERE coachings.team_member_id = team_members.id
            AND coachings.team_id IS NULL
        '''))
        conn.commit()
        print("ℹ️ Bestehende Coachings mit team_id aktualisiert.")

        # 3. Prüfen und Hinzufügen von workshop_participants.original_team_id
        if 'workshop_participants' in inspector.get_table_names():
            columns_wp = [col['name'] for col in inspector.get_columns('workshop_participants')]
            if 'original_team_id' not in columns_wp:
                print("⚠️ Spalte 'original_team_id' in workshop_participants fehlt – wird hinzugefügt...")
                conn.execute(text('ALTER TABLE workshop_participants ADD COLUMN original_team_id INTEGER REFERENCES teams(id)'))
                conn.commit()
                print("✅ Spalte 'original_team_id' in workshop_participants hinzugefügt.")
            else:
                print("✅ Spalte 'original_team_id' in workshop_participants existiert bereits.")

            conn.execute(text('''
                UPDATE workshop_participants
                SET original_team_id = team_members.team_id
                FROM team_members
                WHERE workshop_participants.team_member_id = team_members.id
                AND workshop_participants.original_team_id IS NULL
            '''))
            conn.commit()
            print("ℹ️ Bestehende Workshop-Teilnehmer mit original_team_id aktualisiert.")
        else:
            print("✅ Tabelle 'workshop_participants' existiert noch nicht, später automatisch.")

        # 4. user_projects table
        if 'user_projects' not in inspector.get_table_names():
            print("⚠️ Tabelle 'user_projects' fehlt – wird erstellt...")
            conn.execute(text('''
                CREATE TABLE user_projects (
                    user_id INTEGER NOT NULL,
                    project_id INTEGER NOT NULL,
                    PRIMARY KEY (user_id, project_id),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
                )
            '''))
            conn.commit()
            print("✅ Tabelle 'user_projects' erstellt.")

            # Für alle bestehenden Abteilungsleiter die Zuordnung zum aktuellen Projekt eintragen
            res = conn.execute(text("SELECT id, project_id FROM users WHERE role = 'Abteilungsleiter' AND project_id IS NOT NULL"))
            rows = res.fetchall()
            for user_id, project_id in rows:
                conn.execute(
                    text("INSERT INTO user_projects (user_id, project_id) VALUES (:user_id, :project_id)"),
                    {"user_id": user_id, "project_id": project_id}
                )
            conn.commit()
            print(f"ℹ️ {len(rows)} Abteilungsleiter-Zuordnungen in user_projects eingetragen.")
        else:
            print("✅ Tabelle 'user_projects' existiert bereits.")

        # 5. Fehlende Zuordnungen nachholen
        res = conn.execute(text("""
            SELECT u.id, u.project_id
            FROM users u
            WHERE u.role = 'Abteilungsleiter'
              AND u.project_id IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM user_projects up WHERE up.user_id = u.id AND up.project_id = u.project_id)
        """))
        rows = res.fetchall()
        for user_id, project_id in rows:
            conn.execute(
                text("INSERT INTO user_projects (user_id, project_id) VALUES (:user_id, :project_id)"),
                {"user_id": user_id, "project_id": project_id}
            )
        conn.commit()
        if rows:
            print(f"ℹ️ {len(rows)} zusätzliche Abteilungsleiter-Zuordnungen in user_projects nachgetragen.")

        # ========== assigned_coachings table ==========
        # 6. Create assigned_coachings table if not exists
        if 'assigned_coachings' not in inspector.get_table_names():
            print("⚠️ Tabelle 'assigned_coachings' fehlt – wird erstellt...")
            conn.execute(text('''
                CREATE TABLE assigned_coachings (
                    id SERIAL NOT NULL,
                    project_leader_id INTEGER NOT NULL,
                    coach_id INTEGER NOT NULL,
                    team_member_id INTEGER NOT NULL,
                    deadline TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                    expected_coaching_count INTEGER NOT NULL,
                    desired_performance_note INTEGER,
                    current_performance_note_at_assign FLOAT,
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (id),
                    FOREIGN KEY(project_leader_id) REFERENCES users(id),
                    FOREIGN KEY(coach_id) REFERENCES users(id),
                    FOREIGN KEY(team_member_id) REFERENCES team_members(id)
                )
            '''))
            conn.commit()
            print("✅ Tabelle 'assigned_coachings' erstellt.")

            # Create index on status
            conn.execute(text('CREATE INDEX ix_assigned_coachings_status ON assigned_coachings (status)'))
            conn.commit()
        else:
            print("✅ Tabelle 'assigned_coachings' existiert bereits.")
            # Ensure id column has auto-increment (if table was created without SERIAL)
            conn.execute(text('''
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                   WHERE table_name='assigned_coachings' AND column_name='id' 
                                   AND column_default IS NOT NULL AND column_default LIKE 'nextval%') THEN
                        CREATE SEQUENCE IF NOT EXISTS assigned_coachings_id_seq;
                        ALTER TABLE assigned_coachings ALTER COLUMN id SET DEFAULT nextval('assigned_coachings_id_seq');
                        PERFORM setval('assigned_coachings_id_seq', COALESCE((SELECT MAX(id) FROM assigned_coachings), 1));
                    END IF;
                END
                $$;
            '''))
            conn.commit()
            print("✅ Auto-increment für assigned_coachings.id sichergestellt.")

        # 7. Add assigned_coaching_id to coachings table if not exists
        columns_coachings = [col['name'] for col in inspector.get_columns('coachings')]
        if 'assigned_coaching_id' not in columns_coachings:
            print("⚠️ Spalte 'assigned_coaching_id' in coachings fehlt – wird hinzugefügt...")
            conn.execute(text('ALTER TABLE coachings ADD COLUMN assigned_coaching_id INTEGER REFERENCES assigned_coachings(id)'))
            conn.commit()
            print("✅ Spalte 'assigned_coaching_id' in coachings hinzugefügt.")
        else:
            print("✅ Spalte 'assigned_coaching_id' in coachings existiert bereits.")

        print("--- Migration abgeschlossen ---")

    # Blueprints registrieren
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    print("<<<< auth_bp REGISTRIERT (__init__.py) >>>>")

    from app.main_routes import bp as main_bp 
    app.register_blueprint(main_bp)
    print("<<<< main_bp REGISTRIERT (__init__.py) >>>>")

    from app.admin import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')
    print("<<<< admin_bp REGISTRIERT (__init__.py) >>>>")
    
    # Kontextprozessor für globale Variablen in Templates (z.B. aktuelles Jahr)
    @app.context_processor
    def inject_current_year():
        return {'current_year': datetime.utcnow().year}

    # Kontextprozessor für erlaubte Projekte (für Projektwechsler in der Navbar)
    @app.context_processor
    def inject_user_allowed_projects():
        from app.models import Project
        from app.roles import ROLE_ADMIN, ROLE_BETRIEBSLEITER, ROLE_ABTEILUNGSLEITER
        if current_user.is_authenticated:
            if current_user.role in [ROLE_ADMIN, ROLE_BETRIEBSLEITER]:
                projects = Project.query.order_by(Project.name).all()
            elif current_user.role == ROLE_ABTEILUNGSLEITER:
                projects = current_user.projects.order_by(Project.name).all()
            else:
                projects = []
        else:
            projects = []
        return {'user_allowed_projects': projects}

    # Kontextprozessor für die Anzahl ausstehender zugewiesener Coachings (für Badge)
    @app.context_processor
    def inject_assigned_count():
        from app.roles import ROLE_ADMIN, ROLE_BETRIEBSLEITER, ROLE_PROJEKTLEITER
        if current_user.is_authenticated and current_user.role not in [ROLE_ADMIN, ROLE_BETRIEBSLEITER, ROLE_PROJEKTLEITER]:
            # Nur für Coaches (alle anderen Rollen, die coachen können)
            from app.models import AssignedCoaching
            count = AssignedCoaching.query.filter_by(coach_id=current_user.id, status='pending').count()
        else:
            count = 0
        return {'pending_assigned_count': count}

    # Benutzerdefinierter Jinja-Filter für Athener Zeit
    @app.template_filter('athens_time')
    def format_athens_time(utc_dt, fmt='%d.%m.%Y %H:%M'):
        if not utc_dt:
            return ""
        if not isinstance(utc_dt, datetime):
            if isinstance(utc_dt, str):
                try:
                    utc_dt = datetime.fromisoformat(utc_dt.replace('Z', '+00:00'))
                except ValueError:
                    try:
                        utc_dt = datetime.strptime(utc_dt, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                         return str(utc_dt)
            else:
                return str(utc_dt)

        if utc_dt.tzinfo is None or utc_dt.tzinfo.utcoffset(utc_dt) is None:
            utc_dt = utc_dt.replace(tzinfo=timezone.utc)
        
        athens_tz = pytz.timezone('Europe/Athens')
        try:
            local_dt = utc_dt.astimezone(athens_tz)
            return local_dt.strftime(fmt)
        except Exception as e:
            try:
                return utc_dt.strftime(fmt) + " (UTC?)" 
            except:
                return str(utc_dt)

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass
    
    print("<<<< VOR Import von app.models in create_app (__init__.py) >>>>")
    from app import models
    print("<<<< NACH Import von app.models in create_app (__init__.py) >>>>")

    print("<<<< create_app() FERTIG, app wird zurückgegeben (__init__.py) >>>>")
    return app

print("<<<< VOR globalem Import von app.models am Ende von __init__.py >>>>")
from app import models 
print("<<<< NACH globalem Import von app.models am Ende von __init__.py >>>>")

print("<<<< ENDE __init__.py wurde GELADEN >>>>")
