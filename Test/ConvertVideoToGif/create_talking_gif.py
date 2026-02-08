#!/usr/bin/env python3
"""
Helper script to create a talking GIF from a video file.
This uses moviepy to convert a video to an optimized GIF.

Usage:
    python create_talking_gif.py input_video.mp4 output_talking.gif

Requirements:
    pip install moviepy
"""

import sys
from pathlib import Path

try:
    from moviepy.editor import VideoFileClip
except ImportError as e:
    print("MoviePy import failed:", e)
    sys.exit(1)
    print("Install with: pip install moviepy")
    sys.exit(1)

def create_talking_gif(input_path, output_path, 
                       start_time=0, duration=5, 
                       fps=15, size=(400, 400)):
    """
    Convert video to GIF with specified parameters
    
    Args:
        input_path: Path to input video file
        output_path: Path to output GIF file
        start_time: Start time in seconds (default: 0)
        duration: Duration in seconds (default: 5)
        fps: Frames per second (default: 15, lower = smaller file)
        size: Output size as (width, height) (default: 400x400)
    """
    
    print(f"Loading video: {input_path}")
    clip = VideoFileClip(str(input_path))
    
    # Extract subclip if needed
    if start_time > 0 or duration < clip.duration:
        clip = clip.subclip(start_time, start_time + duration)
    
    # Resize to square (crops to fit)
    clip = clip.resize(height=size[1])
    w, h = clip.size
    
    # Center crop to square
    if w > h:
        x_center = w / 2
        x1 = x_center - h / 2
        x2 = x_center + h / 2
        clip = clip.crop(x1=x1, x2=x2)
    elif h > w:
        y_center = h / 2
        y1 = y_center - w / 2
        y2 = y_center + w / 2
        clip = clip.crop(y1=y1, y2=y2)
    
    # Final resize to exact dimensions
    clip = clip.resize(size)
    
    print(f"Creating GIF...")
    print(f"  Duration: {duration}s")
    print(f"  FPS: {fps}")
    print(f"  Size: {size[0]}x{size[1]}")
    
    # Write GIF
    clip.write_gif(
        str(output_path),
        fps=fps,
        program='ffmpeg',
        opt='OptimizePlus',  # Better optimization
        fuzz=1  # Color reduction for smaller file
    )
    
    file_size = Path(output_path).stat().st_size / (1024 * 1024)  # MB
    print(f"\n✓ GIF created: {output_path}")
    print(f"  File size: {file_size:.2f} MB")
    
    if file_size > 2:
        print("\n⚠️  Warning: File size > 2MB. Consider:")
        print("  - Reducing duration")
        print("  - Lowering FPS (try 10-12)")
        print("  - Reducing size (try 300x300)")

def main():
    if len(sys.argv) < 3:
        print("Usage: python create_talking_gif.py <input_video> <output_gif>")
        print("\nExample:")
        print("  python create_talking_gif.py me_talking.mp4 static/talking.gif")
        print("\nOptional parameters (edit script):")
        print("  start_time: Start from N seconds")
        print("  duration: Length in seconds (default: 5)")
        print("  fps: Frames per second (default: 15)")
        print("  size: Output dimensions (default: 400x400)")
        sys.exit(1)
    
    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)
    
    # Create output directory if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    create_talking_gif(
        input_path,
        output_path,
        start_time=0,    # Edit these values as needed
        duration=5,
        fps=15,
        size=(400, 400)
    )

if __name__ == "__main__":
    main()