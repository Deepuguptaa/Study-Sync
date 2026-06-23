# SyncSphere Pro - All-in-One Media Processing Tool

SyncSphere is a comprehensive full-stack web application that combines multiple media processing tools into a single platform. It includes AI-powered text processing, PDF manipulation, image editing, video editing, and a secure user authentication system — all in a premium, modern UI.

🌐 **Live Demo:** https://study-sync-1-bz70.onrender.com

---

## Features

### 🔐 Authentication System
- User Registration & Login
- Secure password hashing with bcrypt
- JWT Token-based authentication
- MongoDB Atlas cloud database

### 🤖 AI Tools
- **AI Writer:** Generate text using AI or fetch information from Wikipedia
- **Grammar Checker:** Check and correct grammar in your text
- **Notes Taker:** Automatically create bullet-point notes from your text

### 📄 PDF Tools
- **PDF Merger:** Combine multiple PDF files into one
- **PDF Splitter:** Split PDF files into smaller parts
- **Image to PDF:** Convert images to PDF format

### 🖼️ Image Tools
- **Image Resizer:** Resize images to specified dimensions
- **Background Remover:** Remove backgrounds from images using AI
- **Image Converter:** Convert between PNG, JPG, WEBP, GIF formats

### 🎬 Video Tools
- **Merge Video:** Combine multiple video clips
- **Trim Video:** Cut and trim videos
- **Extract Audio:** Extract MP3 audio from any video
- **Remove Audio:** Mute a video permanently
- **Resize Video:** Change video dimensions and resolution

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, Flask |
| Database | MongoDB Atlas |
| Authentication | JWT Tokens, bcrypt |
| Frontend | HTML, Tailwind CSS, JavaScript |
| Deployment | Render, Gunicorn |

---

## Installation

1. **Clone the repository:**
```bash
git clone https://github.com/Deepuguptaa/Study-Sync.git
cd Study-Sync
```

2. **Create a virtual environment:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Set up environment variables — create a `.env` file:**
