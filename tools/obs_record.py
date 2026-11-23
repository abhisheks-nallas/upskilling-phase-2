"""Tiny OBS recorder over OBS's built-in WebSocket server (OBS 28+).

  python tools/obs_record.py status   # version, scene, audio inputs, whether it is recording
  python tools/obs_record.py setup    # add a Display Capture to the current scene if it has none
  python tools/obs_record.py start
  python tools/obs_record.py stop     # prints where the video was saved
  python tools/obs_record.py shot     # saves what OBS sees to recordings/shot.png (to check the capture)

The password comes from recordings/.env (git-ignored). Needs: pip install obsws-python python-dotenv
"""
import base64
import sys
from pathlib import Path
from urllib.parse import urlparse

import obsws_python as obs
from dotenv import dotenv_values

cfg = dotenv_values(Path(__file__).resolve().parent.parent / "recordings" / ".env")
url = urlparse(cfg.get("OBS_WEBSOCKET_URL", "ws://localhost:4455"))
client = obs.ReqClient(host=url.hostname, port=url.port, password=cfg["OBS_WEBSOCKET_PASSWORD"], timeout=10)


def scene_name() -> str:
    return client.get_current_program_scene().current_program_scene_name


def status():
    v = client.get_version()
    rec = client.get_record_status()
    print(f"OBS {v.obs_version}, websocket {v.obs_web_socket_version}, {v.platform}")
    print(f"recording: {rec.output_active} ({rec.output_timecode})")
    scene = scene_name()
    print(f"scene: {scene}")
    for item in client.get_scene_item_list(scene).scene_items:
        print(f"  source: {item['sourceName']} [{item['inputKind']}] visible={item['sceneItemEnabled']}")
    for inp in client.get_input_list().inputs:
        if "audio" in inp["inputKind"] or "wasapi" in inp["inputKind"]:
            muted = client.get_input_mute(inp["inputName"]).input_muted
            print(f"  audio input: {inp['inputName']} [{inp['inputKind']}] muted={muted}")


def setup():
    scene = scene_name()
    kinds = [i["inputKind"] for i in client.get_scene_item_list(scene).scene_items]
    if "monitor_capture" in kinds:
        print("Scene already has a display capture")
        return
    client.create_input(scene, "Display Capture", "monitor_capture", {}, True)
    print(f"Added Display Capture to scene '{scene}'")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "status":
        status()
    elif cmd == "setup":
        setup()
    elif cmd == "start":
        client.start_record()
        print("Recording started")
    elif cmd == "shot":
        source = client.get_scene_item_list(scene_name()).scene_items[0]["sourceName"]
        data = client.get_source_screenshot(source, "png", 960, 540, -1).image_data.split(",", 1)[1]
        out = Path(__file__).resolve().parent.parent / "recordings" / "shot.png"
        out.write_bytes(base64.b64decode(data))
        print("Saved", out)
    elif cmd == "stop":
        print("Saved:", client.stop_record().output_path)
    else:
        sys.exit(__doc__)


main()
