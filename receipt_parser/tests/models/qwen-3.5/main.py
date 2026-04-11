# Use a pipeline as a high-level helper
from transformers import pipeline

import warnings
warnings.filterwarnings("ignore")


import os
import sys

import cv2
import numpy as np
from PIL import Image
# Suppress all stderr (including C++ backend messages)
sys.stderr = open(os.devnull, 'w')


pipe = pipeline("image-text-to-text", model="./Qwen3.5-2B", max_new_tokens=2048, max_length=2048)
# pipe = pipeline("image-text-to-text", model="Qwen/Qwen3.5-2B")

RECEIPT_PROMPT = """
Ukrainian supermarket receipt.
Extract structured data from this receipt image.
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
Make sure have a proper JSON format, otherwise the output will be rejected by the downstream system.
it must start with "{" and end with "}" and use double quotes for keys and string values.
First goes price per unit, then amount of good and then total price of this item.
For example: Банан 1 гат: 72.5 х 1.086 = 78.74. 
Extraction result should be:
{
            "name": "Банан",
            "unit_price": 72.5,
            "unit": "кг",
            "amount": 1.086,
            "item_price": 78.74
        },
"""

# messages = [
#     {
#         "role": "user",
#         "content": [
#             {"type": "image", "url": "./IMG_3479.jpg"},
#             {"type": "text", "text": RECEIPT_PROMPT}
#         ]
#     },
# ]

def resize_image(image_path, out_width=500):
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Image not found: {image_path}")
    h, w = img.shape[:2]
    new_w = out_width
    new_h = int(h * (out_width / w))
    resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
    pil_img = Image.fromarray(cv2.cvtColor(resized, cv2.COLOR_BGR2RGB))
    return pil_img


# Process image: just resize
receipt_img = resize_image("./data/test_2.png", out_width=1200)
# receipt_img.show()
receipt_img.save("cropped_receipt.png")


messages = [
    {
        "role": "user",
        "content": [
            {"type": "image", "url": "cropped_receipt.png"},
            {"type": "text", "text": RECEIPT_PROMPT}
        ]
    },
]
extraction_output = pipe(text=messages)
# print(extraction_output)
assistant_content = extraction_output[0]['generated_text'][1]['content']
print("Assistant content:", assistant_content)
extraction_data = json.loads(assistant_content)
print(json.dumps(extraction_data, indent=2))