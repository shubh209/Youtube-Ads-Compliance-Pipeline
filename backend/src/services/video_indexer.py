import json
import os
import logging
import re
from typing import Dict, Any

from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from langchain_community.vectorstores import AzureSearch
from langchain_core.messages import SystemMessage, HumanMessage

from backend.src.graph.state import VideoAuditState
from backend.src.services.video_indexer import YouTubeTranscriptService

logger = logging.getLogger("brand-guardian")
logging.basicConfig(level=logging.INFO)

# Suppress Azure SDK HTTP noise
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
logging.getLogger("azure.monitor").setLevel(logging.WARNING)
logging.getLogger("azure.identity").setLevel(logging.WARNING)


def _require_env(var_name: str) -> str:
    value = os.getenv(var_name)
    if not value:
        raise ValueError(f"Missing required environment variable: {var_name}")
    return value


# --- NODE 1: THE INDEXER ---
def index_video_node(state: VideoAuditState) -> Dict[str, Any]:
    """
    Fetches transcript and metadata directly from YouTube Data API v3.
    No video download, no Azure Video Indexer — fast and reliable.
    """
    video_url = state.get("video_url")
    logger.info(f"--- [Node: Indexer] Processing: {video_url} ---")

    try:
        if not video_url:
            raise ValueError("No video_url provided in state.")

        yt_service = YouTubeTranscriptService()
        clean_data = yt_service.extract_data(video_url)

        logger.info("--- [Node: Indexer] Extraction Complete ---")
        return clean_data

    except Exception as e:
        logger.error(f"Video Indexer Failed: {e}")
        return {
            "errors": [str(e)],
            "final_status": "FAIL",
            "final_report": f"Video indexing failed: {str(e)}",
            "transcript": "",
            "ocr_text": [],
            "compliance_results": [],
        }


# --- NODE 2: THE COMPLIANCE AUDITOR ---
def audit_content_node(state: VideoAuditState) -> Dict[str, Any]:
    """
    Performs Retrieval-Augmented Generation (RAG) to audit the content.
    """
    logger.info("--- [Node: Auditor] querying Knowledge Base & LLM ---")

    transcript = state.get("transcript", "")

    if not transcript:
        logger.warning("No transcript available. Skipping Audit.")
        return {
            "final_status": "FAIL",
            "final_report": "Audit skipped because video processing failed (No Transcript).",
            "compliance_results": [],
        }

    try:
        azure_openai_endpoint    = _require_env("AZURE_OPENAI_ENDPOINT")
        azure_openai_api_key     = _require_env("AZURE_OPENAI_API_KEY")
        azure_openai_api_version = _require_env("AZURE_OPENAI_API_VERSION")
        chat_deployment          = _require_env("AZURE_OPENAI_CHAT_DEPLOYMENT")
        embed_deployment         = _require_env("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
        azure_search_endpoint    = _require_env("AZURE_SEARCH_ENDPOINT")
        azure_search_key         = _require_env("AZURE_SEARCH_API_KEY")
        azure_search_index_name  = _require_env("AZURE_SEARCH_INDEX_NAME")

        logger.info(f"Chat deployment: {chat_deployment}")
        logger.info(f"Embedding deployment: {embed_deployment}")

        llm = AzureChatOpenAI(
            azure_deployment=chat_deployment,
            azure_endpoint=azure_openai_endpoint,
            api_key=azure_openai_api_key,
            openai_api_version=azure_openai_api_version,
            temperature=0.0,
        )

        embeddings = AzureOpenAIEmbeddings(
            azure_deployment=embed_deployment,
            azure_endpoint=azure_openai_endpoint,
            api_key=azure_openai_api_key,
            openai_api_version=azure_openai_api_version,
        )

        vector_store = AzureSearch(
            azure_search_endpoint=azure_search_endpoint,
            azure_search_key=azure_search_key,
            index_name=azure_search_index_name,
            embedding_function=embeddings.embed_query,
        )

        ocr_text = state.get("ocr_text", [])
        query_text = f"{transcript} {' '.join(ocr_text)}".strip()

        docs = vector_store.similarity_search(query_text, k=3)
        retrieved_rules = "\n\n".join([doc.page_content for doc in docs]) if docs else ""

        # Include video metadata in the audit context
        metadata = state.get("video_metadata", {})
        video_title = metadata.get("title", "Unknown")

        system_prompt = f"""
You are a Senior Brand Compliance Auditor specializing in YouTube advertising policy.

OFFICIAL REGULATORY RULES:
{retrieved_rules}

INSTRUCTIONS:
1. Analyze the video transcript, description, and metadata below.
2. Identify ANY violations of YouTube Ad Policies or FTC guidelines.
3. Return strictly valid JSON in the following format:

{{
    "compliance_results": [
        {{
            "category": "Claim Validation",
            "severity": "CRITICAL",
            "description": "Explanation of the violation..."
        }}
    ],
    "status": "FAIL",
    "final_report": "Summary of findings..."
}}

Severity levels:
- CRITICAL: Must be fixed before ad can run
- WARNING: Should be reviewed
- INFO: Minor recommendation

If no violations are found, set "status" to "PASS" and "compliance_results" to [].
Do not include markdown fences or any text outside the JSON.
""".strip()

        user_message = f"""
VIDEO TITLE: {video_title}
VIDEO METADATA: {metadata}
TRANSCRIPT: {transcript}
ON-SCREEN TEXT / DESCRIPTION: {ocr_text}
""".strip()

        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ])

        content = response.content.strip()

        if "```" in content:
            match = re.search(r"```(?:json)?\s*(.*?)```", content, re.DOTALL)
            if match:
                content = match.group(1).strip()

        audit_data = json.loads(content)

        return {
            "compliance_results": audit_data.get("compliance_results", []),
            "final_status": audit_data.get("status", "FAIL"),
            "final_report": audit_data.get("final_report", "No report generated."),
        }

    except Exception as e:
        logger.error(f"System Error in Auditor Node: {str(e)}")
        logger.error(
            f"Raw LLM Response: {response.content if 'response' in locals() else 'None'}"
        )
        return {
            "errors": [str(e)],
            "final_status": "FAIL",
            "final_report": f"Auditor node failed: {str(e)}",
            "compliance_results": [],
        }