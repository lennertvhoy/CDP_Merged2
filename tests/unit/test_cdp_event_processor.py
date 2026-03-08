from __future__ import annotations

from datetime import UTC, datetime

import scripts.cdp_event_processor as event_processor


class FakeCursor:
    def __init__(self, fetchone_results=None):
        self.fetchone_results = list(fetchone_results or [])
        self.executed: list[tuple[str, tuple | None]] = []

    def execute(self, query, params=None):
        normalized_query = " ".join(query.split())
        self.executed.append((normalized_query, params))

    def fetchone(self):
        if not self.fetchone_results:
            return None
        return self.fetchone_results.pop(0)

    def close(self):
        return None


class FakeConnection:
    def __init__(self, cursor: FakeCursor):
        self._cursor = cursor
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        return None


def test_extract_recipient_email_prefers_to_and_handles_nested_shapes():
    payload = {
        "to": [{"email": " INFO@BBSENTREPRISE.BE "}],
        "metadata": {"kbo_number": "BE0438.437.723"},
    }

    assert event_processor.extract_recipient_email(payload) == "info@bbsentreprise.be"


def test_extract_kbo_from_event_normalizes_nested_metadata():
    payload = {"metadata": {"company_number": "BE 0438.437.723"}}

    assert event_processor.extract_kbo_from_event(payload) == "0438437723"


def test_get_scoring_model_exposes_weights_thresholds_and_rules():
    model = event_processor.get_scoring_model()

    assert model["version"] == event_processor.SCORING_MODEL_VERSION
    assert model["event_weights"]["email.opened"] == 5
    assert model["event_weights"]["email.clicked"] == 10
    assert model["engagement_thresholds"]["medium"]["min_inclusive"] == 20
    assert model["engagement_thresholds"]["high"]["min_inclusive"] == 50
    assert model["recommendation_rules"]["support_expansion"]["trigger"] == "open_tickets > 0"


def test_lookup_company_prefers_kbo_number_from_payload():
    cursor = FakeCursor(
        fetchone_results=[
            ("123e4567-e89b-12d3-a456-426614174000", "0438437723", "B.B.S. Entreprise", "43320"),
        ]
    )

    row = event_processor.lookup_company(
        cursor,
        email=None,
        event_data={"metadata": {"kbo_number": "BE0438.437.723"}},
    )

    assert row == ("123e4567-e89b-12d3-a456-426614174000", "0438437723", "B.B.S. Entreprise", "43320")
    assert cursor.executed[0][1] == ("0438437723",)


def test_update_engagement_score_resolves_unified_360_email_and_commits():
    cursor = FakeCursor(
        fetchone_results=[
            ("123e4567-e89b-12d3-a456-426614174001", "0438437723", "B.B.S. Entreprise", "43320"),
            (15, 1, 1, datetime(2026, 3, 8, 23, 30, tzinfo=UTC)),
        ]
    )
    connection = FakeConnection(cursor)

    original_get_db_connection = event_processor.get_db_connection
    event_processor.get_db_connection = lambda: connection
    try:
        result = event_processor.update_engagement_score(
            "INFO@BBSENTREPRISE.BE",
            "email.clicked",
            {"to": "INFO@BBSENTREPRISE.BE"},
        )
    finally:
        event_processor.get_db_connection = original_get_db_connection

    assert result["kbo_number"] == "0438437723"
    assert result["company_name"] == "B.B.S. Entreprise"
    assert result["engagement_score"] == 15
    assert result["email_opens"] == 1
    assert result["email_clicks"] == 1
    assert connection.committed is True
    assert any("u.tl_email" in query for query, _ in cursor.executed)


def test_init_database_creates_table_and_indexes():
    cursor = FakeCursor()
    connection = FakeConnection(cursor)

    original_get_db_connection = event_processor.get_db_connection
    event_processor.get_db_connection = lambda: connection
    try:
        event_processor.init_database()
    finally:
        event_processor.get_db_connection = original_get_db_connection

    assert connection.committed is True
    assert len(cursor.executed) == 3
    assert "CREATE TABLE IF NOT EXISTS company_engagement" in cursor.executed[0][0]
    assert "INDEX idx_kbo_number" not in cursor.executed[0][0]
