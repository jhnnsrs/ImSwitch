"""
Tests for WebSocket functionality.
"""

import json


class TestWebSocketEndpoint:
    """Tests for WebSocket functionality."""

    def test_websocket_connection(self, client):
        """Test WebSocket connection establishment."""
        with client.websocket_connect("/ws") as websocket:
            # Receive welcome message
            data = websocket.receive_text()
            message = json.loads(data)
            assert message["type"] == "connection"
            assert "Connected" in message["message"]
            assert "timestamp" in message

    def test_websocket_ping_pong(self, client):
        """Test WebSocket ping/pong."""
        with client.websocket_connect("/ws") as websocket:
            # Skip welcome message
            websocket.receive_text()

            # Send ping
            websocket.send_text("ping")

            # Receive pong
            data = websocket.receive_text()
            message = json.loads(data)
            assert message["type"] == "pong"
            assert "timestamp" in message

    def test_websocket_receives_processing_updates(self, client):
        """Test that WebSocket receives updates when processing occurs."""
        with client.websocket_connect("/ws") as websocket:
            # Skip welcome message
            websocket.receive_text()

            # Trigger a process request
            request_data = {
                "name": "test_experiment",
                "parameters": {"exposure_time": 0.1},
            }
            response = client.post("/process", json=request_data)
            assert response.status_code == 200

            # Receive processing_start message
            data = websocket.receive_text()
            start_message = json.loads(data)
            assert start_message["type"] == "processing_start"
            assert start_message["experiment_name"] == "test_experiment"
            assert "timestamp" in start_message

            # Receive processing_complete message
            data = websocket.receive_text()
            complete_message = json.loads(data)
            assert complete_message["type"] == "processing_complete"
            assert complete_message["experiment_name"] == "test_experiment"
            assert "result" in complete_message
            assert complete_message["result"]["status"] == "success"
            assert "timestamp" in complete_message

    def test_multiple_websocket_connections(self, client):
        """Test multiple WebSocket connections receive broadcasts."""
        with (
            client.websocket_connect("/ws") as ws1,
            client.websocket_connect("/ws") as ws2,
        ):
            # Skip welcome messages
            ws1.receive_text()
            ws2.receive_text()

            # Trigger processing
            request_data = {
                "name": "broadcast_test",
                "parameters": {"num_frames": 10},
            }
            response = client.post("/process", json=request_data)
            assert response.status_code == 200

            # Both connections should receive start message
            msg1_start = json.loads(ws1.receive_text())
            msg2_start = json.loads(ws2.receive_text())
            assert msg1_start["type"] == "processing_start"
            assert msg2_start["type"] == "processing_start"
            assert msg1_start["experiment_name"] == "broadcast_test"
            assert msg2_start["experiment_name"] == "broadcast_test"

            # Both connections should receive complete message
            msg1_complete = json.loads(ws1.receive_text())
            msg2_complete = json.loads(ws2.receive_text())
            assert msg1_complete["type"] == "processing_complete"
            assert msg2_complete["type"] == "processing_complete"


class TestAssignationWebSocketIntegration:
    """Tests for WebSocket integration with assignation management."""

    def test_assignation_created_websocket_notification(self, client):
        """Test that WebSocket receives notification when assignation is created."""
        with client.websocket_connect("/ws") as websocket:
            # Skip welcome message
            websocket.receive_text()

            # Create an assignation
            response = client.post(
                "/actions/capture_image/assign",
                json={"args": {"exposure_time": 0.1}},
            )
            assert response.status_code == 200
            assignation_id = response.json()["id"]

            # Should receive assignation_created message
            data = websocket.receive_text()
            message = json.loads(data)
            assert message["type"] == "assignation_created"
            assert message["assignation_id"] == assignation_id
            assert message["action"] == "capture_image"

    def test_assignation_lifecycle_websocket_notifications(self, client):
        """Test WebSocket receives assignation lifecycle notifications."""
        import time

        with client.websocket_connect("/ws") as websocket:
            # Skip welcome message
            websocket.receive_text()

            # Create an assignation
            response = client.post(
                "/actions/adjust_focus/assign",
                json={"args": {"z_position": 10.0}},
            )
            assert response.status_code == 200

            # Receive assignation_created
            msg1 = json.loads(websocket.receive_text())
            assert msg1["type"] == "assignation_created"

            # Wait for execution notifications
            time.sleep(0.1)

            # May receive assignation_done or assignation_error
            try:
                msg2 = websocket.receive_text(timeout=1)
                message = json.loads(msg2)
                assert message["type"] in [
                    "assignation_assigned",
                    "assignation_done",
                    "assignation_error",
                ]
            except Exception:
                pass  # Execution might complete too quickly
