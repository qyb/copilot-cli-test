"""
NAT Engine - Stateful NAT translation with connection tracking

Implements SNAT (source NAT) and DNAT (destination NAT) with connection tracking,
automatic timeout cleanup, and support for TCP/UDP protocols.
"""

import logging
import time
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


logger = logging.getLogger(__name__)


class NATDirection(Enum):
    """NAT translation direction"""
    OUTBOUND = "outbound"  # Internal to external
    INBOUND = "inbound"    # External to internal


class ConnectionState(Enum):
    """TCP connection state for NAT tracking"""
    NONE = "none"
    SYN_SENT = "syn_sent"
    ESTABLISHED = "established"
    FIN_SENT = "fin_sent"
    CLOSED = "closed"


@dataclass
class NATMapping:
    """A NAT translation mapping entry"""
    protocol: str  # "tcp" or "udp"

    # Original packet info
    orig_src_ip: str
    orig_src_port: int
    orig_dst_ip: str
    orig_dst_port: int

    # Translated packet info
    nat_src_ip: str
    nat_src_port: int
    nat_dst_ip: str
    nat_dst_port: int

    # Connection tracking
    state: ConnectionState = ConnectionState.NONE
    created_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)

    # Statistics
    packets_out: int = 0
    packets_in: int = 0
    bytes_out: int = 0
    bytes_in: int = 0

    def is_expired(self, timeout: float) -> bool:
        """Check if this mapping has timed out"""
        return time.time() - self.last_seen > timeout

    def update_activity(self) -> None:
        """Update last activity timestamp"""
        self.last_seen = time.time()


class NATEngine:
    """Stateful NAT translation engine"""

    # Protocol-specific timeouts (seconds)
    TCP_ESTABLISHED_TIMEOUT = 3600  # 1 hour
    TCP_TRANSIENT_TIMEOUT = 120    # 2 minutes
    UDP_TIMEOUT = 300               # 5 minutes

    # Port allocation
    DYNAMIC_PORT_START = 45000
    DYNAMIC_PORT_END = 48500
    DYNAMIC_PORT_RANGE = range(DYNAMIC_PORT_START, DYNAMIC_PORT_END + 1)

    def __init__(self):
        """Initialize the NAT engine"""
        self.mappings: Dict[Tuple, NATMapping] = {}
        self.next_port = self.DYNAMIC_PORT_START
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.logger.info("NAT Engine initialized")

    def create_mapping(
        self,
        protocol: str,
        orig_src_ip: str,
        orig_src_port: int,
        orig_dst_ip: str,
        orig_dst_port: int,
        nat_src_ip: str,
        nat_src_port: Optional[int] = None,
        nat_dst_ip: Optional[str] = None,
        nat_dst_port: Optional[int] = None,
    ) -> NATMapping:
        """Create a new NAT mapping

        Args:
            protocol: "tcp" or "udp"
            orig_src_ip: Original source IP
            orig_src_port: Original source port
            orig_dst_ip: Original destination IP
            orig_dst_port: Original destination port
            nat_src_ip: NAT source IP (usually router's IP)
            nat_src_port: NAT source port (auto-assigned if None)
            nat_dst_ip: NAT destination IP (same as orig if None)
            nat_dst_port: NAT destination port (same as orig if None)

        Returns:
            New NATMapping object
        """
        # Auto-assign port if needed
        if nat_src_port is None:
            nat_src_port = self._allocate_port()

        # Keep destination unchanged if not specified
        if nat_dst_ip is None:
            nat_dst_ip = orig_dst_ip
        if nat_dst_port is None:
            nat_dst_port = orig_dst_port

        mapping = NATMapping(
            protocol=protocol,
            orig_src_ip=orig_src_ip,
            orig_src_port=orig_src_port,
            orig_dst_ip=orig_dst_ip,
            orig_dst_port=orig_dst_port,
            nat_src_ip=nat_src_ip,
            nat_src_port=nat_src_port,
            nat_dst_ip=nat_dst_ip,
            nat_dst_port=nat_dst_port,
        )

        # Store by outbound key
        key = self._make_key(protocol, orig_src_ip, orig_src_port, orig_dst_ip, orig_dst_port)
        self.mappings[key] = mapping

        self.logger.debug(
            f"Created NAT mapping: {orig_src_ip}:{orig_src_port} -> "
            f"{nat_src_ip}:{nat_src_port}"
        )

        return mapping

    def lookup_outbound(
        self,
        protocol: str,
        src_ip: str,
        src_port: int,
        dst_ip: str,
        dst_port: int,
    ) -> Optional[NATMapping]:
        """Lookup outbound mapping (internal to external)

        Args:
            protocol: "tcp" or "udp"
            src_ip: Source IP
            src_port: Source port
            dst_ip: Destination IP
            dst_port: Destination port

        Returns:
            NATMapping if found, None otherwise
        """
        key = self._make_key(protocol, src_ip, src_port, dst_ip, dst_port)
        return self.mappings.get(key)

    def lookup_inbound(
        self,
        protocol: str,
        dst_ip: str,
        dst_port: int,
    ) -> Optional[NATMapping]:
        """Lookup inbound mapping (external to internal)

        Searches for a mapping where nat_src_ip:nat_src_port matches
        the given destination address.

        Args:
            protocol: "tcp" or "udp"
            dst_ip: Destination IP (NAT address)
            dst_port: Destination port (NAT port)

        Returns:
            NATMapping if found, None otherwise
        """
        for mapping in self.mappings.values():
            if (mapping.protocol == protocol and
                mapping.nat_src_ip == dst_ip and
                mapping.nat_src_port == dst_port):
                return mapping
        return None

    def update_tcp_state(
        self,
        mapping: NATMapping,
        flags: str,
    ) -> None:
        """Update TCP connection state

        Args:
            mapping: NATMapping to update
            flags: TCP flags string (e.g., "S", "SA", "F", etc.)
        """
        if "S" in flags and "A" not in flags:
            # SYN without ACK
            mapping.state = ConnectionState.SYN_SENT
        elif "A" in flags:
            # ACK received
            if mapping.state == ConnectionState.SYN_SENT:
                mapping.state = ConnectionState.ESTABLISHED
        elif "F" in flags:
            # FIN
            mapping.state = ConnectionState.FIN_SENT

        mapping.update_activity()

    def cleanup_expired(self) -> int:
        """Clean up expired mappings

        Returns:
            Number of mappings removed
        """
        expired_keys = []

        for key, mapping in self.mappings.items():
            timeout = (
                self.TCP_ESTABLISHED_TIMEOUT
                if mapping.state == ConnectionState.ESTABLISHED
                else self.TCP_TRANSIENT_TIMEOUT
                if mapping.protocol == "tcp"
                else self.UDP_TIMEOUT
            )

            if mapping.is_expired(timeout):
                expired_keys.append(key)

        for key in expired_keys:
            del self.mappings[key]

        if expired_keys:
            self.logger.debug(f"Cleaned up {len(expired_keys)} expired mappings")

        return len(expired_keys)

    def get_stats(self) -> dict:
        """Get NAT engine statistics

        Returns:
            Dictionary with stats
        """
        total_mappings = len(self.mappings)
        tcp_count = sum(1 for m in self.mappings.values() if m.protocol == "tcp")
        udp_count = sum(1 for m in self.mappings.values() if m.protocol == "udp")

        total_packets_out = sum(m.packets_out for m in self.mappings.values())
        total_packets_in = sum(m.packets_in for m in self.mappings.values())
        total_bytes_out = sum(m.bytes_out for m in self.mappings.values())
        total_bytes_in = sum(m.bytes_in for m in self.mappings.values())

        return {
            "total_mappings": total_mappings,
            "tcp_mappings": tcp_count,
            "udp_mappings": udp_count,
            "packets_out": total_packets_out,
            "packets_in": total_packets_in,
            "bytes_out": total_bytes_out,
            "bytes_in": total_bytes_in,
        }

    def _make_key(
        self,
        protocol: str,
        src_ip: str,
        src_port: int,
        dst_ip: str,
        dst_port: int,
    ) -> Tuple:
        """Create a key for mapping lookup"""
        return (protocol, src_ip, src_port, dst_ip, dst_port)

    def _allocate_port(self) -> int:
        """Allocate a dynamic port

        Simple round-robin allocation. In production, this should be
        smarter about avoiding port conflicts.
        """
        port = self.next_port
        self.next_port += 1
        if self.next_port > self.DYNAMIC_PORT_END:
            self.next_port = self.DYNAMIC_PORT_START
        return port

    def __repr__(self) -> str:
        return f"NATEngine({len(self.mappings)} active mappings)"
