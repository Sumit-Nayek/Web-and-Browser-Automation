
import json

from pydantic import BaseModel, create_model
from typing import Optional
import logging

log = logging.getLogger(__name__)

import os
from openai import OpenAI

# It will now pull securely from the Codespaces vault.
# If the key is missing, it will throw a clear error instead of silently failing.
api_key = os.environ.get("NVIDIA_API_KEY")
if not api_key:
    raise ValueError("NVIDIA_API_KEY environment variable is not set. Check your Codespace secrets.")

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=api_key,
    max_retries=0  # CRITICAL: Prevent the SDK from waiting for multiple timeouts
)
def extract_missing_fields_with_llm(text_chunk: str, missing_fields: list[str]) -> dict:
    """
    Dynamically creates a Pydantic schema based on the missing fields,
    then queries the NVIDIA NIM to extract only those fields.
    """
    if not missing_fields:
        return {}

    log.info(f"Querying NIM for missing fields: {missing_fields}")
    
    # 1. Dynamically create a Pydantic model requiring only the missing fields
    schema_fields = {field: (Optional[str], ...) for field in missing_fields}
    DynamicSchema = create_model('MissingFieldsSchema', **schema_fields)

    # 2. Build the system prompt
    system_prompt = (
        "You are an expert financial data extraction AI. "
        "Extract the requested financial terms from the SEC filing text provided. "
        "If a field is truly not present in the text (e.g., an FWP missing a trade date), return null. "
        "Return the data strictly conforming to the requested JSON schema."
    )

    try:
        # We use a fast, highly capable model like Llama 3 70B hosted on NIM
        # Update the model string to point to the correct 3.1 version
        # Using the free DeepSeek endpoint on NVIDIA NIM
        # Using Llama 3.1 8B Instruct for high availability and low latency
        response = client.chat.completions.create(
            model="meta/llama-3.1-8b-instruct",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text_chunk[:15000]} 
            ],
            temperature=0,
            max_tokens=512,
            timeout=15.0, # We can reduce this to 15 seconds since Llama 8B is so fast
            response_format={
                "type": "json_object",
                "schema": DynamicSchema.model_json_schema()
            }
        )
        
        extracted_data = json.loads(response.choices[0].message.content)
        return extracted_data

    except Exception as e:
        log.error(f"LLM Extraction failed: {e}")
        return {field: None for field in missing_fields}