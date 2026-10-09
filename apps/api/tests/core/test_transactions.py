from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4
import pytest
from sqlalchemy import insert, select, func
from app.core import schema as s
from app.core.contracts import Principal
from app.core.database import transaction
from app.core.errors import DomainError
from app.core.receipts import fingerprint, reserve_command, finish_command, ReceiptResponse
from app.core.seed import uid

PRINCIPAL = Principal(user_id=uid(203),site_id=uid(1),role="supervisor")


def incident(database):
    id = uuid4()
    with database.begin() as c:
        c.execute(insert(s.incidents).values(id=id,display_id=str(id),site_id=uid(1),equipment_id=uid(103),reporter_id=uid(201),owner_id=uid(203),origin_shift_occurrence_id=uid(301),owner_shift_occurrence_id=uid(301),status="INVESTIGATING"))
    return id


def test_exact_replay_conflict_and_rollback(database):
    id = incident(database)
    key, fp = "test-command",fingerprint("POST",f"/incidents/{id}",{"text":"원문"})
    response = ReceiptResponse(200,{"data":{"version":2},"meta":{"request_id":"first"}})
    with transaction(database) as tx:
        assert reserve_command(tx.connection,PRINCIPAL,key,fp) is None
        tx.lock_incident(id,uid(1))
        tx.bump_incident(id,1)
        finish_command(tx.connection,PRINCIPAL,key,response)
    with transaction(database) as tx:
        assert reserve_command(tx.connection,PRINCIPAL,key,fp) == response
    with pytest.raises(DomainError):
        with transaction(database) as tx: reserve_command(tx.connection,PRINCIPAL,key,"changed")
    with pytest.raises(RuntimeError):
        with transaction(database) as tx:
            reserve_command(tx.connection,PRINCIPAL,"rollback",fp)
            tx.lock_incident(id)
            tx.bump_incident(id,2)
            raise RuntimeError("injected persistence failure")
    with database.connect() as c:
        assert c.scalar(select(s.incidents.c.version).where(s.incidents.c.id==id)) == 2
        assert c.scalar(select(func.count()).select_from(s.command_receipts)) == 1


def test_inflight_duplicate_is_nonblocking(database):
    reserved,release = Event(),Event()
    def first():
        with transaction(database) as tx:
            reserve_command(tx.connection,PRINCIPAL,"race","hash")
            reserved.set()
            assert release.wait(5)
            finish_command(tx.connection,PRINCIPAL,"race",ReceiptResponse(200,{"data":"ok"}))
    with ThreadPoolExecutor(max_workers=1) as pool:
        future=pool.submit(first)
        try:
            assert reserved.wait(5)
            with pytest.raises(DomainError) as error:
                with transaction(database) as tx: reserve_command(tx.connection,PRINCIPAL,"race","hash")
            assert error.value.code == "COMMAND_IN_PROGRESS"
        finally: release.set()
        future.result()


def test_version_lock_scope_and_once_per_transaction(database):
    id=incident(database)
    with pytest.raises(DomainError) as error:
        with transaction(database) as tx: tx.lock_incident(id,uuid4())
    assert error.value.status == 404
    with pytest.raises(RuntimeError):
        with transaction(database) as tx:
            tx.lock_incident(id)
            tx.bump_incident(id,1)
            tx.bump_incident(id,2)
    def change(_):
        try:
            with transaction(database) as tx:
                tx.lock_incident(id)
                tx.bump_incident(id,1)
            return "ok"
        except DomainError as e: return e.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(change,range(2))) == ["VERSION_CONFLICT","ok"]


def test_receipts_are_actor_scoped_and_replay_error_envelope(database):
    other=PRINCIPAL.model_copy(update={"user_id":uid(204)})
    response=ReceiptResponse(409,{"error":{"code":"INCIDENT_RESOLVED"},"meta":{"request_id":"original"}})
    with transaction(database) as tx:
        reserve_command(tx.connection,PRINCIPAL,"same-key","hash")
        finish_command(tx.connection,PRINCIPAL,"same-key",response)
    with transaction(database) as tx:
        assert reserve_command(tx.connection,PRINCIPAL,"same-key","hash") == response
        assert reserve_command(tx.connection,other,"same-key","hash") is None
        finish_command(tx.connection,other,"same-key",ReceiptResponse(200,{"data":"other"}))
