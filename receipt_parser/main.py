from fastapi import FastAPI, UploadFile, File, HTTPException
from parser import parse_receipt_image

app = FastAPI(title="Receipt Parser Service")


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/parse_receipt")
def parse_receipt(file: UploadFile = File(...)):
    if file.content_type not in ("image/jpeg", "image/png", "image/jpg"):
        raise HTTPException(status_code=400, detail="Only JPEG and PNG images are supported")
    image_bytes = file.file.read()
    result = parse_receipt_image(image_bytes)
    return result
