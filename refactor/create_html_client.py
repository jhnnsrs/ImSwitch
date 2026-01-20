"""
JavaScript/HTML example for connecting to the WebSocket API.

Save this as index.html and open in a web browser.
"""

html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Experiment Processing WebSocket Client</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            border-bottom: 3px solid #007bff;
            padding-bottom: 10px;
        }
        #status {
            padding: 10px;
            margin: 20px 0;
            border-radius: 4px;
            font-weight: bold;
        }
        .connected {
            background-color: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .disconnected {
            background-color: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        #messages {
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 4px;
            padding: 15px;
            height: 400px;
            overflow-y: auto;
            font-family: 'Courier New', monospace;
            font-size: 14px;
        }
        .message {
            margin: 10px 0;
            padding: 8px;
            border-radius: 4px;
            border-left: 4px solid #007bff;
            background-color: white;
        }
        .message.start {
            border-left-color: #ffc107;
            background-color: #fff3cd;
        }
        .message.complete {
            border-left-color: #28a745;
            background-color: #d4edda;
        }
        .message.connection {
            border-left-color: #17a2b8;
            background-color: #d1ecf1;
        }
        button {
            background-color: #007bff;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
            margin: 10px 5px;
            font-size: 16px;
        }
        button:hover {
            background-color: #0056b3;
        }
        button:disabled {
            background-color: #6c757d;
            cursor: not-allowed;
        }
        .controls {
            margin: 20px 0;
        }
        .timestamp {
            color: #6c757d;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔬 Experiment Processing WebSocket Client</h1>
        
        <div id="status" class="disconnected">
            Disconnected
        </div>
        
        <div class="controls">
            <button id="connectBtn" onclick="connect()">Connect</button>
            <button id="disconnectBtn" onclick="disconnect()" disabled>Disconnect</button>
            <button id="clearBtn" onclick="clearMessages()">Clear Messages</button>
        </div>
        
        <h2>Messages</h2>
        <div id="messages"></div>
    </div>

    <script>
        let ws = null;
        const messagesDiv = document.getElementById('messages');
        const statusDiv = document.getElementById('status');
        const connectBtn = document.getElementById('connectBtn');
        const disconnectBtn = document.getElementById('disconnectBtn');

        function connect() {
            if (ws && ws.readyState === WebSocket.OPEN) {
                addMessage('Already connected', 'connection');
                return;
            }

            ws = new WebSocket('ws://localhost:8000/ws');

            ws.onopen = function(event) {
                updateStatus('Connected', true);
                connectBtn.disabled = true;
                disconnectBtn.disabled = false;
                addMessage('WebSocket connection established', 'connection');
            };

            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                handleMessage(data);
            };

            ws.onerror = function(error) {
                addMessage('WebSocket error: ' + error, 'error');
            };

            ws.onclose = function(event) {
                updateStatus('Disconnected', false);
                connectBtn.disabled = false;
                disconnectBtn.disabled = true;
                addMessage('WebSocket connection closed', 'connection');
            };
        }

        function disconnect() {
            if (ws) {
                ws.close();
                ws = null;
            }
        }

        function handleMessage(data) {
            const type = data.type;
            let message = '';
            let className = type;

            switch(type) {
                case 'connection':
                    message = `📡 ${data.message}`;
                    break;
                case 'processing_start':
                    message = `🔵 Processing started: ${data.experiment_name}`;
                    className = 'start';
                    break;
                case 'processing_complete':
                    message = `✅ Processing complete: ${data.experiment_name}<br>`;
                    message += `&nbsp;&nbsp;&nbsp;Status: ${data.result.status}<br>`;
                    message += `&nbsp;&nbsp;&nbsp;Processed data: <pre>${JSON.stringify(data.result.processed_data, null, 2)}</pre>`;
                    className = 'complete';
                    break;
                case 'pong':
                    message = '🏓 Pong received';
                    break;
                default:
                    message = JSON.stringify(data, null, 2);
            }

            addMessage(message, className, data.timestamp);
        }

        function addMessage(text, className = '', timestamp = null) {
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message ' + className;
            
            let content = text;
            if (timestamp) {
                content += `<div class="timestamp">${new Date(timestamp).toLocaleString()}</div>`;
            } else {
                content += `<div class="timestamp">${new Date().toLocaleString()}</div>`;
            }
            
            messageDiv.innerHTML = content;
            messagesDiv.appendChild(messageDiv);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }

        function updateStatus(text, isConnected) {
            statusDiv.textContent = text;
            statusDiv.className = isConnected ? 'connected' : 'disconnected';
        }

        function clearMessages() {
            messagesDiv.innerHTML = '';
        }

        // Auto-connect on page load
        window.onload = function() {
            setTimeout(connect, 500);
        };
    </script>
</body>
</html>
"""

# Write the HTML file
with open("websocket_client.html", "w") as f:
    f.write(html_content)

print("HTML WebSocket client created: websocket_client.html")
print("Open this file in a web browser to test the WebSocket connection.")
