from flask import Flask, request, jsonify
import os

app = Flask(__name__)
UPLOAD_FOLDER = 'incoming_plates'

# 🛡️ Your exclusive API Key (Must exactly match the one in the ESP32 code)
SECRET_KEY = "ParkReserve-Group29-SuperSecret"

# Ensure the image storage directory exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# 🌐 Adopt RESTful API routing (Using bay_id as a path parameter)
@app.route('/api/v1/bays/<int:bay_id>/image', methods=['POST'])
def upload_file(bay_id):
    
    # ==========================================
    # 1. Core Security Defense: Block requests with missing or incorrect API Keys
    # ==========================================
    client_key = request.headers.get('X-API-Key')
    if client_key != SECRET_KEY:
        print(f"⚠️ [Security Block] Illegal request from {request.remote_addr} rejected!")
        return jsonify({"error": "Unauthorized"}), 401

    # ==========================================
    # 2. Extract Business Data: Get the exact capture timestamp
    # ==========================================
    capture_time = request.headers.get('X-Timestamp', 'unknown_time')
    
    # ==========================================
    # 3. Process Image Data
    # ==========================================
    image_data = request.data
    if not image_data:
        return jsonify({"error": "No image data provided"}), 400

    # Concatenate filename with timestamp to prevent overwriting images from the same bay
    filename = f"bay_{bay_id}_{capture_time}.jpg"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    
    # Save the image to the local disk
    with open(filepath, 'wb') as f:
        f.write(image_data)
    
    print(f"✅ [Security Passed] Image received for Bay {bay_id} | Captured at: {capture_time} | Saved as {filename}")
    
    # ==========================================
    # 4. Return 202 Accepted to decouple frontend and backend
    # ==========================================
    # Returning 202 instead of 200 standardly means "The server has accepted the request, but processing is not yet complete."
    # This allows the ESP32 to immediately resume its tasks while the Gateway proceeds to call OpenALPR.
    return jsonify({"message": "Image securely received", "file": filename}), 202

if __name__ == '__main__':
    # Listen on all network interfaces so ESP32 devices on the local network can access it
    app.run(host='0.0.0.0', port=5000)