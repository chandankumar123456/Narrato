from fastapi import FastAPI
import json
import uuid
import os 

from SlideGenerator.slide_gen import generate_slides
from SlideGenerator.ppt_gen import create_ppt

app = FastAPI()

@app.post("/generate")
def generate_presentation(prompt: str):
    raw = generate_slides(prompt)
    slides = json.loads(raw)

    file_name = f"{uuid.uuid4()}.pptx"
    output_dir = os.path.join(os.getcwd(), "output")  # absolute path
    file_path = os.path.join(output_dir, file_name)

    create_ppt(slides, file_path)

    return {"download_url": f"/download/{file_name}"}


from fastapi.responses import FileResponse

@app.get("/download/{file_name}")
def download(file_name: str):
    file_path = os.path.join(os.getcwd(), "output", file_name)
    return FileResponse(
        file_path,
        media_type='application/vnd.openxmlformats-officedocument.presentationml.presentation',
        filename=file_name
    )