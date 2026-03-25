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
    
    # Or use default settings
    sudo python3 router.py
"""

import sys
import argparse
import logging
import subprocess
from typing import Optional


def load_system_routes(route_table, interface: str) -> int:
    """Load system routes into the router's route table
    
    Args:
        route_table: RouteTable instance
        interface: Network interface to filter routes
    
    Returns:
        Number of routes loaded
    """
    try:
        result = subprocess.run(
            ['ip', 'route', 'show'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        route_count = 0
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            
            # Parse route line
            # Format: DESTINATION via GATEWAY dev INTERFACE ...
            # Example: default via 172.16.63.253 dev eth0 proto dhcp src 172.16.35.103 metric 100
            parts = line.split()
            if len(parts) < 4:
                continue
            
            destination = parts[0] if parts[0] != 'default' else '0.0.0.0'
            
            # Find gateway and interface
            gateway = None
            route_iface = None
            
            for i, part in enumerate(parts):
                if part == 'via' and i + 1 < len(parts):
                    gateway = parts[i + 1]
                elif part == 'dev' and i + 1 < len(parts):
                    route_iface = parts[i + 1]
            
            # If no gateway (direct route), use 0.0.0.0
            if gateway is None:
                gateway = '0.0.0.0'
            if route_iface is None:
                route_iface = interface
            
            # Add route
            route_table.add_route(destination, gateway, route_iface)
            route_count += 1
        
        return route_count
    except Exception as e:
        logging.getLogger(__name__).warning(f"Failed to load system routes: {e}")
        return 0


def main():
    """Main entry point for the router"""
    parser = argparse.ArgumentParser(
        description="IPv4 NAT Router - User-mode packet forwarding with address translation"
    )
    parser.add_argument(
        '--interface',
        default='eth0',
        help='Primary network interface for routing (default: eth0)'
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
        
        logger.info(f"Initializing router on interface {args.interface}")
        logger.info(f"NAT mode: {'enabled' if nat_enabled else 'disabled'}")
        
        # Initialize components
        route_table = RouteTable()
        nat_engine = NATEngine()
        forwarder = IPv4Forwarder(route_table, nat_engine, nat_enabled)
        
        # Load system routes
        routes_loaded = load_system_routes(route_table, args.interface)
        logger.info(f"Loaded {routes_loaded} system routes into router table")
        
        packet_handler = PacketHandler(args.interface, forwarder)
        
        # Start packet capture and forwarding
        logger.info("Starting packet capture and forwarding")
        packet_handler.start()
        
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
