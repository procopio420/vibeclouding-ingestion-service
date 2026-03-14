import os
import subprocess


def test_alembic_upgrade_head_smoke():
    # Run alembic upgrade head against the Postgres instance in docker-compose
    repo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    env = os.environ.copy()
    env["DATABASE_URL"] = env.get("DATABASE_URL", "postgresql://vibe:vibe@db:5432/vibe_context")
    # Run upgrade in the ingestor dir so alembic.ini is found
    cwd = os.path.join(repo_dir, "../")
    # Try from the ingestor root; ensure alembic.ini exists at ingestor/alembic.ini
    if not os.path.exists(os.path.join(repo_dir, "alembic.ini")):
        # fallback to repository root if needed
        cwd = os.path.join(repo_dir, "ingestor")
    result = subprocess.run(["alembic", "upgrade", "head"], cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    assert result.returncode == 0, result.stdout
