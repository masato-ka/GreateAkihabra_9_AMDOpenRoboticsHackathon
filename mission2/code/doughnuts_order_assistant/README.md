## Doughnuts Order Assistant Overview

A small FastAPI gateway that triggers a SmolVLA + real robot pipeline to
pick a **chocolate or strawberry doughnut**, put it into a box, and close the lid.
Frontend (chat app, etc.) talks to this gateway over HTTP and SSE.

### API

- **POST `/orders`**
  - Purpose: Start a doughnut order.
  - Request JSON:
    - `flavor`: `"chocolate"` or `"strawberry"`
  - Response JSON:
    - `request_id`: Unique ID of the order

- **POST `/orders/{request_id}/cancel`**
  - Purpose: Cancel an in‑progress order.
  - Response JSON:
    - `canceled`: `true` if the cancel succeeded

- **GET `/events` (SSE)**
  - Purpose: Receive all order state updates as Server‑Sent Events.
  - `Content-Type: text/event-stream`
  - Example `data:` JSON payloads:
    - Status update:
      ```json
      {
        "type": "status_update",
        "request_id": "uuid-1234",
        "stage": "PUTTING_DONUT",
        "progress": 0.5,
        "message": "Putting doughnuts into the box"
      }
      ```
    - Completed:
      ```json
      {
        "type": "completed",
        "request_id": "uuid-1234",
        "result": {
          "delivered": true,
          "flavor": "chocolate"
        }
      }
      ```
    - Error:
      ```json
      {
        "type": "error",
        "request_id": "uuid-1234",
        "message": "robot error ..."
      }
      ```

### State Management (`state_controller`)

- **Main phases (`OrderPhase`)**
  - `WAITING`: Order just accepted
  - `PUTTING_DONUT`: Robot is putting doughnuts into the box
  - `CLOSING_LID`: Robot is closing the lid
  - `DONE`: Finished successfully
  - `CANCELED`: Canceled
  - `ERROR`: Failed

- **Role of `OrderStateManager`**
  - `create_order(flavor)` creates a new order in `WAITING` phase.
  - `set_phase(...)` / `mark_completed(...)` / `mark_canceled(...)` / `mark_error(...)`
    update the phase **and** push SSE events via `events.iter_events()`.

### Robot Worker (design)

- **Worker process**
  - A long‑running worker under `robot_controller`:
    - Initializes the SmolVLA policy and robot **once** at startup.
    - Listens for “start order” commands from the API and, per order, runs:
      1. Put doughnuts into the box (`PUTTING_DONUT`)
      2. Wait for the operator to press `R` on the keyboard
      3. Close the lid (`CLOSING_LID`)
      4. When `R` is pressed again, mark the order as `DONE`

- **Flavor and task prompts**
  - `flavor == "chocolate"`:
    - e.g. `"Please take the chocolate donuts and into the box."`
  - `flavor == "strawberry"`:
    - e.g. `"Please take the strawberry donuts and into the box."`

### How to run (dev)

```bash
cd mission2/code/doughnuts_order_assistant

# Install dependencies (first time only)
uv sync

# Start the API server
uv run uvicorn api.app:app --reload --host 0.0.0.0 --port 8000
```

### Quick manual test

1. Subscribe to SSE in another terminal:
   ```bash
   curl -N http://0.0.0.0:8000/events
   ```
2. Send an order:
   ```bash
   curl -X POST 'http://0.0.0.0:8000/orders' \
     -H 'accept: application/json' \
     -H 'Content-Type: application/json' \
     -d '{"flavor": "chocolate"}'
   ```

With the robot worker wired in, you should see events like
`PUTTING_DONUT` → `CLOSING_LID` → `DONE` flowing over `/events`.

