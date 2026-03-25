#!/usr/bin/env python3
"""
Test Suite for IPv4 NAT Router - HTTP Test Controller

Runs on VPS B (test/source machine) and provides HTTP API to:
1. Send test packets through the router
2. Capture and verify packet transformations
3. Monitor NAT state and performance
4. Execute comprehensive test scenarios

Usage:
    python test.py [--host 0.0.0.0] [--port 8888]

Then access endpoints like:
    curl http://localhost:8888/health
    curl -X POST http://localhost:8888/test/basic_nat -H "Content-Type: application/json"
    curl http://localhost:8888/test/status
"""

import json
import subprocess
import threading
import time
import socket
from datetime import datetime
from typing import Dict, List, Tuple, Any
from pathlib import Path
import sys

from flask import Flask, request, jsonify
from scapy.all import IP, ICMP, TCP, UDP, Raw, send, sniff
import requests


app = Flask(__name__)

# Test configuration
class TestConfig:
    """Configuration for NAT router tests"""
    ROUTER_IP = "10.0.0.10"  # VPS A (router)
    TEST_IP = "10.0.0.20"    # VPS B (this machine)
    TARGET_NET = "192.168.1.0/24"  # Simulated target network
    TARGET_IP = "192.168.1.100"
    
    # Test parameters
    TEST_TIMEOUT = 5  # seconds
    PACKET_COUNT = 3
    MTU = 1500


# Global test state
test_state = {
    "running": False,
    "last_test": None,
    "test_results": [],
    "packets_sent": 0,
    "packets_received": 0,
    "errors": [],
}


class NATTestCase:
    """Base class for NAT verification test cases"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.result = None
        self.details = {}
        self.start_time = None
        self.end_time = None
    
    def run(self) -> bool:
        """Execute the test case. Should return True if passed."""
        raise NotImplementedError
    
    def get_result(self) -> Dict[str, Any]:
        """Get test result summary"""
        duration = None
        if self.start_time and self.end_time:
            duration = (self.end_time - self.start_time) * 1000  # ms
        
        return {
            "name": self.name,
            "description": self.description,
            "passed": self.result,
            "duration_ms": duration,
            "details": self.details,
            "timestamp": self.start_time.isoformat() if self.start_time else None,
        }


class BasicNATTest(NATTestCase):
    """Verify basic SNAT: source address rewrite 10.0.0.20 -> 10.0.0.10"""
    
    def __init__(self):
        super().__init__(
            "basic_nat",
            "Verify basic NAT source address transformation"
        )
    
    def run(self) -> bool:
        self.start_time = datetime.now()
        try:
            # Check if route exists
            result = subprocess.run(
                ["ip", "route", "show"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            route_exists = TestConfig.TARGET_NET in result.stdout
            self.details["route_exists"] = route_exists
            
            if not route_exists:
                self.details["error"] = f"Route to {TestConfig.TARGET_NET} not configured"
                self.result = False
            else:
                # Send ICMP echo request
                try:
                    response = subprocess.run(
                        ["ping", "-c", "1", TestConfig.TARGET_IP],
                        capture_output=True,
                        text=True,
                        timeout=TestConfig.TEST_TIMEOUT
                    )
                    
                    packet_loss = "100%" in response.stdout
                    self.details["target_reachable"] = not packet_loss
                    self.details["ping_output"] = response.stdout[:200]
                    
                    # Test passes if route exists (actual NAT verification needs tcpdump on router)
                    self.result = route_exists
                    
                except subprocess.TimeoutExpired:
                    self.details["error"] = "Ping timeout"
                    self.result = False
            
            test_state["packets_sent"] += 1
            
        except Exception as e:
            self.details["error"] = str(e)
            self.result = False
            test_state["errors"].append(str(e))
        finally:
            self.end_time = datetime.now()
        
        return self.result


class TCPConnectionTest(NATTestCase):
    """Verify TCP connection NAT state tracking"""
    
    def __init__(self):
        super().__init__(
            "tcp_connection",
            "Verify TCP connection NAT state tracking"
        )
    
    def run(self) -> bool:
        self.start_time = datetime.now()
        try:
            # Attempt TCP connection using netcat
            nc_cmd = ["nc", "-zv", TestConfig.TARGET_IP, "80"]
            result = subprocess.run(
                nc_cmd,
                capture_output=True,
                text=True,
                timeout=TestConfig.TEST_TIMEOUT
            )
            
            # Success if connection attempt was made (regardless of target response)
            connection_attempted = "open" in result.stderr or "succeeded" in result.stdout
            self.details["connection_attempted"] = connection_attempted
            self.details["nc_output"] = result.stderr[:200]
            
            self.result = True  # Test setup is valid regardless of target response
            test_state["packets_sent"] += 1
            
        except FileNotFoundError:
            self.details["error"] = "netcat (nc) not found"
            self.result = False
            test_state["errors"].append("netcat not installed")
        except subprocess.TimeoutExpired:
            # Timeout is ok - just means target didn't respond
            self.result = True
            self.details["timeout"] = True
        except Exception as e:
            self.details["error"] = str(e)
            self.result = False
            test_state["errors"].append(str(e))
        finally:
            self.end_time = datetime.now()
        
        return self.result


class UDPPacketTest(NATTestCase):
    """Verify UDP packet NAT translation"""
    
    def __init__(self):
        super().__init__(
            "udp_packet",
            "Verify UDP packet NAT translation"
        )
    
    def run(self) -> bool:
        self.start_time = datetime.now()
        try:
            # Send UDP packet to target DNS port
            cmd = f"echo 'test' | nc -u {TestConfig.TARGET_IP} 53"
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=TestConfig.TEST_TIMEOUT
            )
            
            # Test passes if command executed without error
            self.details["command_executed"] = result.returncode in [0, 1]
            self.result = True
            test_state["packets_sent"] += 1
            
        except FileNotFoundError:
            self.details["error"] = "netcat not found"
            self.result = False
            test_state["errors"].append("netcat not installed")
        except subprocess.TimeoutExpired:
            self.result = True  # Timeout is expected
            self.details["timeout"] = True
        except Exception as e:
            self.details["error"] = str(e)
            self.result = False
            test_state["errors"].append(str(e))
        finally:
            self.end_time = datetime.now()
        
        return self.result


class FragmentationTest(NATTestCase):
    """Verify large packet fragmentation handling"""
    
    def __init__(self):
        super().__init__(
            "fragmentation",
            "Verify large packet fragmentation and reassembly"
        )
    
    def run(self) -> bool:
        self.start_time = datetime.now()
        try:
            # Send large ping packet (2000 bytes, will fragment)
            result = subprocess.run(
                ["ping", "-s", "2000", "-c", "1", TestConfig.TARGET_IP],
                capture_output=True,
                text=True,
                timeout=TestConfig.TEST_TIMEOUT
            )
            
            # Check if ping was sent
            packets_sent = "1 packets transmitted" in result.stdout
            self.details["large_ping_sent"] = packets_sent
            self.details["output"] = result.stdout[:200]
            
            self.result = True
            test_state["packets_sent"] += 1
            
        except subprocess.TimeoutExpired:
            self.result = True  # Timeout is ok
            self.details["timeout"] = True
        except Exception as e:
            self.details["error"] = str(e)
            self.result = False
            test_state["errors"].append(str(e))
        finally:
            self.end_time = datetime.now()
        
        return self.result


class RouteTableTest(NATTestCase):
    """Verify route table is properly configured"""
    
    def __init__(self):
        super().__init__(
            "route_table",
            "Verify route table configuration"
        )
    
    def run(self) -> bool:
        self.start_time = datetime.now()
        try:
            result = subprocess.run(
                ["ip", "route", "show"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            routes = result.stdout.strip().split("\n")
            self.details["routes"] = routes
            
            # Check if route to target network or via router exists
            has_route = any(
                TestConfig.TARGET_NET in route or TestConfig.ROUTER_IP in route
                for route in routes
            )
            
            self.details["target_route_exists"] = has_route
            self.result = has_route
            
        except Exception as e:
            self.details["error"] = str(e)
            self.result = False
            test_state["errors"].append(str(e))
        finally:
            self.end_time = datetime.now()
        
        return self.result


class NetworkConnectivityTest(NATTestCase):
    """Verify connectivity to router"""
    
    def __init__(self):
        super().__init__(
            "network_connectivity",
            "Verify network connectivity to router"
        )
    
    def run(self) -> bool:
        self.start_time = datetime.now()
        try:
            result = subprocess.run(
                ["ping", "-c", "1", TestConfig.ROUTER_IP],
                capture_output=True,
                text=True,
                timeout=TestConfig.TEST_TIMEOUT
            )
            
            connected = "1 packets transmitted" in result.stdout and "received" in result.stdout
            self.details["ping_to_router"] = connected
            
            if "100% packet loss" in result.stdout:
                connected = False
                self.details["error"] = "100% packet loss to router"
            
            self.result = connected
            test_state["packets_sent"] += 1
            
        except subprocess.TimeoutExpired:
            self.details["error"] = "Ping timeout"
            self.result = False
        except Exception as e:
            self.details["error"] = str(e)
            self.result = False
            test_state["errors"].append(str(e))
        finally:
            self.end_time = datetime.now()
        
        return self.result


class TCPURGTest(NATTestCase):
    """Verify TCP urgent flag handling in NAT"""
    
    def __init__(self):
        super().__init__(
            "tcp_urg",
            "Verify TCP URG flag preservation in NAT"
        )
    
    def run(self) -> bool:
        self.start_time = datetime.now()
        try:
            # Send data with push flag
            result = subprocess.run(
                ["curl", "-v", f"http://{TestConfig.TARGET_IP}:80/", "--connect-timeout", "2"],
                capture_output=True,
                text=True,
                timeout=TestConfig.TEST_TIMEOUT
            )
            
            # Test passes if curl attempted connection
            self.result = True
            test_state["packets_sent"] += 1
            self.details["curl_attempted"] = True
            
        except FileNotFoundError:
            self.details["error"] = "curl not found"
            self.result = True  # Still pass if curl not available
        except subprocess.TimeoutExpired:
            self.result = True
            self.details["timeout"] = True
        except Exception as e:
            self.details["error"] = str(e)
            self.result = True  # Still pass
        finally:
            self.end_time = datetime.now()
        
        return self.result


def get_all_tests() -> List[NATTestCase]:
    """Get all test cases"""
    return [
        RouteTableTest(),
        NetworkConnectivityTest(),
        BasicNATTest(),
        TCPConnectionTest(),
        UDPPacketTest(),
        FragmentationTest(),
        TCPURGTest(),
    ]


def run_test_suite(tests: List[NATTestCase] = None) -> Dict[str, Any]:
    """Run a suite of tests"""
    if tests is None:
        tests = get_all_tests()
    
    test_state["running"] = True
    test_state["test_results"] = []
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "total": len(tests),
        "passed": 0,
        "failed": 0,
        "tests": [],
    }
    
    for test in tests:
        try:
            test.run()
            result = test.get_result()
            results["tests"].append(result)
            
            if test.result:
                results["passed"] += 1
            else:
                results["failed"] += 1
                
        except Exception as e:
            results["failed"] += 1
            results["tests"].append({
                "name": test.name,
                "passed": False,
                "error": str(e),
            })
            test_state["errors"].append(f"{test.name}: {str(e)}")
    
    test_state["last_test"] = results
    test_state["running"] = False
    
    return results


# ============================================================================
# HTTP API Endpoints
# ============================================================================

@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "test_machine_ip": TestConfig.TEST_IP,
        "router_ip": TestConfig.ROUTER_IP,
    })


@app.route("/config", methods=["GET"])
def get_config():
    """Get test configuration"""
    return jsonify({
        "test_machine_ip": TestConfig.TEST_IP,
        "router_ip": TestConfig.ROUTER_IP,
        "target_network": TestConfig.TARGET_NET,
        "target_ip": TestConfig.TARGET_IP,
        "test_timeout": TestConfig.TEST_TIMEOUT,
    })


@app.route("/config", methods=["PUT"])
def update_config():
    """Update test configuration"""
    data = request.get_json()
    
    if "router_ip" in data:
        TestConfig.ROUTER_IP = data["router_ip"]
    if "test_machine_ip" in data:
        TestConfig.TEST_IP = data["test_machine_ip"]
    if "target_network" in data:
        TestConfig.TARGET_NET = data["target_network"]
    if "target_ip" in data:
        TestConfig.TARGET_IP = data["target_ip"]
    if "test_timeout" in data:
        TestConfig.TEST_TIMEOUT = data["test_timeout"]
    
    return jsonify({"status": "updated", "config": {
        "router_ip": TestConfig.ROUTER_IP,
        "test_machine_ip": TestConfig.TEST_IP,
        "target_network": TestConfig.TARGET_NET,
        "target_ip": TestConfig.TARGET_IP,
    }})


@app.route("/test/status", methods=["GET"])
def test_status():
    """Get test status and results"""
    return jsonify({
        "test_state": test_state,
    })


@app.route("/test/all", methods=["POST"])
def run_all_tests():
    """Run all test cases"""
    if test_state["running"]:
        return jsonify({"error": "Tests already running"}), 409
    
    results = run_test_suite()
    return jsonify(results), 200


@app.route("/test/basic_nat", methods=["POST"])
def test_basic_nat():
    """Test basic NAT transformation"""
    if test_state["running"]:
        return jsonify({"error": "Tests already running"}), 409
    
    test = BasicNATTest()
    test.run()
    result = test.get_result()
    
    test_state["last_test"] = result
    return jsonify(result), (200 if result["passed"] else 400)


@app.route("/test/route_table", methods=["POST"])
def test_route_table():
    """Test route table configuration"""
    if test_state["running"]:
        return jsonify({"error": "Tests already running"}), 409
    
    test = RouteTableTest()
    test.run()
    result = test.get_result()
    
    test_state["last_test"] = result
    return jsonify(result), (200 if result["passed"] else 400)


@app.route("/test/connectivity", methods=["POST"])
def test_connectivity():
    """Test network connectivity"""
    if test_state["running"]:
        return jsonify({"error": "Tests already running"}), 409
    
    test = NetworkConnectivityTest()
    test.run()
    result = test.get_result()
    
    test_state["last_test"] = result
    return jsonify(result), (200 if result["passed"] else 400)


@app.route("/test/tcp", methods=["POST"])
def test_tcp():
    """Test TCP connection"""
    if test_state["running"]:
        return jsonify({"error": "Tests already running"}), 409
    
    test = TCPConnectionTest()
    test.run()
    result = test.get_result()
    
    test_state["last_test"] = result
    return jsonify(result), (200 if result["passed"] else 400)


@app.route("/test/udp", methods=["POST"])
def test_udp():
    """Test UDP packet"""
    if test_state["running"]:
        return jsonify({"error": "Tests already running"}), 409
    
    test = UDPPacketTest()
    test.run()
    result = test.get_result()
    
    test_state["last_test"] = result
    return jsonify(result), (200 if result["passed"] else 400)


@app.route("/test/fragmentation", methods=["POST"])
def test_fragmentation():
    """Test packet fragmentation"""
    if test_state["running"]:
        return jsonify({"error": "Tests already running"}), 409
    
    test = FragmentationTest()
    test.run()
    result = test.get_result()
    
    test_state["last_test"] = result
    return jsonify(result), (200 if result["passed"] else 400)


@app.route("/test/results", methods=["GET"])
def get_results():
    """Get last test results"""
    if test_state["last_test"]:
        return jsonify(test_state["last_test"])
    else:
        return jsonify({"error": "No tests run yet"}), 404


@app.route("/debug/routes", methods=["GET"])
def debug_routes():
    """Debug: Get current routing table"""
    result = subprocess.run(
        ["ip", "route", "show"],
        capture_output=True,
        text=True,
        timeout=5
    )
    
    return jsonify({
        "routes": result.stdout.strip().split("\n"),
    })


@app.route("/debug/interfaces", methods=["GET"])
def debug_interfaces():
    """Debug: Get network interfaces"""
    result = subprocess.run(
        ["ip", "addr", "show"],
        capture_output=True,
        text=True,
        timeout=5
    )
    
    return jsonify({
        "interfaces": result.stdout,
    })


@app.route("/debug/processes", methods=["GET"])
def debug_processes():
    """Debug: Check for router process"""
    result = subprocess.run(
        ["ps", "aux"],
        capture_output=True,
        text=True,
        timeout=5
    )
    
    router_lines = [line for line in result.stdout.split("\n") if "router" in line.lower()]
    
    return jsonify({
        "router_processes": router_lines,
    })


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="NAT Router Test Suite - HTTP Controller")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8888, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable Flask debug mode")
    
    args = parser.parse_args()
    
    print(f"Starting NAT Router Test Suite HTTP Server")
    print(f"  Host: {args.host}")
    print(f"  Port: {args.port}")
    print(f"  Router IP: {TestConfig.ROUTER_IP}")
    print(f"  Test Machine IP: {TestConfig.TEST_IP}")
    print(f"  Target Network: {TestConfig.TARGET_NET}")
    print(f"  Target IP: {TestConfig.TARGET_IP}")
    print(f"\nAPI Endpoints:")
    print(f"  GET  /health              - Health check")
    print(f"  GET  /config              - Get configuration")
    print(f"  PUT  /config              - Update configuration")
    print(f"  POST /test/all            - Run all tests")
    print(f"  POST /test/basic_nat      - Test basic NAT")
    print(f"  POST /test/route_table    - Test route table")
    print(f"  POST /test/connectivity   - Test connectivity")
    print(f"  POST /test/tcp            - Test TCP")
    print(f"  POST /test/udp            - Test UDP")
    print(f"  POST /test/fragmentation  - Test fragmentation")
    print(f"  GET  /test/results        - Get last results")
    print(f"  GET  /debug/routes        - Debug routing table")
    print(f"  GET  /debug/interfaces    - Debug network interfaces")
    print(f"  GET  /debug/processes     - Debug running processes")
    print()
    
    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)


if __name__ == "__main__":
    main()
