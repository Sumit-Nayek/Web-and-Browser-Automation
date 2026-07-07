import os
from openai import OpenAI

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=os.environ.get("NVIDIA_API_KEY")
)

try:
    response = client.chat.completions.create(
        model="deepseek-ai/deepseek-v4-pro",
        messages=[{"role": "user", "content": "Say 'Connection successful!'"}]
    )
    print(response.choices[0].message.content)
except Exception as e:
    print(f"Error: {e}")