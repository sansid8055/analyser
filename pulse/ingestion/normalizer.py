import re
import emoji
from typing import List
from pulse.ingestion.models import RawReview, Review

def is_english(text: str) -> bool:
    # A very simple heuristic for English: only basic ASCII characters
    # In a real app we might use langdetect
    try:
        text.encode(encoding='utf-8').decode('ascii')
    except UnicodeDecodeError:
        return False
    return True

def has_emoji(text: str) -> bool:
    return emoji.emoji_count(text) > 0

def normalize_reviews(raw_reviews: List[RawReview], min_words: int = 8) -> List[Review]:
    normalized = []
    for r in raw_reviews:
        text = r.text.strip()
        word_count = len(text.split())
        
        if word_count < min_words:
            continue
            
        if has_emoji(text):
            continue
            
        # Optional: check if English
        # if not is_english(text):
        #     continue
            
        normalized.append(
            Review(
                review_id=r.review_id,
                text=text,
                rating=r.rating,
                published_at=r.published_at,
                source=r.source
            )
        )
        
    return normalized
