"""Completely fresh initial schema

Revision ID: faa9dfab0205
Revises: 
Create Date: 2025-05-29 01:12:28.440891 # Dein Zeitstempel

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'faa9dfab0205' # DEIN AKTUELLER HASH
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands MANUELL KORRIGIERT ###
    
    # 1. Users zuerst erstellen
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(length=64), nullable=False),
    sa.Column('email', sa.String(length=120), nullable=False),
    sa.Column('password_hash', sa.String(length=256), nullable=True),
    sa.Column('role', sa.String(length=20), nullable=False),
    # Die Spalte team_id_if_leader wird erstellt, ABER OHNE den ForeignKey Constraint hier,
    # da 'teams' noch nicht existiert. Der FK wird später hinzugefügt, falls nötig,
    # oder die Beziehung wird nur über Team.team_leader_id + App-Logik gehandhabt.
    sa.Column('team_id_if_leader', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=True)
        batch_op.create_index(batch_op.f('ix_users_username'), ['username'], unique=True)

    # 2. Teams erstellen (kann jetzt users.id referenzieren)
    op.create_table('teams',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('team_leader_id', sa.Integer(), nullable=True),
    # Dieser ForeignKeyConstraint ist jetzt sicher, da 'users' existiert.
    sa.ForeignKeyConstraint(['team_leader_id'], ['users.id'], name='fk_team_team_leader_id'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )

    # 3. (Optional, aber sauberer) Den ForeignKey für users.team_id_if_leader JETZT hinzufügen,
    #    da 'teams' nun existiert. Dies war der FK, den Alembic im User-Block haben wollte.
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_foreign_key(
            'fk_user_team_id_if_leader', # Name des Constraints (kannst du auch weglassen, dann generiert Alembic einen)
            'teams', # Referenzierte Tabelle
            ['team_id_if_leader'], # Lokale Spalte(n)
            ['id'] # Remote Spalte(n)
        )

    # 4. TeamMembers erstellen (hängt von teams ab)
    op.create_table('team_members',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('team_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['team_id'], ['teams.id'], name='fk_teammember_team_id'),
    sa.PrimaryKeyConstraint('id')
    )

    # 5. Coachings erstellen (hängt von users und team_members ab)
    op.create_table('coachings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('team_member_id', sa.Integer(), nullable=False),
    sa.Column('coach_id', sa.Integer(), nullable=False),
    sa.Column('coaching_date', sa.DateTime(), nullable=False),
    sa.Column('coaching_style', sa.String(length=50), nullable=True),
    sa.Column('tcap_id', sa.String(length=50), nullable=True),
    sa.Column('leitfaden_begruessung', sa.String(length=10), nullable=True),
    sa.Column('leitfaden_legitimation', sa.String(length=10), nullable=True),
    sa.Column('leitfaden_pka', sa.String(length=10), nullable=True),
    sa.Column('leitfaden_kek', sa.String(length=10), nullable=True),
    sa.Column('leitfaden_angebot', sa.String(length=10), nullable=True),
    sa.Column('leitfaden_zusammenfassung', sa.String(length=10), nullable=True),
    sa.Column('leitfaden_kzb', sa.String(length=10), nullable=True),
    sa.Column('performance_mark', sa.Integer(), nullable=True),
    sa.Column('time_spent', sa.Integer(), nullable=True),
    sa.Column('project_leader_notes', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['coach_id'], ['users.id'], name='fk_coaching_coach_id'),
    sa.ForeignKeyConstraint(['team_member_id'], ['team_members.id'], name='fk_coaching_team_member_id'),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands MANUELL KORRIGIERT (umgekehrte Reihenfolge) ###
    op.drop_table('coachings')
    op.drop_table('team_members')
    
    # Zuerst den nachträglich hinzugefügten FK von users zu teams droppen
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_constraint('fk_user_team_id_if_leader', type_='foreignkey') # Name muss stimmen

    op.drop_table('teams') 
    
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_username'))
        batch_op.drop_index(batch_op.f('ix_users_email'))
    op.drop_table('users')
    # ### end Alembic commands ###