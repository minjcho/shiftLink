"""The public Incident summary selects one newest handover inside readable scope."""
from datetime import timedelta
from uuid import UUID, uuid4

import pytest

from app.core.models import Handover, HandoverAck, HandoverItem, HandoverRevision, Incident, Shift, utcnow


def incident_row(tx, ids):
    incident = Incident(id=str(uuid4()), display_id=f"SUMMARY-{uuid4()}", site_id=ids["site"],
        equipment_id=ids["equipment"], reporter_id=ids["reporter"],
        origin_shift_occurrence_id=ids["outgoing_shift"], owner_shift_occurrence_id=ids["incoming_shift"],
        owner_id=ids["outgoing_supervisor"], status="IN_PROGRESS", version=7)
    tx.add(incident)
    tx.flush()
    return incident


def handover(tx, ids, incident, *, number, created_at, site=None, participant=True, ack=False):
    shift = Shift(id=str(uuid4()), site_id=site or ids["site"], label=f"SHIFT-{number}",
        starts_at=created_at, ends_at=created_at + timedelta(hours=4), supervisor_id=ids["incoming_supervisor"])
    tx.add(shift)
    tx.flush()
    row = Handover(id=str(UUID(int=number)), site_id=site or ids["site"],
        from_shift_occurrence_id=ids["outgoing_shift"], to_shift_occurrence_id=shift.id,
        created_by=ids["outgoing_supervisor"] if participant else ids["maintainer"],
        receiver_id=ids["incoming_supervisor"], cutoff_at=created_at, created_at=created_at)
    tx.add(row)
    tx.flush()
    item = HandoverItem(id=str(uuid4()), handover_id=row.id, incident_id=incident.id, latest_revision=1)
    tx.add(item)
    tx.flush()
    tx.add(HandoverRevision(item_id=item.id, revision=1, snapshot_version=6 if ack else 4,
        snapshot_json={"private": f"snapshot-{number}"}, snapshot_token=f"private-token-{number}"))
    if ack:
        tx.add(HandoverAck(item_id=item.id, revision=1, actor_id=ids["incoming_supervisor"],
            previous_owner_id=ids["outgoing_supervisor"], new_owner_id=ids["incoming_supervisor"], ack_applied_version=7))
    return row.id, item.id


@pytest.mark.ac9
@pytest.mark.parametrize("same_timestamp", [False, True])
def test_summary_orders_readable_handovers_by_created_at_then_id(same_timestamp, session_factory, demo_ids, client, login):
    instant = utcnow()
    with session_factory.begin() as tx:
        incident = incident_row(tx, demo_ids)
        incident_id = incident.id
        # Insert newest first: insertion order must not select the older row.
        newest, newest_item = handover(tx, demo_ids, incident, number=202, created_at=instant, ack=True)
        older, _ = handover(tx, demo_ids, incident, number=201,
            created_at=instant if same_timestamp else instant - timedelta(hours=4))
    login("outgoing_supervisor")
    for _ in range(2):
        response = client.get(f"/api/v1/incidents/{incident_id}")
        assert response.status_code == 200
        summary = response.json()["data"]["handover"]
        assert summary["id"] == newest and summary["id"] != older
        assert summary["item_id"] == newest_item
        assert summary["ack_status"] == "ACKNOWLEDGED" and summary["ack_applied_version"] == 7
        assert summary["is_stale"] is False
        assert "snapshot_token" not in response.text and "private-token" not in response.text


@pytest.mark.ac9
def test_summary_filters_actor_and_site_before_latest_limit(session_factory, demo_ids, client, login):
    instant = utcnow()
    with session_factory.begin() as tx:
        incident = incident_row(tx, demo_ids)
        incident_id = incident.id
        expected, item = handover(tx, demo_ids, incident, number=301, created_at=instant, ack=True)
        unrelated, _ = handover(tx, demo_ids, incident, number=302,
            created_at=instant + timedelta(hours=1), participant=False)
        foreign, _ = handover(tx, demo_ids, incident, number=303,
            created_at=instant + timedelta(hours=2), site=str(uuid4()))
    login("outgoing_supervisor")
    response = client.get(f"/api/v1/incidents/{incident_id}")
    assert response.status_code == 200
    assert response.json()["data"]["handover"]["id"] == expected
    assert response.json()["data"]["handover"]["item_id"] == item
    assert unrelated not in response.text and foreign not in response.text
    login("reporter")
    public = client.get(f"/api/v1/incidents/{incident_id}")
    assert public.status_code == 200 and public.json()["data"]["handover"] is None
    assert all(identifier not in public.text for identifier in (expected, unrelated, foreign, item))
