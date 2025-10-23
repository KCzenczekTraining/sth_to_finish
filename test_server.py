#!/usr/bin/env python3
import aiohttp
import asyncio
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional, List, Dict, Any


BASE_URL = "http://localhost:8123/api/v1"
TEST_USER_ID = "testuser123"

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def create_test_audio_file() -> str:
    """Create a minimal test MP3 file for testing."""
    fd, path = tempfile.mkstemp(suffix='.mp3')
    with os.fdopen(fd, 'wb') as f:
        # Minimal MP3 header for testing - this is a valid but empty MP3 frame
        mp3_header = bytes([
            0xFF, 0xFB, 0x90, 0x00,  # MP3 sync word and header
            0x00, 0x00, 0x00, 0x00,  # Padding
        ])
        f.write(mp3_header)
    
    return path

async def test_health_check() -> bool:
    """Test the health endpoint."""
    logger.info("Testing health endpoint")
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}/health") as response:
            if response.status == 200:
                data = await response.json()
                logger.info(f"Health check passed: {data}")
                return True
            else:
                logger.error(f"Health check failed: {response.status}")
                return False

async def test_upload() -> Optional[str]:
    """Test audio file upload."""
    logger.info("Testing upload")
    audio_file_path = create_test_audio_file()
    
    try:
        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field('user_id', TEST_USER_ID)
            data.add_field('tags', 'test,demo,sine-wave')
            data.add_field('additional_info', 'Test sine wave audio')
            
            with open(audio_file_path, 'rb') as f:
                data.add_field('audio', f, filename='test_audio.mp3', content_type='audio/mpeg')
                
                async with session.post(f"{BASE_URL}/audio/upload", data=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        file_id = result['file_id']
                        logger.info(f"Upload successful: {file_id}")
                        return file_id
                    else:
                        text = await response.text()
                        logger.error(f"Upload failed: {response.status} - {text}")
                        return None
    finally:
        Path(audio_file_path).unlink(missing_ok=True)

async def test_list_files(tag_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """Test file listing with optional tag filter."""
    filter_msg = f" with tag '{tag_filter}'" if tag_filter else ""
    logger.info(f"Testing file listing{filter_msg}")
    
    async with aiohttp.ClientSession() as session:
        params = {'user_id': TEST_USER_ID}
        if tag_filter:
            params['tag'] = tag_filter
            
        async with session.get(f"{BASE_URL}/audio/list", params=params) as response:
            if response.status == 200:
                data = await response.json()
                count = data['total_count']
                logger.info(f"List successful: Found {count} files")
                for file_info in data['files']:
                    size = file_info['file_size']
                    name = file_info['original_filename']
                    logger.info(f"  - {name} ({size} bytes)")
                return data['files']
            else:
                text = await response.text()
                logger.error(f"List failed: {response.status} - {text}")
                return []

async def test_download() -> bool:
    """Test file download as ZIP."""
    logger.info("Testing download")
    
    async with aiohttp.ClientSession() as session:
        params = {'user_id': TEST_USER_ID}
        async with session.get(f"{BASE_URL}/audio/download", params=params) as response:
            if response.status == 200:
                fd, temp_path = tempfile.mkstemp(suffix='.zip')
                try:
                    with os.fdopen(fd, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)
                    
                    file_size = Path(temp_path).stat().st_size
                    logger.info(f"Download successful: {file_size} bytes")
                    return True
                finally:
                    Path(temp_path).unlink(missing_ok=True)
            else:
                text = await response.text()
                logger.error(f"Download failed: {response.status} - {text}")
                return False

async def run_tests() -> bool:
    """Run all API tests and return success status."""
    logger.info("Starting audio server tests")
    
    if not await test_health_check():
        logger.error("Server health check failed")
        return False
    
    file_id = await test_upload()
    if not file_id:
        logger.error("Upload test failed")
        return False
    
    files = await test_list_files()
    if not files:
        logger.error("No files found after upload")
        return False
    
    await test_list_files(tag_filter="test")
    
    if not await test_download():
        logger.error("Download test failed")
        return False
    
    logger.info("All tests completed successfully")
    return True

def main() -> None:
    """Main entry point."""
    try:
        success = asyncio.run(run_tests())
        exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.warning("Tests interrupted by user")
        exit(130)
    except Exception as e:
        logger.error(f"Test runner error: {e}")
        exit(1)

if __name__ == "__main__":
    main()
