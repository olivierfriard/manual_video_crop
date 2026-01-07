"""
Manual cropping of a video
"""

import argparse
import os
import sys
from pathlib import Path

import cv2

__version__ = "0.0.5"
__version_date__ = "2026-01-07"

VIDEO_INPUT = sys.argv[1]
VIDEO_OUTPUT = str(
    Path(VIDEO_INPUT).parent
    / Path(Path(VIDEO_INPUT).stem + "_cropped").with_suffix(".mp4")
)

# Dimensioni predefinite del ROI (in coordinate ORIGINALI del frame)
ROI_W = 200
ROI_H = 200
OBSCURE_FRAME = True

mouse_x, mouse_y = 0, 0
roi_confirmed = False
frame_ready = False
advance = True


def parse_args():
    parser = argparse.ArgumentParser(
        description="Manual video cropping with interactive ROI selection",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument("video", help="Input video file")

    parser.add_argument(
        "output_dir", help="Directory where cropped video and crop script will be saved"
    )

    parser.add_argument("--version", action="version", version="%(prog)s 0.0.4")

    parser.epilog = """
Interactive controls:

Mouse:
  Move mouse        Move ROI center
  Left click / SPACE  Confirm ROI for current frame

Keyboard:
  z     Zoom OUT (reduce display resolution)
  x     Zoom IN  (increase display resolution)
  +     Increase ROI size
  -     Decrease ROI size
  o     Toggle frame obscuring outside ROI
  s     Skip current frame
  u     Undo last crop
  q     Quit immediately (no output)
  ESC   Exit and generate output

Notes:
- Zoom affects ONLY visualization, not crop accuracy
- ROI size is always in original video pixels
"""

    return parser.parse_args()


def mouse_move(event, x, y, flags, param):
    global mouse_x, mouse_y, advance, roi_confirmed
    if event == cv2.EVENT_MOUSEMOVE:
        mouse_x, mouse_y = x, y
        # print(f"{mouse_x=} {mouse_y=}")  # opzionale: molto verboso
    if event == cv2.EVENT_LBUTTONDOWN:
        advance = True
        roi_confirmed = True


def main():
    global roi_confirmed, frame_ready, ROI_W, ROI_H, OBSCURE_FRAME, advance

    args = parse_args()

    VIDEO_INPUT = args.video
    OUTPUT_DIR = args.output_dir

    cap = cv2.VideoCapture(VIDEO_INPUT)

    fps = cap.get(cv2.CAP_PROP_FPS)
    print(f"{fps=}")

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"resolution: {width}x{height}")

    init_size = (width, height)
    desired_size = init_size  # dimensione di VISUALIZZAZIONE (zoom)

    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    crops = []  # lista dei crop salvati: (center_x, center_y, roi_h) in coord ORIGINALI
    frame_idx = 0

    cv2.namedWindow("Seleziona ROI")
    cv2.setMouseCallback("Seleziona ROI", mouse_move)

    def clamp(v, lo, hi):
        return max(lo, min(v, hi))

    def set_zoom(new_w: int):
        """
        Cambia solo la dimensione di display (desired_size), mantenendo aspect ratio.
        Il ROI resta SEMPRE in coordinate originali del frame.
        """
        nonlocal desired_size
        # limiti a piacere: minimo 200px di larghezza, massimo full-res
        new_w = int(clamp(new_w, 200, init_size[0]))
        new_h = int(new_w * init_size[1] / init_size[0])
        desired_size = (new_w, new_h)

    while frame_idx < frame_count:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            break

        advance = False
        frame_h, frame_w = frame.shape[:2]
        roi_confirmed = False

        while not roi_confirmed:
            # --- 1) dimensioni display e scale (display -> originale) ---
            disp_w, disp_h = desired_size
            scale_x = frame_w / disp_w
            scale_y = frame_h / disp_h

            # --- 2) mouse in coordinate ORIGINALI ---
            mx = int(mouse_x * scale_x)
            my = int(mouse_y * scale_y)

            # --- 3) ROI in coordinate ORIGINALI ---
            x1 = clamp(mx - ROI_W // 2, 0, frame_w - ROI_W)
            y1 = clamp(my - ROI_H // 2, 0, frame_h - ROI_H)

            # --- 4) prepara display (ridimensionato) ---
            if desired_size != init_size:
                display = cv2.resize(frame, desired_size)
            else:
                display = frame.copy()

            # --- 5) ROI in coordinate DISPLAY (per overlay e disegno) ---
            dx1 = int(x1 / scale_x)
            dy1 = int(y1 / scale_y)
            dROI_W = max(1, int(ROI_W / scale_x))
            dROI_H = max(1, int(ROI_H / scale_y))

            # clamp per evitare out-of-bounds per rounding
            dx1 = clamp(dx1, 0, display.shape[1] - dROI_W)
            dy1 = clamp(dy1, 0, display.shape[0] - dROI_H)

            if OBSCURE_FRAME:
                overlay = display.copy()
                alpha = 0.60  # 0 = trasparente, 1 = opaco
                overlay[:] = (0, 0, 0)

                overlay[dy1 : dy1 + dROI_H, dx1 : dx1 + dROI_W] = display[
                    dy1 : dy1 + dROI_H, dx1 : dx1 + dROI_W
                ]
                display = cv2.addWeighted(overlay, alpha, display, 1 - alpha, 0)

            # Disegno rettangolo ROI (DISPLAY coords)
            cv2.rectangle(
                display, (dx1, dy1), (dx1 + dROI_W, dy1 + dROI_H), (0, 255, 0), 2
            )
            cv2.line(display, (dx1, dy1), (dx1 + dROI_W, dy1 + dROI_H), (0, 255, 0), 1)
            cv2.line(display, (dx1 + dROI_W, dy1), (dx1, dy1 + dROI_H), (0, 255, 0), 1)

            cv2.putText(
                display,
                (
                    f"frame: {frame_idx} / {frame_count}   "
                    f"Mouse=move   SPACE/Click=Confirm   ESC=Esci   z/x=Zoom   +/-=ROI"
                ),
                (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
            )

            cv2.imshow("Seleziona ROI", display)

            key = cv2.waitKey(15) & 0xFF

            # --- ZOOM (z = zoom out, x = zoom in) ---
            if key == ord("z"):
                set_zoom(desired_size[0] // 2)
            elif key == ord("x"):
                set_zoom(desired_size[0] * 2)

            # ROI size (+ / -)
            if key == 43:  # '+'
                ROI_W += 50
                ROI_H += 50
            elif key == 45:  # '-'
                ROI_W = max(50, ROI_W - 50)
                ROI_H = max(50, ROI_H - 50)

            if key == 27:  # ESC
                cap.release()
                cv2.destroyAllWindows()
                frame_idx = frame_count
                break

            if key == ord("q"):  # quit without generating the cropped video
                sys.exit()

            if key == ord("u"):  # UNDO
                if crops:
                    crops.pop()  # rimuove ultimo crop
                    frame_idx = max(0, frame_idx - 1)
                    print("↩ Undo done", frame_idx)
                    break  # torna al while principale

            if key == ord("o"):  # obscure frame
                OBSCURE_FRAME = not OBSCURE_FRAME
                break

            if key == ord("s"):  # Skip frame
                frame_idx += 1
                break

            if key == 32:  # SPACE: confirm ROI
                roi_confirmed = True

        # Salva crop usando coordinate ORIGINALI del centro (mx, my)
        if roi_confirmed:
            crops.append((mx, my, ROI_H))
            frame_idx += 1

    cap.release()
    cv2.destroyAllWindows()

    all_sizes = set([x[2] for x in crops])
    if len(all_sizes) > 1:
        max_size = max(all_sizes)
    else:
        max_size = ROI_H

    crops = [(x, y) for x, y, _ in crops]
    print(f"{max_size=}")

    ms = 1 / fps

    CROP_OUTPUT = str(
        Path(OUTPUT_DIR) / Path(Path(VIDEO_INPUT).stem + "_crop").with_suffix(".txt")
    )
    VIDEO_OUTPUT = str(
        Path(OUTPUT_DIR) / Path(Path(VIDEO_INPUT).stem + "_cropped").with_suffix(".mp4")
    )

    with open(CROP_OUTPUT, "w") as f_out:
        for idx, (x, y) in enumerate(crops):
            f_out.write(
                f"{round(idx * ms, 3)}   crop w {max_size}, crop h {max_size}, "
                f"crop x {round(x - max_size / 2)}, crop y {round(y - max_size / 2)};\n"
            )

    if sys.platform.startswith("win"):
        CROP_OUTPUT = CROP_OUTPUT.replace("\\", "/").replace("C:", "")

    print(f"{CROP_OUTPUT=}")

    # ffmpeg
    command = (
        f'ffmpeg -y -i "{VIDEO_INPUT}" '
        f'-filter_complex "[0:v]sendcmd=f={str(CROP_OUTPUT)},crop=iw:ih" '
        f'"{VIDEO_OUTPUT}" '
    )
    print(command)
    os.system(command)


if __name__ == "__main__":
    main()
