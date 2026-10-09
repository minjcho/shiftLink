from datetime import timedelta
from uuid import uuid4
import pytest
from sqlalchemy import select, insert, update, func, delete

from app.core.seed import seed, uid
from app.core import schema as s
from app.core.sessions import COOKIE_NAME

ORIGIN = {"Origin": "http://localhost:5173"}


def login(client, key="reporter"):
    return client.post("/api/v1/demo/session", json={"account_key": key}, headers=ORIGIN)


@pytest.mark.parametrize("key,user,role,shift,duty", [
    ("reporter",201,"worker",301,"OPERATOR"), ("maintainer",202,"worker",301,"MAINTENANCE"),
    ("outgoing_supervisor",203,"supervisor",301,"SUPERVISOR"),
    ("incoming_supervisor",204,"supervisor",302,"SUPERVISOR"),
])
def test_real_session_mapping(client, key, user, role, shift, duty):
    response = login(client,key)
    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    me = client.get("/api/v1/me").json()["data"]
    assert me["user_id"] == str(uid(user)) and me["role"] == role
    assert me["shift_occurrence_id"] == str(uid(shift)) and duty in me["duties"]
    assert len(client.get("/api/v1/equipment").json()["data"]["items"]) == 2
    shifts = client.get("/api/v1/shifts").json()["data"]
    assert len(shifts["items"]) == 2 and len(shifts["allowed_pairs"]) == 1


@pytest.mark.parametrize("headers", [{}, {"Origin":"https://evil.invalid"}, {"Origin":"http://localhost:5173.evil.invalid"}])
def test_session_requires_exact_origin(client, headers):
    response = client.post("/api/v1/demo/session", json={"account_key":"reporter"}, headers=headers)
    assert response.status_code == 403 and response.json()["error"]["code"] == "FORBIDDEN"


def test_forged_actor_and_cookie_rejected(client):
    response = client.post("/api/v1/demo/session", json={"account_key":"reporter","role":"supervisor"},headers=ORIGIN)
    assert response.status_code == 422 and response.json()["error"]["code"] == "VALIDATION_ERROR"
    client.cookies.set(COOKIE_NAME, "forged-supervisor-token")
    assert client.get("/api/v1/me").status_code == 401


def test_rotation_revokes_old_session_and_survives_app_restart(client, database, settings):
    from fastapi.testclient import TestClient
    from app.main import create_app
    login(client)
    old = client.cookies.get(COOKIE_NAME)
    login(client,"incoming_supervisor")
    new = client.cookies.get(COOKIE_NAME)
    assert old != new
    with TestClient(create_app(settings,database)) as restarted:
        restarted.cookies.set(COOKIE_NAME, old)
        assert restarted.get("/api/v1/me").status_code == 401
        restarted.cookies.set(COOKIE_NAME, new)
        assert restarted.get("/api/v1/me").json()["data"]["role"] == "supervisor"


@pytest.mark.parametrize("defect", ["expired", "disabled", "unassigned"])
def test_session_rechecks_server_state(client, database, defect):
    login(client)
    with database.begin() as c:
        if defect == "expired": c.execute(update(s.sessions).values(expires_at=func.now()-timedelta(seconds=1)))
        elif defect == "disabled": c.execute(update(s.users).where(s.users.c.id==uid(201)).values(enabled=False))
        else: c.execute(delete(s.shift_assignments).where(s.shift_assignments.c.user_id==uid(201)))
    assert client.get("/api/v1/me").status_code in (401,403)


def test_reads_enforce_site_and_seed_is_repeatable(client, database):
    with database.begin() as c:
        seed(c)
        other_site = uuid4()
        c.execute(insert(s.sites).values(id=other_site,name="other site"))
        c.execute(insert(s.equipment).values(id=uuid4(),site_id=other_site,code="OTHER",label="hidden",aliases=[],default_maintainer_id=uid(202)))
    login(client)
    assert len(client.get("/api/v1/equipment").json()["data"]["items"]) == 2
    with database.connect() as c:
        assert c.scalar(select(func.count()).select_from(s.users)) == 4
        assert c.scalar(select(func.count()).select_from(s.incidents)) == 0


def test_disabled_demo_and_errors(client,database,settings):
    from fastapi.testclient import TestClient
    from app.main import create_app
    with TestClient(create_app(settings.model_copy(update={"demo_account_switch_enabled":False}),database)) as disabled:
        assert login(disabled).status_code == 404
    assert client.get("/api/v1/me").json()["error"]["code"] == "UNAUTHENTICATED"
    response = client.get("/does-not-exist")
    assert response.status_code == 404 and response.json()["meta"]["request_id"]
