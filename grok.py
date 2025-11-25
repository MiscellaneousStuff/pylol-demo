# import os
# from xai_sdk import Client
# from xai_sdk.tools import code_execution, web_search, x_search, collections_search, mcp

import os
from dotenv import load_dotenv
from openai import OpenAI

from dotenv import load_dotenv
load_dotenv()

# client = Client(api_key=os.getenv("XAI_API_KEY"))
# chat = client.chat.create(
#     model="grok-4-1-fast-reasoning",
#     tools=[
#         web_search(),
#         x_search(),
#         code_execution(),
#         collections_search(collection_ids=["..."]),
#         mcp(server_url="..."),
#     ],
# )

client = OpenAI(
    api_key=os.getenv("XAI_API_KEY"),
    base_url="https://api.x.ai/v1",
)

# Send a basic reasoning query
response = client.chat.completions.create(
    model="grok-4-1-fast",
    messages=[
        {"role": "user", "content": "What kind of activity would you suggest, if it rains in San Francisco? Answer in one sentence."}
    ],
    max_tokens=1000,
    temperature=0.2,  # lower temperature for more deterministic answers
)

print(response.choices[0].message.content)