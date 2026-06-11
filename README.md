# Weekly Pulse Note Generator

This application automates the process of generating a Weekly Pulse Note for product and growth teams by analyzing recent app reviews from the Apple App Store and Google Play Store. 

It was built as part of the LIP Challenge (4).

## Features
- **Cross-Platform Scraping**: Fetches reviews from both the Google Play Store and Apple App Store.
- **Date Filtering**: Automatically filters reviews to only include those from the last 8-12 weeks (configurable).
- **LLM-Powered Analysis**: Uses OpenAI to group reviews into max 5 themes, and generates a one-page pulse note containing the Top 3 themes, 3 real user quotes, and 3 actionable ideas.
- **No PII**: All quotes are anonymized and stripped of usernames/IDs.
- **Export & Share**: Includes 1-click buttons to download the raw CSV, download the Markdown report, and draft an email to your team.

## How to Re-Run for a New Week
1. Launch the app by running `streamlit run app_streamlit.py` in your terminal.
2. Open the UI in your browser (`http://localhost:8501`).
3. In the sidebar:
   - Paste your **OpenAI API Key**.
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
*Built using Streamlit, `google-play-scraper`, `app-store-scraper`, and `openai`.*
