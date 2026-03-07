"""Tests for KBO ingestion module."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Set environment variables before importing kbo_ingest (which validates them at import time)
os.environ.setdefault("TRACARDI_USER", "test-user")
os.environ.setdefault("TRACARDI_PASSWORD", "test-password")

from src.ingestion.kbo_ingest import (
    get_access_token,
    ingest_profiles_to_tracardi,
    load_kbo_data,
    transform_to_tracardi_profile,
)


class TestGetAccessToken:
    """Test KBO access token fetching."""

    def test_get_access_token_success(self):
        """Test successful access token fetch."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "test-token-123"}
        mock_response.raise_for_status = MagicMock()

        with patch("src.ingestion.kbo_ingest.requests.post") as mock_post:
            mock_post.return_value = mock_response
            with patch.dict(
                "os.environ",
                {
                    "TRACARDI_HOST": "http://localhost:8686",
                    "TRACARDI_USER": "admin",
                    "TRACARDI_PASSWORD": "admin",
                },
            ):
                token = get_access_token()

        assert token == "test-token-123"
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "http://localhost:8686/user/token"

    def test_get_access_token_http_error(self):
        """Test HTTP error handling during token fetch."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("HTTP 401 Unauthorized")

        with patch("src.ingestion.kbo_ingest.requests.post") as mock_post:
            mock_post.return_value = mock_response
            with patch.dict(
                "os.environ",
                {
                    "TRACARDI_HOST": "http://localhost:8686",
                    "TRACARDI_USER": "admin",
                    "TRACARDI_PASSWORD": "wrong-password",
                },
            ):
                with pytest.raises(Exception, match="HTTP 401 Unauthorized"):
                    get_access_token()


class TestLoadKBOData:
    """Test KBO data loading from CSV files."""

    def test_load_complete_data(self, tmp_path: Path):
        """Test loading complete KBO data from all CSV files."""
        # Create mock CSV files
        enterprise_csv = """EnterpriseNumber,Status,JuridicalForm,StartDate
0207446759,AC,014,2020-01-15
0542123456,AC,017,2019-03-20"""

        denomination_csv = """EntityNumber,Denomination
0207446759,Acme NV
0542123456,Tech BV"""

        address_csv = """EntityNumber,TypeOfAddress,CountryNL,StreetNL,HouseNumber,Zipcode,MunicipalityNL
0207446759,REGO,BE,Korte Meer,1,9000,Gent
0542123456,REGO,BE,Brusselsestraat,10,1000,Brussel"""

        activity_csv = """EntityNumber,NaceCode
0207446759,62010
0207446759,63110
0542123456,62020"""

        contact_csv = """EntityNumber,ContactType,Value
0207446759,EMAIL,info@acme.be
0207446759,TEL,+32 9 123 45 67
0542123456,EMAIL,contact@tech.be"""

        # Write files to temp directory
        (tmp_path / "enterprise.csv").write_text(enterprise_csv)
        (tmp_path / "denomination.csv").write_text(denomination_csv)
        (tmp_path / "address.csv").write_text(address_csv)
        (tmp_path / "activity.csv").write_text(activity_csv)
        (tmp_path / "contact.csv").write_text(contact_csv)

        result = load_kbo_data(tmp_path)

        assert len(result) == 2

        # Check first enterprise
        ent1 = next(e for e in result if e["enterprise_number"] == "0207446759")
        assert ent1["status"] == "AC"
        assert ent1["juridical_form"] == "014"
        assert ent1["start_date"] == "2020-01-15"
        assert ent1["name"] == "Acme NV"
        assert len(ent1["denominations"]) == 1
        assert len(ent1["addresses"]) == 1
        assert len(ent1["activities"]) == 2
        assert ent1["contacts"]["email"] == "info@acme.be"
        assert ent1["contacts"]["tel"] == "+32 9 123 45 67"

    def test_load_missing_files(self, tmp_path: Path):
        """Test handling of missing CSV files."""
        # Only create enterprise.csv and empty supporting files
        enterprise_csv = """EnterpriseNumber,Status,JuridicalForm,StartDate
0207446759,AC,014,2020-01-15"""
        (tmp_path / "enterprise.csv").write_text(enterprise_csv)
        # Create empty supporting files
        (tmp_path / "denomination.csv").write_text("EntityNumber,Denomination\n")
        (tmp_path / "address.csv").write_text(
            "EntityNumber,TypeOfAddress,CountryNL,StreetNL,HouseNumber,Zipcode,MunicipalityNL\n"
        )
        (tmp_path / "activity.csv").write_text("EntityNumber,NaceCode\n")
        (tmp_path / "contact.csv").write_text("EntityNumber,ContactType,Value\n")

        result = load_kbo_data(tmp_path)

        assert len(result) == 1
        assert result[0]["enterprise_number"] == "0207446759"
        assert result[0]["denominations"] == []
        assert result[0]["addresses"] == []
        assert result[0]["activities"] == []
        assert result[0]["contacts"] == {}

    def test_load_empty_directory(self, tmp_path: Path):
        """Test loading from directory with empty enterprise.csv and supporting files."""
        enterprise_csv = """EnterpriseNumber,Status,JuridicalForm,StartDate"""
        (tmp_path / "enterprise.csv").write_text(enterprise_csv)
        # Create empty supporting files
        (tmp_path / "denomination.csv").write_text("EntityNumber,Denomination\n")
        (tmp_path / "address.csv").write_text(
            "EntityNumber,TypeOfAddress,CountryNL,StreetNL,HouseNumber,Zipcode,MunicipalityNL\n"
        )
        (tmp_path / "activity.csv").write_text("EntityNumber,NaceCode\n")
        (tmp_path / "contact.csv").write_text("EntityNumber,ContactType,Value\n")

        result = load_kbo_data(tmp_path)

        assert result == []


class TestTransformToTracardiProfile:
    """Test KBO to profile transformation."""

    def test_transform_complete_data(self):
        """Test transformation with complete KBO data."""
        enterprise = {
            "enterprise_number": "0207446759",
            "status": "AC",
            "juridical_form": "014",
            "start_date": "2020-01-15",
            "name": "Acme NV",
            "denominations": ["Acme NV", "Acme"],
            "addresses": [
                {
                    "type": "REGO",
                    "country": "BE",
                    "street": "Korte Meer",
                    "house_number": "1",
                    "zipcode": "9000",
                    "municipality": "Gent",
                }
            ],
            "activities": ["62010", "63110"],
            "contacts": {"email": "info@acme.be", "tel": "+32 9 123 45 67"},
        }

        result = transform_to_tracardi_profile(enterprise)

        assert result["id"] == "0207.446.759"
        assert result["ids"] == ["0207446759"]
        assert result["traits"]["kbo"]["enterpriseNumber"] == "0207446759"
        assert result["traits"]["kbo"]["status"] == "AC"
        assert result["traits"]["kbo"]["juridicalForm"] == "014"
        assert result["pii"]["name"] == "Acme NV"
        assert result["pii"]["email"] == "info@acme.be"
        assert result["pii"]["telephone"] == "+32 9 123 45 67"

    def test_transform_minimal_data(self):
        """Test transformation with minimal data."""
        enterprise = {
            "enterprise_number": "0542123456",
            "status": None,
            "juridical_form": None,
            "start_date": None,
            "denominations": [],
            "addresses": [],
            "activities": [],
            "contacts": {},
        }

        result = transform_to_tracardi_profile(enterprise)

        assert result["id"] == "0542.123.456"
        assert result["pii"]["name"] == "Unknown"
        assert "email" not in result["pii"]
        assert "telephone" not in result["pii"]

    def test_transform_fallback_name_from_denomination(self):
        """Test that first denomination is used as name when name not set."""
        enterprise = {
            "enterprise_number": "0542123456",
            "status": "AC",
            "denominations": ["Tech BV"],
            "addresses": [],
            "activities": [],
            "contacts": {},
        }

        result = transform_to_tracardi_profile(enterprise)

        assert result["pii"]["name"] == "Tech BV"

    def test_transform_non_standard_enterprise_number(self):
        """Test transformation with non-standard enterprise number length."""
        enterprise = {
            "enterprise_number": "12345",
            "status": "AC",
            "denominations": ["Short Corp"],
            "addresses": [],
            "activities": [],
            "contacts": {},
        }

        result = transform_to_tracardi_profile(enterprise)

        # Should not format with dots if not 10 chars
        assert result["id"] == "12345"


class TestIngestProfilesToTracardi:
    """Test profile ingestion to Tracardi."""

    def test_ingest_profiles_success(self):
        """Test successful profile ingestion."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"imported": 2, "errors": 0}

        profiles = [
            {"id": "0207.446.759", "traits": {}, "pii": {}},
            {"id": "0542.123.456", "traits": {}, "pii": {}},
        ]

        with patch("src.ingestion.kbo_ingest.requests.post") as mock_post:
            mock_post.return_value = mock_response
            with patch.dict(
                "os.environ",
                {
                    "TRACARDI_HOST": "http://localhost:8686",
                    "TRACARDI_USER": "admin",
                    "TRACARDI_PASSWORD": "admin",
                },
            ):
                result = ingest_profiles_to_tracardi(profiles, "test-token")

        assert result.status_code == 200
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "http://localhost:8686/profiles/import"
        assert call_args[1]["headers"]["Authorization"] == "Bearer test-token"
        assert call_args[1]["json"] == profiles
