from pydantic import BaseModel
from datetime import datetime

class RawReview(BaseModel):
    review_id: str
    text: str
    rating: int
    published_at: datetime
    source: str = "play_store"

class Review(BaseModel):
    review_id: str
    text: str
    rating: int
    published_at: datetime
    source: str = "play_store"
