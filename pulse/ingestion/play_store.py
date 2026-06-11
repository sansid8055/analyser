from google_play_scraper import Sort, reviews
from datetime import datetime, timedelta
import hashlib
from typing import List
from pulse.ingestion.models import RawReview

def fetch_play_store_reviews(app_id: str, window_weeks: int) -> List[RawReview]:
    cutoff_date = datetime.now() - timedelta(weeks=window_weeks)
    all_raw_reviews = []
    
    # We use google_play_scraper
    try:
        ps_reviews, _ = reviews(
            app_id,
            lang='en',
            country='us',
            sort=Sort.NEWEST,
            count=10000 # Just fetch a lot and filter by date
        )
        
        seen_hashes = set()
        
        for r in ps_reviews:
            dt = r['at']
            if dt >= cutoff_date:
                # Deduplicate by hash
                content_hash = hashlib.sha256(f"{r['content']}_{r['score']}_{dt}".encode()).hexdigest()
                if content_hash not in seen_hashes:
                    seen_hashes.add(content_hash)
                    
                    all_raw_reviews.append(
                        RawReview(
                            review_id=r.get('reviewId', content_hash),
                            text=r['content'],
                            rating=r['score'],
                            published_at=dt,
                            source="play_store"
                        )
                    )
    except Exception as e:
        print(f"Failed to fetch Play Store reviews: {e}")
        
    return all_raw_reviews
