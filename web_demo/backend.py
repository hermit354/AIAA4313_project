"""FastAPI + SQLite web demo backed by the formal Hiring Agent pipeline."""

from __future__ import annotations

import hashlib
import json
import re
import secrets
import sqlite3
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from evaluation_service import FORMAL_PROMPT_VERSION
from prompt import DEFAULT_MODEL
from web_demo.pipeline import (
    PipelineConfig,
    provider_for,
    provider_registry,
    run_resume_pipeline,
)

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
UPLOADS = DATA / "uploads"
ARTIFACTS = DATA / "artifacts"
DB = DATA / "hiring_agent.db"
TOKENS: dict[str, dict] = {}
WORKER = ThreadPoolExecutor(max_workers=1)
STAGE_NAMES = [
    "PDF_TEXT_EXTRACTION",
    "RESUME_SECTION_PARSE",
    "GITHUB_ENRICHMENT",
    "EVALUATION",
    "RANK_AND_PERSIST",
]

app = FastAPI(title="Hiring Agent Local Demo", version="2.0.0")


def stamp() -> float:
    return time.time()


def db() -> sqlite3.Connection:
    DATA.mkdir(exist_ok=True)
    UPLOADS.mkdir(exist_ok=True)
    ARTIFACTS.mkdir(exist_ok=True)
    connection = sqlite3.connect(DB)
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """create table if not exists users(
             email text primary key,name text,role text,password text,is_demo integer);
           create table if not exists applications(
             id text primary key,email text,filename text,stored_path text,sha256 text,
             status text,created real,score real,base real,bonus real,deduction real,
             resume_json text,evidence_json text,is_demo integer);
           create table if not exists evaluation_runs(
             id text primary key,application_id text,provider text,model_id text,
             status text,created real,completed real,score real,config_json text,
             config_fingerprint text,reused_from text,error text,
             core_score real,bonus real,deduction real,categories_json text,
             evidence_json text,resume_json text,github_json text,
             evaluation_engine text,prompt_version text,schema_mode text,
             artifact_path text);
           create table if not exists stage_runs(
             id text primary key,run_id text,name text,status text,duration_ms integer,
             note text,artifact_path text);
           create table if not exists app_settings(key text primary key,value text);"""
    )
    application_columns = [
        ("stored_path", "text"),
        ("base", "real"),
        ("bonus", "real"),
        ("deduction", "real"),
        ("resume_json", "text"),
        ("evidence_json", "text"),
        ("is_demo", "integer"),
    ]
    run_columns = [
        ("core_score", "real"),
        ("bonus", "real"),
        ("deduction", "real"),
        ("categories_json", "text"),
        ("evidence_json", "text"),
        ("resume_json", "text"),
        ("github_json", "text"),
        ("evaluation_engine", "text"),
        ("prompt_version", "text"),
        ("schema_mode", "text"),
        ("artifact_path", "text"),
    ]
    for table, columns in (
        ("applications", application_columns),
        ("evaluation_runs", run_columns),
    ):
        for column, sql_type in columns:
            try:
                connection.execute(
                    f"alter table {table} add column {column} {sql_type}"
                )
            except sqlite3.OperationalError:
                pass
    try:
        connection.execute("alter table users add column is_demo integer")
    except sqlite3.OperationalError:
        pass
    connection.commit()
    return connection


def rowdict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row else None


def _json(value: str | None, default):
    try:
        return json.loads(value) if value else default
    except json.JSONDecodeError:
        return default


def candidate_identifier(filename: str | None) -> str | None:
    """Return the stable anonymized candidate number embedded in a PDF name."""
    stem = Path(filename or "").stem
    match = re.search(r"(?<!\d)(\d{4,})(?!\d)", stem)
    return match.group(1) if match else None


def run_view(row: sqlite3.Row) -> dict:
    value = rowdict(row)
    value["categories"] = _json(value.pop("categories_json", None), {})
    value["evidence"] = _json(value.pop("evidence_json", None), {})
    value["resume"] = _json(value.pop("resume_json", None), {})
    value["github_data"] = _json(value.pop("github_json", None), None)
    value["config"] = _json(value.pop("config_json", None), {})
    return value


def app_view(row: sqlite3.Row, connection: sqlite3.Connection) -> dict:
    value = rowdict(row)
    value["candidate_identifier"] = candidate_identifier(value.get("filename"))
    value["resume"] = _json(value.pop("resume_json", None), {})
    value["evidence"] = _json(value.pop("evidence_json", None), {})
    value["runs"] = []
    for run in connection.execute(
        "select * from evaluation_runs where application_id=? order by created desc",
        (value["id"],),
    ):
        rendered = run_view(run)
        rendered["stages"] = [
            rowdict(stage)
            for stage in connection.execute(
                "select * from stage_runs where run_id=? order by rowid",
                (rendered["id"],),
            )
        ]
        value["runs"].append(rendered)
    return value


def _default_model() -> str:
    models = provider_registry()
    healthy = [model["id"] for model in models if model["healthy"]]
    if DEFAULT_MODEL in healthy:
        return DEFAULT_MODEL
    return healthy[0] if healthy else DEFAULT_MODEL


def seed(reset: bool = False) -> None:
    connection = db()
    if reset:
        demo_ids = [
            row[0]
            for row in connection.execute("select id from applications where is_demo=1")
        ]
        for application_id in demo_ids:
            run_ids = [
                row[0]
                for row in connection.execute(
                    "select id from evaluation_runs where application_id=?",
                    (application_id,),
                )
            ]
            for run_id in run_ids:
                connection.execute("delete from stage_runs where run_id=?", (run_id,))
            connection.execute(
                "delete from evaluation_runs where application_id=?",
                (application_id,),
            )
        connection.execute("delete from applications where is_demo=1")
    connection.execute(
        "insert or ignore into users values(?,?,?,?,?)",
        ("staff@demo.local", "Research Staff", "staff", "demo123", 1),
    )
    connection.execute(
        "insert or ignore into users values(?,?,?,?,?)",
        ("alice@demo.local", "Alice Chen", "candidate", "demo123", 1),
    )
    current = connection.execute(
        "select value from app_settings where key='default_model'"
    ).fetchone()
    valid_ids = {model["id"] for model in provider_registry()}
    if not current or current["value"] not in valid_ids:
        connection.execute(
            "insert or replace into app_settings values('default_model',?)",
            (_default_model(),),
        )
    connection.commit()
    connection.close()


def user(
    authorization: Annotated[str | None, Header()] = None,
) -> dict:
    token = (authorization or "").removeprefix("Bearer ")
    if token not in TOKENS:
        raise HTTPException(401, "Sign in required")
    return TOKENS[token]


def staff(current=Depends(user)) -> dict:
    if current["role"] != "staff":
        raise HTTPException(403, "Staff access required")
    return current


class Login(BaseModel):
    email: str
    password: str


class RunRequest(BaseModel):
    model: str = DEFAULT_MODEL
    temperature: float = Field(default=0.1, ge=0, le=2)
    topP: float = Field(default=0.9, ge=0, le=1)
    prompt: Literal[FORMAL_PROMPT_VERSION] = FORMAL_PROMPT_VERSION
    cache: Literal["SAFE_REUSE", "FORCE_FRESH"] = "SAFE_REUSE"
    github: bool = True


class Setting(BaseModel):
    model_id: str


@app.on_event("startup")
def start() -> None:
    connection = db()
    connection.execute(
        "update evaluation_runs set status='FAILED_STALE',"
        "completed=?,error='Recovered at server startup' "
        "where status in ('RUNNING','QUEUED')",
        (stamp(),),
    )
    connection.execute(
        "update applications set status='FAILED' where id in ("
        "select application_id from evaluation_runs where status='FAILED_STALE')"
    )
    connection.commit()
    connection.close()
    seed()


@app.get("/")
def page():
    return FileResponse(
        ROOT / "templates" / "hiring_agent_glass_editorial_template.html"
    )


@app.get("/health")
def health():
    return {"ok": True, "db_writable": DATA.exists(), "models": provider_registry()}


@app.post("/api/auth/login")
def login(payload: Login):
    connection = db()
    row = connection.execute(
        "select email,name,role,password from users where email=?",
        (payload.email.lower(),),
    ).fetchone()
    connection.close()
    if not row or row["password"] != payload.password:
        raise HTTPException(401, "Invalid email or password")
    token = secrets.token_urlsafe(32)
    TOKENS[token] = {
        "email": row["email"],
        "name": row["name"],
        "role": row["role"],
    }
    return {"token": token, "user": TOKENS[token]}


@app.get("/api/me")
def me(current=Depends(user)):
    return current


@app.get("/api/candidate/application")
def candidate_application(current=Depends(user)):
    if current["role"] != "candidate":
        raise HTTPException(403, "Candidate access required")
    connection = db()
    row = connection.execute(
        "select id,filename,status,created from applications "
        "where email=? order by created desc limit 1",
        (current["email"],),
    ).fetchone()
    connection.close()
    return {"application": rowdict(row)}


@app.get("/api/staff/applications")
def applications(current=Depends(staff)):
    connection = db()
    result = [
        app_view(row, connection)
        for row in connection.execute(
            "select * from applications order by score desc nulls last,created desc"
        )
    ]
    connection.close()
    return result


@app.get("/api/staff/applications/{application_id}")
def detail(application_id: str, current=Depends(staff)):
    connection = db()
    row = connection.execute(
        "select * from applications where id=?", (application_id,)
    ).fetchone()
    if not row:
        connection.close()
        raise HTTPException(404, "Application not found")
    result = app_view(row, connection)
    connection.close()
    return result


@app.get("/api/staff/runs/{run_id}")
def run_detail(run_id: str, current=Depends(staff)):
    connection = db()
    row = connection.execute(
        "select * from evaluation_runs where id=?", (run_id,)
    ).fetchone()
    if not row:
        connection.close()
        raise HTTPException(404, "Run not found")
    result = run_view(row)
    result["stages"] = [
        rowdict(stage)
        for stage in connection.execute(
            "select * from stage_runs where run_id=? order by rowid", (run_id,)
        )
    ]
    connection.close()
    return result


@app.get("/api/staff/runs/{run_id}/stages")
def stages(run_id: str, current=Depends(staff)):
    connection = db()
    result = [
        rowdict(row)
        for row in connection.execute(
            "select * from stage_runs where run_id=? order by rowid", (run_id,)
        )
    ]
    connection.close()
    return result


@app.get("/api/staff/runs/{run_id}/artifact")
def run_artifact(run_id: str, current=Depends(staff)):
    connection = db()
    row = connection.execute(
        "select artifact_path from evaluation_runs where id=?", (run_id,)
    ).fetchone()
    connection.close()
    if not row or not row["artifact_path"]:
        raise HTTPException(404, "Run artifact unavailable")
    path = Path(row["artifact_path"])
    if not path.exists():
        raise HTTPException(404, "Run artifact unavailable")
    return FileResponse(path, media_type="application/json", filename=run_id + ".json")


@app.get("/api/staff/models")
def models(current=Depends(staff)):
    connection = db()
    row = connection.execute(
        "select value from app_settings where key='default_model'"
    ).fetchone()
    connection.close()
    return {
        "default_model": row["value"] if row else _default_model(),
        "models": provider_registry(),
        "prompt_version": FORMAL_PROMPT_VERSION,
    }


def queue_stages(connection: sqlite3.Connection, run_id: str) -> None:
    for name in STAGE_NAMES:
        connection.execute(
            "insert into stage_runs values(?,?,?,?,?,?,?)",
            (
                uuid.uuid4().hex,
                run_id,
                name,
                "QUEUED",
                0,
                "Waiting for formal evaluation worker",
                None,
            ),
        )


def enqueue(
    application_id: str, run_id: str, path: str | Path, config: PipelineConfig
) -> None:
    WORKER.submit(execute_run, application_id, run_id, path, config)


def execute_run(
    application_id: str, run_id: str, path: str | Path, config: PipelineConfig
) -> None:
    connection = db()
    connection.execute(
        "update evaluation_runs set status='RUNNING' where id=?", (run_id,)
    )
    connection.execute(
        "update stage_runs set status='RUNNING',note='Formal worker started' "
        "where run_id=? and name='PDF_TEXT_EXTRACTION'",
        (run_id,),
    )
    connection.commit()
    try:
        result = run_resume_pipeline(path, config)
        artifact = ARTIFACTS / (run_id + ".json")
        artifact.write_text(
            json.dumps(result.to_json(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        connection.execute(
            """update evaluation_runs set
               status=?,completed=?,score=?,core_score=?,bonus=?,deduction=?,
               categories_json=?,evidence_json=?,resume_json=?,github_json=?,
               evaluation_engine=?,prompt_version=?,schema_mode=?,artifact_path=?
               where id=?""",
            (
                result.status,
                stamp(),
                result.score,
                result.base,
                result.bonus,
                result.deduction,
                json.dumps(result.categories, ensure_ascii=False),
                json.dumps(result.evidence, ensure_ascii=False),
                json.dumps(result.resume, ensure_ascii=False),
                json.dumps(result.github_data, ensure_ascii=False),
                result.evaluation_engine,
                result.config.prompt_version,
                result.config.extraction_schema_mode,
                str(artifact),
                run_id,
            ),
        )
        connection.execute(
            """update applications set
               status=?,score=?,base=?,bonus=?,deduction=?,resume_json=?,evidence_json=?
               where id=?""",
            (
                "UNDER_REVIEW",
                result.score,
                result.base,
                result.bonus,
                result.deduction,
                json.dumps(result.resume, ensure_ascii=False),
                json.dumps(result.evidence, ensure_ascii=False),
                application_id,
            ),
        )
        for stage in result.stages:
            connection.execute(
                """update stage_runs set status=?,duration_ms=?,note=?,artifact_path=?
                   where run_id=? and name=?""",
                (
                    stage.status,
                    stage.duration_ms,
                    stage.note,
                    str(artifact),
                    run_id,
                    stage.name,
                ),
            )
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        for stage in getattr(exc, "stages", []):
            connection.execute(
                """update stage_runs set status=?,duration_ms=?,note=?
                   where run_id=? and name=?""",
                (
                    stage.status,
                    stage.duration_ms,
                    stage.note,
                    run_id,
                    stage.name,
                ),
            )
        connection.execute(
            "update evaluation_runs set status='FAILED',completed=?,error=?,"
            "evaluation_engine='formal_resume_evaluator' where id=?",
            (stamp(), message, run_id),
        )
        connection.execute(
            "update stage_runs set status='FAILED',note=? "
            "where run_id=? and status='RUNNING'",
            (message, run_id),
        )
        connection.execute(
            "update stage_runs set status='SKIPPED',note='Not reached after failure' "
            "where run_id=? and status='QUEUED'",
            (run_id,),
        )
        connection.execute(
            "update applications set status='FAILED' where id=?", (application_id,)
        )
    connection.commit()
    connection.close()


def _insert_run(
    connection: sqlite3.Connection,
    application_id: str,
    run_id: str,
    config: PipelineConfig,
) -> None:
    connection.execute(
        """insert into evaluation_runs(
           id,application_id,provider,model_id,status,created,completed,score,
           config_json,config_fingerprint,reused_from,error,prompt_version,schema_mode,
           evaluation_engine)
           values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            run_id,
            application_id,
            config.provider,
            config.model_id,
            "QUEUED",
            stamp(),
            None,
            None,
            json.dumps(config.__dict__),
            config.fingerprint(),
            None,
            None,
            config.prompt_version,
            config.extraction_schema_mode,
            "formal_resume_evaluator",
        ),
    )
    queue_stages(connection, run_id)


@app.post("/api/candidate/resume")
async def upload(file: UploadFile = File(...), current=Depends(user)):
    if current["role"] != "candidate":
        raise HTTPException(403, "Candidate access required")
    if file.content_type not in {"application/pdf", "application/x-pdf"} or not (
        file.filename or ""
    ).lower().endswith(".pdf"):
        raise HTTPException(415, "Only PDF resumes are accepted")
    raw = await file.read()
    if not raw or len(raw) > 10 * 1024 * 1024 or not raw.startswith(b"%PDF"):
        raise HTTPException(400, "Invalid, empty, or oversized PDF")

    sha = hashlib.sha256(raw).hexdigest()
    stored = UPLOADS / (uuid.uuid4().hex + ".pdf")
    stored.write_bytes(raw)
    application_id = "app-" + uuid.uuid4().hex[:10]
    run_id = "run-" + uuid.uuid4().hex[:10]
    connection = db()
    row = connection.execute(
        "select value from app_settings where key='default_model'"
    ).fetchone()
    model_id = row["value"] if row else _default_model()
    config = PipelineConfig(provider=provider_for(model_id), model_id=model_id)
    connection.execute(
        """insert into applications(
           id,email,filename,stored_path,sha256,status,created,score,base,bonus,
           deduction,resume_json,evidence_json,is_demo)
           values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            application_id,
            current["email"],
            file.filename,
            str(stored),
            sha,
            "PROCESSING",
            stamp(),
            None,
            None,
            None,
            None,
            None,
            None,
            0,
        ),
    )
    _insert_run(connection, application_id, run_id, config)
    connection.commit()
    connection.close()
    enqueue(application_id, run_id, stored, config)
    return {
        "application_id": application_id,
        "run_id": run_id,
        "name": file.filename,
        "size": len(raw),
        "sha256": sha,
    }


@app.post("/api/staff/applications/{application_id}/rerun")
def rerun(application_id: str, payload: RunRequest, current=Depends(staff)):
    available = {model["id"] for model in provider_registry() if model["healthy"]}
    if payload.model not in available:
        raise HTTPException(400, "Model is not available for the formal pipeline")
    connection = db()
    application = connection.execute(
        "select * from applications where id=?", (application_id,)
    ).fetchone()
    if not application:
        connection.close()
        raise HTTPException(404, "Application not found")
    config = PipelineConfig(
        provider=provider_for(payload.model),
        model_id=payload.model,
        temperature=payload.temperature,
        top_p=payload.topP,
        prompt_version=payload.prompt,
        github_enrichment=payload.github,
        force_fresh=payload.cache == "FORCE_FRESH",
    )
    if not config.force_fresh:
        old = connection.execute(
            "select id from evaluation_runs where application_id=? "
            "and config_fingerprint=? and status='COMPLETED'",
            (application_id, config.fingerprint()),
        ).fetchone()
        if old:
            connection.close()
            return {"id": old["id"], "status": "COMPLETED", "reused": True}
    if not application["stored_path"]:
        connection.close()
        raise HTTPException(409, "Application has no source PDF")
    run_id = "run-" + uuid.uuid4().hex[:10]
    _insert_run(connection, application_id, run_id, config)
    connection.commit()
    connection.close()
    enqueue(application_id, run_id, application["stored_path"], config)
    return {"id": run_id, "status": "QUEUED", "reused": False}


@app.patch("/api/staff/settings/default-model")
def model(payload: Setting, current=Depends(staff)):
    available = {model["id"] for model in provider_registry() if model["healthy"]}
    if payload.model_id not in available:
        raise HTTPException(400, "Model is not available for the formal pipeline")
    connection = db()
    connection.execute(
        "insert or replace into app_settings values('default_model',?)",
        (payload.model_id,),
    )
    connection.commit()
    connection.close()
    return payload


@app.get("/api/staff/applications/{application_id}/pdf")
def pdf(application_id: str, current=Depends(staff)):
    connection = db()
    row = connection.execute(
        "select stored_path,filename from applications where id=?", (application_id,)
    ).fetchone()
    connection.close()
    if not row or not row["stored_path"] or not Path(row["stored_path"]).exists():
        raise HTTPException(404, "PDF artifact unavailable")
    return FileResponse(
        row["stored_path"], media_type="application/pdf", filename=row["filename"]
    )


@app.post("/api/demo/reset")
def reset(current=Depends(staff)):
    seed(True)
    return {"ok": True}
