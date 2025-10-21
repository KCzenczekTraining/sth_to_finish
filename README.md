# Audio Server

FastAPI server for audio uploads with metadata. Upload files, tag them, organize by user.

## What it does

- Upload audio files (MP3)
- Tag files and add metadata  
- List files by user and filter by tags
- Download user files as ZIP with metadata
- Async file handling, SQLite storage
- Docker setup included

## Setup

Docker (easiest):
```bash
docker-compose up --build
```

Or manually:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8123
```

Server runs on http://localhost:8123

## Usage

Upload:
```bash
curl -X POST "http://localhost:8123/upload" \
  -F "user_id=alice" \
  -F "tags=[\"music\", \"jazz\"]" \
  -F "audio=@song.mp3"
```

List files:
```bash
curl "http://localhost:8123/list?user_id=alice"
curl "http://localhost:8123/list?user_id=alice&tag=jazz"
```

Download:
```bash
curl "http://localhost:8123/download?user_id=alice" -o files.zip
```

Health check:
```bash
curl "http://localhost:8123/health"
```

## Logs

Logs go to `logs/` directory. Use the log viewer:

```bash
./view_logs.py --follow     # tail all logs
./view_logs.py --file error # errors only  
./view_logs.py --analyze    # usage stats
```

## Testing

```bash
python test_server.py
```

Creates test audio files and hits all endpoints.

## Config

- Max file size: 50MB (change in `utils.py`)
- Port: 8123 (change in docker-compose.yml or launch command)
- Logs rotate automatically

## Notes

Uses SQLite for simplicity. File storage is local disk. For production you'd want more appropriate solution.