from pydantic import BaseModel, validator

class TodoItem(BaseModel):
    id: int
    title: str
    description: str = None
    completed: bool = False

    @validator('id', pre=True)
    def check_id(cls, v):
        if not isinstance(v, int) or v <= 0:
            raise ValueError('ID must be a positive integer')
        return v

    @validator('title', pre=True)
    def check_title(cls, v):
        if not v.strip():
            raise ValueError('Title cannot be empty')
        return v