from fastapi import FastAPI, UploadFile, File
from fastapi.testclient import TestClient
import multipart

app = FastAPI()

@app.post("/")
def upload(file: UploadFile = File(...)):
    return {"filename": file.filename}

client = TestClient(app)

def test_upload():
    try:
        response = client.post("/", files={"file": ("test.txt", b"content")})
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_upload()
