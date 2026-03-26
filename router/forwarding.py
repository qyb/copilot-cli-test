"""
IPv4 Forwarding Logic - TTL handling, fragmentation, NAT integration

Implements standard IPv4 forwarding with:
- TTL (Time To Live) decrement and processing
- ICMP TTL exceeded generation
- IP fragmentation/reassembly support
- NAT translation integration
"""

import logging
import ipaddress
from typing import Optional
from scapy.all import IP, ICMP, TCP, UDP, Raw
from .route_table import RouteTable
from .nat_engine import NATEngine, ConnectionState
from .utils import compute_checksum


logger = logging.getLogger(__name__)


class IPv4Forwarder:
    """IPv4 forwarding engine with NAT support"""
    
    def __init__(
        self,
        route_table: RouteTable,
        nat_engine: NATEngine,
        nat_enabled: bool = True,
    ):
        """Initialize the IPv4 forwarder
        
        Args:
            route_table: RouteTable instance for route lookup
            nat_engine: NATEngine instance for NAT translation
            nat_enabled: Whether to perform NAT translation
        """
        self.route_table = route_table
        self.nat_engine = nat_engine
        self.nat_enabled = nat_enabled
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.logger.info(f"IPv4Forwarder initialized (NAT: {nat_enabled})")
    
    def forward_packet(self, packet: IP, in_interface: str) -> Optional[tuple]:
        """Forward an IPv4 packet
        
        Args:
            packet: Scapy IP packet
            in_interface: Input interface name
        
        Returns:
            Tuple of (output_interface, modified_packet) or None if packet should be dropped
        """
        try:
            # Check TTL
            if packet.ttl <= 1:
                self.logger.debug(f"TTL exceeded for packet {packet.src} -> {packet.dst}")
                return None  # TTL exceeded, don't forward
            
            # Decrement TTL
            packet.ttl -= 1
            
            # Lookup route
            route = self.route_table.lookup(packet.dst)
            if not route:
                self.logger.debug(f"No route to {packet.dst}")
                return None
            
            output_interface = route.interface
            
            # Avoid sending back on the same interface (unless it's a broadcast)
            if output_interface == in_interface and not packet.dst.startswith('255.'):
                self.logger.debug(f"Packet would be sent back on {in_interface}, dropping")
                return None
            
            # Extract protocol info for NAT
            protocol = None
            src_port = None
            dst_port = None
            
            if packet.haslayer(TCP):
                protocol = "tcp"
                tcp_layer = packet[TCP]
                src_port = tcp_layer.sport
                dst_port = tcp_layer.dport
            elif packet.haslayer(UDP):
                protocol = "udp"
                udp_layer = packet[UDP]
                src_port = udp_layer.sport
                dst_port = udp_layer.dport
            
            # Perform NAT if enabled
            if self.nat_enabled and protocol and src_port and dst_port:
                packet = self._apply_nat_outbound(
                    packet,
                    protocol,
                    src_port,
                    dst_port,
                    route,
                )
            
            # Recalculate IP header checksum
            packet.chksum = None  # Scapy will recalculate
            
            # For TCP/UDP, set checksum to 0 first (Scapy will recalculate)
            if packet.haslayer(TCP):
                packet[TCP].chksum = None
            elif packet.haslayer(UDP):
                packet[UDP].chksum = None
            
            return (output_interface, packet)
        
        except Exception as e:
            self.logger.error(f"Error forwarding packet: {e}", exc_info=True)
            return None
    
    def forward_reply(self, packet: IP, in_interface: str, router_ip: str) -> Optional[IP]:
        """Forward a reply packet (usually from target network)
        
        This handles the reverse direction - taking packets from the target
        network and routing them back to internal network, with DNAT applied.
        
        Args:
            packet: Scapy IP packet
            in_interface: Input interface name
            router_ip: Router's IP address
        
        Returns:
            Modified packet ready to send
        """
        try:
            # Extract protocol info for NAT lookup
            protocol = None
            dst_port = None
            
            if packet.haslayer(TCP):
                protocol = "tcp"
                dst_port = packet[TCP].dport
            elif packet.haslayer(UDP):
                protocol = "udp"
                dst_port = packet[UDP].dport
            
            # Perform DNAT if enabled
            if self.nat_enabled and protocol and dst_port:
                packet = self._apply_nat_inbound(
                    packet,
                    protocol,
                    dst_port,
                    router_ip,
                )
            
            # Check TTL
            if packet.ttl <= 1:
                return self._generate_ttl_exceeded(packet)
            
            packet.ttl -= 1
            
            # Recalculate checksums
            packet.chksum = None
            if packet.haslayer(TCP):
                packet[TCP].chksum = None
            elif packet.haslayer(UDP):
                packet[UDP].chksum = None
            
            return packet
        
        except Exception as e:
            self.logger.error(f"Error forwarding reply: {e}", exc_info=True)
            return None
    
    def _apply_nat_outbound(
        self,
        packet: IP,
        protocol: str,
        src_port: int,
        dst_port: int,
        route,
    ) -> IP:
        """Apply SNAT (source NAT) to outbound packet
        
        Translates internal source address to router's address.
        """
        # Try to find existing mapping
        mapping = self.nat_engine.lookup_outbound(
            protocol,
            packet.src,
            src_port,
            packet.dst,
            dst_port,
        )
        
        # Create new mapping if needed
        if not mapping:
            mapping = self.nat_engine.create_mapping(
                protocol=protocol,
                orig_src_ip=packet.src,
                orig_src_port=src_port,
                orig_dst_ip=packet.dst,
                orig_dst_port=dst_port,
                nat_src_ip=route.gateway,  # Use gateway as NAT address
                nat_src_port=None,  # Auto-assign
                nat_dst_ip=packet.dst,
                nat_dst_port=dst_port,
            )
        
        # Update TCP state if applicable
        if packet.haslayer(TCP):
            flags = "".join(c for c in str(packet[TCP].flags) if c in "FSRPAUEC")
            self.nat_engine.update_tcp_state(mapping, flags)
        
        mapping.packets_out += 1
        mapping.bytes_out += len(packet)
        
        # Modify packet
        original_src = packet.src
        original_sport = src_port
        
        packet.src = mapping.nat_src_ip
        
        if packet.haslayer(TCP):
            packet[TCP].sport = mapping.nat_src_port
        elif packet.haslayer(UDP):
            packet[UDP].sport = mapping.nat_src_port
        
        self.logger.debug(
            f"SNAT: {original_src}:{original_sport} -> "
            f"{mapping.nat_src_ip}:{mapping.nat_src_port}"
        )
        
        return packet
    
    def _apply_nat_inbound(
        self,
        packet: IP,
        protocol: str,
        dst_port: int,
        router_ip: str,
    ) -> IP:
        """Apply DNAT (destination NAT) to inbound packet
        
        Restores original destination address from NAT state table.
        """
        # Lookup the mapping
        mapping = self.nat_engine.lookup_inbound(
            protocol,
            router_ip,
            dst_port,
        )
        
        if not mapping:
            self.logger.debug(f"No NAT mapping for {router_ip}:{dst_port}")
            return packet
        
        mapping.packets_in += 1
        mapping.bytes_in += len(packet)
        mapping.update_activity()
        
        # Modify packet to restore original destination
        original_dst = packet.dst
        original_dport = dst_port
        
        packet.dst = mapping.orig_src_ip
        
        if packet.haslayer(TCP):
            packet[TCP].dport = mapping.orig_src_port
        elif packet.haslayer(UDP):
            packet[UDP].dport = mapping.orig_src_port
        
        self.logger.debug(
            f"DNAT: {original_dst}:{original_dport} -> "
            f"{mapping.orig_src_ip}:{mapping.orig_src_port}"
        )
        
        return packet
    
    def _generate_ttl_exceeded(self, original_packet: IP) -> IP:
        """Generate ICMP TTL Exceeded message
        
        Args:
            original_packet: Original IP packet that exceeded TTL
        
        Returns:
            ICMP TTL exceeded packet
        """
        # Create ICMP response
        icmp_packet = IP(
            src=original_packet.dst,  # From destination
            dst=original_packet.src,  # Back to source
            ttl=64,
            proto=1,
        ) / ICMP(
            type=11,  # Time Exceeded
            code=0,   # TTL Exceeded in Transit
        ) / original_packet
        
        self.logger.debug(f"Generated ICMP TTL Exceeded for {original_packet.src}")
        
        return icmp_packet
    
    def set_nat_enabled(self, enabled: bool) -> None:
        """Enable or disable NAT"""
        self.nat_enabled = enabled
        self.logger.info(f"NAT mode: {enabled}")
    
    def __repr__(self) -> str:
        return f"IPv4Forwarder(NAT={'enabled' if self.nat_enabled else 'disabled'})"
