import sqlite3
import os
import uuid
from datetime import datetime

class RunLedger:
    def __init__(self, db_path="data/ledger.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()
        
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            product TEXT,
            iso_week TEXT,
            status TEXT,
            review_count INTEGER,
            window_weeks INTEGER,
            started_at TEXT,
            completed_at TEXT,
            error_message TEXT
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS deliveries (
            run_id TEXT,
            channel TEXT,
            external_id TEXT,
            url TEXT,
            idempotency_key TEXT,
            FOREIGN KEY(run_id) REFERENCES runs(run_id)
        )
        ''')
        
        # Unique constraint for product + iso_week where status is completed
        cursor.execute('''
        CREATE UNIQUE INDEX IF NOT EXISTS idx_completed_runs 
        ON runs(product, iso_week) 
        WHERE status = 'completed'
        ''')
        
        conn.commit()
        conn.close()
        
    def start_run(self, product: str, iso_week: str, review_count: int, window_weeks: int) -> str:
        run_id = str(uuid.uuid4())
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if already completed
        cursor.execute("SELECT run_id FROM runs WHERE product=? AND iso_week=? AND status='completed'", (product, iso_week))
        if cursor.fetchone():
            raise Exception(f"Run for {product} week {iso_week} is already completed.")
            
        cursor.execute('''
        INSERT INTO runs (run_id, product, iso_week, status, review_count, window_weeks, started_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (run_id, product, iso_week, 'pending', review_count, window_weeks, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        return run_id
        
    def mark_completed(self, run_id: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE runs SET status='completed', completed_at=? WHERE run_id=?", (datetime.now().isoformat(), run_id))
        conn.commit()
        conn.close()
        
    def mark_failed(self, run_id: str, error: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE runs SET status='failed', error_message=? WHERE run_id=?", (error, run_id))
        conn.commit()
        conn.close()
        
    def record_delivery(self, run_id: str, channel: str, external_id: str, url: str, idempotency_key: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO deliveries (run_id, channel, external_id, url, idempotency_key)
        VALUES (?, ?, ?, ?, ?)
        ''', (run_id, channel, external_id, url, idempotency_key))
        conn.commit()
        conn.close()
