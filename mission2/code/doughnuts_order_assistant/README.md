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

### Robot execution (persistent worker)
- **Persistent worker process**: Model is loaded once, handles multiple orders via Unix socket.
- Two-phase execution per order:
  - Phase 1: `PUTTING_DONUT` - "Please take the {flavor} donuts and into the box."
  - Phase 2: `CLOSING_LID` - "Please close the box."
- R-key gating between phases:
  - R detection via `evdev` (`/dev/input/event*`, needs permission).
  - Debounced (0.3s); after accepting `R`, wait 10s before proceeding.
  - Success is determined **only by R-key presses** (not by policy exit codes).
  - Flow: Phase 1 → (R + 10s) → Phase 2 → (R + 10s) → `DONE`.

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

**1. Start the persistent worker** (in a separate terminal):

**Option A: Using the `worker` command (after `uv sync` on Linux)**:
```bash
cd mission2/code/doughnuts_order_assistant
uv sync  # Run this once on Linux to register the script
uv run worker  # Uses default arguments
# Or override specific arguments:
uv run worker --duration=60 --device=cpu
```

**Option B: Using the module directly (works everywhere, recommended)**:
```bash
cd mission2/code/doughnuts_order_assistant
uv run python -m robot_controller.worker_cli  # Uses default arguments
# Or override specific arguments:
uv run python -m robot_controller.worker_cli --duration=60 --device=cpu
```

**Option C: Using worker_main with full arguments**:
```bash
cd mission2/code/doughnuts_order_assistant
uv run python -m robot_controller.worker_main \
  --policy.path=masato-ka/smolvla-donuts-shop-v1 \
  --policy.device=cuda \
  --robot.type=bi_so101_follower \
  --robot.id=bi_robot \
  --robot.left_arm_port=/dev/ttyACM3 \
  --robot.right_arm_port=/dev/ttyACM2 \
  --robot.cameras="{front: {type: opencv, index_or_path: /dev/video4, width: 640, height: 480, fps: 30}, back: {type: opencv, index_or_path: /dev/video6, width: 640, height: 480, fps: 30}}" \
  --rtc.enabled=true \
  --rtc.execution_horizon=12 \
  --rtc.max_guidance_weight=10.0 \
  --duration=120 \
  --fps=30 \
  --device=cuda \
  --use_torch_compile=false \
  --policy.input_features='{"observation.state": {"type": "STATE", "shape": [12]}}' \
  --policy.output_features='{"action": {"type": "ACTION", "shape": [12]}}'
```

**2. Start the FastAPI server** (in another terminal):
```bash
cd mission2/code/doughnuts_order_assistant
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

