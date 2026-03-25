#!/usr/bin/env python3
"""
Integration test script - demonstrates using test.py HTTP API

This script can be run from an external machine to test the NAT router
through test.py's HTTP interface.

Usage:
    python integration_test.py http://172.16.39.47:8888
"""

import sys
import json
import time
from typing import Dict, Any
import requests


class TestClient:
    """HTTP client for test.py API"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
    
    def health_check(self) -> bool:
        """Check if test server is healthy"""
        try:
            resp = self.session.get(f"{self.base_url}/health", timeout=5)
            return resp.status_code == 200
        except Exception as e:
            print(f"Health check failed: {e}")
            return False
    
    def get_config(self) -> Dict[str, Any]:
        """Get test configuration"""
        resp = self.session.get(f"{self.base_url}/config", timeout=5)
        return resp.json()
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all test cases"""
        resp = self.session.post(f"{self.base_url}/test/all", timeout=60)
        return resp.json()
    
    def run_single_test(self, test_name: str) -> Dict[str, Any]:
        """Run a single test case"""
        resp = self.session.post(f"{self.base_url}/test/{test_name}", timeout=30)
        return resp.json()
    
    def get_results(self) -> Dict[str, Any]:
        """Get last test results"""
        resp = self.session.get(f"{self.base_url}/test/results", timeout=5)
        return resp.json()
    
    def get_debug_routes(self) -> Dict[str, Any]:
        """Get debug routing information"""
        resp = self.session.get(f"{self.base_url}/debug/routes", timeout=5)
        return resp.json()


def print_test_result(result: Dict[str, Any], indent: int = 0):
    """Pretty print a test result"""
    prefix = "  " * indent
    
    status = "✓ PASS" if result.get("passed") else "✗ FAIL"
    name = result.get("name", "unknown")
    duration = result.get("duration_ms", 0)
    
    print(f"{prefix}{status} {name} ({duration:.1f}ms)")
    
    if not result.get("passed") and result.get("details"):
        details = result.get("details", {})
        if "error" in details:
            print(f"{prefix}  Error: {details['error']}")


def print_suite_results(results: Dict[str, Any]):
    """Pretty print test suite results"""
    total = results.get("total", 0)
    passed = results.get("passed", 0)
    failed = results.get("failed", 0)
    
    print()
    print("=" * 60)
    print(f"Test Results: {passed}/{total} passed, {failed} failed")
    print("=" * 60)
    
    for test in results.get("tests", []):
        print_test_result(test, indent=1)
    
    print()


def main():
    """Main integration test"""
    if len(sys.argv) < 2:
        print("Usage: python integration_test.py <test_server_url>")
        print("Example: python integration_test.py http://172.16.39.47:8888")
        sys.exit(1)
    
    url = sys.argv[1]
    client = TestClient(url)
    
    print(f"NAT Router Integration Tests")
    print(f"Test Server: {url}")
    print()
    
    # Step 1: Health check
    print("Step 1: Health check...")
    if not client.health_check():
        print("✗ Test server is not responding")
        sys.exit(1)
    print("✓ Test server is healthy")
    print()
    
    # Step 2: Get configuration
    print("Step 2: Retrieve configuration...")
    config = client.get_config()
    print(f"  Router IP: {config.get('router_ip')}")
    print(f"  Test Machine IP: {config.get('test_machine_ip')}")
    print(f"  Target Network: {config.get('target_network')}")
    print(f"  Target IP: {config.get('target_ip')}")
    print()
    
    # Step 3: Get debug info
    print("Step 3: Check debug information...")
    try:
        routes = client.get_debug_routes()
        route_list = routes.get("routes", [])
        if route_list:
            print("  Routes configured:")
            for route in route_list[:3]:  # Show first 3 routes
                print(f"    {route}")
            if len(route_list) > 3:
                print(f"    ... and {len(route_list) - 3} more")
    except Exception as e:
        print(f"  Warning: Could not retrieve routes: {e}")
    print()
    
    # Step 4: Run individual tests
    print("Step 4: Running individual tests...")
    test_names = [
        "route_table",
        "connectivity",
        "basic_nat",
        "tcp",
        "udp",
        "fragmentation",
    ]
    
    results = []
    for test_name in test_names:
        try:
            result = client.run_single_test(test_name)
            results.append(result)
            status = "✓" if result.get("passed") else "✗"
            print(f"  {status} {test_name}")
        except Exception as e:
            print(f"  ✗ {test_name}: {e}")
    
    print()
    
    # Step 5: Run full test suite
    print("Step 5: Running full test suite...")
    print("(This may take a minute)")
    
    suite_results = client.run_all_tests()
    print_suite_results(suite_results)
    
    # Step 6: Summary
    print("Summary:")
    passed = suite_results.get("passed", 0)
    total = suite_results.get("total", 0)
    failed = suite_results.get("failed", 0)
    
    if failed == 0:
        print(f"✓ All {total} tests passed!")
        return 0
    else:
        print(f"✗ {failed} test(s) failed out of {total}")
        print("\nFailed tests:")
        for test in suite_results.get("tests", []):
            if not test.get("passed"):
                print(f"  - {test.get('name')}: {test.get('details', {}).get('error', 'Unknown error')}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
