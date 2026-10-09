"""Idempotent reference dataset only; creates no live Incident/Request/Action."""
from datetime import datetime, timedelta, timezone
from sqlalchemy import select

from .models import Document, DocumentChunk, Equipment, EquipmentLog, ResolutionCase, Shift, ShiftAssignment, User


def sid(number):
    return f"00000000-0000-4000-8000-{number:012d}"


SEED_IDS = {"site": sid(1), "equipment": sid(103), "comparison_equipment": sid(102),
            "reporter": sid(201), "maintainer": sid(202), "outgoing_supervisor": sid(203),
            "incoming_supervisor": sid(204), "outgoing_shift": sid(301), "incoming_shift": sid(302)}
DEMO_T0 = datetime(2026, 10, 9, 3, 0, tzinfo=timezone.utc)


def seed_demo(tx):
    if tx.get(User, SEED_IDS["reporter"]):
        return SEED_IDS
    for key, label, role in [("reporter", "현장 작업자", "worker"), ("maintainer", "정비 담당자", "worker"),
                             ("outgoing_supervisor", "출발 책임자", "supervisor"), ("incoming_supervisor", "수신 책임자", "supervisor")]:
        tx.add(User(id=SEED_IDS[key], account_key=key, site_id=SEED_IDS["site"], display_name=label, role=role, enabled=True))
    tx.flush()
    for number, key, supervisor, start, end, active in [(301, "A", "outgoing_supervisor", 0, 4, True), (302, "B", "incoming_supervisor", 4, 8, False)]:
        tx.add(Shift(id=sid(number), site_id=SEED_IDS["site"], label=f"SHIFT-20261009-{key}",
                     starts_at=datetime(2026, 10, 9, start, tzinfo=timezone.utc), ends_at=datetime(2026, 10, 9, end, tzinfo=timezone.utc),
                     supervisor_id=SEED_IDS[supervisor], active=active))
    for number, code, name in [(103, "CV-03", "3번 이송 설비"), (102, "CV-02", "2번 이송 설비")]:
        tx.add(Equipment(id=sid(number), site_id=sid(1), code=code, label=name,
                         aliases=[name, f"{number - 100}호기"], default_maintainer_id=sid(202)))
    tx.flush()
    for key, shift, duty in [("reporter", 301, "OPERATOR"), ("maintainer", 301, "MAINTENANCE"),
                              ("maintainer", 302, "MAINTENANCE"), ("outgoing_supervisor", 301, "SUPERVISOR"),
                              ("incoming_supervisor", 302, "SUPERVISOR")]:
        tx.add(ShiftAssignment(shift_occurrence_id=sid(shift), user_id=SEED_IDS[key], duty=duty))
    logs = [(601, 103, 201, 20, "3번 이송 설비에서 평소와 다른 소리와 떨림을 느꼈다는 보고를 받음."),
            (602, 103, 202, 10, "초기 점검 완료."), (603, 102, 202, 1440, "2번 이송 설비의 모의 점검 기록 작성 완료.")]
    for number, equipment, author, minutes, original in logs:
        tx.add(EquipmentLog(id=sid(number), site_id=sid(1), equipment_id=sid(equipment), author_id=sid(author),
                            text=original, observed_at=DEMO_T0 - timedelta(minutes=minutes), source_location=f"합성 기록 {number}"))
    tx.add(Document(id=sid(701), site_id=sid(1), title="설비 이상 보고의 기록 확인·인계 절차 — 소프트웨어 시험용",
                    version="1", approval_status="approved", equipment_ids=[sid(103), sid(102)], source_location="SOP-DEMO-01"))
    tx.flush()
    paragraphs = [
        "이 문서는 ShiftLink 소프트웨어 시험용 가상 절차다. 실제 설비의 조작·정지·재가동·안전을 승인하지 않는다.",
        "설비 코드, 관찰한 현상, 직접 확인한 내용과 전해 들은 내용을 구분해 기록한다.",
        "점검 기록의 범위와 결과가 불명확하면 그 기록을 작성한 담당자에게 범위와 결과를 확인한다. 이미 확인된 내용은 다시 묻지 않는다.",
        "후속 확인 작업을 제안할 때 확인할 범위와 제출할 결과 항목을 적고, 실제 수행 전 책임자의 승인을 받는다. 같은 목적의 활성 작업이 있으면 그 작업을 유지한다.",
        "데모 확인 작업의 결과에는 확인한 범위, 이전 기록과 달라진 내용, 남은 미확인 사항을 적는다. 물리적 설비 작업 지침을 이 문서에서 만들지 않는다.",
        "교대할 때 미해결 사건, 미응답 질문, 남은 작업, 책임자와 작업 담당자를 함께 전달한다. 인수는 문제 해결과 별개다.",
        "필요한 질문·작업·결과가 모이고 현재 책임자가 검토 사유를 남긴 뒤 사건을 종료한다. 새 정보가 들어오면 최신 내용으로 다시 판단한다.",
        "기록 조회가 실패하거나 근거가 없으면 정상 또는 해결로 추정하지 않는다.",
    ]
    for position, original in enumerate(paragraphs):
        tx.add(DocumentChunk(document_id=sid(701), position=position, text=original, source_location=f"SOP-DEMO-01 §{position}"))
    tx.add(ResolutionCase(id=sid(702), site_id=sid(1), equipment_id=sid(102), title="이전 교대의 기록 범위 확인 사례",
        created_at=DEMO_T0 - timedelta(days=7), snapshot_json={"status": "RESOLVED", "synthetic": True,
            "text": "CV-02의 작업자가 평소와 다른 소리를 보고했다. 정비 기록에는 점검 완료라고 적혀 있었다. 작성자 확인 결과 기록은 외관 관찰에 한정됐고 원인 확인 결과는 없었다. 책임자 승인 후 모의 기록 확인 작업을 진행했다. 다음 교대는 미해결 사건과 진행 중 작업을 인수했다. 담당자의 결과 제출과 책임자의 최종 검토 이후 사건을 종료했다. 이는 과거 합성 사례이며 CV-03의 원인·상태를 보여주는 증거가 아니다."}))
    tx.flush()
    return SEED_IDS


def main():
    from .config import Settings
    from .db import create_session_factory
    settings = Settings.from_env()
    factory = create_session_factory(settings.database_url)
    with factory.begin() as tx:
        seed_demo(tx)


if __name__ == "__main__":
    main()
