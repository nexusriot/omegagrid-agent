import uuid as uuid_mod

import pytest

from skills.uuid_gen import UuidGenSkill


@pytest.fixture
def skill():
    return UuidGenSkill()


def _is_valid_uuid(s: str, version: int) -> bool:
    try:
        u = uuid_mod.UUID(s)
    except (ValueError, AttributeError):
        return False
    return u.version == version


class TestVersions:
    def test_v4_default(self, skill):
        out = skill.execute()
        assert out["version"] == 4
        assert out["count"] == 1
        assert len(out["uuids"]) == 1
        assert _is_valid_uuid(out["uuids"][0], 4)

    def test_v1(self, skill):
        out = skill.execute(version=1)
        assert _is_valid_uuid(out["uuids"][0], 1)

    def test_v4_explicit(self, skill):
        out = skill.execute(version=4)
        assert _is_valid_uuid(out["uuids"][0], 4)

    def test_v3_deterministic(self, skill):
        out1 = skill.execute(version=3, namespace="dns", name="example.com")
        out2 = skill.execute(version=3, namespace="dns", name="example.com")
        # v3 with same namespace+name must be deterministic
        assert out1["uuids"][0] == out2["uuids"][0]
        assert _is_valid_uuid(out1["uuids"][0], 3)

    def test_v5_deterministic(self, skill):
        out1 = skill.execute(version=5, namespace="dns", name="example.com")
        out2 = skill.execute(version=5, namespace="dns", name="example.com")
        assert out1["uuids"][0] == out2["uuids"][0]
        assert _is_valid_uuid(out1["uuids"][0], 5)
        # Includes echo of namespace + name
        assert out1["namespace"] == "dns"
        assert out1["name"] == "example.com"

    def test_v3_different_namespace_yields_different_uuid(self, skill):
        a = skill.execute(version=3, namespace="dns", name="example.com")["uuids"][0]
        b = skill.execute(version=3, namespace="url", name="example.com")["uuids"][0]
        assert a != b


class TestBatch:
    def test_count_multiple(self, skill):
        out = skill.execute(version=4, count=10)
        assert out["count"] == 10
        assert len(out["uuids"]) == 10
        # All distinct (random v4)
        assert len(set(out["uuids"])) == 10

    @pytest.mark.parametrize("count", [0, -1, 51, 100])
    def test_count_out_of_range(self, skill, count):
        out = skill.execute(version=4, count=count)
        assert "error" in out


class TestErrors:
    @pytest.mark.parametrize("version", [0, 2, 6, 7, "abc"])
    def test_unsupported_version(self, skill, version):
        out = skill.execute(version=version)
        assert "error" in out

    def test_v3_missing_name(self, skill):
        out = skill.execute(version=3)
        assert "error" in out and "name" in out["error"]

    def test_v5_missing_name(self, skill):
        out = skill.execute(version=5)
        assert "error" in out and "name" in out["error"]

    def test_unknown_namespace(self, skill):
        out = skill.execute(version=5, namespace="bogus", name="x")
        assert "error" in out and "namespace" in out["error"]
