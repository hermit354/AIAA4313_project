"""initial local-demo schema

Revision ID: 0001_local_demo_schema
"""
from alembic import op

revision = '0001_local_demo_schema'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # SQLite IF NOT EXISTS makes this safe for the prototype database created
    # before migrations were introduced; fresh databases get the same schema.
    for sql in [
      'create table if not exists users(email text primary key,name text,role text,password text,is_demo integer)',
      'create table if not exists applications(id text primary key,email text,filename text,stored_path text,sha256 text,status text,created real,score real,base real,bonus real,deduction real,resume_json text,evidence_json text,is_demo integer)',
      'create table if not exists evaluation_runs(id text primary key,application_id text,provider text,model_id text,status text,created real,completed real,score real,config_json text,config_fingerprint text,reused_from text,error text)',
      'create table if not exists stage_runs(id text primary key,run_id text,name text,status text,duration_ms integer,note text,artifact_path text)',
      'create table if not exists app_settings(key text primary key,value text)',
    ]: op.execute(sql)

def downgrade():
    for table in ['stage_runs','evaluation_runs','applications','app_settings','users']: op.execute(f'drop table if exists {table}')
