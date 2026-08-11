from kivy.uix.screenmanager import Screen
from kivy.uix.button import Button
from kivy.lang import Builder
from kivy.metrics import dp

from core.app_launcher import PRESET_GAMES

KV = '''
<SetupGameScreen>:
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
                text: 'Game & Server'
                font_size: dp(17)
                bold: True
                color: 0.957, 0.973, 1, 1
                halign: 'left'
                text_size: self.size

        # Method selector
        BoxLayout:
            size_hint_y: None
            height: dp(52)
            padding: dp(14), dp(8)
            spacing: dp(8)

            Label:
                text: 'Mode'
                size_hint_x: None
                width: dp(50)
                color: 0.627, 0.667, 0.871, 0.7
                font_size: dp(13)

            Button:
                id: btn_method_all
                text: 'All Packages'
                font_size: dp(13)
                bold: True
                background_normal: ''
                background_color: 0, 0, 0, 0
                on_release: root.set_method('all')

            Button:
                id: btn_method_each
                text: 'Per Package'
                font_size: dp(13)
                bold: True
                background_normal: ''
                background_color: 0, 0, 0, 0
                on_release: root.set_method('each')

        # Current selection
        BoxLayout:
            size_hint_y: None
            height: dp(44)
            padding: dp(14), dp(6)
            canvas.before:
                Color:
                    rgba: 0.051, 0.063, 0.149, 1
                Rectangle:
                    pos: self.pos
                    size: self.size

            Label:
                id: lbl_current
                text: 'Selected: —'
                color: 0, 0.8, 0.8, 1
                font_size: dp(13)
                bold: True
                halign: 'left'
                text_size: self.size
                valign: 'middle'

        # Game preset list
        Label:
            text: 'PRESET GAMES'
            size_hint_y: None
            height: dp(32)
            color: 0.627, 0.667, 0.871, 0.5
            bold: True
            font_size: dp(10)
            letter_spacing: dp(1.5)
            halign: 'left'
            padding: dp(14), 0
            text_size: self.size

        ScrollView:
            do_scroll_x: False
            BoxLayout:
                id: game_list
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                padding: dp(14), dp(4)
                spacing: dp(7)

        # Custom input section
        BoxLayout:
            orientation: 'vertical'
            size_hint_y: None
            height: dp(90)
            padding: dp(14), dp(8)
            spacing: dp(6)

            Label:
                text: 'CUSTOM GAME ID / PRIVATE SERVER LINK'
                font_size: dp(10)
                bold: True
                color: 0.627, 0.667, 0.871, 0.5
                halign: 'left'
                text_size: self.size
                size_hint_y: None
                height: dp(20)
                letter_spacing: dp(1)

            TextInput:
                id: inp_custom
                hint_text: 'Game ID or roblox:// link...'
                font_size: dp(13)
                multiline: False
                background_color: 0.039, 0.047, 0.118, 1
                foreground_color: 0.957, 0.973, 1, 1
                cursor_color: 0, 0.8, 0.8, 1
                hint_text_color: 0.49, 0.52, 0.72, 0.45
                padding: dp(12), dp(10)
                size_hint_y: None
                height: dp(44)

        # Save
        BoxLayout:
            size_hint_y: None
            height: dp(62)
            padding: dp(14), dp(8)

            Button:
                text: 'Save & Apply'
                font_size: dp(15)
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
                        radius: [dp(26)]
                on_release: root.save()
'''

Builder.load_string(KV)


class SetupGameScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._method = 'all'
        self._selected_game = ('', '')

    def on_enter(self):
        from config_manager import config
        self._method = config.get('game_method', 'all')
        self._selected_game = (
            config.get('game_name', ''),
            config.get('game_id', '')
        )
        self._build_game_list()
        self._update_method_ui()
        self._update_current_label()

    def _build_game_list(self):
        gl = self.ids.game_list
        gl.clear_widgets()
        for name, gid in PRESET_GAMES:
            btn = Button(
                text=name,
                size_hint_y=None,
                height=dp(52),
                font_size=dp(14),
                color=(0.784, 0.820, 1, 0.85),
                background_normal='',
                background_color=(0, 0, 0, 0),
            )
            from kivy.graphics import Color, RoundedRectangle
            with btn.canvas.before:
                Color(0.051, 0.063, 0.149, 1)
                rr = RoundedRectangle(pos=btn.pos, size=btn.size, radius=[dp(12)])
            btn.bind(pos=lambda inst, v, r=rr: setattr(r, 'pos', inst.pos))
            btn.bind(size=lambda inst, v, r=rr: setattr(r, 'size', inst.size))
            _name, _gid = name, gid
            btn.bind(on_release=lambda b, n=_name, g=_gid: self._pick_preset(n, g))
            gl.add_widget(btn)

    def _pick_preset(self, name, gid):
        self._selected_game = (name, gid)
        self.ids.inp_custom.text = ''
        self._update_current_label()

    def set_method(self, method):
        self._method = method
        self._update_method_ui()

    def _update_method_ui(self):
        from kivy.graphics import Color, RoundedRectangle
        all_btn = self.ids.btn_method_all
        each_btn = self.ids.btn_method_each
        for btn, active in [(all_btn, self._method == 'all'), (each_btn, self._method == 'each')]:
            btn.canvas.before.clear()
            with btn.canvas.before:
                if active:
                    Color(0, 0.8, 0.8, 1)
                    btn.color = (0.031, 0.043, 0.078, 1)
                else:
                    Color(0.176, 0.180, 0.314, 0.25)
                    btn.color = (0.627, 0.667, 0.871, 0.7)
                RoundedRectangle(pos=btn.pos, size=btn.size, radius=[dp(22)])
            btn.bind(pos=lambda inst, v: self._update_method_ui())

    def _update_current_label(self):
        name, gid = self._selected_game
        if name:
            self.ids.lbl_current.text = f'Selected: {name}'
        else:
            self.ids.lbl_current.text = 'Selected: —'

    def save(self):
        from config_manager import config, save_config
        custom = self.ids.inp_custom.text.strip()
        if custom:
            name = 'Custom'
            gid = custom
        else:
            name, gid = self._selected_game

        config['game_method'] = self._method
        config['game_name'] = name
        config['game_id'] = gid
        save_config()
        self.go_back()

    def go_back(self):
        self.manager.current = 'main'
