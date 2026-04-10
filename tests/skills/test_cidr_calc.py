import pytest

from skills.cidr_calc import CidrCalcSkill


@pytest.fixture
def skill():
    return CidrCalcSkill()


class TestIPv4:
    def test_24(self, skill):
        out = skill.execute(cidr="192.168.1.0/24")
        assert out["version"] == 4
        assert out["network_address"] == "192.168.1.0"
        assert out["broadcast_address"] == "192.168.1.255"
        assert out["netmask"] == "255.255.255.0"
        assert out["hostmask"] == "0.0.0.255"
        assert out["prefix_length"] == 24
        assert out["total_addresses"] == 256
        assert out["usable_hosts"] == 254
        assert out["first_host"] == "192.168.1.1"
        assert out["last_host"] == "192.168.1.254"
        assert out["is_private"] is True
        assert out["is_global"] is False

    def test_32_single_host(self, skill):
        out = skill.execute(cidr="10.1.2.3/32")
        assert out["total_addresses"] == 1
        assert out["usable_hosts"] == 1
        assert out["first_host"] == "10.1.2.3"
        assert out["last_host"] == "10.1.2.3"

    def test_31_rfc3021(self, skill):
        """RFC 3021: /31 point-to-point links count both addresses as usable."""
        out = skill.execute(cidr="10.0.0.0/31")
        assert out["total_addresses"] == 2
        assert out["usable_hosts"] == 2
        assert out["first_host"] == "10.0.0.0"
        assert out["last_host"] == "10.0.0.1"

    def test_strict_false_normalizes_host_bits(self, skill):
        # 192.168.1.5/24 has host bits set; ip_network(strict=False) normalizes
        out = skill.execute(cidr="192.168.1.5/24")
        assert out["network_address"] == "192.168.1.0"

    def test_loopback(self, skill):
        out = skill.execute(cidr="127.0.0.0/8")
        assert out["is_loopback"] is True
        assert out["is_private"] is True

    def test_public(self, skill):
        out = skill.execute(cidr="8.8.8.8/32")
        assert out["is_private"] is False
        assert out["is_global"] is True


class TestIPv6:
    def test_v6_basic(self, skill):
        out = skill.execute(cidr="2001:db8::/32")
        assert out["version"] == 6
        assert out["network_address"] == "2001:db8::"
        assert out["prefix_length"] == 32
        # IPv6 has no broadcast
        assert "broadcast_address" not in out
        # All addresses are "usable" in IPv6
        assert out["usable_hosts"] == out["total_addresses"]

    def test_v6_loopback(self, skill):
        out = skill.execute(cidr="::1/128")
        assert out["is_loopback"] is True
        assert out["total_addresses"] == 1


class TestCheckIp:
    def test_in_network(self, skill):
        out = skill.execute(cidr="192.168.1.0/24", check_ip="192.168.1.42")
        assert out["check_ip_in_network"] is True
        assert out["check_ip"] == "192.168.1.42"

    def test_not_in_network(self, skill):
        out = skill.execute(cidr="192.168.1.0/24", check_ip="10.0.0.1")
        assert out["check_ip_in_network"] is False

    def test_invalid_check_ip(self, skill):
        out = skill.execute(cidr="192.168.1.0/24", check_ip="not-an-ip")
        assert "check_ip_error" in out
        # Network info should still be present
        assert out["prefix_length"] == 24


class TestErrors:
    def test_empty_cidr(self, skill):
        assert "error" in skill.execute(cidr="")

    @pytest.mark.parametrize("bad", [
        "not-a-cidr",
        "999.999.999.999/24",
        "192.168.1.0/33",
        "garbage",
    ])
    def test_invalid_cidr(self, skill, bad):
        out = skill.execute(cidr=bad)
        assert "error" in out
