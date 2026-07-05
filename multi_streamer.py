#!/usr/bin/env python3
import argparse
import subprocess
import threading
import time
import signal
import sys

stop_event = threading.Event()


def build_ffmpeg_cmd(input_path: str, rtmp_url: str) -> list:
    """
    Build the ffmpeg command to loop a video file and stream over RTMP.
    Adjust codecs/bitrates as needed.
    """
    return [
        "ffmpeg",
        "-re",                      # read input at native frame rate
        "-stream_loop", "-1",       # loop input infinitely
        "-i", input_path,
        # Video encoding (change to 'copy' if codec already RTMP-compatible)
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-tune", "zerolatency",
        # Audio encoding
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        "-ac", "2",
        # Output format
        "-f", "flv",
        rtmp_url,
    ]


def stream_worker(name: str, input_path: str, rtmp_url: str, reconnect_delay: int = 5):
    """
    Runs ffmpeg in a loop to keep streaming.
    If ffmpeg exits (e.g. RTMP server dropped), it restarts after a delay.
    """
    while not stop_event.is_set():
        cmd = build_ffmpeg_cmd(input_path, rtmp_url)
        print(f"[{name}] Starting ffmpeg\n  Input: {input_path}\n  URL:   {rtmp_url}")
        try:
            proc = subprocess.Popen(cmd)
        except FileNotFoundError:
            print(f"[{name}] ERROR: ffmpeg not found. Make sure it is installed and on PATH.")
            stop_event.set()
            return

        # Wait for ffmpeg to finish or until we are told to stop
        while proc.poll() is None and not stop_event.is_set():
            time.sleep(1)

        if stop_event.is_set():
            # Graceful shutdown
            if proc.poll() is None:
                print(f"[{name}] Stopping ffmpeg...")
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
            break

        # ffmpeg exited unexpectedly, restart after a delay
        ret = proc.returncode
        print(f"[{name}] ffmpeg exited with code {ret}. Restarting in {reconnect_delay}s...")
        time.sleep(reconnect_delay)


def handle_signal(signum, frame):
    print("\n[main] Caught signal, stopping streams...")
    stop_event.set()


def main():
    parser = argparse.ArgumentParser(
        description="Stream two video files continuously to two RTMP URLs."
    )
    parser.add_argument("--video1", default="vid1.mp4", help="Path to first video file")
    parser.add_argument("--video2", default="vid2.mp4", help="Path to second video file")
    parser.add_argument(
        "--url1",
        default="rtmp://localhost/live/stream1",
        help="RTMP URL for the first stream (default: %(default)s)",
    )
    parser.add_argument(
        "--url2",
        default="rtmp://localhost/live/stream2",
        help="RTMP URL for the second stream (default: %(default)s)",
    )
    parser.add_argument(
        "--reconnect-delay",
        type=int,
        default=5,
        help="Seconds to wait before restarting ffmpeg after it exits",
    )
    args = parser.parse_args()

    # Install signal handlers for Ctrl+C / kill
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    t1 = threading.Thread(
        target=stream_worker,
        args=("stream-1", args.video1, args.url1, args.reconnect_delay),
        daemon=True,
    )
    t2 = threading.Thread(
        target=stream_worker,
        args=("stream-2", args.video2, args.url2, args.reconnect_delay),
        daemon=True,
    )

    t1.start()
    t2.start()

    print("[main] Streams started. Press Ctrl+C to stop.")

    # Keep main thread alive until stop_event is set
    try:
        while not stop_event.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        handle_signal(None, None)

    # Wait for threads to exit
    t1.join()
    t2.join()
    print("[main] All streams stopped. Bye!")


if __name__ == "__main__":
    main()
