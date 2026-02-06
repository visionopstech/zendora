from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.tasks.example_tasks import add_numbers, process_data
from celery.result import AsyncResult
from app.core.celery_app import celery_app

router = APIRouter(prefix="/tasks", tags=["tasks"])


class TaskSubmitResponse(BaseModel):
    """Response when submitting a task."""
    task_id: str
    status: str


class TaskStatusResponse(BaseModel):
    """Response for task status check."""
    task_id: str
    status: str
    result: Optional[dict] = None
    error: Optional[str] = None


class AddNumbersRequest(BaseModel):
    """Request to add two numbers."""
    x: int
    y: int


class ProcessDataRequest(BaseModel):
    """Request to process data."""
    data: dict


@router.post("/add", response_model=TaskSubmitResponse)
async def submit_add_task(request: AddNumbersRequest):
    """
    Submit a task to add two numbers asynchronously.
    
    Returns the task ID that can be used to check status.
    """
    task = add_numbers.delay(request.x, request.y)
    return TaskSubmitResponse(
        task_id=task.id,
        status=task.status
    )


@router.post("/process", response_model=TaskSubmitResponse)
async def submit_process_task(request: ProcessDataRequest):
    """
    Submit a task to process data asynchronously.
    
    Returns the task ID that can be used to check status.
    """
    task = process_data.delay(request.data)
    return TaskSubmitResponse(
        task_id=task.id,
        status=task.status
    )


@router.get("/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """
    Get the status of a task by its ID.
    
    Returns:
        - status: PENDING, STARTED, SUCCESS, FAILURE, RETRY, REVOKED
        - result: The task result if completed successfully
        - error: Error message if task failed
    """
    task_result = AsyncResult(task_id, app=celery_app)
    
    response = TaskStatusResponse(
        task_id=task_id,
        status=task_result.status
    )
    
    if task_result.ready():
        if task_result.successful():
            response.result = {"data": task_result.result}
        else:
            response.error = str(task_result.info)
    elif task_result.state == 'PROGRESS':
        response.result = task_result.info
    
    return response


@router.delete("/{task_id}")
async def cancel_task(task_id: str):
    """
    Cancel/revoke a task by its ID.
    """
    task_result = AsyncResult(task_id, app=celery_app)
    task_result.revoke(terminate=True)
    
    return {
        "task_id": task_id,
        "status": "revoked"
    }
