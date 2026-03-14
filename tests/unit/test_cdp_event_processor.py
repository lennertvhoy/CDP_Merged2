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

    assert row == (
        "123e4567-e89b-12d3-a456-426614174000",
        "0438437723",
        "B.B.S. Entreprise",
        "43320",
    )
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


def test_hash_identifier_produces_deterministic_sha256():
    """Test that hash_identifier produces consistent SHA-256 hashes."""
    email = "test@example.com"
    hash1 = event_processor.hash_identifier(email)
    hash2 = event_processor.hash_identifier(email)
    
    # Should be deterministic
    assert hash1 == hash2
    # Should be 64 hex characters (SHA-256)
    assert len(hash1) == 64
    # Should be different from original
    assert hash1 != email
    # None input should return None
    assert event_processor.hash_identifier(None) is None
    # Empty string should return None
    assert event_processor.hash_identifier("") is None


def test_extract_email_domain_extracts_domain_only():
    """Test that extract_email_domain preserves only the domain part."""
    assert event_processor.extract_email_domain("user@example.com") == "example.com"
    assert event_processor.extract_email_domain("USER@EXAMPLE.COM") == "example.com"
    assert event_processor.extract_email_domain(None) is None
    assert event_processor.extract_email_domain("invalid") is None
    assert event_processor.extract_email_domain("") is None


def test_sanitize_event_data_removes_pii_preserves_metadata():
    """Test that sanitize_event_data removes PII but preserves useful metadata."""
    raw_event = {
        "email_id": "test-email-123",
        "to": "user@example.com",
        "from": "sender@company.com",
        "subject": "Important Email Subject",
        "user_agent": "Mozilla/5.0",
        "kbo_number": "0438437723",
        "metadata": {"campaign_id": "spring2026"},
    }
    
    sanitized = event_processor.sanitize_event_data(raw_event)
    
    # Should NOT contain raw email
    assert "user@example.com" not in str(sanitized)
    assert "sender@company.com" not in str(sanitized)
    # Should NOT contain raw subject
    assert "Important Email Subject" not in str(sanitized)
    
    # SHOULD contain hashes
    assert sanitized["recipient_hash"] == event_processor.hash_identifier("user@example.com")
    assert sanitized["subject_hash"] == event_processor.hash_identifier("important email subject")
    
    # SHOULD contain domains
    assert sanitized["recipient_domain"] == "example.com"
    assert sanitized["sender_domain"] == "company.com"
    
    # SHOULD preserve non-PII metadata
    assert sanitized["email_id"] == "test-email-123"
    assert sanitized["user_agent"] == "Mozilla/5.0"
    assert sanitized["kbo_number"] == "0438437723"
    assert sanitized["metadata"]["campaign_id"] == "spring2026"


def test_sanitize_event_data_handles_click_data():
    """Test that sanitize_event_data properly extracts click domains."""
    event_with_click = {
        "to": "user@example.com",
        "click": {"link": "https://example.com/page?param=1"},
    }
    
    sanitized = event_processor.sanitize_event_data(event_with_click)
    assert sanitized["click_domain"] == "example.com"
    # Should not contain full URL
    assert "https://example.com/page" not in str(sanitized)


def test_update_engagement_score_uses_hashed_email_and_sanitized_data():
    """Test that update_engagement_score stores hashed email and sanitized event data."""
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
            {"to": "INFO@BBSENTREPRISE.BE", "subject": "Confidential"},
        )
    finally:
        event_processor.get_db_connection = original_get_db_connection

    assert result["kbo_number"] == "0438437723"
    assert connection.committed is True
    
    # Find the INSERT query
    insert_query = None
    insert_params = None
    for query, params in cursor.executed:
        if "INSERT INTO company_engagement" in query:
            insert_query = query
            insert_params = params
            break
    
    assert insert_query is not None
    # Should use email_hash column, not email
    assert "email_hash" in insert_query
    # Should NOT have plain email column
    assert "email," not in insert_query.replace("email_hash", "")
    
    # Verify params: email should be hashed
    email_hash_param = insert_params[2]  # 3rd param is email_hash
    assert email_hash_param == event_processor.hash_identifier("info@bbsentreprise.be")
    
    # Verify event_data is sanitized (no raw email in JSON)
    event_data_param = insert_params[5]  # 6th param is event_data
    assert "info@bbsentreprise.be" not in event_data_param
    assert "Confidential" not in event_data_param  # Raw subject should not be present
