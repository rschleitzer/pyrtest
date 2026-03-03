"""Tests for FHIR date search boundary conditions.

Validates that date/instant search prefixes (eq, gt, lt, ge, le) handle
exact boundary matches correctly.  Known server bugs these tests expose:

- gt (greater than) with exact value incorrectly includes the match
  (uses value_high >= param instead of value_low > param.UpperValue)
- le (less or equal) with exact instant incorrectly excludes the match
  (uses value_high < param.UpperValue which is always false when Lower==Upper)

Tests cover both precision levels:
1. Date-precision: Patient.birthDate (YYYY-MM-DD stored as day range)
2. Instant-precision: Observation.effectiveDateTime (exact point in time)
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.fhir_client import FHIRClient
from utils.assertions import FHIRAssertions
from fixtures.resource_generators import FHIRResourceGenerator


KNOWN_BIRTHDATE = "1993-06-15"
KNOWN_INSTANT = "2025-06-15T10:30:00Z"


@pytest.fixture
def client():
    return FHIRClient()


@pytest.fixture
def assertions():
    return FHIRAssertions()


@pytest.fixture
def date_patient(client, assertions):
    """Patient with a known birthDate for boundary testing."""
    patient = FHIRResourceGenerator.generate_patient(
        name=[{"family": "DateBoundaryExact", "given": ["Probe"]}],
        gender="female",
        birthDate=KNOWN_BIRTHDATE,
    )
    resp = client.create(patient)
    created = assertions.assert_created(resp, "Patient")
    yield created
    try:
        client.delete("Patient", created["id"])
    except Exception:
        pass


@pytest.fixture
def instant_obs(client, assertions):
    """Patient + Observation with a known effectiveDateTime."""
    patient = FHIRResourceGenerator.generate_patient(
        name=[{"family": "InstantBoundaryExact", "given": ["Probe"]}],
    )
    resp = client.create(patient)
    pat = assertions.assert_created(resp, "Patient")

    obs_resource = FHIRResourceGenerator.generate_observation(
        patient_ref=FHIRResourceGenerator.generate_reference("Patient", pat["id"]),
        effectiveDateTime=KNOWN_INSTANT,
    )
    resp = client.create(obs_resource)
    obs = assertions.assert_created(resp, "Observation")

    yield {"patient": pat, "observation": obs}

    try:
        client.delete("Observation", obs["id"])
    except Exception:
        pass
    try:
        client.delete("Patient", pat["id"])
    except Exception:
        pass


def _bundle_ids(bundle):
    """Extract resource IDs from match entries."""
    return [
        e["resource"]["id"]
        for e in bundle.get("entry", [])
        if e.get("search", {}).get("mode", "match") == "match"
    ]


# ---------------------------------------------------------------------------
# Date-precision boundary tests (Patient.birthDate = YYYY-MM-DD)
# ---------------------------------------------------------------------------
class TestDateBoundary:
    """Exact boundary tests for date-precision search parameters."""

    def test_eq_exact_date(self, client, assertions, date_patient):
        """eq with exact birthDate should match."""
        resp = client.search("Patient", {
            "family": "DateBoundaryExact",
            "birthdate": KNOWN_BIRTHDATE,
        })
        bundle = assertions.assert_bundle(resp, "Patient")
        assert date_patient["id"] in _bundle_ids(bundle)

    def test_ne_exact_date(self, client, assertions, date_patient):
        """ne with exact birthDate should NOT match."""
        resp = client.search("Patient", {
            "family": "DateBoundaryExact",
            "birthdate": f"ne{KNOWN_BIRTHDATE}",
        })
        bundle = assertions.assert_bundle(resp)
        assert date_patient["id"] not in _bundle_ids(bundle)

    def test_gt_exact_date_no_match(self, client, assertions, date_patient):
        """gt with exact birthDate should NOT match (value is not greater than itself)."""
        resp = client.search("Patient", {
            "family": "DateBoundaryExact",
            "birthdate": f"gt{KNOWN_BIRTHDATE}",
        })
        bundle = assertions.assert_bundle(resp)
        assert date_patient["id"] not in _bundle_ids(bundle)

    def test_lt_exact_date_no_match(self, client, assertions, date_patient):
        """lt with exact birthDate should NOT match (value is not less than itself)."""
        resp = client.search("Patient", {
            "family": "DateBoundaryExact",
            "birthdate": f"lt{KNOWN_BIRTHDATE}",
        })
        bundle = assertions.assert_bundle(resp)
        assert date_patient["id"] not in _bundle_ids(bundle)

    def test_ge_exact_date(self, client, assertions, date_patient):
        """ge with exact birthDate should match."""
        resp = client.search("Patient", {
            "family": "DateBoundaryExact",
            "birthdate": f"ge{KNOWN_BIRTHDATE}",
        })
        bundle = assertions.assert_bundle(resp, "Patient")
        assert date_patient["id"] in _bundle_ids(bundle)

    def test_le_exact_date(self, client, assertions, date_patient):
        """le with exact birthDate should match."""
        resp = client.search("Patient", {
            "family": "DateBoundaryExact",
            "birthdate": f"le{KNOWN_BIRTHDATE}",
        })
        bundle = assertions.assert_bundle(resp, "Patient")
        assert date_patient["id"] in _bundle_ids(bundle)

    # Sanity checks: off-by-one day should match the complementary operator
    def test_gt_day_before(self, client, assertions, date_patient):
        """gt with the day before should match."""
        resp = client.search("Patient", {
            "family": "DateBoundaryExact",
            "birthdate": "gt1993-06-14",
        })
        bundle = assertions.assert_bundle(resp, "Patient")
        assert date_patient["id"] in _bundle_ids(bundle)

    def test_lt_day_after(self, client, assertions, date_patient):
        """lt with the day after should match."""
        resp = client.search("Patient", {
            "family": "DateBoundaryExact",
            "birthdate": "lt1993-06-16",
        })
        bundle = assertions.assert_bundle(resp, "Patient")
        assert date_patient["id"] in _bundle_ids(bundle)

    def test_gt_day_after_no_match(self, client, assertions, date_patient):
        """gt with the day after should NOT match."""
        resp = client.search("Patient", {
            "family": "DateBoundaryExact",
            "birthdate": "gt1993-06-16",
        })
        bundle = assertions.assert_bundle(resp)
        assert date_patient["id"] not in _bundle_ids(bundle)

    def test_lt_day_before_no_match(self, client, assertions, date_patient):
        """lt with the day before should NOT match."""
        resp = client.search("Patient", {
            "family": "DateBoundaryExact",
            "birthdate": "lt1993-06-14",
        })
        bundle = assertions.assert_bundle(resp)
        assert date_patient["id"] not in _bundle_ids(bundle)


# ---------------------------------------------------------------------------
# Instant-precision boundary tests (Observation.effectiveDateTime)
# ---------------------------------------------------------------------------
class TestInstantBoundary:
    """Exact boundary tests for instant-precision search parameters."""

    def test_eq_exact_instant(self, client, assertions, instant_obs):
        """eq with exact effectiveDateTime should match."""
        resp = client.search("Observation", {
            "subject": f"Patient/{instant_obs['patient']['id']}",
            "date": KNOWN_INSTANT,
        })
        bundle = assertions.assert_bundle(resp, "Observation")
        assert instant_obs["observation"]["id"] in _bundle_ids(bundle)

    def test_ne_exact_instant(self, client, assertions, instant_obs):
        """ne with exact effectiveDateTime should NOT match."""
        resp = client.search("Observation", {
            "subject": f"Patient/{instant_obs['patient']['id']}",
            "date": f"ne{KNOWN_INSTANT}",
        })
        bundle = assertions.assert_bundle(resp)
        assert instant_obs["observation"]["id"] not in _bundle_ids(bundle)

    def test_gt_exact_instant_no_match(self, client, assertions, instant_obs):
        """gt with exact effectiveDateTime should NOT match."""
        resp = client.search("Observation", {
            "subject": f"Patient/{instant_obs['patient']['id']}",
            "date": f"gt{KNOWN_INSTANT}",
        })
        bundle = assertions.assert_bundle(resp)
        assert instant_obs["observation"]["id"] not in _bundle_ids(bundle)

    def test_lt_exact_instant_no_match(self, client, assertions, instant_obs):
        """lt with exact effectiveDateTime should NOT match."""
        resp = client.search("Observation", {
            "subject": f"Patient/{instant_obs['patient']['id']}",
            "date": f"lt{KNOWN_INSTANT}",
        })
        bundle = assertions.assert_bundle(resp)
        assert instant_obs["observation"]["id"] not in _bundle_ids(bundle)

    def test_ge_exact_instant(self, client, assertions, instant_obs):
        """ge with exact effectiveDateTime should match."""
        resp = client.search("Observation", {
            "subject": f"Patient/{instant_obs['patient']['id']}",
            "date": f"ge{KNOWN_INSTANT}",
        })
        bundle = assertions.assert_bundle(resp, "Observation")
        assert instant_obs["observation"]["id"] in _bundle_ids(bundle)

    def test_le_exact_instant(self, client, assertions, instant_obs):
        """le with exact effectiveDateTime should match."""
        resp = client.search("Observation", {
            "subject": f"Patient/{instant_obs['patient']['id']}",
            "date": f"le{KNOWN_INSTANT}",
        })
        bundle = assertions.assert_bundle(resp, "Observation")
        assert instant_obs["observation"]["id"] in _bundle_ids(bundle)

    # Sanity checks: one second off should match the complementary operator
    def test_gt_one_second_before(self, client, assertions, instant_obs):
        """gt with one second before should match."""
        resp = client.search("Observation", {
            "subject": f"Patient/{instant_obs['patient']['id']}",
            "date": "gt2025-06-15T10:29:59Z",
        })
        bundle = assertions.assert_bundle(resp, "Observation")
        assert instant_obs["observation"]["id"] in _bundle_ids(bundle)

    def test_lt_one_second_after(self, client, assertions, instant_obs):
        """lt with one second after should match."""
        resp = client.search("Observation", {
            "subject": f"Patient/{instant_obs['patient']['id']}",
            "date": "lt2025-06-15T10:30:01Z",
        })
        bundle = assertions.assert_bundle(resp, "Observation")
        assert instant_obs["observation"]["id"] in _bundle_ids(bundle)

    def test_gt_one_second_after_no_match(self, client, assertions, instant_obs):
        """gt with one second after should NOT match."""
        resp = client.search("Observation", {
            "subject": f"Patient/{instant_obs['patient']['id']}",
            "date": "gt2025-06-15T10:30:01Z",
        })
        bundle = assertions.assert_bundle(resp)
        assert instant_obs["observation"]["id"] not in _bundle_ids(bundle)

    def test_lt_one_second_before_no_match(self, client, assertions, instant_obs):
        """lt with one second before should NOT match."""
        resp = client.search("Observation", {
            "subject": f"Patient/{instant_obs['patient']['id']}",
            "date": "lt2025-06-15T10:29:59Z",
        })
        bundle = assertions.assert_bundle(resp)
        assert instant_obs["observation"]["id"] not in _bundle_ids(bundle)


# ---------------------------------------------------------------------------
# Cross-precision: instant param against date-stored value
# ---------------------------------------------------------------------------
class TestCrossPrecisionBoundary:
    """Test instant-precision search param against date-precision stored value.

    The server converts date-precision values to UTC using Europe/Berlin
    (W. Europe Standard Time).  For June dates (CEST = UTC+2):

        birthDate '1993-06-15' is stored as:
          value_low  = 1993-06-14T22:00:00Z   (midnight CEST → UTC)
          value_high = 1993-06-15T22:00:00Z   (midnight+1d CEST → UTC)

    These tests use the actual UTC boundaries so they are timezone-correct.
    """

    # The actual UTC boundaries for '1993-06-15' in CEST (UTC+2)
    RANGE_LOW = "1993-06-14T22:00:00Z"    # midnight CEST in UTC
    RANGE_HIGH = "1993-06-15T22:00:00Z"   # midnight+1d CEST in UTC
    RANGE_MID = "1993-06-15T10:00:00Z"    # midpoint inside the range

    def test_ge_range_low(self, client, assertions, date_patient):
        """ge with exact value_low should match."""
        resp = client.search("Patient", {
            "family": "DateBoundaryExact",
            "birthdate": f"ge{self.RANGE_LOW}",
        })
        bundle = assertions.assert_bundle(resp, "Patient")
        assert date_patient["id"] in _bundle_ids(bundle)

    def test_le_range_high(self, client, assertions, date_patient):
        """le with exact value_high should match."""
        resp = client.search("Patient", {
            "family": "DateBoundaryExact",
            "birthdate": f"le{self.RANGE_HIGH}",
        })
        bundle = assertions.assert_bundle(resp, "Patient")
        assert date_patient["id"] in _bundle_ids(bundle)

    def test_gt_range_high_no_match(self, client, assertions, date_patient):
        """gt with exact value_high should NOT match (nothing above the range)."""
        resp = client.search("Patient", {
            "family": "DateBoundaryExact",
            "birthdate": f"gt{self.RANGE_HIGH}",
        })
        bundle = assertions.assert_bundle(resp)
        assert date_patient["id"] not in _bundle_ids(bundle)

    def test_lt_range_low_no_match(self, client, assertions, date_patient):
        """lt with exact value_low should NOT match (nothing below the range)."""
        resp = client.search("Patient", {
            "family": "DateBoundaryExact",
            "birthdate": f"lt{self.RANGE_LOW}",
        })
        bundle = assertions.assert_bundle(resp)
        assert date_patient["id"] not in _bundle_ids(bundle)

    def test_gt_midpoint_no_match(self, client, assertions, date_patient):
        """gt with a point inside the range should NOT match (range is not entirely above)."""
        resp = client.search("Patient", {
            "family": "DateBoundaryExact",
            "birthdate": f"gt{self.RANGE_MID}",
        })
        bundle = assertions.assert_bundle(resp)
        assert date_patient["id"] not in _bundle_ids(bundle)

    def test_lt_midpoint_no_match(self, client, assertions, date_patient):
        """lt with a point inside the range should NOT match (range is not entirely below)."""
        resp = client.search("Patient", {
            "family": "DateBoundaryExact",
            "birthdate": f"lt{self.RANGE_MID}",
        })
        bundle = assertions.assert_bundle(resp)
        assert date_patient["id"] not in _bundle_ids(bundle)
