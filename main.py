import sys
from ingest import run_pipeline as ingest_jobs
from evaluate import run_evaluation_loop
from dispatch import dispatch_top_matches

def run_agent():
    print("========================================")
    print("[*] JOB SCOUT AGENT: STARTING DAILY RUN")
    print("========================================\n")
    
    # 1. Fetch & Store
    print(">>> STEP 1: INGESTION")
    ingest_jobs()
    print()

    # 2. Score & Filter
    print(">>> STEP 2: EVALUATION")
    run_evaluation_loop()
    print()

    # 3. Alert
    print(">>> STEP 3: DISPATCH")
    dispatch_top_matches(min_score=60, limit=3)
    print()

    print("========================================")
    print("[+] JOB SCOUT AGENT: RUN COMPLETED")
    print("========================================")

if __name__ == "__main__":
    run_agent()