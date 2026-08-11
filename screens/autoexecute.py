import os
import threading

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.lang import Builder
from kivy.app import App
from kivy.metrics import dp
from kivy.clock import Clock

KV = '''
<AutoexecuteScreen>:
    canvas.before:
        Color:
            rgba: 0.031, 0.043, 0.078, 1
        Rectangle:
            pos: self.pos
            size: self.size

    BoxLayout:
        orientation: 'vertical'

        # Top bar
        BoxLayout:
            size_hint_y: None
            height: dp(54)
            padding: dp(12), dp(8)
            spacing: dp(10)
            canvas.before:
                Color:
                    rgba: 0.027, 0.035, 0.102, 1
                Rectangle:
                    pos: self.pos
                    size: self.size

            Button:
                text: '‹'
                size_hint_x: None
                width: dp(36)
                font_size: dp(22)
                bold: True
                color: 0, 0.8, 0.8, 1
                background_normal: ''
                background_color: 0, 0, 0, 0
                on_release: root.go_back()

            Label:
                text: 'Autoexecute'
                font_size: dp(17)
                bold: True
                color: 0.957, 0.973, 1, 1
                halign: 'left'
                text_size: self.size

        # Path + count info
        BoxLayout:
            orientation: 'vertical'
            size_hint_y: None
            height: dp(52)
            padding: dp(16), dp(6)

            Label:
                id: lbl_path
                text: '/sdcard/Delta/Autoexecute'
                color: 0, 0.8, 0.8, 0.8
                font_size: dp(12)
                halign: 'left'
                text_size: self.size
                valign: 'middle'

            Label:
                id: lbl_count
                text: '0 files'
                color: 0.627, 0.667, 0.871, 0.5
                font_size: dp(12)
                halign: 'left'
                text_size: self.size
                valign: 'middle'

        # File list
        ScrollView:
            do_scroll_x: False
            BoxLayout:
                id: file_list
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                padding: dp(14), dp(6)
                spacing: dp(7)

        # Bottom actions
        BoxLayout:
            size_hint_y: None
            height: dp(62)
            padding: dp(14), dp(8)
            spacing: dp(10)
            canvas.before:
                Color:
                    rgba: 0.027, 0.035, 0.102, 1
                Rectangle:
                    pos: self.pos
                    size: self.size

            Button:
                text: '+ New File'
                font_size: dp(14)
                bold: True
                color: 0.031, 0.043, 0.078, 1
                background_normal: ''
                background_color: 0, 0, 0, 0
                canvas.before:
                    Color:
                        rgba: 0.957, 0.973, 1, 1
                    RoundedRectangle:
                        pos: self.pos
                        size: self.size
                        radius: [dp(22)]
                on_release: root.add_file_dialog()

            Button:
                text: 'Refresh'
                font_size: dp(13)
                color: 0.627, 0.667, 0.871, 0.7
                background_normal: ''
                background_color: 0, 0, 0, 0
                size_hint_x: None
                width: dp(90)
                canvas.before:
                    Color:
                        rgba: 0.176, 0.180, 0.314, 0.3
                    RoundedRectangle:
                        pos: self.pos
                        size: self.size
                        radius: [dp(22)]
                on_release: root.load_files()
'''

Builder.load_string(KV)


class AutoexecuteScreen(Screen):
    def on_enter(self):
        from config_manager import config
        path = config.get('autoexecute_path', '/sdcard/Delta/Autoexecute')
        self.ids.lbl_path.text = path
        self.load_files()

    def _get_path(self):
        from config_manager import config
        return config.get('autoexecute_path', '/sdcard/Delta/Autoexecute')

    def load_files(self):
        path = self._get_path()
        self.ids.file_list.clear_widgets()
        try:
            os.makedirs(path, exist_ok=True)
            files = sorted(os.listdir(path))
        except Exception:
            files = []

        self.ids.lbl_count.text = f'{len(files)} file(s) in folder'

        if not files:
            lbl = Label(
                text='No files found.',
                size_hint_y=None,
                height=dp(40),
                color=(0.45, 0.45, 0.45, 1),
                font_size=dp(13),
            )
            self.ids.file_list.add_widget(lbl)
            return

        for fname in files:
            fpath = os.path.join(path, fname)
            try:
                size = os.path.getsize(fpath)
                size_str = f'{size} bytes'
            except Exception:
                size_str = '?'

            row = BoxLayout(
                orientation='horizontal',
                size_hint_y=None,
                height=dp(56),
                padding=(dp(14), dp(8)),
                spacing=dp(10),
            )
            with row.canvas.before:
                from kivy.graphics import Color, RoundedRectangle
                Color(0.051, 0.063, 0.149, 1)
                rr = RoundedRectangle(pos=row.pos, size=row.size, radius=[dp(12)])
            row.bind(pos=lambda w, v, r=rr: setattr(r, 'pos', w.pos),
                     size=lambda w, v, r=rr: setattr(r, 'size', w.size))

            lbl = Label(
                text=f'{fname}  ({size_str})',
                font_size=dp(13),
                color=(0.784, 0.820, 1, 0.85),
                halign='left',
                text_size=(None, None),
            )
            lbl.bind(size=lambda w, *a: setattr(w, 'text_size', (w.width, None)))

            _fname = fname
            btn_del = Button(
                text='Del',
                size_hint_x=None,
                width=dp(52),
                font_size=dp(12),
                bold=True,
                color=(1, 0.35, 0.35, 1),
                background_normal='',
                background_color=(0, 0, 0, 0),
            )
            btn_del.bind(on_release=lambda b, f=_fname: self._confirm_delete(f))

            btn_edit = Button(
                text='Edit',
                size_hint_x=None,
                width=dp(52),
                font_size=dp(12),
                bold=True,
                color=(0, 0.8, 0.8, 1),
                background_normal='',
                background_color=(0, 0, 0, 0),
            )
            btn_edit.bind(on_release=lambda b, f=_fname: self._edit_file(f))

            row.add_widget(lbl)
            row.add_widget(btn_edit)
            row.add_widget(btn_del)
            self.ids.file_list.add_widget(row)

    def add_file_dialog(self):
        self._open_editor('', '')

    def _edit_file(self, fname):
        path = os.path.join(self._get_path(), fname)
        try:
            with open(path, 'r') as f:
                content = f.read()
        except Exception:
            content = ''
        self._open_editor(fname, content)

    def _open_editor(self, fname, content):
        layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(8))

        name_input = TextInput(
            text=fname,
            hint_text='File name (e.g. script.lua)',
            size_hint_y=None,
            height=dp(46),
            font_size=dp(13),
            multiline=False,
            background_color=(0.039, 0.047, 0.118, 1),
            foreground_color=(0.957, 0.973, 1, 1),
            cursor_color=(0, 0.8, 0.8, 1),
            hint_text_color=(0.49, 0.52, 0.72, 0.4),
            padding=[dp(12), dp(12)],
        )

        script_input = TextInput(
            text=content,
            hint_text='Enter your Lua script here...',
            font_size=dp(13),
            background_color=(0.027, 0.031, 0.086, 1),
            foreground_color=(0.957, 0.973, 1, 1),
            cursor_color=(0, 0.8, 0.8, 1),
            hint_text_color=(0.49, 0.52, 0.72, 0.4),
            padding=[dp(12), dp(10)],
        )

        btn_row = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        btn_cancel = Button(
            text='Cancel',
            background_normal='',
            background_color=(0.176, 0.188, 0.380, 0.5),
            color=(0.627, 0.667, 0.871, 0.8),
        )
        btn_save = Button(
            text='Save File',
            background_normal='',
            background_color=(0.957, 0.973, 1, 1),
            color=(0.027, 0.031, 0.086, 1),
            bold=True,
        )
        btn_row.add_widget(btn_cancel)
        btn_row.add_widget(btn_save)

        layout.add_widget(name_input)
        layout.add_widget(script_input)
        layout.add_widget(btn_row)

        popup = Popup(
            title='Script Editor',
            content=layout,
            size_hint=(0.95, 0.88),
            background_color=(0.039, 0.047, 0.118, 1),
            title_color=(0, 0.8, 0.8, 1),
        )

        btn_cancel.bind(on_release=popup.dismiss)

        def do_save(*a):
            n = name_input.text.strip()
            s = script_input.text
            if not n:
                return
            fpath = os.path.join(self._get_path(), n)
            try:
                os.makedirs(self._get_path(), exist_ok=True)
                with open(fpath, 'w') as f:
                    f.write(s)
            except Exception:
                pass
            popup.dismiss()
            self.load_files()

        btn_save.bind(on_release=do_save)
        popup.open()

    def _confirm_delete(self, fname):
        layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(12))
        layout.add_widget(Label(
            text=f'Delete "{fname}"?',
            color=(1, 1, 1, 1),
            font_size=dp(14),
        ))
        btn_row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        btn_no = Button(
            text='Cancel',
            background_normal='',
            background_color=(0.15, 0.15, 0.15, 1),
            color=(0.7, 0.7, 0.7, 1),
        )
        btn_yes = Button(
            text='Delete',
            background_normal='',
            background_color=(0.8, 0.15, 0.15, 1),
            color=(1, 1, 1, 1),
        )
        btn_row.add_widget(btn_no)
        btn_row.add_widget(btn_yes)
        layout.add_widget(btn_row)

        popup = Popup(
            title='Confirm Delete',
            content=layout,
            size_hint=(0.8, 0.35),
            background_color=(0.039, 0.047, 0.118, 1),
            title_color=(1, 0.35, 0.35, 1),
        )
        btn_no.bind(on_release=popup.dismiss)

        def do_delete(*a):
            fpath = os.path.join(self._get_path(), fname)
            try:
                os.remove(fpath)
            except Exception:
                pass
            popup.dismiss()
            self.load_files()

        btn_yes.bind(on_release=do_delete)
        popup.open()

    def go_back(self):
        self.manager.current = 'main'
