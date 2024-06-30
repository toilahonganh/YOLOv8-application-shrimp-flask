import datetime
import io
import json
import os
import time
import secrets
import socketio

from PIL import Image
from socket import SocketIO
from requests import Session
from flask_mysqldb import MySQL
from flask_session import Session
from yolov8 import yolov8_predict
from werkzeug.utils import secure_filename
from flask_marshmallow import Marshmallow
from flask_cors import CORS, cross_origin
from flask_socketio import emit, SocketIO
from flask import Flask, request, jsonify, send_file, session

app = Flask(__name__)

socketio = SocketIO(app)
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mkv', 'mov'}
app.secret_key = 'dhbsfbsdbc8223bd'
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '12345678'
app.config['MYSQL_DB'] = 'yolov8shrimp'
mysql = MySQL(app)
ma = Marshmallow(app)

image_dir = "upload"

class UserSchema(ma.Schema):
    class Meta:
        fields = ('email', 'username', 'avatar', 'password')
        
user_schema = UserSchema()
users_schema = UserSchema(many=True) 

# Endpoint for mobile user login.
@app.route("/login-mobile", methods=["POST"])
def login_mobile():
    try:
        data = request.json
        email = data["email"]
        password = data["password"]

        cur = mysql.connection.cursor()
        cur.execute(f"\nSELECT * FROM user WHERE email = '{email}'\n")
        user = cur.fetchone()
        cur.close()

        if user and password == user[3]:
            session["user"] = {"email": email, "username": user[2]}
            token = secrets.token_hex(16)
            session["token"] = token
            print("\nLOGIN SUCCESSFUL\n")
            return jsonify({
                "success": True,
                "message": "Logged in successfully",
                "token": token
            })
        else:
            print("\nEMAIL OR USER ARE NOT DEFINED\n")
            return jsonify({
                "success": False,
                "message": "Email or password incorrect"
            }) 
            
    except Exception as e:
        print("\nLOGIN ERROR\n")
        return jsonify({"success": False, "message": "Error: " + str(e)})

# Endpoint for mobile user registration
@app.route("/register-mobile", methods=["POST"])
def register_mobile():
    data = request.json
    email = data["email"]
    username = data["username"]
    password = data["password"]

    if len(password) < 6:
        print("\nPASSWORD MUST BE OVER 6 CHARACTERS\n")
        return jsonify({
            "success": False,
            "message": "Password must contain at least 6 characters!"
        })
    try: 
        cur = mysql.connection.cursor()
        cur.execute(f"\nSELECT * FROM user WHERE email = '{email}'\n")
        existing_user = cur.fetchone()
        cur.close()
        print("\nUSER EXISTED\n")
        if existing_user:
            return jsonify({
                "success": False,
                "message": "User already exists!"
            })
        else:
            cur = mysql.connection.cursor()
            cur.execute(f"INSERT INTO user (email, username, avatar, password) VALUES ('{email}', '{username}', 'https://ps.w.org/user-avatar-reloaded/assets/icon-256x256.png?rev=2540745', '{password}')")
            mysql.connection.commit()
            cur.close()
            print("\nREGISTER SUCCESSFUL\n")
            return jsonify({"success": True, "message": "Đăng ký thành công"})
    except Exception as e:
        print("\nREGISTER FAILED\n")
        return jsonify({
            "success": False,
            "message": "Registration failed: " + str(e)
        })
    
# Endpoint for changing the password for a user.    
@app.route("/change_password_mobile", methods=["POST"])
def change_password_mobile():
    try:
        data = request.json
        email = data["email"]
        old_password = data["oldPassword"]
        new_password = data["newPassword"]
        new_username = data["newUsername"]

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM user WHERE email = %s", (email,))
        user = cur.fetchone()

        if user and user[3] == old_password:
            cur.execute(f"UPDATE user SET username = '{new_username}', password = '{new_password}' WHERE email = '{email}'")
            mysql.connection.commit()
            cur.close()
            return jsonify({"success": True, "message": "Password was successfully changed"})
        else:
            return jsonify({"success": False, "message": "Old email or password is incorrect"})
    except Exception as e:
        return jsonify({"success": False, "message": "Error when changing password: " + str(e)})

# Endpoint for uploading images and processing them with YOLOv8 model.
@app.route("/upload", methods=["POST"])
@cross_origin()
def upload_image():
    try:
        if "image" not in request.files:
            return jsonify({"error": "No image part"})
        image = request.files["image"]
        if image.filename == "":
            return jsonify({"error": "No selected image"})
        image_bytes = image.read()
        img = Image.open(io.BytesIO(image_bytes))
        model = yolov8_predict(img)

        if model is not None:
            unique_object_types = []
            shrimp_counts = {}
            response_datas = []
            for result in model["results"]:
                object_type = result["Object type"]
                if object_type not in unique_object_types:
                    unique_object_types.append(object_type)
                if object_type.endswith('Shrimp'):
                    if object_type not in shrimp_counts:
                        shrimp_counts[object_type] = 1
                    else:
                        shrimp_counts[object_type] += 1
        
            current_time = datetime.datetime.now()
            formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
            image_path = model["image_path"]
            total_shrimp = sum(shrimp_counts.values())
            shrimp_counts_str = ', '.join([f"{key}: {value}" for key, value in shrimp_counts.items()])
            shrimp_counts_json = json.dumps(shrimp_counts)
            email_user = session['user']['email']

            
            cur = mysql.connection.cursor()
            query = """INSERT INTO history (shrimp_image, shrimp_kind, shrimp_total, c_time, email) 
                    VALUES (%s, %s, %s, %s, %s)"""
            values = (image_path, shrimp_counts_json, total_shrimp, formatted_time, email_user)
            cur.execute(query, values)
            mysql.connection.commit()
            cur.close()

            print("\nIDENTIFICATION SUCCESSFUL\n")

            response_data = {
                "email_user": email_user,
                "shrimp_image": image_path,
                "c_time": formatted_time,
                "object_types": unique_object_types,
                "shrimp_kind" : shrimp_counts_str,
                "shrimp_total": total_shrimp
            }
            response_datas.append(response_data)
            return jsonify(response_datas)
        else:
            return jsonify({"message": "No objects detected in the image. Data not pushed to the database."})
    except Exception as e:
        return jsonify({"error": "An error occurred while processing the image: " + str(e)})
    return jsonify({"message": "Image uploaded successfully"})

# Endpoint for uploading videos.
@app.route('/upload-video', methods=['POST'])
def upload_video():
    if 'video' not in request.files:
        return jsonify({'htmlresponse': 'Error! No file found', 'success': False})

    video_file = request.files['video']
    if video_file and allowed_file(video_file.filename):
        filename = secure_filename(video_file.filename)
        video_path = os.path.join(app.config['image_dir'], filename)
        video_file.save(video_path)
        # Thực hiện xử lý video ở đây
        # Sau khi xử lý, trả về kết quả bằng jsonify hoặc theo cách bạn muốn
        return jsonify({'htmlresponse': 'Video uploaded successfully', 'success': True})
    else:
        return jsonify({'htmlresponse': 'Error! Invalid file type', 'success': False})

@socketio.on("connect")
def handle_connect():
    print("Client connected")


@socketio.on("disconnect")
def handle_disconnect():
    print("Client disconnected")
    
@app.route("/getimage/<filename>")
@cross_origin()
def get_image(filename):
    image_path = os.path.join(image_dir, filename)
    return send_file(image_path)

def get_image_list():
    return [
        f for f in os.listdir(image_dir)
        if os.path.isfile(os.path.join(image_dir, f))
    ]

@socketio.on("get_images")
def get_images():
    while True:
        time.sleep(1)
        current_image_list = get_image_list()
        emit("update_images", {"images": current_image_list})
        
# Endpoint for retrieving user information.        
@app.route('/get_user', methods=["GET"])
@cross_origin()
def get_user():
    try:
        email_user = session['user']['email']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM user WHERE email = %s", (email_user,))
        user = cur.fetchone()
        cur.close()

        if user:
            user_data = {
                "email": user[0],
                "username": user[1],
                "avatar": user[2]
            }
            return jsonify({"user": user_data})
        else:
            return jsonify({"message": "User not found!"})

    except Exception as e:
        return jsonify({"error": "Error while querying user information: " + str(e)})
    
# Endpoint for invalidating session tokens.
@app.route("/invalidate-token", methods=["POST"])
@cross_origin()
def invalidate_token():
    try:
        received_token = request.json.get("token")
        received_email = request.json.get("email")

        # Kiểm tra xem token và username nhận được từ client có khớp với session hiện tại không
        if received_email == session.get(
                "email") and received_token == session.get("token"):
            # Hủy session token và username chỉ khi chúng khớp với session hiện tại
            session.pop("token", None)
            session.pop("username", None)
            return jsonify({"success": True, "message": "Sessions have been cancelled"})
        else:
            return jsonify({"error": "Does not match current session"})
    except Exception as e:
        return jsonify({"error": "Error canceling session:" + str(e)}), 500

# Endpoint for retrieving history details.
@app.route("/get_details", methods=["POST", "GET"])
@cross_origin()
def get_details():
    try:
        if "email" not in session:
            return jsonify({"success": False, "message": "Not logged in yet"})

        data = request.get_json()
        shrimp_image = data["shrimp_image"]
        c_time = data["c_time"]
        shrimp_kind = data["shrimp_kind"]

        email_user = session['user']['email']

        cur = mysql.connection.cursor()
        cur.execute(f"SELECT shrimp_image, c_time, shrimp_kind FROM history WHERE email = '{email_user}'")
        history_entries = cur.fetchall()
        cur.close()
        history_details = []
        
        for history_entry in history_entries:
            entry_details = {
                "shrimp_image": history_entry[0],
                "c_time": history_entry[1].strftime("%Y-%m-%d %H:%M:%S"),
                "shrimp_kind": json.loads(history_entry[2])
            }
            history_details.append(entry_details)

        return jsonify({"success": True, "history_details": history_details})
    except Exception as e:
        return jsonify({"success": False, "message": "Error when retrieving history details: " + str(e)})

def delete_image(image_name):
    try:
        image_path = os.path.join("upload", image_name)
        if os.path.exists(image_path):
            os.remove(image_path)
            print(f"Removed images: {image_name}")
        else:
            print(f"Image does not exist: {image_name}")
    except Exception as e:
        print(f"Lỗi khi xóa hình ảnh {image_name}: {str(e)}")

# Endpoint for deleting history entries.
@app.route("/delete_history", methods=["POST"])
@cross_origin()
def delete_history():
    try:
        # Nhận dữ liệu từ yêu cầu POST
        data = request.get_json()
        shrimp_image = data["shrimp_image"]
        print(shrimp_image)

        email_user = session['user']['email']

        conn = mysql.connection
        cursor = conn.cursor()
        
        query_select = """
            SELECT * FROM history
            WHERE email = %s AND shrimp_image = %s
        """
        cursor.execute(query_select, (email_user, shrimp_image))
        history_entry = cursor.fetchone()

        if history_entry:
            query_delete = """
                DELETE FROM history
                WHERE email = %s AND shrimp_image = %s
            """
            cursor.execute(query_delete, (email_user, shrimp_image))
            conn.commit()
            delete_image(shrimp_image)
            cursor.close()
            return jsonify({"success": True, "message": "History deleted successfully"})
        else:
            cursor.close()
            return jsonify({"success": False, "message": "No history found to delete"})
    
    except Exception as e:
        return jsonify({"success": False, "message": "Error when deleting history: " + str(e)})

# Endpoint for retrieving all images uploaded by the user.
@app.route('/getAllImage', methods=["GET"])
def get_all():
    try:
        offset = request.args.get("offset")
        offset = int(offset) if offset else 0  

        cur = mysql.connection.cursor()
        query = f"""
            SELECT shrimp_image, MAX(c_time) AS newest_time, 
                   GROUP_CONCAT(shrimp_kind) AS shrimp_kind, 
                   SUM(shrimp_total) AS total_shrimp
            FROM history
            WHERE email = %s
            GROUP BY shrimp_image
            ORDER BY newest_time DESC
            LIMIT 20 OFFSET {offset}
        """
        email_user = session['user']['email']
        cur.execute(query, (email_user,))
        data = cur.fetchall()
        total_shrimp_all_images = sum(row[3] for row in data)  # Tính tổng tất cả shrimp_total
        cur.close()
        return jsonify({"images": data, "total_shrimp_all_images": total_shrimp_all_images})

    except Exception as e:
        return jsonify({"error": str(e)})


# Endpoint for retrieving total quantity of each shrimp kind from all history entries.
# Route để lấy tổng số lượng tôm từng loại từ cơ sở dữ liệu
@app.route('/getTotalShrimpKind', methods=['GET'])
def getTotalShrimpKind():
    try:
        email_user = session['user']['email']  # Lấy email của người dùng đang đăng nhập

        cur = mysql.connection.cursor()
        query = """
            SELECT 
                SUM(JSON_EXTRACT(shrimp_kind, '$.BigShrimp')) AS BigShrimp,
                SUM(JSON_EXTRACT(shrimp_kind, '$.SmallShrimp')) AS SmallShrimp,
                SUM(JSON_EXTRACT(shrimp_kind, '$.MediumShrimp')) AS MediumShrimp
            FROM history
            WHERE email = %s  # Lọc dữ liệu theo email của người dùng đang đăng nhập
        """
        cur.execute(query, (email_user,))
        data = cur.fetchone()
        cur.close()

        # Tạo từ điển chứa tổng số lượng tôm từng loại
        total_shrimp_by_kind = {
            "BigShrimp": data[0],
            "SmallShrimp": data[1],
            "MediumShrimp": data[2]
        }

        return jsonify(total_shrimp_by_kind)
    except Exception as e:
        return jsonify({"error": str(e)})
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

if __name__ == "__main__":
    with app.app_context():
        app.run(debug=True, port=8080)
