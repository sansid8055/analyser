from openai import OpenAI
from typing import List
import os

def generate_embeddings(texts: List[str], api_key: str, model="text-embedding-3-small", batch_size=64) -> List[List[float]]:
    client = OpenAI(api_key=api_key)
    all_embeddings = []
    
    # Process in batches
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        try:
            response = client.embeddings.create(input=batch, model=model)
            batch_embeddings = [data.embedding for data in response.data]
            all_embeddings.extend(batch_embeddings)
        except Exception as e:
            print(f"Error generating embeddings for batch {i}: {e}")
            # Pad with zeros or handle gracefully in production
            all_embeddings.extend([[0.0] * 1536 for _ in batch])
            
    return all_embeddings
