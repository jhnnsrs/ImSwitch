# EngineManager - Task Scheduling System

## Overview

The EngineManager is a sophisticated task scheduling and execution system for microscope operations. It provides asynchronous task processing with real-time status updates via WebSocket.

## Features

- **Asynchronous Task Queue**: Tasks are queued and processed asynchronously using asyncio
- **Task Lifecycle Management**: Tasks transition through states: PENDING → RUNNING → COMPLETED/FAILED/CANCELLED
- **Real-time Updates**: WebSocket broadcasts for all task events
- **RESTful API**: Complete CRUD operations for task management
- **Multiple Microscope Actions**: Support for image capture, stage movement, and focus adjustment

## Architecture

### Task Model

```python
class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Task(BaseModel):
    id: str
    name: str
    action: str
    parameters: Optional[Dict[str, Any]]
    status: TaskStatus
    result: Optional[Dict[str, Any]]
    error: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
```

### EngineManager Class

The EngineManager manages the task queue and execution:

- **schedule_task()**: Adds a task to the queue and assigns it PENDING status
- **cancel_task()**: Cancels a pending or running task
- **get_task()**: Retrieves a specific task by ID
- **list_tasks()**: Lists all tasks, optionally filtered by status
- **_process_tasks()**: Background worker that processes tasks from the queue
- **_execute_task()**: Executes a single task and updates its status
- **_perform_microscope_action()**: Performs the actual microscope operation (currently mocked)

### Microscope Actions

Currently supported actions:

1. **capture_image**: Simulates image capture
2. **move_stage**: Simulates stage movement with x, y, z coordinates
3. **adjust_focus**: Simulates focus adjustment with position and speed

## API Endpoints

### Create Task

```http
POST /tasks
Content-Type: application/json

{
    "name": "capture_sample_1",
    "action": "capture_image",
    "parameters": {
        "exposure": 100,
        "gain": 1.5
    }
}
```

Response:
```json
{
    "id": "uuid-here",
    "name": "capture_sample_1",
    "action": "capture_image",
    "parameters": {"exposure": 100, "gain": 1.5},
    "status": "pending",
    "result": null,
    "error": null,
    "created_at": "2024-01-01T12:00:00",
    "started_at": null,
    "completed_at": null
}
```

### List Tasks

```http
GET /tasks
GET /tasks?status=pending
GET /tasks?status=completed
```

### Get Task by ID

```http
GET /tasks/{task_id}
```

### Cancel Task

```http
DELETE /tasks/{task_id}
```

## WebSocket Events

The EngineManager broadcasts the following events via WebSocket:

### Task Scheduled
```json
{
    "type": "task_scheduled",
    "task_id": "uuid-here",
    "name": "capture_sample_1",
    "action": "capture_image",
    "timestamp": "2024-01-01T12:00:00"
}
```

### Task Started
```json
{
    "type": "task_started",
    "task_id": "uuid-here",
    "timestamp": "2024-01-01T12:00:01"
}
```

### Task Completed
```json
{
    "type": "task_completed",
    "task_id": "uuid-here",
    "result": {"image_data": "..."},
    "timestamp": "2024-01-01T12:00:05"
}
```

### Task Failed
```json
{
    "type": "task_failed",
    "task_id": "uuid-here",
    "error": "Error message here",
    "timestamp": "2024-01-01T12:00:05"
}
```

### Task Cancelled
```json
{
    "type": "task_cancelled",
    "task_id": "uuid-here",
    "timestamp": "2024-01-01T12:00:03"
}
```

## Usage Examples

### Python Client

```python
import asyncio
import websockets
import requests
import json

# Create a task via REST API
response = requests.post(
    "http://localhost:8000/tasks",
    json={
        "name": "my_task",
        "action": "capture_image",
        "parameters": {"exposure": 100}
    }
)
task = response.json()
print(f"Created task: {task['id']}")

# Monitor task via WebSocket
async def monitor_tasks():
    async with websockets.connect("ws://localhost:8000/ws") as websocket:
        while True:
            message = await websocket.recv()
            data = json.loads(message)
            print(f"Event: {data['type']}, Task: {data.get('task_id')}")

asyncio.run(monitor_tasks())
```

### cURL Examples

```bash
# Create a task
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"name": "test", "action": "capture_image"}'

# List all tasks
curl http://localhost:8000/tasks

# List pending tasks
curl "http://localhost:8000/tasks?status=pending"

# Get specific task
curl http://localhost:8000/tasks/{task_id}

# Cancel task
curl -X DELETE http://localhost:8000/tasks/{task_id}
```

## Integration with Hardware

To integrate with actual microscope hardware, modify the `_perform_microscope_action()` method in [simple.py](simple.py):

```python
async def _perform_microscope_action(self, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Perform actual microscope action - integrate with hardware here."""
    
    if action == "capture_image":
        # Replace with actual camera interface
        image = await self.camera.capture(**parameters)
        return {"image_data": image, "timestamp": datetime.now().isoformat()}
    
    elif action == "move_stage":
        # Replace with actual stage controller
        await self.stage.move_to(
            x=parameters.get("x", 0),
            y=parameters.get("y", 0),
            z=parameters.get("z", 0)
        )
        return {"new_position": self.stage.get_position()}
    
    # ... etc
```

## Testing

The EngineManager is fully tested with 47 comprehensive tests covering:

- Task creation and scheduling
- Task lifecycle management
- Status filtering
- Task cancellation
- WebSocket event broadcasting
- Error handling
- Edge cases

Run tests:
```bash
uv run pytest refactor/test_simple.py -v
```

## Performance

- Tasks are processed asynchronously, allowing concurrent operations
- WebSocket broadcasting is non-blocking
- Task queue uses asyncio.Queue for efficient concurrent access
- Background worker processes tasks continuously

## Future Enhancements

1. **Priority Queue**: Add task priority levels
2. **Task Dependencies**: Support for task chains and dependencies
3. **Retry Logic**: Automatic retry for failed tasks
4. **Task History**: Store completed tasks in database
5. **Resource Management**: Track and limit concurrent hardware access
6. **Task Scheduling**: Support for scheduled/delayed task execution
7. **Batch Operations**: Create multiple tasks in one request
8. **Task Progress**: Support for long-running tasks with progress updates
