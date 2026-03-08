# try to invoke bedrock Qwen3 VL

import boto3 
import json 
import base64  

client = boto3.client("bedrock-runtime", region_name="eu-west-1")  


# image_path = "../../app/data/receipts/IMG_3492.HEIC"
image_path = "/Users/oleh_venhryniuk/Projects/my-finance/receipt_parser/app/data/receipts/IMG_3492.HEIC"

with open(image_path, "rb") as f: 
    image_data = base64.standard_b64encode(f.read()).decode("utf-8")  

response = client.invoke_model( 
    modelId="qwen.qwen3-vl-235b-a22b", 
    body=json.dumps({ 
        "anthropic_version": "bedrock-2023-05-31", 
        "max_tokens": 1024, 
        "messages": [{ 
            "role": "user", 
            "content": [ 
                { 
                    "type": "image", 
                    "source": { 
                        "type": "base64", 
                        "media_type": "image/heic", 
                        "data": image_data 
                     } 
                }, 
                { 
                     "type": "text", 
                     "text": """Extract structured data from this receipt image.
                                Don't add any information that is not explicitly present in the image.
                                Return ONLY valid JSON (no markdown, no code fences).
                                Return a JSON object with keys:
                                - items (list of {name, amount, unit, unit_price, item_price})
                                where each item has:
                                    - name (str): item description (e.g., "beef")
                                    - amount (float): quantity (e.g., 0.5)
                                    - unit (str): unit of measurement (e.g., "kg", "pcs", "l")
                                    - unit_price (float): price per unit (e.g., 300)
                                    - item_price (float): total price for this item (e.g., 150)
                                - store (str): store name
                                - date (str): date in ISO-8601 format
                                - total (float): total receipt amount
                                - raw_text (str): full OCR text from receipt
                                """
                } 
            ] 
        }] 
    }) 
)  

result = json.loads(response["body"].read()) 
print(result["content"][0]["text"])