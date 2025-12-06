## Doughnuts Order Assistant (current behavior)

FastAPI gateway + SmolVLA (per-order subprocess) + evdev-based `R` key gating.
Frontend (chat app, etc.) uses HTTP + SSE.

### API
- **POST `/orders`**
  - Body: `{"flavor": "chocolate" | "strawberry"}`
  - Returns: `{"request_id": "..."}`
- **POST `/orders/{request_id}/cancel`**
  - Returns: `{"canceled": true}`
- **GET `/events`** (SSE)
  - `Content-Type: text/event-stream`
  - `data:` payload examples:
    - Status:
      ```json
      {"type":"status_update","request_id":"...","stage":"PUTTING_DONUT","progress":0.5,"message":"Putting doughnuts into the box..."}
      ```
    - Completed:
      ```json
      {"type":"completed","request_id":"...","result":{"delivered":true,"flavor":"chocolate"}}
      ```
    - Error:
      ```json
      {"type":"error","request_id":"...","message":"robot error ..."}
      ```

### State management (`state_controller`)
- Phases: `WAITING` → `PUTTING_DONUT` → `CLOSING_LID` → `DONE` (or `CANCELED` / `ERROR`)
- `OrderStateManager` updates phases and pushes SSE events.

### Robot execution (current)
- Each order spawns `robot_controller.vla_controller_rtc` as a subprocess (loads model per order).
- After the policy run finishes, we gate completion by physical `R` key:
  - R detection via `evdev` (`/dev/input/event*`, needs permission).
  - Debounced (0.3s); after accepting `R`, wait 10s before completing.
  - Flow: `PUTTING_DONUT` → (policy run) → `CLOSING_LID` → (R + 10s) → `DONE`.

### Prerequisites
- Python 3.10.x (`requires-python = ">=3.10,<3.11"`).
- ROCm stack (torch/vision/audio + pytorch-triton-rocm pinned to rocm6.3).
- `evdev` installed and permission to read `/dev/input/event*` (udev rule or run with appropriate privileges).
- Model: `masato-ka/smolvla-donuts-shop-v1`.
- Robot ports/cameras (default in `LerobotDonutRobotAdapter`):
  - left_arm: `/dev/ttyACM3`
  - right_arm: `/dev/ttyACM2`
  - cameras: `/dev/video4`, `/dev/video6`

### Run (dev)
```bash
cd mission2/code/doughnuts_order_assistant
uv sync           # install deps from pyproject/uv.lock
uv run uvicorn api.app:app --reload --host 0.0.0.0 --port 8000
```

### Quick test
```bash
# Subscribe to SSE
curl -N http://0.0.0.0:8000/events

# Send an order
curl -X POST 'http://0.0.0.0:8000/orders' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{"flavor": "chocolate"}'
```

You should observe `PUTTING_DONUT` → `CLOSING_LID` → `DONE` on `/events` after pressing physical `R`.

