# Celery & Redis Setup

This project uses Celery for asynchronous task processing with Redis as the message broker and result backend.

## Architecture

- **Redis**: Message broker and result backend
- **Celery Worker**: Processes background tasks
- **Celery Beat**: Scheduler for periodic tasks (optional)

## Services

The following services are configured in `docker-compose.yml`:

1. **redis**: Redis server on port 6379
2. **celery_worker**: Celery worker that processes tasks
3. **celery_beat**: Celery beat scheduler for periodic tasks

## Starting the Services

Start all services including Redis and Celery:

```bash
docker-compose up --build
```

Or start in detached mode:

```bash
docker-compose up -d --build
```

## Using Celery Tasks

### 1. Creating a New Task

Create a new task in `app/tasks/`:

```python
from app.core.celery_app import celery_app
import logging

logger = logging.getLogger(__name__)

@celery_app.task(name="app.tasks.my_module.my_task")
def my_task(arg1: str, arg2: int) -> dict:
    """
    Description of what the task does.
    
    Args:
        arg1: Description
        arg2: Description
        
    Returns:
        dict: Result
    """
    logger.info(f"Processing task with {arg1} and {arg2}")
    
    # Your task logic here
    result = {"status": "success", "data": arg1}
    
    return result
```

### 2. Calling a Task from Your API

```python
from app.tasks.my_module import my_task

# Call task asynchronously
task = my_task.delay("hello", 42)
task_id = task.id

# Or with apply_async for more control
task = my_task.apply_async(
    args=["hello", 42],
    countdown=60  # Execute after 60 seconds
)
```

### 3. Checking Task Status

```python
from celery.result import AsyncResult
from app.core.celery_app import celery_app

task_result = AsyncResult(task_id, app=celery_app)

# Check status
print(task_result.status)  # PENDING, STARTED, SUCCESS, FAILURE

# Get result (blocking)
if task_result.ready():
    result = task_result.result
```

## API Endpoints

The project includes example endpoints for testing Celery:

### Submit a Task

```bash
# Add two numbers
curl -X POST http://localhost:8000/api/tasks/add \
  -H "Content-Type: application/json" \
  -d '{"x": 10, "y": 20}'

# Response: {"task_id": "abc-123", "status": "PENDING"}
```

### Check Task Status

```bash
curl http://localhost:8000/api/tasks/{task_id}

# Response: 
# {
#   "task_id": "abc-123",
#   "status": "SUCCESS",
#   "result": {"data": 30}
# }
```

### Cancel a Task

```bash
curl -X DELETE http://localhost:8000/api/tasks/{task_id}
```

## Common Use Cases

### 1. Send Email Asynchronously

```python
from app.tasks.email_tasks import send_email_task

send_email_task.delay(
    to_email="user@example.com",
    subject="Welcome!",
    html_content="<h1>Welcome to Zendora</h1>"
)
```

### 2. Process Data in Background

```python
from app.tasks.example_tasks import process_data

task = process_data.delay({"items": [1, 2, 3]})
```

### 3. Scheduled/Periodic Tasks

Configure in `app/core/celery_app.py`:

```python
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    'send-daily-reports': {
        'task': 'app.tasks.reports.generate_daily_report',
        'schedule': crontab(hour=9, minute=0),  # 9:00 AM daily
    },
    'cleanup-old-data': {
        'task': 'app.tasks.cleanup.cleanup_old_data',
        'schedule': crontab(hour=2, minute=0, day_of_week=0),  # 2:00 AM every Sunday
    },
}
```

## Monitoring

### View Worker Logs

```bash
docker-compose logs -f celery_worker
```

### View Beat Logs

```bash
docker-compose logs -f celery_beat
```

### Check Redis

```bash
# Connect to Redis CLI
docker-compose exec redis redis-cli

# Check number of pending tasks
> LLEN celery
```

## Task Configuration

Tasks can be configured with various options:

```python
@celery_app.task(
    name="app.tasks.important_task",
    bind=True,              # Bind to get 'self' with task info
    max_retries=3,          # Maximum retry attempts
    default_retry_delay=60, # Delay between retries (seconds)
    time_limit=300,         # Hard time limit (seconds)
    soft_time_limit=270,    # Soft time limit (seconds)
    acks_late=True,         # Acknowledge after task completes
    reject_on_worker_lost=True,
)
def important_task(self, data):
    try:
        # Task logic
        return {"success": True}
    except Exception as exc:
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
```

## Environment Variables

The following environment variables are used:

- `REDIS_URL`: Redis connection URL (default: `redis://localhost:6379/0`)
- `CELERY_BROKER_URL`: Celery broker URL (defaults to REDIS_URL)
- `CELERY_RESULT_BACKEND`: Celery result backend URL (defaults to REDIS_URL)

## Development Tips

1. **Auto-reload Workers**: For development, add `--autoreload` flag:
   ```bash
   celery -A app.core.celery_app worker --loglevel=info --autoreload
   ```

2. **Test Tasks in Shell**: Use Celery's Python shell:
   ```bash
   docker-compose exec api python -m celery -A app.core.celery_app shell
   ```

3. **Purge All Tasks**: Clear all pending tasks:
   ```bash
   docker-compose exec api celery -A app.core.celery_app purge
   ```

4. **Inspect Active Tasks**:
   ```bash
   docker-compose exec api celery -A app.core.celery_app inspect active
   ```

## Production Considerations

1. **Scale Workers**: Run multiple worker instances:
   ```bash
   docker-compose up --scale celery_worker=4
   ```

2. **Task Queues**: Organize tasks by priority:
   ```python
   # High priority queue
   important_task.apply_async(args=[data], queue='high_priority')
   
   # Low priority queue
   background_task.apply_async(args=[data], queue='low_priority')
   ```

3. **Monitoring Tools**: Consider using:
   - Flower: Celery monitoring tool
   - Prometheus + Grafana: Metrics and dashboards

4. **Redis Persistence**: Configure Redis for data persistence in production

## Troubleshooting

### Tasks not executing
- Check worker is running: `docker-compose ps`
- Check worker logs: `docker-compose logs celery_worker`
- Verify Redis connection: `docker-compose exec redis redis-cli ping`

### Tasks stuck in PENDING
- Worker might be down or overwhelmed
- Check task is registered: `docker-compose exec api celery -A app.core.celery_app inspect registered`

### High memory usage
- Limit tasks per child: `--max-tasks-per-child=100`
- Reduce prefetch multiplier: `--prefetch-multiplier=1`
