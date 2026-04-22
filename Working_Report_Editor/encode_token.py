"""
encode_token.py — Run this ONCE on your PC to encode token.pickle for GitHub.

Steps:
  1. Run your project locally once so token.pickle is created
  2. Run: python encode_token.py
  3. Copy the printed base64 string
  4. Paste it into GitHub → Settings → Secrets → TOKEN_PICKLE_B64
"""

import base64

with open("token.pickle", "rb") as f:
    encoded = base64.b64encode(f.read()).decode("utf-8")

print("=" * 60)
print("Copy everything below this line and paste into GitHub Secret")
print("Secret name: TOKEN_PICKLE_B64")
print("=" * 60)
print(encoded)
