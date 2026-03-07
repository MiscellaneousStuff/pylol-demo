import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("XAI_API_KEY"),
    base_url="https://api.x.ai/v1",
)

def invoke_model(s):
    # Send a basic reasoning query
    response = client.chat.completions.create(
        model="grok-4-1-fast",
        messages=[
            {"role": "user", "content": s}
        ],
        max_tokens=4096,
        temperature=0.2,
    )

    return response.choices[0].message.content