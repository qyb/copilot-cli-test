"""
Router package - IPv4 NAT routing implementation

Core modules:
- route_table: IPv4 routing table with CIDR longest prefix matching
- nat_engine: Stateful NAT translation engine (SNAT/DNAT)
- forwarding: IPv4 forwarding logic with TTL/fragmentation handling
- packet_handler: Scapy-based packet capture and transmission
- utils: Helper functions (checksums, etc.)
"""

__version__ = "1.0.0"
__all__ = [
    "RouteTable",
    "NATEngine",
    "IPv4Forwarder",
    "PacketHandler",
]
