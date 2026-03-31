import sys
import os

sys.path.insert(0, "/system/apps/copilot-loop")
os.chdir("/system/apps/copilot-loop")

from badgeware import Image, screen, run, io
import gc


frame_index = 1
last_frame_time = 0
current_frame = None
FRAME_DURATION = 33
LAST_FRAME_PAUSE = 10000
TOTAL_FRAMES = 39

def update():
    global frame_index, last_frame_time, current_frame

    is_last_frame = (frame_index == TOTAL_FRAMES)
    pause_duration = LAST_FRAME_PAUSE if is_last_frame else FRAME_DURATION

    if io.ticks - last_frame_time >= pause_duration:
        new_index = (frame_index % TOTAL_FRAMES) + 1
        if new_index != frame_index or current_frame is None:
            frame_index = new_index
            last_frame_time = io.ticks
            # Free previous frame before loading new one
            del current_frame
            gc.collect()
            current_frame = Image.load("frames/frame_{:04d}.png".format(frame_index))

    if current_frame is not None:
        screen.blit(current_frame, 0, 0)

if __name__ == "__main__":
    run(update)
