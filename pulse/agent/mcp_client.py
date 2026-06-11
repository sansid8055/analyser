import requests
from typing import Optional


def append_to_doc(
    server_url: str,
    doc_id: str,
    content: str,
) -> dict:
    """
    Append text content to a Google Doc via the external MCP server.

    Endpoint: POST {server_url}/append_to_doc
    Payload:  { "doc_id": "...", "content": "..." }

    Returns the JSON response from the MCP server.
    Raises on HTTP or connection errors.
    """
    url = f"{server_url.rstrip('/')}/append_to_doc"
    payload = {"doc_id": doc_id, "content": content}

    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def create_email_draft(
    server_url: str,
    to: str,
    subject: str,
    body: str,
) -> dict:
    """
    Create a Gmail draft via the external MCP server.

    Endpoint: POST {server_url}/create_email_draft
    Payload:  { "to": "...", "subject": "...", "body": "..." }

    Returns the JSON response from the MCP server.
    Raises on HTTP or connection errors.
    """
    url = f"{server_url.rstrip('/')}/create_email_draft"
    payload = {"to": to, "subject": subject, "body": body}

    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()
