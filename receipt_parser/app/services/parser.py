from datetime import date
from qreader import QReader
import cv2 as cv
import numpy as np
import requests 

# Create a QReader instance
qreader = QReader()


def parse_receipt_image(image_bytes: bytes) -> dict:  # noqa: ARG001
    """
    Decode QR code from receipt image and fetch tax cabinet data using the URL in the QR.
    """
    # Convert image bytes to OpenCV format
    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv.imdecode(nparr, cv.IMREAD_COLOR)
    image = cv.cvtColor(image, cv.COLOR_BGR2RGB)

    # Use the detect_and_decode function to get the decoded QR data
    # qreader returns a tuple of decoded strings
    decoded_text = qreader.detect_and_decode(image=image)

    print("Decoded QR data:", decoded_text)

    result = {"raw_text": decoded_text}
    
    # Extract the first decoded URL from the tuple
    if decoded_text and len(decoded_text) > 0:
        qr_url = decoded_text[0]
        print(f"QR URL: {qr_url}")
        
        # Fetch the tax cabinet data using the URL from QR code
        try:
            tax_response = requests.get(qr_url)
            result["tax_cabinet_response"] = tax_response.text
            print("Tax cabinet response status:", tax_response.status_code)
        except Exception as e:
            result["tax_cabinet_error"] = str(e)
            print(f"Error fetching tax cabinet: {e}")
    
    return result
