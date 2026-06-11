import re

def scrub_pii(text: str) -> str:
    # Basic email
    text = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '[EMAIL]', text)
    
    # Phone numbers (basic 10 digit or international)
    text = re.sub(r'\+?\d{1,3}[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{3,4}[-.\s]?\d{4}', '[PHONE]', text)
    
    # Simple ID numbers (like 12 digit aadhaar or PAN-like structure)
    text = re.sub(r'\b\d{12}\b', '[ID]', text)
    
    # We could scrub financial amounts, but prompt says "Keep in v1 - useful theme signal"
    
    return text
