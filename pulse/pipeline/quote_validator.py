import re
from typing import List, Dict, Any
from pulse.ingestion.models import Review

def clean_text(text: str) -> str:
    # Normalize whitespace and punctuation for validation
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def validate_quotes(generated_theme: Dict[str, Any], source_reviews: List[Review]) -> Dict[str, Any]:
    if not generated_theme or "quotes" not in generated_theme:
        return generated_theme
        
    valid_quotes = []
    source_texts = [clean_text(r.text) for r in source_reviews]
    
    for quote in generated_theme.get("quotes", []):
        clean_quote = clean_text(quote)
        
        # Check substring match
        is_valid = False
        for st in source_texts:
            if clean_quote in st:
                is_valid = True
                break
                
        if is_valid:
            valid_quotes.append(quote)
        else:
            print(f"Dropped hallucinated quote: {quote}")
            
    generated_theme["quotes"] = valid_quotes
    return generated_theme
