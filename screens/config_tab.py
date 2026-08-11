from kivy.uix.screenmanager import Screen
from kivy.lang import Builder
from kivy.metrics import dp

KV = '''
<CfgRow@BoxLayout>:
    setting_key: ''
    label_text: ''
    is_toggle: False
    orientation: 'horizontal'
    size_hint_y: None
    height: dp(54)
    spacing: dp(10)
    padding: dp(14), dp(8)
    canvas.before:
        Color:
            rgba: 0.051, 0.063, 0.149, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(12)]
    Label:
        text: root.label_text
        font_size: dp(13)
        color: 0.784, 0.820, 1, 0.85
        halign: 'left'
        text_size: self.size

<ConfigTab>:
    canvas.before:
        Color:
            rgba: 0.031, 0.043, 0.078, 1
        Rectangle:
            pos: self.pos
            size: self.size

    BoxLayout:
        orientation: 'vertical'
        padding: dp(18), dp(16), dp(18), dp(14)
        spacing: dp(10)

        # Header
        Label:
            text: 'Config'
            font_size: dp(20)
            bold: True
            color: 0.957, 0.973, 1, 1
            halign: 'left'
            text_size: self.size
            size_hint_y: None
            height: dp(40)

        ScrollView:
            do_scroll_x: False
            BoxLayout:
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                spacing: dp(6)
                id: config_list

        Widget:
            size_hint_y: None
            height: dp(10)

        Button:
            text: 'Open Full Config'
            size_hint_y: None
            height: dp(50)
            font_size: dp(14)
            bold: True
            color: 0.957, 0.973, 1, 1
            background_normal: ''
            background_color: 0, 0, 0, 0
            canvas.before:
                Color:
                    rgba: 0.176, 0.188, 0.380, 1
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [dp(25)]
                Color:
                    rgba: 0.176, 0.180, 0.314, 0.5
                Line:
                    rounded_rectangle: self.x, self.y, self.width, self.height, dp(25)
                    width: dp(1)
            on_release: root.open_full_config()
'''

Builder.load_string(KV)

SUMMARY_SETTINGS = [
    ('retry_count',      'Max Retries'),
    ('retry_delay',      'Retry Delay (s)'),
    ('rejoin_cooldown',  'Rejoin Cooldown (s)'),
    ('launch_wait',      'Launch Wait (s)'),
    ('check_interval',   'Check Interval (s)'),
    ('webhook_interval', 'Webhook Interval (s)'),
    ('sequential_join',  'Sequential Join'),
    ('clear_cache',      'Clear Cache on Rejoin'),
    ('webhook_enabled',  'Webhook Enabled'),
]


class ConfigTab(Screen):
    def on_enter(self):
        from kivy.uix.label import Label
        from config_manager import config
        box = self.ids.config_list
        box.clear_widgets()
        for key, label in SUMMARY_SETTINGS:
            val = config.get(key, '—')
            row = self._make_row(label, val)
            box.add_widget(row)

    def _make_row(self, label, value):
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.label import Label
        row = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(50),
            padding=[dp(14), dp(8)],
            spacing=dp(10),
        )
        with row.canvas.before:
            from kivy.graphics import Color, RoundedRectangle
            Color(0.051, 0.063, 0.149, 1)
            RoundedRectangle(pos=row.pos, size=row.size, radius=[dp(12)])
        row.bind(pos=lambda inst, v: self._update_bg(inst),
                 size=lambda inst, v: self._update_bg(inst))

        lbl = Label(
            text=label,
            font_size=dp(13),
            color=(0.784, 0.820, 1, 0.85),
            halign='left',
            text_size=(None, None),
        )
        lbl.bind(size=lambda inst, v: setattr(inst, 'text_size', (inst.width, None)))
        val_lbl = Label(
            text=str(value),
            font_size=dp(13),
            bold=True,
            color=(0, 0.8, 0.8, 1) if isinstance(value, bool) and value else (0.957, 0.973, 1, 0.7),
            halign='right',
            size_hint_x=None,
            width=dp(80),
        )
        val_lbl.bind(size=lambda inst, v: setattr(inst, 'text_size', (inst.width, None)))
        row.add_widget(lbl)
        row.add_widget(val_lbl)
        return row

    def _update_bg(self, inst):
        from kivy.graphics import Color, RoundedRectangle
        inst.canvas.before.clear()
        with inst.canvas.before:
            Color(0.051, 0.063, 0.149, 1)
            RoundedRectangle(pos=inst.pos, size=inst.size, radius=[dp(12)])

    def open_full_config(self):
        from kivy.app import App
        App.get_running_app().root.current = 'config_tool'
