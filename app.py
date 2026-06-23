from flask import Flask, render_template, request, jsonify, send_file, session
from flask_cors import CORS
import os
import tempfile
import time
import io
import shutil
import re
import logging
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import jwt
import datetime

# PDF imports
from PyPDF2 import PdfMerger, PdfReader, PdfWriter
from fpdf import FPDF

# AI imports
# language_tool_python disabled
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
# transformers disabled on free plan
import wikipediaapi
from sumy.summarizers.lex_rank import LexRankSummarizer
import nltk

# Image imports
from PIL import Image
# from rembg import remove  # disabled on free plan

# Video imports
import ffmpeg

# MongoDB
from pymongo import MongoClient
from bson.objectid import ObjectId

# Initialize Flask app
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# ─── Config ────────────────────────────────────────────────
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'syncsphere_secret_key_2024_change_in_production')
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/syncsphere')
JWT_EXPIRE_HOURS = 168  # 7 days

# ─── MongoDB Connection ─────────────────────────────────────
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
    client.server_info()  # Test connection
    db = client['syncsphere']
    users_collection = db['users']
    users_collection.create_index('email', unique=True)
    print("✅ MongoDB Connected!")
except Exception as e:
    print(f"⚠️  MongoDB not connected: {e}")
    db = None
    users_collection = None

# Create necessary folders
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'output'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Initialize AI components
try:
    ai_writer = None  # disabled on free plan
except Exception as e:
    logging.warning(f"Could not load AI writer model: {e}")
    ai_writer = None

try:
    tool = None  # disabled
except Exception as e:
    logging.warning(f"Could not load LanguageTool: {e}")
    tool = None

wiki_wiki = wikipediaapi.Wikipedia(user_agent="Mozilla/5.0", language="en")

try:
    nltk.download("punkt", quiet=True)
    nltk.download("punkt_tab", quiet=True)
except Exception as e:
    logging.warning(f"Could not download nltk data: {e}")

# ─── Helper Functions ───────────────────────────────────────
def allowed_video_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'mp4', 'avi', 'mov', 'mkv'}

def allowed_image_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'webp', 'gif'}

def safe_remove_file(file_path, max_attempts=3):
    for attempt in range(max_attempts):
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            return True
        except PermissionError:
            if attempt < max_attempts - 1:
                time.sleep(1)
            continue
    return False

def generate_token(user_id):
    """JWT token generate karo"""
    payload = {
        'user_id': str(user_id),
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=JWT_EXPIRE_HOURS),
        'iat': datetime.datetime.utcnow()
    }
    return jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')

def verify_token(token):
    """Token verify karo aur user_id return karo"""
    try:
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        return payload['user_id']
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def token_required(f):
    """Protected route decorator"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({'success': False, 'message': 'Token missing hai. Login karo.'}), 401
        user_id = verify_token(token)
        if not user_id:
            return jsonify({'success': False, 'message': 'Token invalid ya expired hai.'}), 401
        return f(user_id, *args, **kwargs)
    return decorated

# ==========================================
# AUTH API ROUTES
# ==========================================

@app.route('/api/auth/signup', methods=['POST'])
def signup():
    if users_collection is None:
        return jsonify({'success': False, 'message': 'Database connected nahi hai. MongoDB start karo.'}), 503

    data = request.get_json()
    full_name = data.get('fullName', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    # Validation
    if not full_name or len(full_name) < 2:
        return jsonify({'success': False, 'message': 'Full name kam se kam 2 characters ka hona chahiye.'}), 400
    if not email or '@' not in email:
        return jsonify({'success': False, 'message': 'Valid email daalo.'}), 400
    if not password or len(password) < 6:
        return jsonify({'success': False, 'message': 'Password kam se kam 6 characters ka hona chahiye.'}), 400

    # Check duplicate email
    if users_collection.find_one({'email': email}):
        return jsonify({'success': False, 'message': 'Yeh email already registered hai. Sign In karo.'}), 400

    # User create karo
    hashed_password = generate_password_hash(password)
    user_doc = {
        'fullName': full_name,
        'email': email,
        'password': hashed_password,
        'createdAt': datetime.datetime.utcnow()
    }
    result = users_collection.insert_one(user_doc)
    token = generate_token(result.inserted_id)

    return jsonify({
        'success': True,
        'message': f'Account ban gaya! Welcome, {full_name}! 🎉',
        'token': token,
        'user': {
            'id': str(result.inserted_id),
            'fullName': full_name,
            'email': email
        }
    }), 201


@app.route('/api/auth/login', methods=['POST'])
def login():
    if users_collection is None:
        return jsonify({'success': False, 'message': 'Database connected nahi hai. MongoDB start karo.'}), 503

    data = request.get_json()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'success': False, 'message': 'Email aur password daalo.'}), 400

    # User dhundo
    user = users_collection.find_one({'email': email})
    if not user or not check_password_hash(user['password'], password):
        return jsonify({'success': False, 'message': 'Email ya password galat hai.'}), 401

    token = generate_token(user['_id'])

    return jsonify({
        'success': True,
        'message': f"Welcome back, {user['fullName']}! 👋",
        'token': token,
        'user': {
            'id': str(user['_id']),
            'fullName': user['fullName'],
            'email': user['email']
        }
    })


@app.route('/api/auth/me', methods=['GET'])
@token_required
def get_me(user_id):
    if users_collection is None:
        return jsonify({'success': False, 'message': 'Database error'}), 503
    user = users_collection.find_one({'_id': ObjectId(user_id)})
    if not user:
        return jsonify({'success': False, 'message': 'User nahi mila'}), 404
    return jsonify({
        'success': True,
        'user': {
            'id': str(user['_id']),
            'fullName': user['fullName'],
            'email': user['email']
        }
    })


# ==========================================
# PAGE ROUTES (Frontend)
# ==========================================

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/tools/pdf")
def pdf_tools():
    return render_template("pdf.html")

@app.route("/tools/ai")
def ai_tools():
    return render_template("ai.html")

@app.route("/tools/image/convert")
def img_convert():
    return render_template("convertorimg.html")

@app.route("/tools/image/remove_bg")
def img_remove_bg():
    return render_template("bremover.html")

@app.route("/tools/image/resize")
def img_resize():
    return render_template("resizeimg.html")

@app.route("/tools/video")
def video_tools():
    return render_template("video/index.html")

@app.route("/tools/video/resize")
def video_resize():
    return render_template("video/resize.html")

@app.route("/tools/video/trim")
def video_trim():
    return render_template("video/trim.html")

@app.route("/tools/video/merge")
def video_merge():
    return render_template("video/merge.html")

@app.route("/tools/video/extract_audio")
def video_extract_audio():
    return render_template("video/extract-audio.html")

@app.route("/tools/video/remove_audio")
def video_remove_audio():
    return render_template("video/remove-audio.html")


# ==========================================
# API ROUTES (Backend Processors)
# ==========================================

# ----------------- AI APIs -----------------
@app.route("/api/ai_writer", methods=["POST"])
def ai_writer_api():
    data = request.json
    prompt = data.get("text", "").strip()
    if len(prompt.split()) > 800:
        return jsonify({"error": "Input too long! Please enter up to 300 words."}), 400

    try:
        page = wiki_wiki.page(prompt)
        if page.exists():
            wiki_content = page.summary[:500]
            generated_text = f"According to Wikipedia: {wiki_content}\n\nFor more details, visit: {page.fullurl}"
        else:
            if ai_writer:
                result = ai_writer(prompt, max_length=200, do_sample=True, truncation=True)
                generated_text = result[0].get("generated_text", "No text generated!")
            else:
                generated_text = "AI Writer is currently offline."

        return jsonify({"generated_text": generated_text})
    except Exception as e:
        return jsonify({"error": f"AI Writer Error: {str(e)}"}), 500

@app.route("/api/grammar_check", methods=["POST"])
def grammar_check():
    if not tool:
        return jsonify({"error": "Grammar tool is currently offline"}), 500
    data = request.json
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "Input text is empty"}), 400
    matches = tool.check(text)
    corrected_text = language_tool_python.utils.correct(text, matches)
    corrections = [{"offset": m.offset, "length": m.errorLength, "message": m.message} for m in matches]
    return jsonify({"corrected_text": corrected_text, "corrections": corrections})

@app.route("/api/notes_taker", methods=["POST"])
def notes_taker():
    try:
        data = request.json
        text = data.get("text", "").strip()
        if not text:
            return jsonify({"error": "Input text is empty"}), 400
        cleaned_text = re.sub(r"\[\d+\]", "", text)
        if not cleaned_text:
            return jsonify({"error": "Input text contains only citations or invalid data"}), 400
        parser = PlaintextParser.from_string(cleaned_text, Tokenizer("english"))
        summarizer = LexRankSummarizer()
        notes = summarizer(parser.document, 5)
        if not notes:
            return jsonify({"notes": "No key points extracted. Try different input."})
        notes_text = "\n".join(f"- {str(sentence)}" for sentence in notes)
        return jsonify({"notes": notes_text})
    except Exception as e:
        return jsonify({"error": f"Notes Taker Error: {str(e)}"}), 500

# ----------------- PDF APIs -----------------
@app.route('/api/merge_pdfs', methods=['POST'])
def merge_pdfs():
    files = request.files.getlist('files')
    if not files:
        return jsonify({'error': 'No files provided'}), 400
    merger = PdfMerger()
    saved_files = []
    try:
        for file in files:
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            saved_files.append(filepath)
            merger.append(filepath)
        output_path = os.path.join(OUTPUT_FOLDER, f'merged_{int(time.time())}.pdf')
        merger.write(output_path)
        merger.close()
        return send_file(output_path, as_attachment=True)
    finally:
        for path in saved_files:
            safe_remove_file(path)

@app.route('/api/split_pdf', methods=['POST'])
def split_pdf():
    file = request.files.get('file')
    start = request.form.get('start')
    end = request.form.get('end')
    if not file or not start or not end:
        return jsonify({'error': 'File and page range are required'}), 400
    try:
        start, end = int(start), int(end)
    except ValueError:
        return jsonify({'error': 'Start and End must be integers'}), 400
    filepath = ""
    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        reader = PdfReader(filepath)
        writer = PdfWriter()
        if start < 1 or end > len(reader.pages) or start > end:
            return jsonify({'error': 'Invalid page range'}), 400
        for i in range(start - 1, end):
            writer.add_page(reader.pages[i])
        output_path = os.path.join(OUTPUT_FOLDER, f'split_{int(time.time())}.pdf')
        with open(output_path, 'wb') as output_file:
            writer.write(output_file)
        return send_file(output_path, as_attachment=True)
    finally:
        if filepath:
            safe_remove_file(filepath)

@app.route('/api/images-to-pdf', methods=['POST'])
def images_to_pdf():
    files = request.files.getlist('files')
    if not files:
        return jsonify({'error': 'No images provided'}), 400
    pdf = FPDF()
    saved_files = []
    try:
        for file in files:
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            saved_files.append(filepath)
            pdf.add_page()
            pdf.image(filepath, x=10, y=10, w=190)
        output_path = os.path.join(OUTPUT_FOLDER, f'images_to_pdf_{int(time.time())}.pdf')
        pdf.output(output_path)
        return send_file(output_path, as_attachment=True)
    finally:
        for path in saved_files:
            safe_remove_file(path)

# ----------------- Image APIs -----------------
@app.route('/api/convert_image', methods=['POST'])
def convert_format():
    if 'file' not in request.files or 'format' not in request.form:
        return jsonify({"error": "Missing file or format"}), 400
    file = request.files['file']
    target_format = request.form['format'].lower()
    if not allowed_image_file(file.filename):
        return jsonify({"error": "Invalid image format"}), 400
    ALLOWED_OUTPUT_FORMATS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
    if target_format not in ALLOWED_OUTPUT_FORMATS:
        return jsonify({"error": "Invalid target format"}), 400
    try:
        input_image = Image.open(io.BytesIO(file.read()))
        if target_format == "jpg":
            target_format = "JPEG"
            if input_image.mode in ("RGBA", "P"):
                input_image = input_image.convert("RGB")
        output_bytes = io.BytesIO()
        input_image.save(output_bytes, format=target_format.upper())
        output_bytes.seek(0)
        return send_file(output_bytes, mimetype=f"image/{target_format.lower()}", download_name=f"converted-image.{target_format.lower()}", as_attachment=True)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/remove_bg', methods=['POST'])
def remove_bg():
    if 'file' not in request.files:
        return jsonify({"error": "No image uploaded"}), 400
    file = request.files['file']
    if not allowed_image_file(file.filename):
        return jsonify({"error": "Invalid image format"}), 400
    try:
        input_image = Image.open(io.BytesIO(file.read()))
        return jsonify({"error": "Background removal is not available on free plan. Run locally."}), 503
        output_bytes = io.BytesIO()
        output_image.save(output_bytes, format="PNG")
        output_bytes.seek(0)
        return send_file(output_bytes, mimetype="image/png", download_name="no-bg.png", as_attachment=True)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/resize_image', methods=['POST'])
def resize_image():
    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided'}), 400
    image_file = request.files['image']
    width = int(request.form.get('width', 800))
    height = int(request.form.get('height', 600))
    try:
        img = Image.open(image_file)
        resized_img = img.resize((width, height), Image.LANCZOS)
        img_buffer = io.BytesIO()
        img_format = img.format or "JPEG"
        resized_img.save(img_buffer, format=img_format)
        img_buffer.seek(0)
        return send_file(img_buffer, mimetype=f'image/{img_format.lower()}')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ----------------- Video APIs -----------------
@app.route('/api/resize_video', methods=['POST'])
def resize_video():
    if 'video' not in request.files:
        return jsonify({'error': 'No video file provided'}), 400
    video = request.files['video']
    if not allowed_video_file(video.filename):
        return jsonify({'error': 'Invalid file type.'}), 400
    try:
        width = int(request.form.get('width', 0))
        height = int(request.form.get('height', 0))
        if width <= 0 or height <= 0:
            return jsonify({'error': 'Invalid dimensions'}), 400
    except ValueError:
        return jsonify({'error': 'Invalid dimension values'}), 400
    temp_dir = None
    try:
        temp_dir = tempfile.mkdtemp()
        input_path = os.path.join(temp_dir, 'input.mp4')
        video.save(input_path)
        probe = ffmpeg.probe(input_path)
        video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
        original_width = int(video_info['width'])
        original_height = int(video_info['height'])
        aspect_ratio = original_width / original_height
        if width / height > aspect_ratio:
            new_width = int(height * aspect_ratio)
            new_width = new_width - (new_width % 2)
            new_height = height - (height % 2)
        else:
            new_width = width - (width % 2)
            new_height = int(width / aspect_ratio)
            new_height = new_height - (new_height % 2)
        output_path = os.path.join(temp_dir, 'output.mp4')
        stream = ffmpeg.input(input_path)
        v = stream.video.filter('scale', new_width, new_height)
        a = stream.audio
        out = ffmpeg.output(v, a, output_path, vcodec='libx264', acodec='aac', preset='ultrafast')
        ffmpeg.run(out, overwrite_output=True, capture_stdout=True, capture_stderr=True)
        with open(output_path, 'rb') as f:
            file_data = f.read()
        return send_file(io.BytesIO(file_data), mimetype='video/mp4', as_attachment=True, download_name='resized_video.mp4')
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

@app.route('/api/trim_video', methods=['POST'])
def trim_video():
    if 'video' not in request.files:
        return jsonify({'error': 'No video file provided'}), 400
    video = request.files['video']
    if not allowed_video_file(video.filename):
        return jsonify({'error': 'Invalid file type.'}), 400
    try:
        start_time = float(request.form.get('start_time', 0))
        end_time = float(request.form.get('end_time', 0))
        if start_time >= end_time or start_time < 0:
            return jsonify({'error': 'Invalid time range'}), 400
    except ValueError:
        return jsonify({'error': 'Invalid time values'}), 400
    temp_dir = None
    try:
        temp_dir = tempfile.mkdtemp()
        input_path = os.path.join(temp_dir, 'input.mp4')
        video.save(input_path)
        output_path = os.path.join(temp_dir, 'output.mp4')
        stream = ffmpeg.input(input_path, ss=start_time, t=end_time-start_time)
        out = ffmpeg.output(stream, output_path, c='copy')
        ffmpeg.run(out, overwrite_output=True, capture_stdout=True, capture_stderr=True)
        with open(output_path, 'rb') as f:
            file_data = f.read()
        return send_file(io.BytesIO(file_data), mimetype='video/mp4', as_attachment=True, download_name='trimmed_video.mp4')
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

@app.route('/api/merge_video', methods=['POST'])
def merge_video():
    files = request.files.getlist('videos')
    if len(files) < 2:
        return jsonify({'error': 'Provide at least two video files'}), 400
    temp_dir = tempfile.mkdtemp()
    try:
        inputs = []
        for i, file in enumerate(files):
            if allowed_video_file(file.filename):
                path = os.path.join(temp_dir, f'input_{i}.mp4')
                file.save(path)
                inputs.append(path)
        if len(inputs) < 2:
            return jsonify({'error': 'Not enough valid video files'}), 400
        list_path = os.path.join(temp_dir, 'files.txt')
        with open(list_path, 'w') as f:
            for p in inputs:
                f.write(f"file '{os.path.abspath(p)}'\n")
        output_path = os.path.join(temp_dir, 'merged.mp4')
        out = ffmpeg.input(list_path, format='concat', safe=0).output(output_path, c='copy')
        ffmpeg.run(out, overwrite_output=True, capture_stdout=True, capture_stderr=True)
        with open(output_path, 'rb') as f:
            file_data = f.read()
        return send_file(io.BytesIO(file_data), mimetype='video/mp4', as_attachment=True, download_name='merged_video.mp4')
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

@app.route('/api/extract_audio', methods=['POST'])
def extract_audio():
    if 'video' not in request.files:
        return jsonify({'error': 'No video file provided'}), 400
    video = request.files['video']
    if not allowed_video_file(video.filename):
        return jsonify({'error': 'Invalid file type.'}), 400
    temp_dir = tempfile.mkdtemp()
    try:
        input_path = os.path.join(temp_dir, 'input.mp4')
        video.save(input_path)
        output_path = os.path.join(temp_dir, 'audio.mp3')
        out = ffmpeg.input(input_path).output(output_path, acodec='libmp3lame', q=4)
        ffmpeg.run(out, overwrite_output=True, capture_stdout=True, capture_stderr=True)
        with open(output_path, 'rb') as f:
            file_data = f.read()
        return send_file(io.BytesIO(file_data), mimetype='audio/mpeg', as_attachment=True, download_name='extracted_audio.mp3')
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

@app.route('/api/remove_audio', methods=['POST'])
def remove_audio():
    if 'video' not in request.files:
        return jsonify({'error': 'No video file provided'}), 400
    video = request.files['video']
    if not allowed_video_file(video.filename):
        return jsonify({'error': 'Invalid file type.'}), 400
    temp_dir = tempfile.mkdtemp()
    try:
        input_path = os.path.join(temp_dir, 'input.mp4')
        video.save(input_path)
        output_path = os.path.join(temp_dir, 'no_audio.mp4')
        out = ffmpeg.input(input_path).output(output_path, vcodec='copy', an=None)
        ffmpeg.run(out, overwrite_output=True, capture_stdout=True, capture_stderr=True)
        with open(output_path, 'rb') as f:
            file_data = f.read()
        return send_file(io.BytesIO(file_data), mimetype='video/mp4', as_attachment=True, download_name='muted_video.mp4')
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
