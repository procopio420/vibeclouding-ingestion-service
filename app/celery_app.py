try:
    from celery import Celery
except Exception:  # pragma: no cover
    class Celery:  # minimal stub for environments where Celery isn't installed yet
        def __init__(self, *a, **k):
            pass
import os


def make_celery_app() -> Celery:
    broker = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")
    backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/0")

    app = Celery("vibecloud", broker=broker, backend=backend)

    # Ensure the repo_ingest queue exists and tasks route to it
    try:
        from kombu import Queue
    except Exception:  # pragma: no cover
        class Queue:  # type: ignore
            def __init__(self, *a, **k):
                pass
    app.conf.update(
        task_queues=(Queue("repo_ingest", routing_key="repo_ingest"),),
        task_routes={"repo_ingest_worker": {"queue": "repo_ingest", "routing_key": "repo_ingest"}},
        accept_content=["json"],
        task_serializer="json",
        result_serializer="json",
        broker_transport_options={"visibility_timeout": 3600},
        enable_utc=True,
        worker_prefetch_multiplier=1,
    )

    return app


celery_app = make_celery_app()


# Task definitions - defined here to avoid circular imports
@celery_app.task(bind=True, name="repo_ingest_worker")
def repo_ingest_worker(self, job_id: str, project_id: str, repo_url: str, reference: str = "main"):
    """Robust repo_ingest_worker with bounded DB usage and safe session handling."""
    import json
    import subprocess
    import tempfile
    import uuid
    from datetime import datetime

    from app.db import get_session, init_db, ProjectModel, JobModel, ArtifactModel
    from app.pipelines.repo_pipeline import extract_repo_signals
    from app.pipelines.graph_pipeline import generate_graph_artifacts
    from app.adapters import get_storage_adapter
    from app.serializers.markdown_serializer import render_all
    from app.core.instrumentation import get_logger, log_event

    storage = get_storage_adapter()
    logger = get_logger(__name__)

    init_db()
    session = get_session()
    job = session.query(JobModel).filter(JobModel.id == job_id).first()
    if not job:
        job = JobModel(
            id=job_id,
            project_id=project_id,
            job_type="repo_ingest",
            status="queued",
            payload=json.dumps({"repo_url": repo_url, "reference": reference}),
            created_at=datetime.utcnow(),
        )
        session.add(job)
        session.commit()
    if job.status != "running":
        job.status = "running"
        job.started_at = datetime.utcnow()
        session.commit()

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            clone_cmd = ["git", "clone", "--depth", "1", repo_url, tmpdir]
            subprocess.run(clone_cmd, check=True, timeout=300)
            repo_path = tmpdir

            signals = extract_repo_signals(repo_path, repo_url)
            context = signals

            md_artifacts = render_all(context)
            artifacts_index = []
            for fname, content in md_artifacts.items():
                path = f"{project_id}/output/markdown/{fname}"
                full = storage.store(path, content)
                artifacts_index.append(fname)
                art = ArtifactModel(id=str(uuid.uuid4()), project_id=project_id, name=fname, path=full, type="markdown", created_at=datetime.utcnow())
                session.add(art)
            session.commit()

            graph_artifacts = generate_graph_artifacts(context)
            for fname, content in graph_artifacts.items():
                path = f"{project_id}/output/graphs/{fname}"
                if isinstance(content, (dict, list)):
                    content_bytes = json.dumps(content, indent=2).encode('utf-8')
                else:
                    content_bytes = str(content).encode('utf-8')
                full = storage.store(path, content_bytes)
                artifacts_index.append(fname)
                art = ArtifactModel(id=str(uuid.uuid4()), project_id=project_id, name=fname, path=full, type="graph", created_at=datetime.utcnow())
                session.add(art)
            session.commit()

            context_path = f"{project_id}/output/context.json"
            storage.store(context_path, json.dumps(context, indent=2))

            from app.services.context_aggregator import build_consolidated_context, persist_consolidated
            consolidated = build_consolidated_context(context, graph_artifacts, artifacts_index)
            persist_consolidated(project_id, consolidated)

            from app.services.webhook_sender import send_context_generated_webhook
            send_context_generated_webhook(project_id)

            status_before = job.status
            job.status = "completed"
            job.completed_at = datetime.utcnow()
            session.commit()
            session.close()
            log_event(logger, "repo_ingest_completed", {"job_id": job_id, "project_id": project_id, "status_before": status_before, "artifacts": artifacts_index})
            return {
                "job_id": job_id,
                "project_id": project_id,
                "status": job.status,
                "artifacts": artifacts_index,
            }
    except Exception as e:
        try:
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            session.commit()
        finally:
            session.close()
        log_event(logger, "repo_ingest_failed", {"job_id": job_id, "project_id": project_id, "error": str(e)})
        raise
