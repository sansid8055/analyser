import os
import json
from typing import List
from datetime import datetime
from pulse.ingestion.models import RawReview, Review

def save_cache(product: str, date_str: str, raw_reviews: List[RawReview], normalized_reviews: List[Review]):
    cache_dir = os.path.join("data", "cache", product, date_str)
    os.makedirs(cache_dir, exist_ok=True)
    
    # Save raw
    raw_path = os.path.join(cache_dir, "reviews_raw.json")
    with open(raw_path, 'w', encoding='utf-8') as f:
        json.dump([r.model_dump(mode='json') for r in raw_reviews], f, indent=2)
        
    # Save normalized
    norm_path = os.path.join(cache_dir, "reviews_normalized.json")
    with open(norm_path, 'w', encoding='utf-8') as f:
        json.dump([r.model_dump(mode='json') for r in normalized_reviews], f, indent=2)
        
    # Save manifest
    manifest_path = os.path.join(cache_dir, "manifest.json")
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump({
            "product": product,
            "date": date_str,
            "raw_count": len(raw_reviews),
            "normalized_count": len(normalized_reviews)
        }, f, indent=2)

def load_normalized_cache(product: str, date_str: str) -> List[Review]:
    norm_path = os.path.join("data", "cache", product, date_str, "reviews_normalized.json")
    if not os.path.exists(norm_path):
        return []
        
    with open(norm_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return [Review(**r) for r in data]
