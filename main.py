"""
main.py — Big Brain AI
Kivy Android chat UI backed by OneMind kernel (kernel.py).
"""

import os
import sys
import shutil
import threading
import traceback

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.filechooser import FileChooserIconView
from kivy.uix.image import Image as KivyImage
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.utils import get_color_from_hex

# ─────────────────────────────────────────────────────────────────────────────
# CRASH LOGGER
# Uses app-private storage on Android, home dir on desktop.
# Never crashes the app if the log write itself fails.
# ─────────────────────────────────────────────────────────────────────────────

def _crash_log_path():
    try:
        from android.storage import app_storage_path
        base = app_storage_path()
    except ImportError:
        base = os.path.expanduser("~")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "bigbrain_crash.txt")


def _log_crash(exc_type, exc_value, exc_tb):
    try:
        with open(_crash_log_path(), "a", encoding="utf-8") as fh:
            fh.write("".join(traceback.format_exception(exc_type, exc_value, exc_tb)))
    except Exception:
        pass


sys.excepthook = _log_crash

# ─────────────────────────────────────────────────────────────────────────────
# COLOUR PALETTE
# Every name used anywhere in this file is defined exactly once, right here.
# ─────────────────────────────────────────────────────────────────────────────

BG_DARK      = get_color_from_hex("#0A000F")   # window background
BG_MID       = get_color_from_hex("#110022")   # AI bubble / input bar bg
PURPLE_DEEP  = get_color_from_hex("#2D0045")   # header / user bubble bg
PURPLE_MID   = get_color_from_hex("#6B00A8")   # buttons
PURPLE_LIGHT = get_color_from_hex("#9B30FF")   # status / thinking label
GREEN_NEON   = get_color_from_hex("#00FF88")   # send button label
GREEN_DIM    = get_color_from_hex("#00AA55")   # download button bg
WHITE_SOFT   = get_color_from_hex("#E8D5FF")   # primary text
BLACK_PURE   = get_color_from_hex("#000000")   # download button text
GREY_DARK    = get_color_from_hex("#1A0028")   # text input background

Window.clearcolor = BG_DARK

# ─────────────────────────────────────────────────────────────────────────────
# KERNEL INIT
# Wrapped in try/except so a missing API key never crashes the UI.
# ─────────────────────────────────────────────────────────────────────────────

try:
    from kernel import OneMind
    brain = OneMind(api_key=os.environ.get("GEMINI_API_KEY", ""))
except Exception:
    brain = None


# ─────────────────────────────────────────────────────────────────────────────
# MESSAGE BUBBLE
# ─────────────────────────────────────────────────────────────────────────────

class MessageBubble(BoxLayout):
    def __init__(self, text, is_user=True, media_path=None, **kwargs):
        super().__init__(**kwargs)
        self.orientation  = "vertical"
        self.size_hint_y  = None
        self.padding      = [dp(8), dp(4)]
        self.spacing      = dp(4)

        bubble_color = PURPLE_DEEP if is_user else BG_MID
        text_color   = list(WHITE_SOFT) if is_user else list(get_color_from_hex("#C0FFA0"))

        lbl = Label(
            text=text, markup=True, size_hint_y=None,
            text_size=(Window.width * 0.78, None),
            halign="left", valign="top",
            color=text_color, font_size=dp(14),
            padding=[dp(12), dp(8)],
        )
        lbl.bind(texture_size=lambda inst, val: setattr(inst, "height", val[1] + dp(16)))
        self.height = lbl.height + dp(16)
        lbl.bind(height=lambda inst, val: setattr(self, "height", val + dp(16)))

        with self.canvas.before:
            Color(*bubble_color)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(16)])
        self.bind(pos=lambda *a: setattr(self.rect, "pos", self.pos))
        self.bind(size=lambda *a: setattr(self.rect, "size", self.size))

        self.add_widget(lbl)

        if media_path and os.path.exists(media_path):
            ext = os.path.splitext(media_path)[1].lower()
            if ext in (".png", ".jpg", ".jpeg"):
                img = KivyImage(source=media_path, size_hint_y=None, height=dp(200))
                self.add_widget(img)
                self.height += dp(210)

            dl_btn = Button(
                text="Download", size_hint_y=None, height=dp(36),
                background_color=list(GREEN_DIM) + [1],
                color=list(BLACK_PURE) + [1],
                font_size=dp(13),
            )
            dl_btn.bind(on_press=lambda x: self._download(media_path))
            self.add_widget(dl_btn)
            self.height += dp(46)

    def _download(self, media_path):
        try:
            from android.storage import primary_external_storage_path
            dest_dir = os.path.join(primary_external_storage_path(), "BigBrainAI")
        except ImportError:
            dest_dir = os.path.expanduser("~/Downloads/BigBrainAI")
        os.makedirs(dest_dir, exist_ok=True)
        shutil.copy2(media_path, os.path.join(dest_dir, os.path.basename(media_path)))


# ─────────────────────────────────────────────────────────────────────────────
# MAIN CHAT LAYOUT
# ─────────────────────────────────────────────────────────────────────────────

class BigBrainChat(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation  = "vertical"
        self.spacing      = 0
        self.uploaded_file = None
        self._build_ui()

    def _build_ui(self):
        # ── Header ──────────────────────────────────────────────────────────
        header = BoxLayout(size_hint_y=None, height=dp(60), padding=[dp(16), dp(8)])
        with header.canvas.before:
            Color(*PURPLE_DEEP)
            self._header_rect = RoundedRectangle(
                pos=header.pos, size=header.size, radius=[0]
            )
        header.bind(pos=lambda *a: setattr(self._header_rect, "pos", header.pos))
        header.bind(size=lambda *a: setattr(self._header_rect, "size", header.size))
        title = Label(
            text=(
                "[b][color=9B30FF]BIG[/color] "
                "[color=00FF88]BRAIN[/color] "
                "[color=E8D5FF]AI[/color][/b]"
            ),
            markup=True, font_size=dp(22), halign="left", valign="middle",
        )
        header.add_widget(title)
        self.add_widget(header)

        # ── Chat scroll area ────────────────────────────────────────────────
        self.scroll = ScrollView(size_hint_y=1)
        self.chat_layout = BoxLayout(
            orientation="vertical", size_hint_y=None,
            spacing=dp(8), padding=[dp(12), dp(12)],
        )
        self.chat_layout.bind(minimum_height=self.chat_layout.setter("height"))
        self.scroll.add_widget(self.chat_layout)
        self.add_widget(self.scroll)

        # ── Thinking / status label ─────────────────────────────────────────
        self.thinking_label = Label(
            text="", size_hint_y=None, height=dp(24),
            color=list(PURPLE_LIGHT) + [1], font_size=dp(12),
        )
        self.add_widget(self.thinking_label)

        # ── Input row ──────────────────────────────────────────────────────
        input_row = BoxLayout(
            size_hint_y=None, height=dp(56),
            spacing=dp(6), padding=[dp(8), dp(6)],
        )
        with input_row.canvas.before:
            Color(*BG_MID)
            self._input_rect = RoundedRectangle(
                pos=input_row.pos, size=input_row.size, radius=[0]
            )
        input_row.bind(pos=lambda *a: setattr(self._input_rect, "pos", input_row.pos))
        input_row.bind(size=lambda *a: setattr(self._input_rect, "size", input_row.size))

        upload_btn = Button(
            text="[+]", size_hint_x=None, width=dp(44),
            size_hint_y=None, height=dp(44),
            background_color=list(PURPLE_MID) + [1], font_size=dp(16),
        )
        upload_btn.bind(on_press=self._open_file_chooser)
        input_row.add_widget(upload_btn)

        self.text_input = TextInput(
            hint_text="Ask Big Brain anything...", multiline=False,
            size_hint_y=None, height=dp(44),
            background_color=list(GREY_DARK) + [1],
            foreground_color=list(WHITE_SOFT) + [1],
            font_size=dp(14), padding=[dp(12), dp(10)],
        )
        self.text_input.bind(on_text_validate=self._on_send)
        input_row.add_widget(self.text_input)

        send_btn = Button(
            text=">>", size_hint_x=None, width=dp(44),
            size_hint_y=None, height=dp(44),
            background_color=list(PURPLE_MID) + [1],
            color=list(GREEN_NEON) + [1],
            font_size=dp(16), bold=True,
        )
        send_btn.bind(on_press=self._on_send)
        input_row.add_widget(send_btn)

        self.add_widget(input_row)

        # ── Welcome message ─────────────────────────────────────────────────
        self._add_message(
            "Welcome to Big Brain AI.\n\n"
            "I can chat, reason, generate images, audio, video, and code.\n"
            "All work is handled privately on your device.\n\n"
            "What shall we create?",
            is_user=False,
        )

    # ── Message helpers ──────────────────────────────────────────────────────

    def _add_message(self, text, is_user=True, media_path=None):
        bubble = MessageBubble(
            text=text, is_user=is_user, media_path=media_path,
            size_hint_x=0.85,
            pos_hint={"right": 1} if is_user else {"x": 0},
        )
        self.chat_layout.add_widget(bubble)
        Clock.schedule_once(lambda dt: setattr(self.scroll, "scroll_y", 0), 0.1)

    # ── Send flow ────────────────────────────────────────────────────────────

    def _on_send(self, *args):
        msg = self.text_input.text.strip()
        if not msg:
            return
        self.text_input.text = ""
        self._add_message(msg, is_user=True)
        self.thinking_label.text = "Big Brain is thinking..."
        threading.Thread(
            target=self._process_message, args=(msg,), daemon=True
        ).start()

    def _process_message(self, msg):
        try:
            if brain:
                response, media = brain.chat(msg, self.uploaded_file)
            else:
                response = "Brain not initialized. Check GEMINI_API_KEY."
                media    = None
        except Exception as e:
            response = f"Error: {e}"
            media    = None
        self.uploaded_file = None
        Clock.schedule_once(lambda dt: self._show_response(response, media), 0)

    def _show_response(self, response, media_path):
        self.thinking_label.text = ""
        self._add_message(response, is_user=False, media_path=media_path)

    # ── File chooser ─────────────────────────────────────────────────────────

    def _open_file_chooser(self, *args):
        chooser = FileChooserIconView(path=os.path.expanduser("~"))
        popup   = Popup(title="Select File", content=chooser, size_hint=(0.95, 0.8))

        def _on_select(inst, selection, *args):
            if selection:
                path = selection[0]
                try:
                    with open(path, "r", errors="ignore") as f:
                        content = f.read(50000)
                    self.uploaded_file = {
                        "name":    os.path.basename(path),
                        "content": content,
                        "path":    path,
                    }
                    self.thinking_label.text = f"Attached: {os.path.basename(path)}"
                except Exception:
                    self.uploaded_file = {
                        "name":    os.path.basename(path),
                        "content": "",
                        "path":    path,
                    }
                popup.dismiss()

        chooser.bind(on_submit=_on_select)
        popup.open()


# ─────────────────────────────────────────────────────────────────────────────
# APP ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

class BigBrainApp(App):
    def build(self):
        self.title = "Big Brain AI"
        return BigBrainChat()


if __name__ == "__main__":
    BigBrainApp().run()
