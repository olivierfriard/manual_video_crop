"""
Manual cropping of a video

"""

import os
import sys
from pathlib import Path

import cv2

__version__ = "0.0.3"

VIDEO_INPUT = sys.argv[1]
VIDEO_OUTPUT = str(
    Path(VIDEO_INPUT).parent
    / Path(Path(VIDEO_INPUT).stem + "_cropped").with_suffix(".mp4")
)

# Dimensioni predefinite del ROI
ROI_W = 200
ROI_H = 200
OBSCURE_FRAME = True

mouse_x, mouse_y = 0, 0
roi_confirmed = False
frame_ready = False
advance = True


def mouse_move(event, x, y, flags, param):
    global mouse_x, mouse_y, advance, roi_confirmed
    if event == cv2.EVENT_MOUSEMOVE:
        mouse_x, mouse_y = x, y
    if event == cv2.EVENT_LBUTTONDOWN:
        advance = True
        roi_confirmed = True
        print(advance)


def main():
    global roi_confirmed, frame_ready, ROI_W, ROI_H, OBSCURE_FRAME, advance

    cap = cv2.VideoCapture(VIDEO_INPUT)
    fps = cap.get(cv2.CAP_PROP_FPS)
    print(f"{fps=}")
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    crops = []  # lista dei crop salvati
    frame_idx = 0

    out = None  # inizializzato dopo lettura primo frame con dimensioni corrette

    cv2.namedWindow("Seleziona ROI")
    cv2.setMouseCallback("Seleziona ROI", mouse_move)

    while frame_idx < frame_count:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if not ret:
            break
        advance = False

        frame_h, frame_w = frame.shape[:2]
        roi_confirmed = False

        while not roi_confirmed:
            # Calcola coordinate ROI centrata sul cursore
            x1 = max(0, mouse_x - ROI_W // 2)
            y1 = max(0, mouse_y - ROI_H // 2)
            x1 = min(x1, frame_w - ROI_W)
            y1 = min(y1, frame_h - ROI_H)

            # Clone per disegnare overlay
            display = frame.copy()

            if OBSCURE_FRAME:
                # Creiamo un layer oscurato
                overlay = display.copy()
                alpha = 0.60  # 0 = trasparente, 1 = opaco

                overlay[:] = (0, 0, 0)
                # Ripristina la zona del ROI NON oscura
                overlay[y1 : y1 + ROI_H, x1 : x1 + ROI_W] = display[
                    y1 : y1 + ROI_H, x1 : x1 + ROI_W
                ]
                # Applica l’overlay al frame con blending
                display = cv2.addWeighted(overlay, alpha, display, 1 - alpha, 0)

            # Disegno rettangolo ROI
            # Rettangolo e diagonali sopra l’overlay
            cv2.rectangle(display, (x1, y1), (x1 + ROI_W, y1 + ROI_H), (0, 255, 0), 2)
            cv2.line(display, (x1, y1), (x1 + ROI_W, y1 + ROI_H), (0, 255, 0), 1)
            cv2.line(display, (x1 + ROI_W, y1), (x1, y1 + ROI_H), (0, 255, 0), 1)

            cv2.putText(
                display,
                f"frame: {frame_idx} / {frame_count}   Move mouse. SPACE/left click=Confirm ROI, ESC=Esci",
                (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
            )

            cv2.imshow("Seleziona ROI", display)

            key = cv2.waitKey(15) & 0xFF
            if key != 255:
                print(key)

            if key == 43:
                ROI_W += 50
                ROI_H += 50

            if key == 45:
                ROI_W -= 50
                ROI_H -= 50

            if key == 27:  # ESC
                cap.release()
                cv2.destroyAllWindows()
                frame_idx = frame_count
                break

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

        # Applica crop
        if roi_confirmed:
            # roi_crop = frame[y1 : y1 + ROI_H, x1 : x1 + ROI_W]
            print(mouse_x, mouse_y)
            crops.append((mouse_x, mouse_y, ROI_H))
            frame_idx += 1
        # out.write(roi_crop)

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
        Path(sys.argv[2]) / Path(Path(VIDEO_INPUT).stem + "_crop").with_suffix(".txt")
    )
    VIDEO_OUTPUT = str(
        Path(sys.argv[2])
        / Path(Path(VIDEO_INPUT).stem + "_cropped").with_suffix(".mp4")
    )

    with open(CROP_OUTPUT, "w") as f_out:
        for idx, (x, y) in enumerate(crops):
            f_out.write(
                f"{round(idx * ms, 3)}   crop w {max_size}, crop h {max_size}, crop x {round(x - max_size / 2)}, crop y {round(y - max_size / 2)};\n"
            )

    if sys.platform.startswith("win"):
        CROP_OUTPUT = CROP_OUTPUT.replace(r'\', '/').replace('c:', ''))

    print(f"{CROP_OUTPUT=}")

    # ffmpeg
    print(
        f'ffmpeg -i "{sys.argv[1]}" -filter_complex "[0:v]sendcmd=f={str(CROP_OUTPUT)}" "{VIDEO_OUTPUT}" '
    )
    os.system(
        f'ffmpeg -i "{sys.argv[1]}" -filter_complex "[0:v]sendcmd=f={str(CROP_OUTPUT)}" "{VIDEO_OUTPUT}" '
    )


if __name__ == "__main__":
    main()
