from app.core.celery_app import celery_app
import logging
import time

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.example.add_numbers")
def add_numbers(x: int, y: int) -> int:
    """
    Example task: Add two numbers.
    
    Args:
        x: First number
        y: Second number
        
    Returns:
        int: Sum of x and y
    """
    logger.info(f"Adding {x} + {y}")
    result = x + y
    logger.info(f"Result: {result}")
    return result


@celery_app.task(name="app.tasks.example.process_data", bind=True)
def process_data(self, data: dict) -> dict:
    """
    Example task: Process some data with progress tracking.
    
    Args:
        data: Dictionary containing data to process
        
    Returns:
        dict: Processed data
    """
    total_steps = 10
    
    for i in range(total_steps):
        # Update task state to show progress
        self.update_state(
            state='PROGRESS',
            meta={
                'current': i + 1,
                'total': total_steps,
                'status': f'Processing step {i + 1}/{total_steps}'
            }
        )
        
        # Simulate work
        time.sleep(1)
        logger.info(f"Processed step {i + 1}/{total_steps}")
    
    return {
        "status": "completed",
        "processed_items": total_steps,
        "original_data": data
    }
