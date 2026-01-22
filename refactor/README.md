# Microscope Control API v2.0

A modern, async-first API for microscope control with an actor-based execution system, 
real-time state synchronization, and WebSocket-based event delivery.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        React Frontend                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │useAssignation│  │  useState()  │  │ useWebSocket │          │
│  │   hooks      │  │  "stage.pos" │  │  (events)    │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
└─────────┼─────────────────┼─────────────────┼───────────────────┘
          │                 │                 │
          ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Backend                            │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │DefinitionReg │  │  StateProxy  │  │   Agent      │          │
│  │  @register   │  │  (buffered)  │  │  (actors)    │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                              │                  │
│  ┌──────────────────────────────────────────┐│                  │
│  │              Actor System                ││                  │
│  │  ┌────────┐  ┌────────┐  ┌────────┐     ││                  │
│  │  │ Actor1 │  │ Actor2 │  │ Actor3 │     ││                  │
│  │  └────────┘  └────────┘  └────────┘     ││                  │
│  └──────────────────────────────────────────┘│                  │
│                                              │                  │
│  ┌───────────────────────────────────────────┘                  │
│  │        WebSocket Broadcasts                                  │
│  │  • assignation_created  • assignation_done                   │
│  │  • assignation_yield    • assignation_error                  │
│  │  • state_update         • assignation_progress               │
│  └──────────────────────────────────────────────────────────────│
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │   Microscope    │
                   │   Hardware      │
                   └─────────────────┘
```

## Core Concepts

### 1. Actor-Based Execution (Inspired by rekuest-next)

Actions are defined as regular Python functions and automatically wrapped in actors
for async execution. When you "assign" an action, it returns immediately with an 
assignation ID. Results are delivered via WebSocket.

```python
# api/microscope_actions.py
from refactor.api.actors import register

@register(
    name="capture_image",
    description="Capture an image from the camera",
    collections=["imaging", "camera"],
)
async def capture_image(
    exposure_time: float = 0.1,
    resolution: list[int] | None = None,
    channel: str = "default",
) -> dict:
    """Capture an image from the microscope camera."""
    # Interact with actual hardware here
    image = await camera.capture(exposure=exposure_time)
    return {"image_id": str(image.id), "shape": image.shape}
```

**Key Features:**
- Function signature is automatically introspected to generate API schema
- Supports sync/async functions
- Supports generators for streaming results (time-lapse, z-stacks)
- Actions run in their own actors for isolation

### 2. Assignation Lifecycle

```
POST /actions/capture_image/assign
{
    "args": {"exposure_time": 0.1, "resolution": [1024, 1024]},
    "reference": "my-capture-001"  // Optional client reference
}

→ Response (immediate):
{
    "id": "assign-abc123",
    "action": "capture_image", 
    "status": "PENDING",
    "args": {"exposure_time": 0.1, ...},
    "created_at": "2024-01-15T10:30:00Z"
}
```

**Status Flow:**
```
PENDING → ASSIGNED → RUNNING → DONE
                           └→ ERROR
                           └→ CANCELLED
```

**WebSocket Events:**
```json
{"type": "assignation_created", "assignation_id": "abc123", "action": "capture_image"}
{"type": "assignation_assigned", "assignation_id": "abc123"}
{"type": "assignation_progress", "assignation_id": "abc123", "progress": 50}
{"type": "assignation_done", "assignation_id": "abc123", "returns": {"image_id": "..."}}
```

### 3. Generator Actions (Streaming Results)

For actions that produce multiple results (like time-lapse or z-stacks):

```python
@register(
    name="time_lapse",
    description="Capture a time-lapse sequence",
    collections=["imaging", "timelapse"],
)
async def time_lapse(
    num_frames: int = 10,
    interval: float = 1.0,
    exposure_time: float = 0.1,
):
    """Stream images over time."""
    for frame in range(num_frames):
        await asyncio.sleep(interval)
        image = await camera.capture(exposure=exposure_time)
        yield {
            "frame": frame,
            "image_id": str(uuid4()),
            "timestamp": datetime.now().isoformat(),
        }
```

Each `yield` sends an `assignation_yield` WebSocket event, allowing the frontend
to display progress in real-time.

### 4. State Proxy (Buffered State)

The `StateProxy` provides shared state that:
- Supports nested keys via dot notation (`stage.position.x`)
- Buffers updates and broadcasts them periodically via WebSocket
- Provides atomic snapshots with versioning

```python
# In your action handler
await state_proxy.set("stage.position", [x, y, z])
await state_proxy.set("camera.exposure", 0.1)

# Batch updates
await state_proxy.set_many({
    "laser.488nm.power": 50,
    "laser.488nm.enabled": True,
})
```

---

## API Endpoints

### Actions

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/actions` | GET | List all registered actions |
| `/actions/{name}` | GET | Get action definition |
| `/actions/{name}/assign` | POST | Assign (execute) an action |

### Assignations

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/assignations` | GET | List assignations (with filters) |
| `/assignations/{id}` | GET | Get assignation status/result |
| `/assignations/{id}` | DELETE | Cancel an assignation |

### State

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/state` | GET | Get current state snapshot |
| `/state` | PUT | Update single state value |
| `/state` | PATCH | Batch update state values |
| `/state/{key}` | DELETE | Delete state key |

### WebSocket

Connect to `/ws` for real-time events.

---

## React Frontend Integration

### useAssignAction Hook

A React hook for executing actions with async tracking:

```tsx
// hooks/useAssignAction.ts
import { useState, useCallback, useEffect } from 'react';

interface Assignation {
  id: string;
  action: string;
  status: 'PENDING' | 'ASSIGNED' | 'RUNNING' | 'DONE' | 'ERROR' | 'CANCELLED';
  args: Record<string, any>;
  returns?: Record<string, any>;
  yields: Array<Record<string, any>>;
  error?: string;
  progress?: number;
}

interface UseAssignActionResult {
  assign: (args?: Record<string, any>) => Promise<Assignation>;
  assignation: Assignation | null;
  isRunning: boolean;
  error: string | null;
  yields: Array<Record<string, any>>;
}

export function useAssignAction(actionName: string): UseAssignActionResult {
  const [assignation, setAssignation] = useState<Assignation | null>(null);
  const [yields, setYields] = useState<Array<Record<string, any>>>([]);
  const ws = useWebSocket(); // Your WebSocket context

  const assign = useCallback(async (args = {}) => {
    setYields([]);
    const response = await fetch(`/actions/${actionName}/assign`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ args }),
    });
    const data = await response.json();
    setAssignation(data);
    return data;
  }, [actionName]);

  // Listen for WebSocket updates
  useEffect(() => {
    if (!assignation) return;

    const handler = (event: MessageEvent) => {
      const msg = JSON.parse(event.data);
      if (msg.assignation_id !== assignation.id) return;

      switch (msg.type) {
        case 'assignation_assigned':
        case 'assignation_progress':
          setAssignation(prev => prev ? { ...prev, ...msg } : prev);
          break;
        case 'assignation_yield':
          setYields(prev => [...prev, msg.value]);
          break;
        case 'assignation_done':
          setAssignation(prev => prev ? { 
            ...prev, 
            status: 'DONE', 
            returns: msg.returns 
          } : prev);
          break;
        case 'assignation_error':
          setAssignation(prev => prev ? { 
            ...prev, 
            status: 'ERROR', 
            error: msg.error 
          } : prev);
          break;
      }
    };

    ws.addEventListener('message', handler);
    return () => ws.removeEventListener('message', handler);
  }, [assignation?.id, ws]);

  return {
    assign,
    assignation,
    isRunning: assignation?.status === 'RUNNING' || assignation?.status === 'ASSIGNED',
    error: assignation?.error ?? null,
    yields,
  };
}
```

### Usage Example: Capture Button

```tsx
function CaptureButton() {
  const { assign, isRunning, assignation } = useAssignAction('capture_image');

  const handleCapture = async () => {
    await assign({ exposure_time: 0.1 });
  };

  return (
    <div>
      <button onClick={handleCapture} disabled={isRunning}>
        {isRunning ? 'Capturing...' : 'Capture Image'}
      </button>
      {assignation?.status === 'DONE' && (
        <p>Captured: {assignation.returns?.image_id}</p>
      )}
    </div>
  );
}
```

### Usage Example: Time-Lapse with Progress

```tsx
function TimeLapseCapture() {
  const { assign, isRunning, yields, assignation } = useAssignAction('time_lapse');

  const startTimeLapse = async () => {
    await assign({ num_frames: 10, interval: 1.0 });
  };

  return (
    <div>
      <button onClick={startTimeLapse} disabled={isRunning}>
        {isRunning ? `Frame ${yields.length}/10...` : 'Start Time-Lapse'}
      </button>
      
      {isRunning && (
        <progress value={yields.length} max={10} />
      )}
      
      <div className="thumbnails">
        {yields.map((frame, i) => (
          <img key={i} src={`/images/${frame.image_id}`} alt={`Frame ${i}`} />
        ))}
      </div>
    </div>
  );
}
```

### useMicroscopeState Hook

Subscribe to real-time state updates:

```tsx
export function useMicroscopeState<T>(key: string, defaultValue: T): T {
  const [value, setValue] = useState<T>(defaultValue);
  const ws = useWebSocket();

  useEffect(() => {
    // Initial fetch
    fetch(`/state?key=${key}`)
      .then(res => res.json())
      .then(data => setValue(data.state[key] ?? defaultValue));

    // Subscribe to updates
    const handler = (event: MessageEvent) => {
      const msg = JSON.parse(event.data);
      if (msg.type === 'state_update' && key in msg.updates) {
        setValue(msg.updates[key]);
      }
    };
    ws.addEventListener('message', handler);
    return () => ws.removeEventListener('message', handler);
  }, [key, ws]);

  return value;
}

// Usage
function StagePosition() {
  const position = useMicroscopeState('stage.position', [0, 0, 0]);
  return <div>Stage: X={position[0]}, Y={position[1]}, Z={position[2]}</div>;
}
```

---

## Running the API

```bash
cd refactor
python run.py
# or
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000/docs for the interactive API documentation.

---

## Project Structure

```
refactor/
├── run.py                    # Simple startup script
├── api/
│   ├── __init__.py
│   ├── main.py               # Entry point
│   ├── app.py                # FastAPI app factory with lifespan
│   ├── routes.py             # All HTTP/WebSocket endpoints
│   ├── models.py             # Pydantic models
│   ├── dependencies.py       # Typed FastAPI dependencies
│   ├── managers.py           # ConnectionManager
│   ├── state.py              # StateProxy for buffered state
│   ├── microscope_actions.py # Registered microscope actions
│   └── actors/
│       ├── __init__.py       # Public exports
│       ├── messages.py       # Actor message types
│       ├── base.py           # Actor base class
│       ├── functional.py     # FunctionalActor wrapper
│       ├── agent.py          # Agent (manages actors)
│       └── registry.py       # DefinitionRegistry, @register
└── tests/
    ├── conftest.py           # Test fixtures
    ├── test_endpoints.py     # API endpoint tests
    ├── test_registry.py      # Registry tests
    ├── test_managers.py      # Manager tests
    ├── test_models.py        # Model tests
    ├── test_state.py         # State tests
    └── test_websocket.py     # WebSocket tests
```

---

## Running Tests

```bash
cd /path/to/ImSwitch
python -m pytest refactor/tests/ -v
```

All 95 tests should pass.
