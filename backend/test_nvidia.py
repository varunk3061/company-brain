import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("NVIDIA_API_KEY"),
    base_url="https://integrate.api.nvidia.com/v1",
)

try:
    models = client.models.list()
    print("Model catalogue is accessible.")

    matches = [
        model.id for model in models.data
        if "nemotron-3.5-super-vl-120b-a12b" in model.id
    ]
    print("Matching models:", matches)

    response = client.chat.completions.create(
        model="nvidia/nemotron-3.5-super-vl-120b-a12b",
        messages=[{"role": "user", "content": "Reply with OK."}],
        max_tokens=32,
    )
    print("Completion:", response.choices[0].message.content)

except Exception as exc:
    print("Error:", type(exc).__name__)
    print("Details:", str(exc))