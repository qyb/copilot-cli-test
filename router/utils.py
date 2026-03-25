"""
Utility Functions - Checksums, address parsing, etc.

Helper functions for packet manipulation and validation.
"""

import struct
import socket


def compute_checksum(data: bytes) -> int:
    """Compute Internet checksum (RFC 1071)
    
    Used for IP header and ICMP checksums.
    
    Args:
        data: Bytes to checksum
    
    Returns:
        16-bit checksum value
    """
    # Ensure data length is even
    if len(data) % 2:
        data += b'\x00'
    
    # Sum 16-bit words
    checksum = 0
    for i in range(0, len(data), 2):
        w = (data[i] << 8) + data[i + 1]
        checksum += w
    
    # Add carries to lower 16 bits
    while checksum >> 16:
        checksum = (checksum & 0xFFFF) + (checksum >> 16)
    
    # Ones complement
    return ~checksum & 0xFFFF


def compute_tcp_checksum(
    src_ip: str,
    dst_ip: str,
    tcp_packet: bytes,
) -> int:
    """Compute TCP checksum (RFC 793)
    
    TCP checksum includes a pseudo-header with source and destination IPs.
    
    Args:
        src_ip: Source IP address string
        dst_ip: Destination IP address string
        tcp_packet: TCP packet bytes (with checksum field zeroed)
    
    Returns:
        16-bit checksum value
    """
    # Pseudo-header
    src_bytes = socket.inet_aton(src_ip)
    dst_bytes = socket.inet_aton(dst_ip)
    protocol = 6  # TCP
    tcp_len = len(tcp_packet)
    
    pseudo_header = (
        src_bytes +
        dst_bytes +
        struct.pack('!HH', protocol, tcp_len)
    )
    
    return compute_checksum(pseudo_header + tcp_packet)


def compute_udp_checksum(
    src_ip: str,
    dst_ip: str,
    udp_packet: bytes,
) -> int:
    """Compute UDP checksum (RFC 768)
    
    UDP checksum includes a pseudo-header like TCP.
    
    Args:
        src_ip: Source IP address string
        dst_ip: Destination IP address string
        udp_packet: UDP packet bytes (with checksum field zeroed)
    
    Returns:
        16-bit checksum value (0 if original was 0, per UDP spec)
    """
    # Pseudo-header
    src_bytes = socket.inet_aton(src_ip)
    dst_bytes = socket.inet_aton(dst_ip)
    protocol = 17  # UDP
    udp_len = len(udp_packet)
    
    pseudo_header = (
        src_bytes +
        dst_bytes +
        struct.pack('!HH', protocol, udp_len)
    )
    
    checksum = compute_checksum(pseudo_header + udp_packet)
    
    # UDP checksum of 0 means checksum was not calculated
    # If result is 0, change to 0xFFFF
    return checksum if checksum else 0xFFFF


def ip_string_to_int(ip_str: str) -> int:
    """Convert IP address string to integer
    
    Args:
        ip_str: IP address string (e.g., "172.16.35.103")
    
    Returns:
        32-bit integer representation
    """
    return struct.unpack('!I', socket.inet_aton(ip_str))[0]


def ip_int_to_string(ip_int: int) -> str:
    """Convert integer to IP address string
    
    Args:
        ip_int: 32-bit integer
    
    Returns:
        IP address string
    """
    return socket.inet_ntoa(struct.pack('!I', ip_int))
