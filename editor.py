from PIL import Image, ImageTk, ImageDraw
from tkinter import ttk
from datetime import timedelta
import tkinter as tk
from tkinter import filedialog, messagebox, font
import cv2
import easyocr
import pysrt
from PIL import Image, ImageTk
from tkinterdnd2 import DND_FILES, TkinterDnD
import copy
import threading
from tqdm import trange
from utils import *

reader = None
OCR_INTERVAL = 3


class OCRRangeSelector:
    def __init__(self, parent, cap, timeline_total_ms):
        self.parent = parent
        self.cap = cap
        self.timeline_total_ms = timeline_total_ms
        self.result = None

        self.top_ratio = 0.76
        self.bottom_ratio = 0.98
        self.left_ratio = 0.10
        self.right_ratio = 0.90

        self.dragging = None
        self.drag_start_y = 0
        self.drag_start_x = 0

        self.setup_ui()
        self.update_frame(0)

    def setup_ui(self):
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Select OCR Region")
        self.dialog.geometry("800x700")
        self.dialog.transient(self.parent)
        self.dialog.grab_set()

        # Main frame
        main_frame = tk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Instruction label
        instruction_label = tk.Label(
            main_frame,
            text="Drag the neon green border to adjust the OCR region. Use the timeline to preview different frames.",
        )
        instruction_label.pack(pady=(0, 10))

        # Video display area
        self.video_frame = tk.Frame(main_frame, bg='black')
        self.video_frame.pack(fill=tk.BOTH, expand=True)

        self.video_label = tk.Label(self.video_frame, bg='black')
        self.video_label.pack(expand=True)

        # Bind mouse events
        self.video_label.bind("<Button-1>", self.on_mouse_press)
        self.video_label.bind("<B1-Motion>", self.on_mouse_drag)
        self.video_label.bind("<ButtonRelease-1>", self.on_mouse_release)

        # Timeline frame
        timeline_frame = tk.Frame(main_frame)
        timeline_frame.pack(fill=tk.X, pady=(10, 0))

        # Timeline scale
        self.timeline_var = tk.DoubleVar()
        self.timeline_scale = tk.Scale(
            timeline_frame,
            from_=0,
            to=self.timeline_total_ms,
            orient=tk.HORIZONTAL,
            variable=self.timeline_var,
            command=self.on_timeline_change,
            resolution=100,
            length=400,
            showvalue=False
        )
        self.timeline_scale.pack(fill=tk.X)

        # Time display
        self.time_label = tk.Label(timeline_frame, text="00:00.000")
        self.time_label.pack()

        # Region display
        range_frame = tk.Frame(main_frame)
        range_frame.pack(fill=tk.X, pady=(10, 0))

        tk.Label(range_frame, text="OCR Region:").pack(side=tk.LEFT)
        self.range_label = tk.Label(range_frame, text="")
        self.range_label.pack(side=tk.LEFT, padx=(10, 0))

        # Button frame
        button_frame = tk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        # Reset button
        reset_button = tk.Button(
            button_frame,
            text="Reset region",
            command=self.reset_range
        )
        reset_button.pack(side=tk.LEFT)

        # OK and Cancel buttons
        tk.Button(
            button_frame,
            text="OK",
            command=self.confirm,
            bg='lightgreen'
        ).pack(side=tk.RIGHT, padx=(5, 0))

        tk.Button(
            button_frame,
            text="Cancel",
            command=self.cancel
        ).pack(side=tk.RIGHT)

        self.update_range_display()

    def format_time(self, ms):
        """Convert milliseconds to time format"""
        minutes = int(ms // 60000)
        seconds = int((ms % 60000) // 1000)
        milliseconds = int(ms % 1000)
        return f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"

    def on_timeline_change(self, value):
        """Update frame when timeline changes"""
        ms = float(value)
        self.update_frame(ms)
        total_time_formatted = self.format_time(self.timeline_total_ms)
        current_time_formatted = self.format_time(ms)
        self.time_label.config(
            text=f"{current_time_formatted} / {total_time_formatted}")

    def update_frame(self, ms):
        """Update displayed video frame"""
        self.cap.set(cv2.CAP_PROP_POS_MSEC, ms)
        success, frame = self.cap.read()

        if not success:
            return

        # Convert color space
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Resize frame to fit display area
        height, width = frame.shape[:2]
        display_width = 720
        display_height = int(height * display_width / width)

        frame_resized = cv2.resize(frame, (display_width, display_height))

        # Convert to PIL image
        pil_image = Image.fromarray(frame_resized)

        # Draw OCR region on image
        self.draw_ocr_range(pil_image, display_width, display_height)

        # Convert to PhotoImage and display
        photo = ImageTk.PhotoImage(pil_image)
        self.video_label.configure(image=photo)
        self.video_label.image = photo

        # Save current frame size for mouse events
        self.current_width = display_width
        self.current_height = display_height

    def draw_ocr_range(self, pil_image, width, height):
        """Draw OCR region on the image"""
        draw = ImageDraw.Draw(pil_image)

        # Calculate actual coordinates
        top = int(height * self.top_ratio)
        bottom = int(height * self.bottom_ratio)
        left = int(width * self.left_ratio)
        right = int(width * self.right_ratio)

        # Draw neon green border (thicker lines)
        border_width = 3
        color = 'lime'  # Neon green

        # Draw rectangle border
        for i in range(border_width):
            draw.rectangle(
                [left - i, top - i, right + i, bottom + i],
                outline=color,
                width=1
            )

        # Draw semi-transparent fill
        # Semi-transparent green
        overlay = Image.new('RGBA', pil_image.size, (0, 255, 0, 30))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rectangle(
            [left, top, right, bottom], fill=(0, 255, 0, 30))

        # Merge layers
        pil_image.paste(Image.alpha_composite(
            pil_image.convert('RGBA'), overlay))

    def on_mouse_press(self, event):
        """Mouse press event"""
        if not hasattr(self, 'current_width'):
            return

        x, y = event.x, event.y
        width, height = self.current_width, self.current_height

        # Calculate actual coordinates of current OCR region
        top = int(height * self.top_ratio)
        bottom = int(height * self.bottom_ratio)
        left = int(width * self.left_ratio)
        right = int(width * self.right_ratio)

        # Check mouse position to determine which edge to drag
        tolerance = 10

        if abs(y - top) < tolerance and left <= x <= right:
            self.dragging = 'top'
        elif abs(y - bottom) < tolerance and left <= x <= right:
            self.dragging = 'bottom'
        elif abs(x - left) < tolerance and top <= y <= bottom:
            self.dragging = 'left'
        elif abs(x - right) < tolerance and top <= y <= bottom:
            self.dragging = 'right'
        elif left <= x <= right and top <= y <= bottom:
            self.dragging = 'move'
            self.drag_start_x = x
            self.drag_start_y = y
            self.drag_start_left = self.left_ratio
            self.drag_start_right = self.right_ratio
            self.drag_start_top = self.top_ratio
            self.drag_start_bottom = self.bottom_ratio

    def on_mouse_drag(self, event):
        """Mouse drag event"""
        if not self.dragging or not hasattr(self, 'current_width'):
            return

        x, y = event.x, event.y
        width, height = self.current_width, self.current_height

        if self.dragging == 'top':
            new_ratio = max(0, min(y / height, self.bottom_ratio - 0.05))
            self.top_ratio = new_ratio
        elif self.dragging == 'bottom':
            new_ratio = max(self.top_ratio + 0.05, min(1, y / height))
            self.bottom_ratio = new_ratio
        elif self.dragging == 'left':
            new_ratio = max(0, min(x / width, self.right_ratio - 0.05))
            self.left_ratio = new_ratio
        elif self.dragging == 'right':
            new_ratio = max(self.left_ratio + 0.05, min(1, x / width))
            self.right_ratio = new_ratio
        elif self.dragging == 'move':
            dx = (x - self.drag_start_x) / width
            dy = (y - self.drag_start_y) / height

            # Calculate new position, ensure not out of bounds
            new_left = max(0, min(1 - (self.drag_start_right - self.drag_start_left),
                                  self.drag_start_left + dx))
            new_right = new_left + \
                (self.drag_start_right - self.drag_start_left)
            new_top = max(0, min(1 - (self.drag_start_bottom - self.drag_start_top),
                                 self.drag_start_top + dy))
            new_bottom = new_top + \
                (self.drag_start_bottom - self.drag_start_top)

            self.left_ratio = new_left
            self.right_ratio = new_right
            self.top_ratio = new_top
            self.bottom_ratio = new_bottom

        # Update display
        current_time = self.timeline_var.get()
        self.update_frame(current_time)
        self.update_range_display()

    def on_mouse_release(self, event):
        """Mouse release event"""
        self.dragging = None

    def update_range_display(self):
        """Update region display label"""
        range_text = f"Top: {self.top_ratio:.2f}, Bottom: {self.bottom_ratio:.2f}, " \
            f"Left: {self.left_ratio:.2f}, Right: {self.right_ratio:.2f}"
        self.range_label.config(text=range_text)

    def reset_range(self):
        """Reset region to default values"""
        self.top_ratio = 0.76
        self.bottom_ratio = 0.98
        self.left_ratio = 0.10
        self.right_ratio = 0.90

        current_time = self.timeline_var.get()
        self.update_frame(current_time)
        self.update_range_display()

    def confirm(self):
        """Confirm selection"""
        self.result = {
            'top': self.top_ratio,
            'bottom': self.bottom_ratio,
            'left': self.left_ratio,
            'right': self.right_ratio
        }
        self.dialog.destroy()

    def cancel(self):
        """Cancel selection"""
        self.result = None
        self.dialog.destroy()

    def show(self):
        """Show dialog and wait for result"""
        self.dialog.wait_window()
        return self.result


class SubtitleEditorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Subtitle Editor")

        self.main_pane = tk.PanedWindow(
            root, orient=tk.HORIZONTAL, sashrelief=tk.RAISED)
        self.main_pane.pack(fill=tk.BOTH, expand=True)

        self.left_frame = tk.Frame(self.main_pane)
        self.right_frame = tk.Frame(self.main_pane)

        self.main_pane.add(self.left_frame, minsize=400)
        self.main_pane.add(self.right_frame, minsize=400)

        # Left-side subtitle list
        self.listbox = tk.Listbox(
            self.left_frame,
            selectmode=tk.EXTENDED  # Enable continuous selection
        )
        self.listbox.pack(fill=tk.BOTH, expand=True)
        self.listbox.bind('<<ListboxSelect>>', self.display_selected_frames)

        # Buttons
        self.load_srt_button = tk.Button(
            self.left_frame, text="Load subtitle file", command=self.load_srt
        )
        self.load_srt_button.pack(fill=tk.X)

        self.load_video_button = tk.Button(
            self.left_frame, text="Load video file", command=self.load_video
        )
        self.load_video_button.pack(fill=tk.X)

        self.ocr_button = tk.Button(
            self.left_frame, text="Extract subtitle via OCR", command=self.extract_subtitles_with_ocr
        )
        self.ocr_button.pack(fill=tk.X)

        # Right-side video display and subtitle edit
        self.video_frame_label = tk.Label(self.right_frame)
        self.video_frame_label.pack()

        self.subtitle_text = tk.Text(self.right_frame, height=2, width=30)
        self.subtitle_text.configure(font=tk.font.Font(size=28))
        self.subtitle_text.tag_configure("center", justify='center')
        self.subtitle_text.tag_add("center", "1.0", "end")
        self.subtitle_text.bind('<<Modified>>', self.on_text_modified)
        self.subtitle_text.pack()

        self.srt_path_text = tk.Label(self.right_frame)
        self.srt_path_text.pack(side='bottom')

        self.video_path_text = tk.Label(self.right_frame)
        self.video_path_text.pack(side='bottom')

        self.info_text = tk.Label(self.right_frame)
        self.info_text.pack(side='bottom')

        self.status_frame = tk.Frame(root, bd=1, relief=tk.SUNKEN)
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_text = tk.Label(self.status_frame, text="", anchor='w')
        self.status_text.pack(side=tk.LEFT, padx=5)

        # Initialize variables
        self.subtitles = None
        self.video_path = None
        self.cap = None
        self.edited = tk.BooleanVar(value=False)
        self.edited.trace(
            'w', lambda *args: self.info_text.configure(text='Unsaved' if self.edited.get() else 'Saved'))
        self.history = []
        self.last_selection_List = []

        # Enable drag-and-drop
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind('<<Drop>>', self.drop_files)

        # Bind keys
        # Bind 'e' key for editing
        self.subtitle_text.bind('<Escape>', self.listbox_focus)
        self.listbox.bind('<KeyPress>', self.on_listbox_keypress)
        self.listbox.bind(
            '<Shift-N>', lambda e: [move_up(self.listbox), self.display_selected_frames()])  # move up
        self.listbox.bind('<Command-z>', self.undo)
        # self.listbox.bind('<Command-Shift-z>', self.redo)
        self.root.bind('<Command-s>', self.save_srt)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # --- SeekBar ---
        self.timeline_canvas = tk.Canvas(
            self.right_frame, height=20, cursor='sb_h_double_arrow')
        self.timeline_canvas.pack(fill=tk.X)

        self.timeline_canvas.bind("<Button-1>", self.on_timeline_press)
        self.timeline_canvas.bind("<B1-Motion>", self.on_timeline_drag)

        self.timeline_total_ms = 0
        # Current X position of the seekbar (used for drawing the line)
        self.seekbar_position = 0

        self.timeline_time_label = tk.Label(
            self.right_frame, text="00:00.000 / 00:00.000")
        self.timeline_time_label.pack()

    def _update_status(self, text):
        self.root.after(0, lambda: self.status_text.configure(text=text))

    def extract_subtitles_with_ocr(self):
        if not self.cap:
            messagebox.showerror("Error", "Please load video file first.")
            return

        # Show OCR region selection dialog
        selector = OCRRangeSelector(
            self.root, self.cap, self.timeline_total_ms)
        range_config = selector.show()

        if range_config is None:
            return  # User cancelled

        # Save the selected region configuration
        self.ocr_range = range_config

        thread = threading.Thread(target=self._ocr_worker)
        thread.start()

    def _ocr_worker(self):
        global reader
        if reader is None:
            self._update_status('Loading OCR model...')
            reader = easyocr.Reader(['ch_tra'])

        # Use a separate VideoCapture instance to avoid conflict
        cap = cv2.VideoCapture(self.video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        print(f'''\
FPS: {fps}
Frames: {total_frames}
Duration: {timedelta(seconds=total_frames / fps)}\
        ''')
        logs = []
        maker = SubtitleMaker()

        cap.set(cv2.CAP_PROP_POS_MSEC, 0)
        for i in (pbar := trange(total_frames, desc="Progress")):
            ret, frame = cap.read()
            if not ret:
                break
            if i % OCR_INTERVAL != 0:
                continue
            current_time = timedelta(
                milliseconds=cap.get(cv2.CAP_PROP_POS_MSEC))
            # clip the image to the region containing captions
            frame = frame[int(frame.shape[0] * self.ocr_range['top']):int(frame.shape[0] * self.ocr_range['bottom']),
                          int(frame.shape[1] * self.ocr_range['left']):int(frame.shape[1] * self.ocr_range['right']), :]
            result = reader.readtext(frame, width_ths=0.2)
            # sort by left to right
            text = ' '.join([x[1] for x in result])
            text = remove_strange_char(text).strip()
            confidence = avg([fragment[2] for fragment in result])
            logs.append(f'{current_time} {text} {confidence}')
            pbar.set_description(text)
            self._update_status(f'Frame {i}/{total_frames}: {text}')
            maker.next_frame(current_time, text, confidence)

        maker.end(timedelta(seconds=total_frames / fps))
        self.subtitles = pysrt.SubRipFile(maker.get_subtitles())
        self.srt_path = None
        self.srt_path_text.configure(text='srt not saved')
        self.update_subtitle_list()
        self.edited.set(True)
        self.history = []
        self._update_status('')

    def draw_seekbar(self):
        self.timeline_canvas.delete("all")
        width = self.timeline_canvas.winfo_width() or self.timeline_canvas_width

        # timeline
        self.timeline_canvas.create_rectangle(
            0, 8, width, 12, fill='darkgray', outline='')

        # current position
        self.timeline_canvas.create_line(
            self.seekbar_position, 0, self.seekbar_position, 20, fill='red', width=2)

    def on_timeline_press(self, event):
        self.update_seekbar(event.x)

    def on_timeline_drag(self, event):
        self.update_seekbar(event.x)

    def update_seekbar(self, x):
        if not self.cap or self.timeline_total_ms == 0:
            return

        width = self.timeline_canvas.winfo_width()
        x = max(0, min(x, width))
        self.seekbar_position = x
        self.draw_seekbar()

        ratio = x / width
        ms = int(ratio * self.timeline_total_ms)

        self.timeline_time_label.configure(
            text=f"{format_millis(ms)} / {format_millis(self.timeline_total_ms)}"
        )

        self.cap.set(cv2.CAP_PROP_POS_MSEC, ms)
        success, frame = self.cap.read()
        if success:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(frame)
            image = ImageTk.PhotoImage(image)
            self.video_frame_label.configure(image=image)
            self.video_frame_label.image = image

    def undo(self, event):
        if self.history:
            indices = self.listbox.curselection()
            idx = indices[0] if indices else None
            self.subtitles = self.history.pop()
            self.update_subtitle_list()
            self.edited.set(True)
            if idx is not None:
                self.listbox.selection_set(idx)
                self.listbox.activate(idx)
                self.listbox.see(idx)

    def on_listbox_keypress(self, event):
        if event.char in ['e', 'ㄍ']:  # Bind 'e' key for editing
            self.subtitle_text.focus_set()
        elif event.char in ['d', 'ㄎ']:
            self.delete_subtitles()
        elif event.char in ['m', 'ㄩ']:  # Bind 'm' key for merging subtitles
            self.merge_subtitles()
        elif event.char in ['r', 'ㄐ']:
            self.reload_srt()
        elif event.char in ['n', 'ㄙ']:  # move down
            move_down(self.listbox)
            self.display_selected_frames()
        elif event.char in ['h', 'ㄘ']:
            self.rotate_selected_frame()
        elif event.char in [',', 'ㄝ']:
            self.add_comma()

    def add_comma(self):
        selected_indices = self.listbox.curselection()
        if len(selected_indices) != 1:
            return
        idx = selected_indices[0]
        parts = self.subtitles[idx].text.split()
        self.subtitles[idx].text = '，'.join(parts)
        self.update_subtitle_list()
        self.listbox.selection_set(idx)
        self.listbox.activate(idx)
        self.listbox.see(idx)
        self.display_selected_frames()

    def rotate_selected_frame(self):
        selected_indices = self.listbox.curselection()
        if len(selected_indices) != 1:
            return
        idx = selected_indices[0]
        parts = self.subtitles[idx].text.split()
        self.subtitles[idx].text = ' '.join(parts[1:] + parts[:1])
        self.update_subtitle_list()
        self.listbox.selection_set(idx)
        self.listbox.activate(idx)
        self.listbox.see(idx)
        self.display_selected_frames()

    def listbox_focus(self, event=None):
        selected_indices = self.listbox.curselection()
        self.listbox.focus_set()
        if selected_indices:
            self.listbox.activate(selected_indices[0])
            self.listbox.see(selected_indices[0])

    def load_srt(self, path=None):
        # Load subtitle file
        self.srt_path = path or filedialog.askopenfilename(
            filetypes=[("SRT files", "*.srt")])
        if self.srt_path:
            self.srt_path_text.configure(text=self.srt_path)
            self.subtitles = pysrt.open(self.srt_path)
            self.update_subtitle_list()
        self.edited.set(False)
        self.history = []

    def reload_srt(self, event=None):
        if messagebox.askyesno("Confirmation", "Are you sure you want to reload?"):
            indices = self.listbox.curselection()
            self.subtitles = pysrt.open(self.srt_path)
            self.update_subtitle_list()
            if indices:
                idx = indices[0]
                self.listbox.selection_set(idx)
                self.listbox.activate(idx)
                self.listbox.see(idx)
            self.edited.set(False)

            self.info_text.configure(text='Reloaded!')
            self.root.after(1000, lambda: self.info_text.configure(
                text='Unsaved' if self.edited.get() else 'Saved'))

    def update_subtitle_list(self):
        self.listbox.delete(0, tk.END)
        previous_end_time = None
        for index, subtitle in enumerate(self.subtitles):
            time_range = f"{format_time(subtitle.start)} - {format_time(subtitle.end)}"
            self.listbox.insert(tk.END, f"{time_range}: {subtitle.text}")
            if previous_end_time is not None and subtitle.start == previous_end_time:
                if self.listbox.itemcget(index - 1, 'bg') == '':
                    self.listbox.itemconfig(index - 1, {'bg': 'lightpink'})
                else:
                    self.listbox.itemconfig(index - 1, {'bg': 'lightyellow'})
                self.listbox.itemconfig(index, {'bg': 'lightyellow'})
            previous_end_time = subtitle.end

    def load_video(self, path=None):
        # Load video file
        self.video_path = path or filedialog.askopenfilename(
            filetypes=[("MP4 files", "*.mp4"), ("WebM files", "*.webm")])
        if self.video_path:
            self.video_path_text.configure(text=self.video_path)
            self.cap = cv2.VideoCapture(self.video_path)

            self.draw_seekbar()
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            frame_count = self.cap.get(cv2.CAP_PROP_FRAME_COUNT)
            self.timeline_total_ms = int((frame_count / fps) * 1000)
            self.update_seekbar(0)

    def display_selected_frames(self, event=None):
        indices = self.listbox.curselection()
        if not indices:
            return
        idx = indices[-1]
        subtitle = self.subtitles[idx]
        self.display_subtitle(subtitle)

    def check_continuous_selection(self, selected_indices):
        # Check if selected indices are continuous
        return list(selected_indices) == list(
            range(selected_indices[0], selected_indices[-1] + 1)
        )

    def display_subtitle(self, subtitle):
        # Display frame and subtitle for a single subtitle
        if self.cap and self.subtitles:
            t = (get_milliseconds(subtitle.start) +
                 get_milliseconds(subtitle.end)) / 2
            self.cap.set(cv2.CAP_PROP_POS_MSEC, t)
            success, frame = self.cap.read()
            if not success:
                return

            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(frame)
            image = ImageTk.PhotoImage(image)

            self.video_frame_label.configure(image=image)
            self.video_frame_label.image = image

            # Update subtitle text
            self.subtitle_text.delete(1.0, tk.END)
            self.subtitle_text.insert(tk.END, subtitle.text)
            self.subtitle_text.edit_modified(False)
            self.subtitle_text.tag_add("center", "1.0", "end")
            set_cursor_to_center(self.subtitle_text)

            if self.timeline_total_ms:
                width = self.timeline_canvas.winfo_width()
                ratio = t / self.timeline_total_ms
                self.seekbar_position = int(width * ratio)
                self.draw_seekbar()
                self.timeline_time_label.configure(
                    text=f"{format_millis(int(t))} / {format_millis(self.timeline_total_ms)}"
                )

    def drop_files(self, event):
        file_path = event.data.strip('{}')  # Remove curly braces if present
        if file_path.endswith('.srt'):
            self.load_srt(file_path)
        elif file_path.endswith('.mp4'):
            self.load_video(file_path)
        else:
            messagebox.showerror(
                "Error", "Unsupported file format. Please drop an .srt or .mp4 file.")

    def on_text_modified(self, event=None):
        if not self.subtitles:
            return
        selected_indices = self.listbox.curselection()
        if len(selected_indices) != 1:
            return
        idx = selected_indices[0]
        if self.subtitle_text.edit_modified():
            self.subtitle_text.edit_modified(False)  # Clear modified flag
            new_text = self.subtitle_text.get(1.0, tk.END).strip()
            if self.subtitles[idx].text != new_text:
                self.edited.set(True)
                self.subtitles[idx].text = new_text
                self.update_subtitle_list()
                self.listbox.selection_set(idx)
                self.listbox.activate(idx)
                self.listbox.see(idx)

    def delete_subtitles(self, event=None):
        selected_indices = self.listbox.curselection()
        if not selected_indices:
            return
        self.history.append(copy.deepcopy(self.subtitles))
        self.edited.set(True)
        for i in sorted(selected_indices, reverse=True):
            if 0 <= i < len(self.subtitles):
                del self.subtitles[i]
        self.update_subtitle_list()

        # Restore focus and adjust selection
        if len(self.subtitles) > 0:
            new_selection_index = min(
                min(selected_indices), len(self.subtitles) - 1)
            self.listbox.selection_set(new_selection_index)
            self.listbox.activate(new_selection_index)
            self.listbox.see(new_selection_index)
            self.display_selected_frames()  # Update display with new selection
        else:
            # Clear text and video frame if no subtitles left
            self.subtitle_text.delete(1.0, tk.END)
            self.video_frame_label.configure(image='')

    def merge_subtitles(self, event=None):
        indices = sorted(self.listbox.curselection())
        if len(indices) <= 1:
            return
        self.history.append(copy.deepcopy(self.subtitles))
        self.edited.set(True)
        end_time = self.subtitles[indices[-1]].end
        for i in range(len(indices) - 1, 0, -1):
            del self.subtitles[indices[i]]
        self.subtitles[indices[0]].end = end_time

        self.update_subtitle_list()
        self.listbox.selection_set(indices[0])
        self.listbox.activate(indices[0])
        self.listbox.see(indices[0])
        self.display_selected_frames()

    def save_srt(self, event=None):
        if self.srt_path is None:
            path = filedialog.asksaveasfilename(
                defaultextension=".srt",
                filetypes=[("SRT files", "*.srt")],
                title="Save subtitle file"
            )
            if not path:
                return  # User cancelled save
            self.srt_path = path
            self.srt_path_text.configure(text=self.srt_path)

        self.subtitles.save(self.srt_path, encoding='utf-8')
        self.edited.set(False)

    def on_close(self):
        if self.edited.get():
            result = messagebox.askyesnocancel(
                "Unsaved Changes",
                "You have unsaved changes. Do you want to save before exiting?"
            )
            if result is None:
                return
            elif result:
                self.save_srt()
                self.root.destroy()
            else:
                self.root.destroy()
        else:
            self.root.destroy()


if __name__ == "__main__":
    root = TkinterDnD.Tk()
    root.geometry("1280x720")
    app = SubtitleEditorApp(root)
    root.mainloop()
