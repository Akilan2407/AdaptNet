"""
Smoke test to verify C agent and controller binary execution.
"""
import subprocess
import os

def test_c_agent_binary():
    bin_path = os.path.join(os.path.dirname(__file__), "../../bin/agent")
    assert os.path.exists(bin_path), "Agent binary must exist after 'make all'"
    result = subprocess.run([bin_path, "-v"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "Adaptive Network Traffic Management" in result.stdout

def test_c_controller_binary():
    bin_path = os.path.join(os.path.dirname(__file__), "../../bin/controller")
    assert os.path.exists(bin_path), "Controller binary must exist after 'make all'"
    result = subprocess.run([bin_path, "-v"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "Network Controller" in result.stdout
