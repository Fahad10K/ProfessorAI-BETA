import requests
import os

# Test PDF upload
def test_upload():
    url = "http://localhost:8000/api/upload-pdfs"
    
    # Create a test file if it doesn't exist
    test_pdf = "test_upload.pdf"
    if not os.path.exists(test_pdf):
        with open(test_pdf, 'wb') as f:
            f.write(b'%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Resources<<>>/Contents 4 0 R/Parent 2 0 R>>endobj 4 0 obj<</Length 44>>stream\nBT /F1 24 Tf 100 700 Td (This is a test PDF) Tj ET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f \n0000000000 00000 n \n0000000069 00000 n \n0000000116 00000 n \n0000000179 00000 n\n\ntrailer\n<</Size 5/Root 1 0 R>>\nstartxref\n234\n%%EOF')
    
    # Open the file in binary mode
    with open(test_pdf, 'rb') as f:
        files = [('files', (test_pdf, f, 'application/pdf'))]
        data = {'course_title': 'Test Course'}
        
        try:
            print("Sending request to:", url)
            response = requests.post(
                url, 
                files=files,
                data=data
            )
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.text}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    test_upload()
