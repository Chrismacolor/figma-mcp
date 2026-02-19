import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from server import auth
from server.http_routes import init_routes
from server.job_queue import JobQueue

TEST_TOKEN = "test-token"


@pytest.fixture()
def queue():
    return JobQueue()


@pytest.fixture()
def app(queue):
    auth._auth_token = TEST_TOKEN
    application = FastAPI()
    application.include_router(init_routes(queue))
    return application


@pytest.fixture()
def client(app):
    return TestClient(app)


@pytest.fixture()
def auth_headers():
    return {"Authorization": f"Bearer {TEST_TOKEN}"}
