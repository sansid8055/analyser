# Weekly Pulse Note Generator

This application automates the process of generating a Weekly Pulse Note for product and growth teams by analyzing recent app reviews from the Apple App Store and Google Play Store. 

It was built as part of the LIP Challenge (4).

The system supports two modes of operation:
1. **Interactive Frontend (Streamlit)**: A web UI for quickly generating and exporting pulse notes on the fly.
2. **Automated Pipeline (CLI + MCP)**: A highly structured background process that groups reviews via UMAP/HDBSCAN clustering, generates summaries using Groq's Llama-3 models, and uses an external MCP Server to directly update Google Docs and draft Gmail emails.

## Features
- **Cross-Platform Scraping**: Fetches reviews from both the Google Play Store and Apple App Store.
- **Date Filtering**: Automatically filters reviews to only include those from the last 8-12 weeks (configurable).
- **Advanced Clustering**: Uses OpenAI embeddings, UMAP, and HDBSCAN to intelligently group similar reviews into clusters before summarization.
- **LLM-Powered Analysis**: Uses Groq (`llama-3.3-70b-versatile`) to generate a pulse note containing the top themes, real user quotes, and actionable product ideas.
- **No PII**: All quotes are anonymized and stripped of usernames/IDs.
- **Automated Delivery**: The CLI tool communicates with an external MCP server to append findings directly to a Google Doc and draft summary emails to a predefined list of recipients.

## Setup
Ensure you have all dependencies installed:
```bash
pip install -r requirements.txt
```

### Environment Variables
Copy `.env.example` to `.env` and configure your API keys:
```
OPENAI_API_KEY=your_openai_api_key
GROQ_API_KEY=your_groq_api_key
MCP_SERVER_URL=http://localhost:8000
```

## How to Re-Run for a New Week

### Option A: Using the Automated CLI (Recommended)
You can trigger the pipeline to fetch reviews, cluster them, and automatically deliver the report via the MCP server:
```bash
python -m pulse.cli --product groww
```
* **Dry Run**: To test the pipeline without sending the report to Google Docs/Gmail, add `--dry-run`.
* **Configurations**: Behavior is controlled by `config/pipeline.yaml` and product-specific settings in `config/products/groww.yaml`.

### Option B: Using the Interactive UI (Streamlit)
1. Launch the app by running `streamlit run app_streamlit.py` in your terminal.
2. Open the UI in your browser (`http://localhost:8501`).
3. In the sidebar:
   - Your **Groq API Key** will load from your `.env` file automatically.
   - Select the **Weeks of Reviews to Fetch** (e.g., set to 8 or 12).
   - Enter your **Play Store App ID** (e.g., `com.whatsapp`).
   - Enter your **App Store Name & ID** (e.g., `whatsapp-messenger` and `310633997`).
4. Click **Generate Weekly Pulse**.
5. Once the analysis is complete, click **Draft Email** to send the latest note to your alias!

## Theme Legend
The LLM dynamically categorizes reviews into up to 5 of the most relevant themes based on the current week's data. Examples of themes include:
- **Onboarding/Signup**: Issues or praise regarding account creation, logging in, or KYC.
- **Payments/Transactions**: Feedback on adding funds, making payments, or withdrawals.
- **UI/UX & Navigation**: Comments on the app's design, ease of use, or finding specific features.
- **Performance/Bugs**: Reports of crashes, freezing, or slow loading times.
- **Customer Support**: Experiences with getting help, chatbots, or email support.

---
*Built using Python, Streamlit, Groq, OpenAI, HDBSCAN, and Model Context Protocol (MCP).*
