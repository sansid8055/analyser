import streamlit as st
import pandas as pd
from google_play_scraper import reviews, Sort
from app_store_scraper import AppStore

from datetime import datetime, timedelta
from openai import OpenAI
import urllib.parse

st.set_page_config(page_title="Weekly Pulse Note Generator", layout="wide")

st.title("📊 Weekly Pulse Note Generator")
st.markdown("Turn recent App Store + Play Store reviews into a one-page weekly pulse!")

import os
import yaml
from dotenv import load_dotenv

load_dotenv()

with st.sidebar:
    st.header("Settings")
    default_api_key = os.getenv("GROQ_API_KEY", "")
    groq_api_key = st.text_input("Groq API Key", type="password", value=default_api_key)
    weeks_to_fetch = st.slider("Weeks of Reviews to Fetch", min_value=1, max_value=12, value=8)
    
    st.divider()
    st.subheader("App Details")
    
    # Try to load default from config
    default_play_store_id = "com.nextbillion.groww"
    try:
        with open("config/products/groww.yaml", "r") as f:
            cfg = yaml.safe_load(f)
            default_play_store_id = cfg.get("play_store", {}).get("app_id", default_play_store_id)
    except Exception:
        pass

    play_store_id = st.text_input("Play Store App ID", value=default_play_store_id)
    app_store_name = st.text_input("App Store App Name", value="groww")
    app_store_id = st.text_input("App Store App ID", value="1404871703")
    
    fetch_button = st.button("Generate Weekly Pulse", type="primary")

@st.cache_data(show_spinner=False)
def fetch_reviews(play_store_id, app_store_name, app_store_id, weeks):
    cutoff_date = datetime.now() - timedelta(weeks=weeks)
    all_reviews = []
    
    # Play Store
    if play_store_id:
        try:
            ps_reviews, _ = reviews(
                play_store_id,
                lang='en',
                country='us',
                sort=Sort.NEWEST,
                count=1000
            )
            for r in ps_reviews:
                if r['at'] >= cutoff_date:
                    all_reviews.append({
                        "Source": "Play Store",
                        "Date": r['at'],
                        "Rating": r['score'],
                        "Title": "N/A", 
                        "Text": r['content']
                    })
        except Exception as e:
            st.warning(f"Failed to fetch Play Store reviews: {e}")
            
    # App Store
    if app_store_name and app_store_id:
        try:
            app_store = AppStore(country='us', app_name=app_store_name, app_id=app_store_id)
            app_store.review(how_many=1000)
            for r in app_store.reviews:
                if r['date'] >= cutoff_date:
                    all_reviews.append({
                        "Source": "App Store",
                        "Date": r['date'],
                        "Rating": r['rating'],
                        "Title": r.get('title', ''),
                        "Text": r.get('review', '')
                    })
        except Exception as e:
            st.warning(f"Failed to fetch App Store reviews: {e}")
            
    return pd.DataFrame(all_reviews)

def generate_pulse_note(df_reviews, api_key):
    if df_reviews.empty:
        return "No reviews found in the selected timeframe."
        
    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    
    # Sample up to 150 reviews to stay within Groq token limits
    if len(df_reviews) > 150:
        sample_df = df_reviews.sample(n=150, random_state=42)
    else:
        sample_df = df_reviews
        
    reviews_text = ""
    for idx, row in sample_df.iterrows():
        reviews_text += f"Rating: {row['Rating']} | Title: {row['Title']} | Text: {row['Text']}\n"
        
    prompt = f"""
You are an expert Product Manager. Analyze the following app reviews and generate a Weekly Pulse Note.

Requirements:
1. Group reviews into 5 themes max (e.g., onboarding, KYC, payments, statements, withdrawals).
2. Generate a weekly one-page note containing:
   - Top 3 themes (with brief description)
   - 3 real user quotes (do NOT include any PII, usernames, emails, or IDs)
   - 3 action ideas based on the reviews
3. Keep the note scannable and strictly UNDER 250 words.
4. Format as Markdown.

Reviews:
{reviews_text}
"""
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You are an expert product analyst."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=600
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Groq API Error: {str(e)}"

if fetch_button:
    if not groq_api_key:
        st.error("Please provide a Groq API Key in the sidebar.")
    elif not play_store_id and not (app_store_name and app_store_id):
        st.error("Please provide at least a Play Store App ID or App Store Name & ID.")
    else:
        with st.spinner("Fetching reviews..."):
            df = fetch_reviews(play_store_id, app_store_name, app_store_id, weeks_to_fetch)
            
        if df.empty:
            st.warning("No reviews found for the specified timeframe.")
        else:
            st.success(f"Fetched {len(df)} reviews from the last {weeks_to_fetch} weeks.")
            
            with st.spinner("Generating Weekly Pulse Note using Groq LLM..."):
                pulse_note = generate_pulse_note(df, groq_api_key)
                
            st.divider()
            st.markdown(pulse_note)
            
            st.divider()
            st.subheader("Export Options")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.download_button(
                    label="Download CSV",
                    data=df.to_csv(index=False).encode('utf-8'),
                    file_name="reviews.csv",
                    mime="text/csv"
                )
                
            with col2:
                st.download_button(
                    label="Download Note (MD)",
                    data=pulse_note.encode('utf-8'),
                    file_name="weekly_pulse.md",
                    mime="text/markdown"
                )
                
            with col3:
                subject = urllib.parse.quote("Weekly App Pulse Note")
                body = urllib.parse.quote(pulse_note)
                mailto_link = f"mailto:?subject={subject}&body={body}"
                st.markdown(f'<a href="{mailto_link}" target="_blank"><button style="background-color:#4CAF50;color:white;padding:8px 16px;border:none;border-radius:4px;cursor:pointer;">Draft Email</button></a>', unsafe_allow_html=True)
                
            st.divider()
            st.subheader("Raw Data Preview")
            st.dataframe(df, use_container_width=True)
