import argparse
import yaml
import os
from datetime import datetime
from pulse.ingestion.play_store import fetch_play_store_reviews
from pulse.ingestion.normalizer import normalize_reviews
from pulse.ingestion.cache import save_cache
from pulse.pipeline.scrubber import scrub_pii
from pulse.pipeline.embeddings import generate_embeddings
from pulse.pipeline.clustering import cluster_reviews
from pulse.pipeline.summarizer import summarize_cluster
from pulse.pipeline.quote_validator import validate_quotes
from pulse.render.doc_section import build_section
from pulse.render.email_teaser import build_teaser
from pulse.agent.mcp_client import append_to_doc, create_email_draft
from pulse.ledger.store import RunLedger

def main():
    parser = argparse.ArgumentParser(description="Weekly Pulse Note CLI")
    parser.add_argument("--product", required=True, help="Product slug (e.g., groww)")
    parser.add_argument("--iso-week", default=datetime.now().strftime("%Y-W%W"), help="ISO week (e.g., 2026-W23)")
    parser.add_argument("--dry-run", action="store_true", help="Skip MCP writes")
    parser.add_argument("--mcp-server-url", default=os.getenv("MCP_SERVER_URL", "http://localhost:8000"), help="URL of the external MCP server")
    
    args = parser.parse_args()
    
    print(f"Starting pulse run for {args.product} week {args.iso_week}...")
    
    # Load config
    with open(f"config/products/{args.product}.yaml", "r") as f:
        product_cfg = yaml.safe_load(f)
    with open("config/pipeline.yaml", "r") as f:
        pipeline_cfg = yaml.safe_load(f)
        
    app_id = product_cfg["play_store"]["app_id"]
    window_weeks = product_cfg["ingestion"]["window_weeks"]
    display_name = product_cfg.get("display_name", args.product.capitalize())
    
    # Initialize Ledger
    ledger = RunLedger()
    
    # Phase 1: Ingestion
    print("Fetching reviews from Play Store...")
    raw_reviews = fetch_play_store_reviews(app_id, window_weeks)
    
    print(f"Normalizing {len(raw_reviews)} raw reviews...")
    normalized_reviews = normalize_reviews(raw_reviews, min_words=product_cfg["ingestion"]["min_words"])
    
    if len(normalized_reviews) < product_cfg["ingestion"]["min_reviews"]:
        print(f"Aborting: Only {len(normalized_reviews)} normalized reviews found, need at least {product_cfg['ingestion']['min_reviews']}.")
        return
        
    print(f"Saving {len(normalized_reviews)} normalized reviews to cache...")
    save_cache(args.product, args.iso_week, raw_reviews, normalized_reviews)
    
    try:
        run_id = ledger.start_run(args.product, args.iso_week, len(normalized_reviews), window_weeks)
    except Exception as e:
        print(f"Ledger Error: {e}")
        return
        
    try:
        # Phase 2: Pipeline
        print("Scrubbing PII...")
        for r in normalized_reviews:
            r.text = scrub_pii(r.text)
            
        print("Generating embeddings via OpenAI...")
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            raise Exception("OPENAI_API_KEY not found in environment")
            
        embeddings = generate_embeddings(
            [r.text for r in normalized_reviews], 
            api_key=openai_key, 
            model=pipeline_cfg["embedding"]["model"],
            batch_size=pipeline_cfg["embedding"]["batch_size"]
        )
        
        print("Running UMAP and HDBSCAN clustering...")
        clusters = cluster_reviews(
            normalized_reviews, 
            embeddings,
            n_neighbors=pipeline_cfg["clustering"]["umap"]["n_neighbors"],
            n_components=pipeline_cfg["clustering"]["umap"]["n_components"],
            min_cluster_size=pipeline_cfg["clustering"]["hdbscan"]["min_cluster_size"]
        )
        
        # Phase 3: Summarization
        print("Summarizing top clusters using Groq LLM...")
        groq_key = os.getenv("GROQ_API_KEY")
        if not groq_key:
            raise Exception("GROQ_API_KEY not found in environment")
            
        top_clusters = clusters[:pipeline_cfg["summarization"]["max_themes"]]
        
        final_report = []
        for c in top_clusters:
            theme_data = summarize_cluster(c, api_key=groq_key, model=pipeline_cfg["summarization"]["model"])
            if theme_data:
                # Validate Quotes
                theme_data = validate_quotes(theme_data, c["reviews"])
                final_report.append(theme_data)
                
        print("\n--- GENERATED PULSE NOTE ---")
        for theme in final_report:
            print(f"\nTheme: {theme.get('theme_name')}")
            print(f"Summary: {theme.get('summary')}")
            print("Quotes:")
            for q in theme.get('quotes', []):
                print(f' - "{q}"')
            print("Action Ideas:")
            for a in theme.get('action_ideas', []):
                print(f" - {a.get('title')}: {a.get('detail')}")
                
        # Phase 4 & 5: Delivery via MCP
        if args.dry_run:
            print("\nDry run completed. Skipping MCP delivery.")
            ledger.mark_completed(run_id)
        else:
            mcp_url = args.mcp_server_url
            doc_id = product_cfg["delivery"]["google_doc_id"]
            recipients = product_cfg["delivery"]["email"]["recipients"]

            # --- Phase 4: Google Docs ---
            print(f"\nDelivering to Google Docs via MCP server at {mcp_url}...")
            doc_content = build_section(
                product_display_name=display_name,
                iso_week=args.iso_week,
                window_weeks=window_weeks,
                themes=final_report,
            )

            try:
                doc_response = append_to_doc(mcp_url, doc_id, doc_content)
                doc_external_id = doc_response.get("heading_id", doc_response.get("id", ""))
                doc_url = doc_response.get("url", f"https://docs.google.com/document/d/{doc_id}")
                print(f"Google Doc updated successfully.")
            except Exception as doc_err:
                print(f"Google Docs delivery failed: {doc_err}")
                doc_external_id = ""
                doc_url = f"https://docs.google.com/document/d/{doc_id}"

            ledger.record_delivery(
                run_id, "google_doc", doc_external_id, doc_url,
                f"{args.product}-{args.iso_week}"
            )

            # --- Phase 5: Gmail ---
            print(f"Creating Gmail draft via MCP server at {mcp_url}...")
            email_data = build_teaser(
                product_display_name=display_name,
                iso_week=args.iso_week,
                window_weeks=window_weeks,
                themes=final_report,
                doc_url=doc_url,
            )

            for recipient in recipients:
                try:
                    email_response = create_email_draft(
                        mcp_url,
                        to=recipient,
                        subject=email_data["subject"],
                        body=email_data["body"],
                    )
                    draft_id = email_response.get("draft_id", email_response.get("id", ""))
                    print(f"Gmail draft created for {recipient}.")
                except Exception as email_err:
                    print(f"Gmail draft failed for {recipient}: {email_err}")
                    draft_id = ""

                ledger.record_delivery(
                    run_id, "gmail", draft_id, "",
                    f"{args.product}-{args.iso_week}-email"
                )

            ledger.mark_completed(run_id)
            print("Run and delivery completed successfully!")
            
    except Exception as e:
        print(f"Run failed: {e}")
        ledger.mark_failed(run_id, str(e))

if __name__ == "__main__":
    main()
