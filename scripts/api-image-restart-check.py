"""Validate image-job persistence across two real API processes."""

from __future__ import annotations

import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
DB_URL = os.environ.get(
    "VAYUJIT_TEST_DATABASE_URL",
    "postgresql+psycopg://vayujit:vayujit_dev@127.0.0.1:5432/vayujit_test",
)
BASE_URL = "http://127.0.0.1:18080"
ORIGIN = "http://127.0.0.1:4200"

sys.path.insert(0, str(API_ROOT))
from vayujit_api.ai.image_models import AIImageOutput
from vayujit_api.ai.studio_models import AIStudioJob
from vayujit_api.ai.studio_worker import run_ai_jobs_once
from vayujit_api.core.database import Base
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.main import create_app  # noqa: F401


def wait_for_api(process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f"API exited during startup with code {process.returncode}"
            )
        try:
            response = httpx.get(f"{BASE_URL}/api/v1/health", timeout=1)
            if response.status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.25)
    raise TimeoutError("API did not become healthy")


def start_api() -> subprocess.Popen[bytes]:
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(API_ROOT),
            "VAYUJIT_ENV": "test",
            "VAYUJIT_ENVIRONMENT": "test",
            "VAYUJIT_DATABASE_URL": DB_URL,
            "VAYUJIT_TEST_DATABASE_URL": DB_URL,
            "VAYUJIT_API_PORT": "18080",
        }
    )
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "vayujit_api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "18080",
        ],
        cwd=API_ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    wait_for_api(process)
    return process


def counts(
    factory: sessionmaker[Session], job_id: str, output_id: str
) -> tuple[int, int, int]:
    with factory() as db:
        return (
            db.scalar(
                select(func.count())
                .select_from(AIStudioJob)
                .where(AIStudioJob.id == job_id)
            )
            or 0,
            db.scalar(
                select(func.count())
                .select_from(AIImageOutput)
                .where(AIImageOutput.id == output_id)
            )
            or 0,
            db.scalar(select(func.count()).select_from(AIImageOutput)) or 0,
        )


def main() -> None:
    engine = create_engine(DB_URL)
    reset_test_schema(engine, Base.metadata, database_url=DB_URL)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    first: subprocess.Popen[bytes] | None = None
    second: subprocess.Popen[bytes] | None = None
    try:
        session_cookies = httpx.Cookies()
        first = start_api()
        with httpx.Client(base_url=BASE_URL, headers={"Origin": ORIGIN}) as client:
            setup = client.post(
                "/api/v1/auth/setup-owner",
                json={
                    "full_name": "Restart Owner",
                    "email": "restart-image@example.com",
                    "password": "correct horse battery staple",
                    "password_confirmation": "correct horse battery staple",
                },
            )
            assert setup.status_code == 201, setup.text
            brand = client.post("/api/v1/brands", json={"name": "Restart Brand"})
            assert brand.status_code == 201, brand.text
            product = client.post(
                "/api/v1/products",
                json={
                    "name": "Restart Product",
                    "product_type": "physical",
                    "description": "Restart-safe product",
                    "category": "Home",
                    "price_amount": "20.00",
                    "price_currency": "USD",
                },
            )
            assert product.status_code == 201, product.text
            product_id = product.json()["id"]
            activated = client.post(f"/api/v1/products/{product_id}/activate")
            assert activated.status_code == 200, activated.text
            queued = client.post(
                "/api/v1/ai/images/generate",
                json={
                    "brand_id": brand.json()["id"],
                    "product_id": product_id,
                    "operation": "generate_product_image",
                    "width": 64,
                    "height": 64,
                    "idempotency_key": f"restart-{uuid.uuid4().hex}",
                },
            )
            assert queued.status_code == 202, queued.text
            body = queued.json()
            generation_id = body["generation_id"]
            job_id = body["outputs"][0]["job_id"]
            output_id = body["outputs"][0]["id"]
            before = counts(factory, job_id, output_id)
            assert before[:2] == (1, 1)
            session_cookies.update(client.cookies)
        first.terminate()
        first.wait(timeout=15)
        first = None
        try:
            httpx.get(f"{BASE_URL}/api/v1/health", timeout=1)
        except httpx.HTTPError:
            pass
        else:
            raise AssertionError("API remained reachable after stop")
        second = start_api()
        with httpx.Client(
            base_url=BASE_URL, headers={"Origin": ORIGIN}, cookies=session_cookies
        ) as client:
            assert client.get("/api/v1/health").status_code == 200
            generation = client.get(f"/api/v1/ai/images/generations/{generation_id}")
            assert generation.status_code == 200, generation.text
            assert generation.json()["generation_id"] == generation_id
            with factory() as db:
                assert run_ai_jobs_once(db, "restart-worker", limit=10) == 1
            output = client.get(f"/api/v1/ai/images/outputs/{output_id}")
            assert output.status_code == 200, output.text
            assert output.json()["id"] == output_id
            assert output.json()["job_id"] == job_id
        after = counts(factory, job_id, output_id)
        assert after[:2] == before[:2]
        assert after[2] == 1
        print("API restart: PASS")
        print(f"generation_id={generation_id} job_id={job_id} output_id={output_id}")
        print(f"rows_before={before} rows_after={after}")
    finally:
        for process in (first, second):
            if process is not None and process.poll() is None:
                process.terminate()
                process.wait(timeout=15)
        reset_test_schema(engine, Base.metadata, database_url=DB_URL)
        engine.dispose()


if __name__ == "__main__":
    main()
