# 📚 Audiobook Web App

> A self-hosted, privacy-focused web application for managing and listening to audiobooks with synchronized text-audio playback.

## ✨ Introduction

**Audiobook Web App** is a modern solution for audiobook enthusiasts who want to host their own library. It provides a seamless experience for uploading, managing, and listening to audiobooks directly in your browser.

Unlike standard players, this application specializes in **synchronized reading**: it pairs audio with text, allowing you to read along as you listen, complete with word-level highlighting. It is perfect for language learners or anyone who enjoys an immersive reading experience.

### 🚀 Key Features

- **Self-Hosted & Private**: You own your data. No third-party tracking.
- **Web-Based Player**: Access your library from any device with a modern browser.
- **Synchronized Playback**:
  - **Text-to-Speech Generation**: Upload a `.txt` file, and the server will generate audio and word-level alignment data automatically (using Edge-TTS).
  - **Custom Audiobooks**: Upload your own pre-generated aligned audiobooks (via ZIP).
- **Progress Tracking**: Automatically remembers your playback position for every book.
- **User Management**: Multi-user support with an invitation code system to control registration.
- **Responsive Design**: Built with SvelteKit for a fast, fluid UI on desktop and mobile.

---

## 🔒 Privacy & Security

- **No IP Logging**: This software is designed **not** to record or store user IP addresses.
- **Minimal Data Collection**: The activity log only tracks essential actions (e.g., "User X uploaded Book Y") to help administrators clean datas, without compromising user anonymity regarding their location or device fingerprint.
- **Self-Contained**: No external analytics or "phone home" telemetry.

---

## 📂 Supported Formats

### ✅ Fully Supported

- **Plain Text (`.txt`)**:
  - Upload a text file, and the system automatically converts it to an audiobook using high-quality TTS.
  - Generates word-level timestamps for synchronized highlighting.
- **Audiobook Packages (`.zip`)**:
  - For advanced users who want to upload pre-processed books.
  - **Structure**: The ZIP must contain chapter files matching the naming convention: `ch001_audio.mp3`, `ch001_text.txt`, `ch001_align.json`.

### ⚠️ Experimental / Not Currently Supported

- **EPUB (`.epub`)**:
  - Support for standard EPUB files is currently **experimental** and **incomplete**.
  - You may experience issues with chapter parsing or text display.

---

## 🛠 Architecture

The project is built on a robust, containerized microservices architecture:

- **Frontend**: SvelteKit (Node.js) - Provides a fast, reactive user interface.
- **Backend**: FastAPI (Python) - Handles business logic, file processing, and TTS generation.
- **Database**: PostgreSQL - Stores user data, book metadata, and reading progress.
- **Gateway**: Nginx - Acts as a reverse proxy to handle routing and static files.
- **Infrastructure**: Docker Compose - Orchestrates all services for easy deployment.

```mermaid
graph TD
    Client[User Browser] --> Nginx
    Nginx --> Frontend[SvelteKit Frontend]
    Nginx --> Backend[FastAPI Backend]
    Backend --> DB[(PostgreSQL)]
    Backend --> FS[File System (Media)]
```

---

## 🚀 Deployment

For detailed status on deploying to a cloud server with Nginx and SSL, please refer to the [Cloud Deployment Guide](docs/CLOUD_DEPLOYMENT.md).

### Quick Start (Local)

1.  **Clone the repository**:

    ```bash
    git clone https://github.com/yourusername/Audiobook_web_APP.git
    cd Audiobook_web_APP
    ```

2.  **Configure Environment**:

    ```bash
    cp .env.example .env
    # Edit .env and set your secrets and database credentials
    ```

3.  **Start with Docker Compose**:

    ```bash
    docker compose up -d --build
    ```

4.  **Access the App**:
    Open `http://localhost:8123` (or your configured port).

---

## 🤝 Contributing

Contributions are welcome! If you're interested in improving EPUB support or adding new features, please submit a Pull Request.

## 📄 License

[MIT License](LICENSE)
