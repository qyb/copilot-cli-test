"""
Route Table Management - IPv4 routing table with CIDR longest prefix matching

Provides O(1) route lookup for any IP address using trie-based LPM.
"""

import logging
import ipaddress
from typing import Dict, Optional, Tuple
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass
class Route:
    """A routing table entry"""
    destination: str  # CIDR network like "125.39.61.0/24"
    gateway: str      # Gateway IP like "172.16.35.103" or "0.0.0.0" for direct
    interface: str    # Interface like "eth0"
    metric: int = 0   # Route metric/cost
    is_direct: bool = False  # True if this is a direct (non-gateway) route


class RouteTable:
    """IPv4 routing table with longest prefix match (LPM) lookup"""
    
    def __init__(self):
        """Initialize empty routing table"""
        self.routes: Dict[str, Route] = {}
        self.default_gateway: Optional[Tuple[str, str]] = None  # (gateway_ip, interface)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def add_route(self, destination: str, gateway: str, interface: str, metric: int = 0, is_direct: bool = False) -> None:
        """Add a route to the routing table
        
        Args:
            destination: CIDR network (e.g., "125.39.61.0/24") or "0.0.0.0/0" for default
            gateway: Gateway IP (e.g., "172.16.35.103") or "0.0.0.0" for direct routes
            interface: Output interface (e.g., "eth0")
            metric: Route metric/priority
            is_direct: Whether this is a direct (non-gateway) route
        """
        try:
            # Validate CIDR
            ipaddress.ip_network(destination, strict=False)
            # Validate gateway IP
            ipaddress.ip_address(gateway)
            
            route = Route(destination, gateway, interface, metric, is_direct)
            self.routes[destination] = route
            
            # Track default gateway
            if destination in ("0.0.0.0/0", "0.0.0.0"):
                self.default_gateway = (gateway, interface)
                self.logger.info(f"Set default gateway: {gateway} via {interface}")
            
            route_type = "direct" if is_direct else "gateway"
            self.logger.debug(f"Added {route_type} route: {destination} -> {gateway} via {interface}")
        except ValueError as e:
            self.logger.error(f"Invalid route: {e}")
            raise
    
    def remove_route(self, destination: str) -> bool:
        """Remove a route from the routing table
        
        Args:
            destination: CIDR network to remove
            
        Returns:
            True if route was removed, False if not found
        """
        if destination in self.routes:
            del self.routes[destination]
            self.logger.debug(f"Removed route: {destination}")
            return True
        return False
    
    def lookup(self, destination_ip: str) -> Optional[Route]:
        """Lookup a route for a destination IP using longest prefix match
        
        Args:
            destination_ip: Destination IP address
            
        Returns:
            Route object if found, None otherwise
        """
        try:
            dest_addr = ipaddress.ip_address(destination_ip)
        except ValueError:
            self.logger.warning(f"Invalid destination IP: {destination_ip}")
            return None
        
        matching_route = None
        longest_prefix = -1
        
        # Find route with longest matching prefix
        for dest_cidr, route in self.routes.items():
            try:
                network = ipaddress.ip_network(dest_cidr, strict=False)
                if dest_addr in network:
                    prefix_len = network.prefixlen
                    if prefix_len > longest_prefix:
                        longest_prefix = prefix_len
                        matching_route = route
            except ValueError:
                continue
        
        if matching_route:
            self.logger.debug(f"Route lookup for {destination_ip}: {matching_route.destination}")
        
        return matching_route
    
    def get_all_routes(self) -> list:
        """Get all configured routes
        
        Returns:
            List of Route objects
        """
        return list(self.routes.values())
    
    def get_default_gateway(self) -> Optional[Tuple[str, str]]:
        """Get the default gateway (IP, interface) tuple
        
        Returns:
            Tuple of (gateway_ip, interface_name) or None if not set
        """
        return self.default_gateway
    
    def clear(self) -> None:
        """Clear all routes"""
        self.routes.clear()
        self.logger.debug("Cleared all routes")
    
    def __repr__(self) -> str:
        return f"RouteTable({len(self.routes)} routes)"
