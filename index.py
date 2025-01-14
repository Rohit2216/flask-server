
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import face_recognition
import mysql.connector
from mysql.connector.pooling import MySQLConnectionPool
import base64
from io import BytesIO
import os
from PIL import Image
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Ensure UPLOAD_FOLDER points to the correct path relative to the script
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'public/user_images')

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)  # Create the folder if it doesn't exist

# Database configuration
db_config = {
    "host": os.getenv("DB_HOST", "46.202.163.32"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "database": os.getenv("DB_NAME", "erp"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", "Rohit@2309"),
    "pool_name": "mypool",
    "pool_size": 5
}

# Initialize connection pool
try:
    connection_pool = MySQLConnectionPool(**db_config)
except Exception as e:
    print(f"Error connecting to MySQL database: {e}")
    raise

def get_db_connection():
    try:
        connection = connection_pool.get_connection()
        return connection
    except Exception as e:
        print(f"Error getting database connection from pool: {e}")
        raise

def extract_image_name(image_path):
    """
    Extract the file name from the given path.
    """
    return os.path.basename(image_path) if image_path else None

@app.route('/compare-image', methods=['POST'])
def compare_image():
    conn = None
    cursor = None
    try:
        # Get the base64 image and user_id from the request
        data = request.json
        user_id = data.get('user_id')  # Get user_id
        image_data = data.get('image')

        if not user_id or not image_data:
            return jsonify({"success": False, "message": "No user_id or image provided"}), 400

        # Fetch stored image for the specific user from the database
        conn = get_db_connection()
        cursor = conn.cursor()

        # Query to get the stored image for the given user_id
        cursor.execute("SELECT name, email, mobile, image as photo FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()

        if not user:
            return jsonify({"success": False, "message": "User not found"}), 404

        # Extract the file name of the user's photo
        file_name = user[3]
        
        if not file_name:
            return jsonify({"success": False, "message": "No image found for this user"}), 404

        file_name = extract_image_name(file_name)  # Extract only the image name
        file_path = os.path.join(UPLOAD_FOLDER, file_name)

        print(f"Checking file path: {file_path}")  # Debug print to verify the file path

        if not os.path.exists(file_path):
            return jsonify({"success": False, "message": f"Stored image not found for user at {file_path}"}), 404

        # Decode and process the uploaded image
        image_data = image_data.split(',')[1]  # Extract the base64 part of the image
        image_bytes = base64.b64decode(image_data)
        img_array = face_recognition.load_image_file(BytesIO(image_bytes))
        img_encoding = face_recognition.face_encodings(img_array)
        if len(img_encoding) == 0:
            return jsonify({"success": False, "message": "No face detected"}), 400
        img_encoding = img_encoding[0]

        # Process the stored image
        stored_img_array = face_recognition.load_image_file(file_path)
        stored_img_encoding = face_recognition.face_encodings(stored_img_array)
        if len(stored_img_encoding) == 0:
            return jsonify({"success": False, "message": "No face detected in stored image"}), 400
        stored_img_encoding = stored_img_encoding[0]

        # Compare the uploaded image with the stored image
        # results = face_recognition.compare_faces([stored_img_encoding], img_encoding)
        results = face_recognition.compare_faces([stored_img_encoding], img_encoding, tolerance=0.5)  # Use stricter tolerance

        if results[0]:
            return jsonify({
                "success": True,
                "message": "User verified successfully!",
                "name": user[0],
                "email": user[1],
                "mobile": user[2],
                "photo": user[3]
            })
        else:
            return jsonify({"success": False, "message": "No matching face found for the user"}), 404

    except Exception as e:
        print("An error occurred:", str(e))
        return jsonify({"success": False, "message": "An error occurred on the server"}), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route('/user_images/<filename>')
def serve_image(filename):
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.isfile(file_path):
        return jsonify({"success": False, "message": "File not found"}), 404

    return send_from_directory(UPLOAD_FOLDER, filename)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=9000)
