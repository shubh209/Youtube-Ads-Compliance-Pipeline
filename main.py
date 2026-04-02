"""
Main Execution Entry Point for Brand Guardian AI.

Usage:
    # Pass URL directly as argument:
    python main.py https://youtu.be/dT7S75eYhcQ

    # Or run interactively (will prompt you):
    python main.py
"""

import uuid
import json
import sys
import logging
from dotenv import load_dotenv

load_dotenv(override=True)

from backend.src.graph.workflow import app

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("brand-guardian-runner")


def run_audit(video_url: str):
    """
    Runs a full compliance audit for the given YouTube URL.

    Args:
        video_url: A valid YouTube video URL (youtu.be or youtube.com)
    """
    session_id = str(uuid.uuid4())
    logger.info(f"Starting Audit Session: {session_id}")
    logger.info(f"Target URL: {video_url}")

    initial_inputs = {
        "video_url": video_url,
        "video_id": f"vid_{session_id[:8]}",
        "compliance_results": [],
        "errors": []
    }

    print("\n--- INPUT PAYLOAD ---")
    print(json.dumps(initial_inputs, indent=2))

    try:
        final_state = app.invoke(initial_inputs)

        print("\n--- WORKFLOW COMPLETE ---")
        print("\n=== COMPLIANCE AUDIT REPORT ===")
        print(f"Video ID : {final_state.get('video_id')}")
        print(f"Status   : {final_state.get('final_status')}")

        print("\n[ VIOLATIONS DETECTED ]")
        results = final_state.get('compliance_results', [])
        if results:
            for issue in results:
                print(f"  - [{issue.get('severity')}] {issue.get('category')}: {issue.get('description')}")
        else:
            print("  No violations found.")

        print("\n[ FINAL SUMMARY ]")
        print(final_state.get('final_report'))

    except Exception as e:
        logger.error(f"Workflow Execution Failed: {str(e)}")
        raise


if __name__ == "__main__":
    # --- Accept URL from CLI argument OR prompt the user ---
    if len(sys.argv) > 1:
        # e.g.  python main.py https://youtu.be/dT7S75eYhcQ
        url = sys.argv[1].strip()
    else:
        # Interactive fallback — no hardcoded URL
        url = input("Enter YouTube Ad URL to audit: ").strip()

    if not url:
        print("ERROR: No URL provided. Exiting.")
        sys.exit(1)

    if "youtube.com" not in url and "youtu.be" not in url:
        print("ERROR: Please provide a valid YouTube URL.")
        sys.exit(1)

    run_audit(url)