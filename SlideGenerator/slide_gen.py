from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI

client = OpenAI()

def generate_slides(prompt: str):
    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {
                "role": "system",
                "content": "Generate presentation slides in JSON format"
            },
            {
                "role": "user",
                "content": f"""
                Create slides for: {prompt}

                Format:
                [
                  {{
                    "title": "Slide title",
                    "bullets": ["point1", "point2"]
                  }}
                ]
                """
            }
        ]
    )
    return response.choices[0].message.content