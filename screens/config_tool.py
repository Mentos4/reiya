from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.lang import Builder
from kivy.metrics import dp

KV = '''
<ConfigToolScreen>:
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
                text: 'Config Tool'
                font_size: dp(17)
                bold: True
                color: 0.957, 0.973, 1, 1
                halign: 'left'
                text_size: self.size

        ScrollView:
            do_scroll_x: False
            BoxLayout:
                id: cfg_grid
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                padding: dp(14), dp(10)
                spacing: dp(7)

        # Save button
        BoxLayout:
            size_hint_y: None
            height: dp(62)
            padding: dp(14), dp(8)

            Button:
                id: btn_save
                text: 'Save All Settings'
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

SETTINGS = [
    ('rejoin_interval',        'Rejoin interval',           'int',  'minutes'),
    ('offline_wait',           'Offline wait',              'int',  'seconds'),
    ('retry_count',            'Max retries',               'int',  ''),
    ('retry_delay',            'Retry delay',               'int',  'seconds'),
    ('check_interval',         'Check interval',            'int',  'seconds'),
    ('launch_wait',            'Launch wait',               'int',  'seconds'),
    ('rejoin_cooldown',        'Rejoin cooldown',           'int',  'seconds'),
    ('webhook_interval',       'Webhook interval',          'int',  'seconds'),
    ('trigger',                'Trigger',                   'str',  ''),
    ('autoexecute_path',       'Autoexecute path',          'str',  ''),
    ('sequential_join',        'Sequential join',           'bool', ''),
    ('clear_cache',            'Clear cache on rejoin',     'bool', ''),
    ('webhook_enabled',        'Webhook enabled',           'bool', ''),
]


class SettingRow(BoxLayout):
    def __init__(self, idx, key, label, stype, note, value, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'horizontal'
        self.size_hint_y = None
        self.height = dp(58)
        self.padding = (dp(14), dp(10))
        self.spacing = dp(10)
        self.key = key
        self.stype = stype
        self._bool_val = bool(value) if stype == 'bool' else False

        with self.canvas.before:
            from kivy.graphics import Color, RoundedRectangle
            Color(0.051, 0.063, 0.149, 1)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(12)])
        self.bind(pos=self._upd, size=self._upd)

        name_lbl = Label(
            text=label,
            font_size=dp(13),
            color=(0.784, 0.820, 1, 0.85),
            halign='left',
            text_size=(None, None),
        )
        name_lbl.bind(size=lambda w, *a: setattr(w, 'text_size', (w.width, None)))

        if stype == 'bool':
            self._toggle_btn = Button(
                size_hint_x=None,
                width=dp(68),
                font_size=dp(12),
                bold=True,
                background_normal='',
                background_color=(0, 0, 0, 0),
            )
            self._set_bool_ui()
            self._toggle_btn.bind(on_release=self._toggle_bool)
            self.add_widget(name_lbl)
            self.add_widget(self._toggle_btn)
            self._inp = None
        else:
            self._inp = TextInput(
                text=str(value),
                size_hint_x=None,
                width=dp(120),
                height=dp(38),
                size_hint_y=None,
                font_size=dp(13),
                multiline=False,
                background_color=(0.027, 0.031, 0.086, 1),
                foreground_color=(0.957, 0.973, 1, 1),
                cursor_color=(0, 0.8, 0.8, 1),
                padding=[dp(8), dp(10)],
            )
            self.add_widget(name_lbl)
            self.add_widget(self._inp)
            self._toggle_btn = None

    def _upd(self, *a):
        self._bg.pos = self.pos
        self._bg.size = self.size

    def _set_bool_ui(self):
        from kivy.graphics import Color, RoundedRectangle
        btn = self._toggle_btn
        btn.canvas.before.clear()
        with btn.canvas.before:
            if self._bool_val:
                Color(0, 0.8, 0.8, 1)
                btn.text = 'ON'
                btn.color = (0.031, 0.043, 0.078, 1)
            else:
                Color(0.176, 0.188, 0.380, 0.5)
                btn.text = 'OFF'
                btn.color = (0.49, 0.52, 0.72, 0.6)
            RoundedRectangle(pos=btn.pos, size=btn.size, radius=[dp(18)])

    def _toggle_bool(self, *a):
        self._bool_val = not self._bool_val
        self._set_bool_ui()

    def get_value(self):
        if self.stype == 'bool':
            return self._bool_val
        raw = self._inp.text.strip() if self._inp else ''
        if self.stype == 'int':
            try:
                return int(raw)
            except ValueError:
                return 0
        return raw


class ConfigToolScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._rows = []

    def on_enter(self):
        from config_manager import config
        grid = self.ids.cfg_grid
        grid.clear_widgets()
        self._rows = []

        for i, (key, label, stype, note) in enumerate(SETTINGS, 1):
            value = config.get(key, '')
            row = SettingRow(i, key, label, stype, note, value)
            self._rows.append(row)
            grid.add_widget(row)

    def save(self):
        from config_manager import config, save_config
        from kivy.clock import Clock
        for row in self._rows:
            config[row.key] = row.get_value()
        save_config()
        self.ids.btn_save.text = 'Saved!'
        Clock.schedule_once(
            lambda dt: setattr(self.ids.btn_save, 'text', 'Save All Settings'), 1.5
        )
        self.go_back()

    def go_back(self):
        self.manager.current = 'main'
