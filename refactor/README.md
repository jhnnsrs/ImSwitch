# Microscope Control API

A modern, async-first API for microscope control with real-time state synchronization and a declarative action system.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        React Frontend                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ useAction()  │  │  useState()  │  │ useWebSocket │          │
│  │ "capture"    │  │  "stage.pos" │  │  (updates)   │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
└─────────┼─────────────────┼─────────────────┼───────────────────┘
          │                 │                 │
          ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Backend                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ ActionRegistry│  │  StateProxy  │  │ WebSocket    │          │
│  │ @register    │  │  (buffered)  │  │ Broadcasts   │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                           │                                     │
│                    ┌──────┴──────┐                              │
│                    │EngineManager│                              │
│                    │ Task Queue  │                              │
│                    └──────┬──────┘                              │
└───────────────────────────┼─────────────────────────────────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │   Microscope    │
                   │   Hardware      │
                   └─────────────────┘
```

## Core Concepts

### 1. Action Registry

Actions are the atomic operations the microscope can perform. They're registered with a simple decorator:

```python
# api/actions.py
from refactor.api import register

@register(
    name="capture_image",
    description="Capture an image from the camera",
    parameters_schema={
        "type": "object",
        "properties": {
            "exposure_time": {"type": "number"},
            "channel": {"type": "string"},
        },
    },
    tags=["imaging", "camera"],
)
async def capture_image(params):
    # Interact with actual hardware here
    image = await camera.capture(
        exposure=params.get("exposure_time", 0.1)
    )
    return {"image_id": image.id, "shape": image.shape}
```

### 2. State Proxy (Buffered State)

The `StateProxy` provides a shared state that:
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

### 3. Engine Manager (Task Queue)

Long-running or sequential operations are scheduled as tasks:

```python
POST /tasks
{
    "name": "Z-Stack Acquisition",
    "action": "acquire_z_stack",
    "parameters": {"z_start": 0, "z_end": 100, "z_step": 1}
}
```

Tasks emit WebSocket events: `task_scheduled`, `task_started`, `task_completed`, `task_failed`.

---

## React Frontend Integration

### useAction Hook

A React hook that wraps action execution with loading states and error handling:

```tsx
// hooks/useAction.ts
import { useState, useCallback } from 'react';

interface ActionResult<T> {
  execute: (params?: Record<string, any>) => Promise<T>;
  data: T | null;
  loading: boolean;
  error: Error | null;
}

export function useAction<T = any>(actionName: string): ActionResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const execute = useCallback(async (params = {}) => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`/actions/${actionName}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: actionName, parameters: params }),
      });
      const result = await response.json();
      setData(result.result);
      return result.result;
    } catch (err) {
      setError(err as Error);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [actionName]);

  return { execute, data, loading, error };
}
```

### Usage in Components

```tsx
// components/CaptureButton.tsx
function CaptureButton() {
  const { execute, loading } = useAction('capture_image');

  return (
    <button 
      onClick={() => execute({ exposure_time: 0.1 })}
      disabled={loading}
    >
      {loading ? 'Capturing...' : 'Capture Image'}
    </button>
  );
}
```

### useMicroscopeState Hook

Subscribe to real-time state updates via WebSocket:

```tsx
// hooks/useMicroscopeState.ts
import { useState, useEffect } from 'react';

export function useMicroscopeState<T>(key: string, defaultValue: T): T {
  const [value, setValue] = useState<T>(defaultValue);
  const ws = useWebSocket(); // Your WebSocket context

  useEffect(() => {
    // Initial fetch
    fetch(`/state?key=${key}`)
      .then(res => res.json())
      .then(data => setValue(data.state[key] ?? defaultValue));

    // Subscribe to updates
    const handler = (message: any) => {
      if (message.type === 'state_update' && message.keys.includes(key)) {
        setValue(message.updates[key]);
      }
    };
    ws.on('message', handler);
    return () => ws.off('message', handler);
  }, [key]);

  return value;
}
```

### Usage in Components

```tsx
// components/StagePosition.tsx
function StagePosition() {
  const position = useMicroscopeState('stage.position', [0, 0, 0]);
  const { execute } = useAction('move_stage');

  return (
    <div>
      <p>X: {position[0]} Y: {position[1]} Z: {position[2]}</p>
      <button onClick={() => execute({ position: [0, 0, 0] })}>
        Go Home
      </button>
    </div>
  );
}
```

### useTask Hook

For long-running operations with progress tracking:

```tsx
// hooks/useTask.ts
export function useTask() {
  const [task, setTask] = useState<Task | null>(null);
  const ws = useWebSocket();

  const schedule = async (name: string, action: string, params: any) => {
    const response = await fetch('/tasks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, action, parameters: params }),
    });
    const newTask = await response.json();
    setTask(newTask);
    return newTask;
  };

  useEffect(() => {
    if (!task) return;
    
    const handler = (msg: any) => {
      if (msg.task_id === task.id) {
        setTask(prev => ({ ...prev, status: msg.type.replace('task_', '') }));
      }
    };
    ws.on('message', handler);
    return () => ws.off('message', handler);
  }, [task?.id]);

  return { task, schedule, cancel: () => fetch(`/tasks/${task?.id}`, { method: 'DELETE' }) };
}
```

---

## API Endpoints

### Actions
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/actions` | List all registered actions |
| GET | `/actions?tag=imaging` | Filter actions by tag |
| GET | `/actions/{name}` | Get action details & schema |
| POST | `/actions/{name}/execute` | Execute action immediately |

### State
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/state` | Get full state snapshot |
| GET | `/state?key=stage.position` | Get specific key |
| PUT | `/state` | Update single key |
| PATCH | `/state` | Batch update multiple keys |
| DELETE | `/state/{key}` | Delete a key |

### Tasks
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/tasks` | Schedule a new task |
| GET | `/tasks` | List all tasks |
| GET | `/tasks?status=running` | Filter by status |
| GET | `/tasks/{id}` | Get task details |
| DELETE | `/tasks/{id}` | Cancel a task |

### WebSocket
| Endpoint | Description |
|----------|-------------|
| `ws://host/ws` | Real-time updates |

**WebSocket Message Types:**
- `state_update` - Buffered state changes
- `task_scheduled`, `task_started`, `task_completed`, `task_failed`
- `processing_start`, `processing_complete`

---

## Running the Server

```bash
# Simple run script
python refactor/run.py

# Or with uvicorn directly
uvicorn refactor.api.app:create_app --factory --reload
```

## Adding Custom Actions

Create a new file or add to `api/actions.py`:

```python
from refactor.api import register

@register(
    name="my_custom_action",
    description="Does something custom",
    tags=["custom"],
)
async def my_custom_action(params):
    # Your implementation
    return {"status": "done"}
```

The action is automatically available at `/actions/my_custom_action/execute`.

---

## Design Principles

1. **Declarative Actions**: Actions are self-describing with schemas, enabling automatic UI generation
2. **Reactive State**: UI subscribes to state; hardware updates push to UI automatically
3. **Task-Based Async**: Long operations don't block; progress is streamed via WebSocket
4. **Type Safety**: Pydantic models + TypeScript types = end-to-end type safety
5. **Separation of Concerns**: Actions define *what*, Engine handles *when*, State tracks *current*
