"""
Example WebSocket client for connecting to the experiment processing API.

Usage:
    python websocket_client_example.py
"""

import asyncio
import json
import websockets
import sys


async def listen_to_updates():
    """Connect to WebSocket and listen for experiment processing updates."""
    uri = "ws://localhost:8000/ws"

    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to experiment processing updates")
            print("-" * 50)

            # Receive welcome message
            message = await websocket.recv()
            data = json.loads(message)
            print(f"[{data['type']}] {data['message']}")
            print(f"Timestamp: {data['timestamp']}")
            print("-" * 50)

            # Listen for updates
            while True:
                try:
                    message = await websocket.recv()
                    data = json.loads(message)

                    if data["type"] == "processing_start":
                        print(f"\n🔵 Processing started: {data['experiment_name']}")
                        print(f"   Timestamp: {data['timestamp']}")

                    elif data["type"] == "processing_complete":
                        print(f"\n✅ Processing complete: {data['experiment_name']}")
                        print(f"   Status: {data['result']['status']}")
                        print(
                            f"   Processed data: {json.dumps(data['result']['processed_data'], indent=2)}"
                        )
                        print(f"   Timestamp: {data['timestamp']}")

                    elif data["type"] == "pong":
                        print(f"\n🏓 Pong received at {data['timestamp']}")

                    print("-" * 50)

                except websockets.exceptions.ConnectionClosed:
                    print("\nConnection closed")
                    break

    except ConnectionRefusedError:
        print("Error: Could not connect to the server.")
        print("Make sure the server is running on http://localhost:8000")
        print("\nStart the server with:")
        print("  python simple.py")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


async def send_ping_periodically(interval=30):
    """Send periodic ping messages to keep connection alive."""
    uri = "ws://localhost:8000/ws"

    async with websockets.connect(uri) as websocket:
        # Skip welcome message
        await websocket.recv()

        while True:
            await asyncio.sleep(interval)
            await websocket.send("ping")


if __name__ == "__main__":
    print("Experiment Processing API - WebSocket Client")
    print("=" * 50)

    try:
        asyncio.run(listen_to_updates())
    except KeyboardInterrupt:
        print("\n\nDisconnected by user")
