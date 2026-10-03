# app/routes/image_routes.py
import os
from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse
from app.ml.landmark_detector import detect_landmark

router = APIRouter(prefix="/image", tags=["image"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/landmark")
async def identify_landmark(file: UploadFile = File(...)):
    # save temp image
    filepath = os.path.join(UPLOAD_DIR, file.filename)

    with open(filepath, "wb") as f:
        f.write(await file.read())

    # run inference
    result = detect_landmark(filepath)

    # remove file after prediction (optional)
    # os.remove(filepath)

    return JSONResponse(result)
