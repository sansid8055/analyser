from openai import OpenAI
import json
from typing import List, Dict, Any

def summarize_cluster(cluster_data: Dict[str, Any], api_key: str, model="llama-3.3-70b-versatile", max_samples=8) -> Dict[str, Any]:
    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    
    # Sort reviews by length or usefulness and take top max_samples
    samples = sorted(cluster_data["reviews"], key=lambda r: len(r.text), reverse=True)[:max_samples]
    
    reviews_text = ""
    for r in samples:
        reviews_text += f"Rating: {r.rating} | Text: {r.text}\n"
        
    prompt = f"""
You are an expert product analyst. Analyze the following cluster of user reviews (size: {cluster_data['size']}, avg rating: {cluster_data['avg_rating']:.1f}).

Generate a JSON object strictly following this schema:
{{
  "theme_name": "Short descriptive name",
  "summary": "1 sentence description",
  "quotes": ["exact quote 1", "exact quote 2"],
  "action_ideas": [
    {{ "title": "Idea title", "detail": "Idea detail" }}
  ]
}}

Reviews:
{reviews_text}
"""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a JSON-only API. Only output valid JSON without markdown formatting like ```json."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=800,
            temperature=0.2
        )
        content = response.choices[0].message.content.strip()
        if content.startswith('```json'):
            content = content[7:-3]
        if content.startswith('```'):
            content = content[3:-3]
            
        return json.loads(content)
    except Exception as e:
        print(f"LLM Summarization failed for cluster {cluster_data['label']}: {e}")
        return {}
