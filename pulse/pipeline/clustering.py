import numpy as np
import umap
import hdbscan
from typing import List, Dict, Any
from pulse.ingestion.models import Review

def cluster_reviews(reviews: List[Review], embeddings: List[List[float]], n_neighbors=15, n_components=5, min_cluster_size=5) -> List[Dict[str, Any]]:
    if len(reviews) < 20:
        return []
        
    embeddings_np = np.array(embeddings)
    
    # 1. Dimensionality reduction
    reducer = umap.UMAP(
        n_neighbors=n_neighbors,
        n_components=n_components,
        metric='cosine',
        random_state=42
    )
    reduced_embeddings = reducer.fit_transform(embeddings_np)
    
    # 2. Clustering
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=3,
        gen_min_span_tree=True
    )
    cluster_labels = clusterer.fit_predict(reduced_embeddings)
    
    # 3. Group and rank clusters
    clusters_data = {}
    
    for idx, label in enumerate(cluster_labels):
        if label == -1:
            continue # Noise
            
        if label not in clusters_data:
            clusters_data[label] = {
                "label": label,
                "reviews": [],
                "size": 0,
                "avg_rating": 0.0,
                "score": 0.0
            }
            
        clusters_data[label]["reviews"].append(reviews[idx])
        clusters_data[label]["size"] += 1
        
    # Calculate score = size × (6 - avg_rating)
    result = []
    for label, data in clusters_data.items():
        ratings = [r.rating for r in data["reviews"]]
        avg_rating = sum(ratings) / len(ratings)
        score = data["size"] * (6 - avg_rating)
        
        data["avg_rating"] = avg_rating
        data["score"] = score
        result.append(data)
        
    # Sort by score descending
    result.sort(key=lambda x: x["score"], reverse=True)
    return result
