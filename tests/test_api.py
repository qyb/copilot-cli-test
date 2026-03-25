"""
Unit tests for NAT Router test suite

Run with: pytest tests/ -v
"""

import pytest
from unittest.mock import patch, MagicMock
from test import (
    BasicNATTest,
    TCPConnectionTest,
    UDPPacketTest,
    FragmentationTest,
    RouteTableTest,
    NetworkConnectivityTest,
    TCPURGTest,
    run_test_suite,
)


class TestNATTestCases:
    """Test the test cases themselves"""
    
    def test_route_table_test_structure(self):
        """Route table test should have proper structure"""
        test = RouteTableTest()
        assert test.name == "route_table"
        assert test.description
        assert test.get_result() is not None
    
    def test_basic_nat_test_structure(self):
        """Basic NAT test should have proper structure"""
        test = BasicNATTest()
        assert test.name == "basic_nat"
        assert test.description
        assert test.get_result() is not None
    
    def test_tcp_connection_test_structure(self):
        """TCP connection test should have proper structure"""
        test = TCPConnectionTest()
        assert test.name == "tcp_connection"
        assert test.description
    
    def test_udp_packet_test_structure(self):
        """UDP packet test should have proper structure"""
        test = UDPPacketTest()
        assert test.name == "udp_packet"
        assert test.description
    
    def test_fragmentation_test_structure(self):
        """Fragmentation test should have proper structure"""
        test = FragmentationTest()
        assert test.name == "fragmentation"
        assert test.description
    
    def test_network_connectivity_test_structure(self):
        """Network connectivity test should have proper structure"""
        test = NetworkConnectivityTest()
        assert test.name == "network_connectivity"
        assert test.description
    
    def test_tcp_urg_test_structure(self):
        """TCP URG test should have proper structure"""
        test = TCPURGTest()
        assert test.name == "tcp_urg"
        assert test.description


class TestTestResults:
    """Test result format and structure"""
    
    def test_test_result_has_required_fields(self):
        """Test result should have all required fields"""
        test = RouteTableTest()
        test.run()
        result = test.get_result()
        
        assert "name" in result
        assert "description" in result
        assert "passed" in result
        assert "details" in result
        assert "timestamp" in result
    
    def test_test_result_boolean_passed(self):
        """Test result 'passed' field should be boolean"""
        test = RouteTableTest()
        test.run()
        result = test.get_result()
        
        assert isinstance(result["passed"], bool)


class TestTestSuite:
    """Test the test suite runner"""
    
    def test_test_suite_factory(self):
        """Test suite should create properly structured tests"""
        # Just verify the factory works without running full suite
        from test import get_all_tests
        tests = get_all_tests()
        
        assert len(tests) > 0
        assert all(hasattr(t, 'run') for t in tests)
        assert all(hasattr(t, 'name') for t in tests)
        assert all(hasattr(t, 'get_result') for t in tests)


class TestConfigValues:
    """Test configuration values"""
    
    def test_router_ip_not_empty(self):
        """Router IP should be configured"""
        from test import TestConfig as TC
        assert TC.ROUTER_IP
    
    def test_test_ip_not_empty(self):
        """Test machine IP should be configured"""
        from test import TestConfig as TC
        assert TC.TEST_IP
    
    def test_target_ip_not_empty(self):
        """Target IP should be configured"""
        from test import TestConfig as TC
        assert TC.TARGET_IP
    
    def test_ips_are_different(self):
        """Router IP and test IP should be different"""
        from test import TestConfig as TC
        assert TC.ROUTER_IP != TC.TEST_IP
