#!/bin/bash
# Quick start script for NAT router test server
# Run on VPS B (test machine)

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${PROJECT_ROOT}/.venv"

echo "=== NAT Router Test Suite - Quick Start ==="
echo

# Check if venv exists
if [ ! -d "$VENV" ]; then
    echo "Error: Virtual environment not found at $VENV"
    echo "Please run: python3 -m venv .venv"
    exit 1
fi

# Activate venv
source "$VENV/bin/activate"

# Check dependencies
echo "Checking dependencies..."
python -m pip install -q -r "$PROJECT_ROOT/requirements.txt"

echo "✓ Dependencies ready"
echo

# Print configuration
echo "Configuration:"
echo "  Router IP: 172.16.35.103"
echo "  Test Machine IP: 172.16.39.47"
echo "  Target Network: 125.39.61.0/24"
echo "  Target IP: 125.39.61.75"
echo

# Check network connectivity
echo "Checking network connectivity..."
if ping -c 1 -W 2 172.16.35.103 > /dev/null 2>&1; then
    echo "✓ Connected to router (172.16.35.103)"
else
    echo "⚠ Warning: Cannot reach router (172.16.35.103)"
    echo "  Ensure VPS A (router) is online and configured"
fi

# Check route configuration
ROUTE_EXISTS=$(ip route show | grep -q "192.168.1" && echo "yes" || echo "no")
if [ "$ROUTE_EXISTS" = "yes" ]; then
    echo "✓ Target route configured"
else
    echo "⚠ Warning: Target route not configured"
    echo "  Configure with: sudo ip route add 125.39.61.0/24 via 172.16.35.103"
fi

echo

# Parse arguments
HOST="0.0.0.0"
PORT=8888
DEBUG=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --host)
            HOST="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --debug)
            DEBUG="--debug"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--host HOST] [--port PORT] [--debug]"
            exit 1
            ;;
    esac
done

# Start test server
echo "Starting test server..."
echo "  Host: $HOST"
echo "  Port: $PORT"
echo
echo "API endpoints:"
echo "  Health check:    curl http://$HOST:$PORT/health"
echo "  Run all tests:   curl -X POST http://$HOST:$PORT/test/all"
echo "  View config:     curl http://$HOST:$PORT/config"
echo "  Test results:    curl http://$HOST:$PORT/test/results"
echo
echo "See docs/test.md for complete API documentation"
echo

exec python test.py --host "$HOST" --port "$PORT" $DEBUG
