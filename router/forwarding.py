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
from scapy.arch import get_if_addr
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
        internal_networks: Optional[list] = None,
    ):
        """Initialize the IPv4 forwarder
        
        Args:
            route_table: RouteTable instance for route lookup
            nat_engine: NATEngine instance for NAT translation
            nat_enabled: Whether to perform NAT translation
            internal_networks: List of internal networks (CIDR format) that should NOT be SNATed
        """
        self.route_table = route_table
        self.nat_engine = nat_engine
        self.nat_enabled = nat_enabled
        self.internal_networks = internal_networks or []
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        if self.internal_networks:
            self.logger.info(f"Internal networks for NAT exclusion: {self.internal_networks}")
        self.logger.info(f"IPv4Forwarder initialized (NAT: {nat_enabled})")
    
    def _is_external_traffic(self, dst_ip: str, route) -> bool:
        """Determine if traffic is destined for external network
        
        SNAT should only be applied to traffic going to external networks.
        Internal namespace-to-namespace traffic should NOT be SNATed.
        
        Args:
            dst_ip: Destination IP address
            route: Route object from routing table lookup
            
        Returns:
            True if traffic is external (should apply SNAT), False if internal
        """
        # Direct routes (gateway="0.0.0.0") are internal - don't SNAT
        if route.gateway == "0.0.0.0":
            self.logger.debug(f"Direct route for {dst_ip}, not external - skipping SNAT")
            return False
        
        # Check if destination is in internal networks list
        try:
            dst_addr = ipaddress.ip_address(dst_ip)
            for internal_net in self.internal_networks:
                network = ipaddress.ip_network(internal_net, strict=False)
                if dst_addr in network:
                    self.logger.debug(
                        f"Destination {dst_ip} is in internal network {internal_net} - skipping SNAT"
                    )
                    return False
        except (ValueError, ipaddress.NetmaskValueError):
            self.logger.warning(f"Invalid IP or network format")
        
        # Otherwise, it's external traffic - apply SNAT
        return True
    
    def _get_interface_ip(self, interface: str) -> Optional[str]:
        """Get IP address of an interface"""
        try:
            return get_if_addr(interface)
        except Exception as e:
            self.logger.error(f"Failed to get IP for interface {interface}: {e}")
            return None
    
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
            
            # Extract protocol info FIRST for NAT processing
            protocol = None
            src_port = None
            dst_port = None
            icmp_id = None
            
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
            elif packet.haslayer(ICMP):
                protocol = "icmp"
                icmp_layer = packet[ICMP]
                # ICMP uses ID instead of port for echo requests/replies
                if hasattr(icmp_layer, 'id'):
                    icmp_id = icmp_layer.id
                src_port = 0
                dst_port = 0
            
            # Apply DNAT FIRST if this is a reply packet from gateway
            # This changes packet.dst, so we need to re-lookup route afterwards
            dnat_applied = False
            if self.nat_enabled and protocol:
                default_gw = self.route_table.get_default_gateway()
                if default_gw:
                    gw_ip, gw_iface = default_gw
                    # For DNAT, check if packet came from gateway interface
                    # AND is destined to any IP on that interface (could be interface IP or gateway IP)
                    if in_interface == gw_iface:
                        # Get the actual interface IP
                        interface_ip = self._get_interface_ip(gw_iface)
                        # Check if packet is destined to our interface or gateway
                        if packet.dst == interface_ip or packet.dst == gw_ip:
                            # This could be a DNAT reply
                            if protocol == "icmp":
                                self.logger.debug(
                                    f"DNAT lookup for ICMP: protocol={protocol}, dst_ip={packet.dst}, icmp_id={icmp_id}"
                                )
                                nat_mapping = self.nat_engine.lookup_inbound(
                                    protocol,
                                    packet.dst,  # Our IP (the nat_src_ip in the mapping)
                                    icmp_id if icmp_id else 0,
                                )
                            elif protocol in ("tcp", "udp") and dst_port:
                                self.logger.debug(
                                    f"DNAT lookup for TCP/UDP: protocol={protocol}, dst_ip={packet.dst}, dst_port={dst_port}"
                                )
                                nat_mapping = self.nat_engine.lookup_inbound(
                                    protocol,
                                    packet.dst,
                                    dst_port,
                                )
                            else:
                                nat_mapping = None
                            
                            if nat_mapping:
                                self.logger.info(
                                    f"DNAT (reply): {protocol.upper()} from {packet.src} "
                                    f"dst {packet.dst} -> {nat_mapping.orig_src_ip} "
                                    f"(mapping: orig_src={nat_mapping.orig_src_ip}:{nat_mapping.orig_src_port})"
                                )
                                # Restore original destination address to the ORIGINAL SOURCE (reverse of SNAT)
                                # For return traffic, destination should be the original source IP
                                packet.dst = nat_mapping.orig_src_ip
                                if protocol == "tcp" and packet.haslayer(TCP):
                                    packet[TCP].dport = nat_mapping.orig_src_port
                                    packet[TCP].chksum = None  # Force recalculation
                                elif protocol == "udp" and packet.haslayer(UDP):
                                    packet[UDP].dport = nat_mapping.orig_src_port
                                    packet[UDP].chksum = None  # Force recalculation
                                # Invalidate IP checksum to force recalculation
                                packet.chksum = None
                                dnat_applied = True
                                # For ICMP, ID typically stays the same
            
            # Now lookup route with possibly DNAT'd destination
            route = self.route_table.lookup(packet.dst)
            
            # If no specific route found, use default gateway if available
            if not route:
                default_gw = self.route_table.get_default_gateway()
                if default_gw:
                    gw_ip, gw_iface = default_gw
                    self.logger.debug(
                        f"No specific route for {packet.dst}, using default gateway {gw_ip} via {gw_iface}"
                    )
                    # Create a temporary route for this packet
                    from .route_table import Route
                    route = Route(destination='0.0.0.0/0', gateway=gw_ip, interface=gw_iface)
                else:
                    self.logger.debug(f"No route to {packet.dst}")
                    return None
            
            output_interface = route.interface
            
            # Loopback prevention: drop if input == output
            # BUT: allow if this packet was just DNAT'd (now going to internal network)
            if output_interface == in_interface and not packet.dst.startswith('255.') and not dnat_applied:
                self.logger.debug(f"Loopback prevention: {packet.src} -> {packet.dst} from {in_interface}, dropping")
                return None
            
            # Reject traffic coming FROM gateway interface (external network)
            # Exception: packets already processed by DNAT (packet.dst has been changed)
            default_gw = self.route_table.get_default_gateway()
            if default_gw:
                gw_ip, gw_iface = default_gw
                if in_interface == gw_iface and not dnat_applied:
                    # If we're still destined for our interface IP or gateway IP (not DNAT'd), drop it
                    interface_ip = self._get_interface_ip(gw_iface)
                    if packet.dst == gw_ip or packet.dst == interface_ip:
                        self.logger.debug(f"Drop external traffic from {in_interface}: {packet.src} -> {packet.dst} (no DNAT match)")
                        return None
            
            # Apply SNAT if needed
            if self.nat_enabled and protocol:
                if (protocol == "icmp" or (src_port and dst_port)) and self._is_external_traffic(packet.dst, route):
                    packet = self._apply_nat_outbound(
                        packet,
                        protocol,
                        src_port,
                        dst_port,
                        route,
                        output_interface,
                        icmp_id=icmp_id,
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
        output_interface: str,
        icmp_id: int = None,
    ) -> IP:
        """Apply SNAT (source NAT) to outbound packet
        
        Translates internal source address to router's address.
        Only applied for external network traffic.
        
        For ICMP: icmp_id is used instead of port numbers
        """
        # Validate that gateway is not "0.0.0.0" (should not reach here due to _is_external_traffic check)
        if route.gateway == "0.0.0.0":
            self.logger.warning(f"Direct route detected in _apply_nat_outbound for {packet.dst} - not applying SNAT")
            return packet
        
        # Get the actual IP address of the output interface to use as SNAT source
        nat_src_ip = self._get_interface_ip(output_interface)
        if not nat_src_ip:
            self.logger.warning(f"Could not get IP for interface {output_interface}, using gateway as fallback")
            nat_src_ip = route.gateway
        
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
            # For ICMP, use icmp_id as the port number for mapping storage
            nat_port = icmp_id if protocol == "icmp" else None
            
            mapping = self.nat_engine.create_mapping(
                protocol=protocol,
                orig_src_ip=packet.src,
                orig_src_port=src_port if protocol != "icmp" else icmp_id,
                orig_dst_ip=packet.dst,
                orig_dst_port=dst_port if protocol != "icmp" else icmp_id,
                nat_src_ip=nat_src_ip,  # Use actual interface IP as NAT address
                nat_src_port=nat_port,  # For ICMP, use ID; for TCP/UDP, auto-assign
                nat_dst_ip=packet.dst,
                nat_dst_port=dst_port if protocol != "icmp" else icmp_id,
            )
        
        # Update TCP state if applicable
        if packet.haslayer(TCP):
            flags = "".join(c for c in str(packet[TCP].flags) if c in "FSRPAUEC")
            self.nat_engine.update_tcp_state(mapping, flags)
        
        mapping.packets_out += 1
        mapping.bytes_out += len(packet)
        
        # Modify packet
        original_src = packet.src
        original_sport = src_port if protocol != "icmp" else icmp_id
        
        packet.src = mapping.nat_src_ip
        
        if packet.haslayer(TCP):
            packet[TCP].sport = mapping.nat_src_port
        elif packet.haslayer(UDP):
            packet[UDP].sport = mapping.nat_src_port
        elif packet.haslayer(ICMP) and icmp_id is not None:
            # For ICMP, keep the ID but now it's associated with the NAT'd IP
            # The ID doesn't need to change, only the source IP changes
            pass
        
        if protocol == "icmp":
            self.logger.debug(
                f"SNAT ICMP: {original_src} -> {mapping.nat_src_ip}"
            )
        else:
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
