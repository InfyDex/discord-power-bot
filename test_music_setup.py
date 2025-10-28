"""
Test script to verify music setup
Run this to check if all music dependencies are properly installed
"""

import sys

def test_imports():
    """Test if all required packages are installed"""
    print("Testing music bot dependencies...\n")
    
    results = []
    
    # Test discord.py
    try:
        import discord
        print(f"✅ discord.py version: {discord.__version__}")
        results.append(True)
    except ImportError as e:
        print(f"❌ discord.py not installed: {e}")
        results.append(False)
    
    # Test PyNaCl (required for voice)
    try:
        import nacl
        print(f"✅ PyNaCl installed")
        results.append(True)
    except ImportError as e:
        print(f"❌ PyNaCl not installed: {e}")
        results.append(False)
    
    # Test yt-dlp
    try:
        import yt_dlp
        print(f"✅ yt-dlp installed")
        results.append(True)
    except ImportError as e:
        print(f"❌ yt-dlp not installed: {e}")
        results.append(False)
    
    # Test FFmpeg
    print("\nTesting FFmpeg...")
    try:
        import subprocess
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, 
                              text=True,
                              timeout=5)
        if result.returncode == 0:
            # Extract version from output
            version_line = result.stdout.split('\n')[0]
            print(f"✅ FFmpeg found: {version_line}")
            results.append(True)
        else:
            print(f"❌ FFmpeg command failed with code {result.returncode}")
            results.append(False)
    except FileNotFoundError:
        print("❌ FFmpeg NOT found in PATH!")
        print("   Download from: https://github.com/BtbN/FFmpeg-Builds/releases")
        print("   Or install via: choco install ffmpeg")
        results.append(False)
    except Exception as e:
        print(f"❌ Error testing FFmpeg: {e}")
        results.append(False)
    
    # Summary
    print("\n" + "="*50)
    if all(results):
        print("✅ ALL TESTS PASSED! Music bot is ready to use!")
        print("\nYou can now use:")
        print("  !play <song name>  - Play a song")
        print("  /play <song name>  - Play a song (slash command)")
        print("  !testmusic         - Test in Discord")
        return 0
    else:
        print("❌ SOME TESTS FAILED!")
        print(f"   Passed: {sum(results)}/{len(results)}")
        print("\nPlease install missing dependencies.")
        return 1

if __name__ == "__main__":
    sys.exit(test_imports())
