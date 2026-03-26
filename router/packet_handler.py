"""
Packet Handler - Scapy-based packet capture and transmission

Captures packets on a network interface, processes them through the
forwarding engine, and sends the modified packets back out.
"""

import logging
import signal
import sys
from typing import Optional, Callable
from scapy.all import sniff, send, IP, get_if_list
import subprocess


logger = logging.getLogger(__name__)


class PacketHandler:
    """Packet capture and transmission handler"""
    
    def __init__(
        self,
        interface: str,
        forwarder,
        filter_str: str = "ip",
    ):
        """Initialize packet handler
        
        Args:
            interface: Network interface to capture on (e.g., "eth0")
            forwarder: IPv4Forwarder instance for packet processing
            filter_str: BPF filter for packet capture
        """
        self.interface = interface
        self.forwarder = forwarder
        self.filter_str = filter_str
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.running = False
        self.packet_count = 0
        self.error_count = 0
        
        # Validate interface exists
        if not self._interface_exists():
            raise ValueError(f"Interface {interface} not found")
        
        self.logger.info(f"PacketHandler initialized on {interface}")
    
    def start(self) -> None:
        """Start packet capture and forwarding
        
        This is a blocking call that runs until interrupted.
        """
        self.running = True
        self.logger.info(f"Starting packet capture on {self.interface}")
        
        # Setup signal handlers only in main thread
        import threading
        if threading.current_thread() is threading.main_thread():
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
        
        try:
            # Start sniffing
            sniff(
                iface=self.interface,
                filter=self.filter_str,
                prn=self._packet_callback,
                store=False,
            )
        except KeyboardInterrupt:
            self.logger.info("Packet capture interrupted")
        except PermissionError:
            self.logger.error(f"Permission denied: must run as root to capture on {self.interface}")
            sys.exit(1)
        except Exception as e:
            self.logger.error(f"Error during packet capture: {e}", exc_info=True)
            sys.exit(1)
        finally:
            self.stop()
    
    def stop(self) -> None:
        """Stop packet capture"""
        self.running = False
        self.logger.info(
            f"Packet handler stopped. Processed {self.packet_count} packets, "
            f"{self.error_count} errors"
        )
    
    def _packet_callback(self, packet) -> None:
        """Callback for each captured packet
        
        Args:
            packet: Scapy packet object
        """
        try:
            self.packet_count += 1
            
            # Only process IP packets
            if not packet.haslayer(IP):
                self.logger.debug(f"Packet #{self.packet_count}: No IP layer, skipping")
                return
            
            ip_packet = packet[IP]
            self.logger.debug(f"Processing IP packet: {ip_packet.src} -> {ip_packet.dst} on {self.interface}")
            
            # Forward the packet
            result = self.forwarder.forward_packet(ip_packet, self.interface)
            
            if result:
                output_interface, forwarded_packet = result
                self.logger.info(
                    f"Forwarding packet: {ip_packet.src} -> {ip_packet.dst} "
                    f"from {self.interface} to {output_interface}"
                )
                # Send the forwarded packet
                from scapy.all import send
                try:
                    send(forwarded_packet, iface=output_interface, verbose=False)
                    self.logger.debug(
                        f"Sent packet: {ip_packet.src} -> {ip_packet.dst} "
                        f"via {output_interface} (TTL: {forwarded_packet.ttl})"
                    )
                except Exception as send_error:
                    self.logger.warning(
                        f"Failed to send packet on {output_interface}: {send_error}"
                    )
            else:
                self.logger.debug(f"Packet {ip_packet.src} -> {ip_packet.dst} not forwarded (no route or filtered)")
        
        except Exception as e:
            self.error_count += 1
            self.logger.error(f"Error processing packet: {e}", exc_info=False)
    
    def _interface_exists(self) -> bool:
        """Check if network interface exists
        
        Returns:
            True if interface exists, False otherwise
        """
        try:
            interfaces = get_if_list()
            return self.interface in interfaces
        except Exception:
            return False
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)
    
    def __repr__(self) -> str:
        return f"PacketHandler({self.interface}, {self.packet_count} packets)"
