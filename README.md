# SyncSphere Pro - All-in-One Media Processing Tool

SyncSphere is a comprehensive web application that combines multiple media processing tools into a single platform. It includes AI-powered text processing, PDF manipulation, image editing, and video editing capabilities, all presented in a premium, modern user interface.

## Features

### 1. AI Tools
- **AI Writer**: Generate text using AI or fetch information from Wikipedia
- **Grammar Checker**: Check and correct grammar in your text
- **Notes Taker**: Automatically create bullet-point notes from your text

### 2. PDF Tools
- **PDF Merger**: Combine multiple PDF files into one
- **PDF Splitter**: Split PDF files into smaller parts
- **Image to PDF**: Convert images to PDF format

### 3. Image Tools
- **Image Resizer**: Resize images to specified dimensions
- **Background Remover**: Remove backgrounds from images using AI
- **Image Converter**: Convert images between different formats (PNG, JPG, WEBP, GIF)

### 4. Video Tools
- **Merge Video**: Combine multiple video clips
- **Trim Video**: Cut and trim videos
- **Extract Audio**: Extract MP3 audio from any video
- **Remove Audio**: Mute a video permanently
- **Resize Video**: Change video dimensions and resolution

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/SyncSphere.git
cd SyncSphere
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install the required dependencies:
```bash
pip install -r requirements.txt
```

## Running the Application

1. Start the Flask server:
```bash
python app.py
```

2. Open your web browser and navigate to:
```
http://localhost:5000
```

## File Format Support

### Images
- Supported Input: PNG, JPG, JPEG, WEBP, GIF
- Supported Output: PNG, JPG, JPEG, WEBP, GIF

### Videos
- Supported Formats: MP4, AVI, MOV, MKV

### PDFs
- Supported Input: PDF files
- Supported Output: PDF files

## Security Features

- Secure file handling
- Temporary file cleanup after processing
- Input validation
- CORS protection

## License

This project is licensed under the MIT License - see the LICENSE file for details.
