#!/usr/bin/env python3
"""
IPv4 NAT Router - Main Entry Point

A lightweight user-mode IPv4 NAT router implemented with Scapy.
Captures packets, performs NAT translation, and forwards between interfaces.

Usage:
    # Enable IP forwarding first
    sudo sysctl -w net.ipv4.ip_forward=1
    
    # Run router on eth0 with NAT
    sudo python3 router.py --interface eth0 --nat-mode
    
    # Run router on multiple interfaces
    sudo python3 router.py --interface veth_host_a --interface veth_host_b --nat-mode
    
    # Or use default settings
    sudo python3 router.py
"""

import sys
import argparse
import logging
import subprocess
import threading
from typing import Optional


def load_system_routes(route_table, interface: str = None) -> tuple:
    """Load system routes into the router's route table
    
    Args:
        route_table: RouteTable instance
        interface: Optional network interface to filter routes (if None, loads all routes)
    
    Returns:
        Tuple of (routes_loaded, gateway_interfaces, internal_networks) where:
        - routes_loaded: number of routes added
        - gateway_interfaces: set of interface names connected to gateways
        - internal_networks: list of internal network CIDR ranges
    """
    try:
        result = subprocess.run(
            ['ip', 'route', 'show'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        route_count = 0
        gateway_interfaces = set()
        internal_networks = set()
        
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            
            # Parse route line
            # Format: DESTINATION via GATEWAY dev INTERFACE ...
            # Example: default via 172.16.63.253 dev eth0 proto dhcp src 172.16.35.103 metric 100
            # Direct route: 10.0.0.0/24 dev veth_host_a proto kernel scope link src 10.0.0.1
            parts = line.split()
            if len(parts) < 2:
                continue
            
            destination = parts[0] if parts[0] != 'default' else '0.0.0.0/0'
            
            # Find gateway and interface
            gateway = None
            route_iface = None
            
            for i, part in enumerate(parts):
                if part == 'via' and i + 1 < len(parts):
                    gateway = parts[i + 1]
                elif part == 'dev' and i + 1 < len(parts):
                    route_iface = parts[i + 1]
            
            # Skip if no interface found
            if route_iface is None:
                continue
            
            # Track gateway interfaces (interfaces connected to a gateway)
            if gateway is not None:
                gateway_interfaces.add(route_iface)
                # If no specific interface filter, or this route matches the filter
                if interface is None or route_iface == interface:
                    if gateway is None:
                        gateway = '0.0.0.0'
                    
                    route_table.add_route(destination, gateway, route_iface, is_direct=False)
                    route_count += 1
            else:
                # Direct route (no gateway)
                if interface is None or route_iface == interface:
                    # Mark this as an internal network (direct route)
                    internal_networks.add(destination)
                    route_table.add_route(destination, '0.0.0.0', route_iface, is_direct=True)
                    route_count += 1
        
        return (route_count, gateway_interfaces, list(internal_networks))
    except Exception as e:
        logging.getLogger(__name__).warning(f"Failed to load system routes: {e}")
        return (0, set(), [])


def main():
    """Main entry point for the router"""
    parser = argparse.ArgumentParser(
        description="IPv4 NAT Router - User-mode packet forwarding with address translation"
    )
    parser.add_argument(
        '--interface',
        action='append',
        dest='interfaces',
        help='Network interface(s) for routing (can be specified multiple times)'
    )
    parser.add_argument(
        '--nat-mode',
        action='store_true',
        default=True,
        help='Enable NAT mode with source address translation (default: enabled)'
    )
    parser.add_argument(
        '--no-nat',
        action='store_true',
        help='Disable NAT mode, forward without translation'
    )
    parser.add_argument(
        '--log-level',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level (default: INFO)'
    )
    parser.add_argument(
        '--log-file',
        default=None,
        help='Log file path (default: log to console)'
    )
    
    args = parser.parse_args()
    
    # If no interfaces specified, use defaults
    if not args.interfaces:
        args.interfaces = ['eth0']
    
    # Configure logging
    log_level = getattr(logging, args.log_level)
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    if args.log_file:
        logging.basicConfig(
            level=log_level,
            format=log_format,
            filename=args.log_file,
            filemode='a'
        )
    else:
        logging.basicConfig(
            level=log_level,
            format=log_format
        )
    
    logger = logging.getLogger(__name__)
    logger.info("Starting IPv4 NAT Router")
    
    # Determine NAT mode
    nat_enabled = args.nat_mode and not args.no_nat
    
    try:
        # Import router components
        from router.packet_handler import PacketHandler
        from router.forwarding import IPv4Forwarder
        from router.nat_engine import NATEngine
        from router.route_table import RouteTable
        
        logger.info(f"Initializing router on interfaces: {', '.join(args.interfaces)}")
        logger.info(f"NAT mode: {'enabled' if nat_enabled else 'disabled'}")
        
        # Initialize components
        route_table = RouteTable()
        nat_engine = NATEngine()
        
        # Load system routes (use first interface as reference, or None to load all)
        routes_loaded, gateway_ifaces, internal_networks = load_system_routes(route_table)
        logger.info(f"Loaded {routes_loaded} system routes into router table")
        logger.info(f"Detected gateway interfaces: {gateway_ifaces if gateway_ifaces else 'none'}")
        logger.info(f"Detected internal networks: {internal_networks if internal_networks else 'none'}")
        
        # Create forwarder with internal networks list for NAT exclusion
        forwarder = IPv4Forwarder(route_table, nat_engine, nat_enabled, internal_networks)
        
        # Check for default gateway
        default_gw = route_table.get_default_gateway()
        if default_gw:
            gw_ip, gw_iface = default_gw
            logger.info(f"Default gateway: {gw_ip} via {gw_iface}")
            # Add default gateway interface to monitored interfaces if not already present
            if gw_iface not in args.interfaces:
                logger.info(f"Adding default gateway interface {gw_iface} to monitored interfaces")
                args.interfaces.append(gw_iface)
        
        # Create packet handlers for all interfaces
        handlers = []
        threads = []
        for interface in args.interfaces:
            try:
                handler = PacketHandler(interface, forwarder)
                handlers.append(handler)
                logger.info(f"Created handler for interface {interface}")
            except ValueError as e:
                logger.error(f"Failed to create handler for {interface}: {e}")
        
        if not handlers:
            logger.error("No valid interfaces found for routing")
            sys.exit(1)
        
        # Start packet capture and forwarding on all interfaces in separate threads
        logger.info("Starting packet capture and forwarding on all interfaces")
        for handler in handlers:
            thread = threading.Thread(target=handler.start, daemon=True)
            thread.start()
            threads.append(thread)
            logger.info(f"Started handler thread for {handler.interface}")
        
        # Keep the main thread alive while handlers run in background
        while True:
            try:
                import time
                time.sleep(1)
            except KeyboardInterrupt:
                raise
        
    except ImportError as e:
        logger.error(f"Failed to import router modules: {e}")
        logger.error("Make sure router/ directory and its modules are present")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Router shutting down...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
