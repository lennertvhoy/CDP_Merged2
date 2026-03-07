"""Tests for Tracardi loader module."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.ingestion.tracardi_loader import (
    infer_province,
    ingest_to_tracardi,
    load_and_aggregate_data,
)


class TestInferProvince:
    """Test province inference from zipcode."""

    def test_infer_province_gent(self):
        """Test province inference for Gent."""
        assert infer_province("9000") == "Oost-Vlaanderen"
        assert infer_province("9050") == "Oost-Vlaanderen"

    def test_infer_province_bruges(self):
        """Test province inference for Bruges."""
        assert infer_province("8000") == "West-Vlaanderen"
        assert infer_province("8200") == "West-Vlaanderen"

    def test_infer_province_antwerp(self):
        """Test province inference for Antwerp."""
        assert infer_province("2000") == "Antwerpen"
        assert infer_province("2020") == "Antwerpen"

    def test_infer_province_limburg(self):
        """Test province inference for Limburg."""
        assert infer_province("3500") == "Limburg"
        assert infer_province("3600") == "Limburg"

    def test_infer_province_brussels(self):
        """Test province inference for Brussels."""
        assert infer_province("1000") == "Brussels"
        assert infer_province("1200") == "Brussels"

    def test_infer_province_vlaams_brabant(self):
        """Test province inference for Vlaams-Brabant."""
        assert infer_province("1500") == "Vlaams-Brabant"
        assert infer_province("3000") == "Vlaams-Brabant"

    def test_infer_province_other(self):
        """Test province inference for other regions."""
        assert infer_province("4000") == "Other"
        assert infer_province("5000") == "Other"

    def test_infer_province_empty(self):
        """Test province inference with empty zipcode."""
        assert infer_province("") == "Unknown"
        assert infer_province(None) == "Unknown"

    def test_infer_province_invalid(self):
        """Test province inference with invalid zipcode."""
        assert infer_province("ABC") == "Unknown"
        assert infer_province("12") == "Other"


class TestLoadAndAggregateData:
    """Test data loading and aggregation."""

    @pytest.fixture
    def mock_data_dir(self, tmp_path: Path):
        """Create mock KBO data files."""
        data_dir = tmp_path / "data" / "kbo"
        data_dir.mkdir(parents=True)

        # Address.csv - with entities in valid zipcode ranges
        address_csv = """EntityNumber,TypeOfAddress,CountryNL,StreetNL,HouseNumber,Zipcode,MunicipalityNL
0207446759,REGO,BE,Korte Meer,1,9000,Gent
0542123456,REGO,BE,Brusselsestraat,10,1000,Brussel
0673890123,REGO,BE,Meir,50,2000,Antwerpen
0789456789,REGO,BE,Stationstraat,5,5000,Namur"""
        (data_dir / "address.csv").write_text(address_csv)

        # Enterprise.csv - only 2 are active
        enterprise_csv = """EnterpriseNumber,Status,JuridicalForm,StartDate
0207446759,AC,014,2020-01-15
0542123456,AC,017,2019-03-20
0673890123,AC,014,2018-06-10"""
        (data_dir / "enterprise.csv").write_text(enterprise_csv)

        # Denomination.csv
        denomination_csv = """EntityNumber,Denomination
0207446759,Acme NV
0542123456,Tech BV
0673890123,Shop LLC"""
        (data_dir / "denomination.csv").write_text(denomination_csv)

        # Activity.csv
        activity_csv = """EntityNumber,NaceCode
0207446759,62010
0207446759,63110
0542123456,62020
0673890123,47110"""
        (data_dir / "activity.csv").write_text(activity_csv)

        # Contact.csv
        contact_csv = """EntityNumber,ContactType,Value
0207446759,EMAIL,info@acme.be
0207446759,TEL,+32 9 123 45 67
0542123456,EMAIL,contact@tech.be
0673890123,TEL,+32 3 123 45 67"""
        (data_dir / "contact.csv").write_text(contact_csv)

        return data_dir

    @pytest.mark.asyncio
    async def test_load_and_aggregate_data_success(self, mock_data_dir: Path, tmp_path: Path):
        """Test successful data loading and aggregation."""
        with patch("src.ingestion.tracardi_loader.DATA_DIR", str(mock_data_dir)):
            result = await load_and_aggregate_data()

        assert len(result) == 3  # 3 enterprises in valid zipcodes and active

        # Check first enterprise
        ent1 = next(e for e in result if e["enterprise_number"] == "0207446759")
        assert ent1["name"] == "Acme NV"
        assert ent1["status"] == "AC"
        assert ent1["province"] == "Oost-Vlaanderen"
        assert ent1["address"]["city"] == "Gent"
        assert ent1["address"]["zipcode"] == "9000"
        assert len(ent1["nace_codes"]) == 2
        assert "62010" in ent1["nace_codes"]
        assert len(ent1["emails"]) == 1
        assert "info@acme.be" in ent1["emails"]
        assert len(ent1["phones"]) == 1

    @pytest.mark.asyncio
    async def test_load_and_aggregate_data_missing_address_file(self, tmp_path: Path):
        """Test handling when address file is missing."""
        data_dir = tmp_path / "data" / "kbo"
        data_dir.mkdir(parents=True)

        with patch("src.ingestion.tracardi_loader.DATA_DIR", str(data_dir.parent)):
            result = await load_and_aggregate_data()

        assert result == []

    @pytest.mark.asyncio
    async def test_load_and_aggregate_data_filters_by_status(
        self, mock_data_dir: Path, tmp_path: Path
    ):
        """Test that only active enterprises are retained."""
        # Modify enterprise.csv to have inactive entries
        enterprise_csv = """EnterpriseNumber,Status,JuridicalForm,StartDate
0207446759,AC,014,2020-01-15
0542123456,IN,017,2019-03-20
0673890123,AC,014,2018-06-10"""
        (mock_data_dir / "enterprise.csv").write_text(enterprise_csv)

        with patch("src.ingestion.tracardi_loader.DATA_DIR", str(mock_data_dir)):
            result = await load_and_aggregate_data()

        # Should only include AC (active) enterprises
        enterprise_numbers = [e["enterprise_number"] for e in result]
        assert "0207446759" in enterprise_numbers
        assert "0673890123" in enterprise_numbers
        assert "0542123456" not in enterprise_numbers  # IN = inactive


class TestIngestToTracardi:
    """Test ingestion to Tracardi."""

    @pytest.mark.asyncio
    async def test_ingest_single_profile(self):
        """Test loading a single profile."""
        data = [
            {
                "enterprise_number": "0207446759",
                "name": "Acme NV",
                "status": "AC",
                "address": {
                    "street": "Korte Meer 1",
                    "zipcode": "9000",
                    "city": "Gent",
                    "country": "BE",
                },
                "province": "Oost-Vlaanderen",
                "nace_codes": ["62010"],
                "emails": ["info@acme.be"],
                "phones": ["+32 9 123 45 67"],
            }
        ]

        mock_client = MagicMock()
        mock_client.import_profiles = AsyncMock()

        with patch("src.ingestion.tracardi_loader.TracardiClient") as mock_client_cls:
            mock_client_cls.return_value = mock_client
            with patch.dict(os.environ, {"KBO_INGEST_BATCH_SIZE": "10"}):
                await ingest_to_tracardi(data)

        mock_client.import_profiles.assert_called_once()
        call_args = mock_client.import_profiles.call_args
        batch = call_args[0][0]
        assert len(batch) == 1
        assert batch[0]["id"] == "0207446759"
        assert batch[0]["traits"]["name"] == "Acme NV"
        assert batch[0]["traits"]["email"] == "info@acme.be"

    @pytest.mark.asyncio
    async def test_ingest_batch_profiles(self):
        """Test loading multiple profiles in batches."""
        data = [
            {
                "enterprise_number": f"020744675{i}",
                "name": f"Company {i}",
                "status": "AC",
                "address": {"street": "Test", "zipcode": "9000", "city": "Gent", "country": "BE"},
                "province": "Oost-Vlaanderen",
                "nace_codes": ["62010"],
                "emails": [],
                "phones": [],
            }
            for i in range(5)
        ]

        mock_client = MagicMock()
        mock_client.import_profiles = AsyncMock()

        with patch("src.ingestion.tracardi_loader.TracardiClient") as mock_client_cls:
            mock_client_cls.return_value = mock_client
            with patch.dict(os.environ, {"KBO_INGEST_BATCH_SIZE": "2"}):
                await ingest_to_tracardi(data)

        # Should be called 3 times (2+2+1)
        assert mock_client.import_profiles.call_count == 3

    @pytest.mark.asyncio
    async def test_ingest_with_error_handling(self):
        """Test error handling during load."""
        data = [
            {
                "enterprise_number": "0207446759",
                "name": "Acme NV",
                "status": "AC",
                "address": {"street": "Test", "zipcode": "9000", "city": "Gent", "country": "BE"},
                "province": "Oost-Vlaanderen",
                "nace_codes": [],
                "emails": [],
                "phones": [],
            }
        ]

        mock_client = MagicMock()
        mock_client.import_profiles = AsyncMock(side_effect=Exception("Connection failed"))

        with patch("src.ingestion.tracardi_loader.TracardiClient") as mock_client_cls:
            mock_client_cls.return_value = mock_client
            with patch.dict(os.environ, {"KBO_INGEST_BATCH_SIZE": "10"}):
                with pytest.raises(Exception, match="Connection failed"):
                    await ingest_to_tracardi(data)

    @pytest.mark.asyncio
    async def test_ingest_sets_metadata_time(self):
        """Test that metadata time is set for profiles."""
        data = [
            {
                "enterprise_number": "0207446759",
                "name": "Acme NV",
                "status": "AC",
                "address": {"street": "Test", "zipcode": "9000", "city": "Gent", "country": "BE"},
                "province": "Oost-Vlaanderen",
                "nace_codes": [],
                "emails": [],
                "phones": [],
            }
        ]

        mock_client = MagicMock()
        mock_client.import_profiles = AsyncMock()

        with patch("src.ingestion.tracardi_loader.TracardiClient") as mock_client_cls:
            mock_client_cls.return_value = mock_client
            with patch.dict(os.environ, {"KBO_INGEST_BATCH_SIZE": "10"}):
                await ingest_to_tracardi(data)

        call_args = mock_client.import_profiles.call_args
        batch = call_args[0][0]
        assert "metadata" in batch[0]
        assert "time" in batch[0]["metadata"]
        assert "create" in batch[0]["metadata"]["time"]
        assert "update" in batch[0]["metadata"]["time"]


class TestBatchUpload:
    """Test batch upload functionality."""

    @pytest.mark.asyncio
    async def test_batch_upload_success(self):
        """Test successful batch upload."""
        data = [
            {
                "enterprise_number": f"020744675{i}",
                "name": f"Company {i}",
                "status": "AC",
                "address": {"street": "Test", "zipcode": "9000", "city": "Gent", "country": "BE"},
                "province": "Oost-Vlaanderen",
                "nace_codes": [],
                "emails": [f"info{i}@test.be"],
                "phones": [],
            }
            for i in range(3)
        ]

        mock_client = MagicMock()
        mock_client.import_profiles = AsyncMock(return_value={"imported": 3})

        with patch("src.ingestion.tracardi_loader.TracardiClient") as mock_client_cls:
            mock_client_cls.return_value = mock_client
            with patch.dict(os.environ, {"KBO_INGEST_BATCH_SIZE": "10"}):
                await ingest_to_tracardi(data)

        mock_client.import_profiles.assert_called_once()
        call_args = mock_client.import_profiles.call_args
        assert len(call_args[0][0]) == 3

    @pytest.mark.asyncio
    async def test_batch_upload_partial_failure(self):
        """Test partial batch failure handling."""
        data = [
            {
                "enterprise_number": "0207446759",
                "name": "Company 1",
                "status": "AC",
                "address": {"street": "Test", "zipcode": "9000", "city": "Gent", "country": "BE"},
                "province": "Oost-Vlaanderen",
                "nace_codes": [],
                "emails": [],
                "phones": [],
            }
        ]

        mock_client = MagicMock()
        mock_client.import_profiles = AsyncMock(
            side_effect=[
                Exception("First batch failed"),
            ]
        )

        with patch("src.ingestion.tracardi_loader.TracardiClient") as mock_client_cls:
            mock_client_cls.return_value = mock_client
            with patch.dict(os.environ, {"KBO_INGEST_BATCH_SIZE": "10"}):
                with pytest.raises(Exception, match="First batch failed"):
                    await ingest_to_tracardi(data)
