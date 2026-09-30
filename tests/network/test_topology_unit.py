"""
Unit tests for Mininet SmallLANTopology (Phase 2).
"""
import pytest
from network.topology.lan_topology import SmallLANTopology

def test_topology_default_scaling():
    topo = SmallLANTopology(num_hosts=5)
    assert len(topo.hosts()) == 5
    assert len(topo.switches()) == 1
    assert len(topo.links()) == 5

def test_topology_custom_scaling():
    topo = SmallLANTopology(num_hosts=20, bw=50.0, delay="5ms", loss=1.0)
    assert len(topo.hosts()) == 20
    assert len(topo.links()) == 20
    assert topo.bw == 50.0
    assert topo.delay == "5ms"
    assert topo.loss == 1.0

def test_topology_ip_address_assignment():
    topo = SmallLANTopology(num_hosts=5)
    assert topo.get_host_ip("h1") == "192.168.1.10"
    assert topo.get_host_ip("h2") == "192.168.1.11"
    assert topo.get_host_ip("h5") == "192.168.1.14"

def test_topology_bounds():
    # Min bounds = 2
    topo_min = SmallLANTopology(num_hosts=1)
    assert len(topo_min.hosts()) == 2

    # Max bounds = 50
    topo_max = SmallLANTopology(num_hosts=100)
    assert len(topo_max.hosts()) == 50
