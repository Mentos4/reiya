from kivy.uix.screenmanager import Screen
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.metrics import dp

KV = '''
<RejoinTab>:
    canvas.before:
        Color:
            rgba: 0.031, 0.043, 0.078, 1
        Rectangle:
            pos: self.pos
            size: self.size

    BoxLayout:
        orientation: 'vertical'
        padding: dp(18), dp(16), dp(18), dp(14)
        spacing: dp(14)

        # Header
        Label:
            text: 'Auto Rejoin'
            font_size: dp(20)
            bold: True
            color: 0.957, 0.973, 1, 1
            halign: 'left'
            text_size: self.size
            size_hint_y: None
            height: dp(40)

        # Status card
        BoxLayout:
            orientation: 'horizontal'
            size_hint_y: None
            height: dp(72)
            spacing: dp(12)
            padding: dp(16), dp(14)
            canvas.before:
                Color:
                    rgba: 0.051, 0.063, 0.149, 1
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [dp(14)]
            BoxLayout:
                orientation: 'vertical'
                Label:
                    text: 'STATUS'
                    font_size: dp(9)
                    bold: True
                    color: 0.627, 0.667, 0.871, 0.5
                    halign: 'left'
                    text_size: self.size
                    letter_spacing: dp(1.2)
                Label:
                    id: status_label
                    text: 'Idle'
                    font_size: dp(16)
                    bold: True
                    color: 0.957, 0.973, 1, 0.9
                    halign: 'left'
                    text_size: self.size
            BoxLayout:
                orientation: 'vertical'
                Label:
                    text: 'GAME'
                    font_size: dp(9)
                    bold: True
                    color: 0.627, 0.667, 0.871, 0.5
                    halign: 'left'
                    text_size: self.size
                    letter_spacing: dp(1.2)
                Label:
                    id: game_label
                    text: '—'
                    font_size: dp(13)
                    color: 0.957, 0.973, 1, 0.7
                    halign: 'left'
                    text_size: self.size

        # Toggle button
        Button:
            id: toggle_btn
            text: 'Start'
            size_hint_y: None
            height: dp(50)
            font_size: dp(15)
            bold: True
            color: 0.957, 0.973, 1, 1
            background_normal: ''
            background_color: 0, 0, 0, 0
            canvas.before:
                Color:
                    rgba: 0.298, 0.251, 0.753, 1
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [dp(25)]
            on_release: root.toggle_rejoin()

        # Log area header
        BoxLayout:
            size_hint_y: None
            height: dp(28)
            Label:
                text: 'LOG'
                font_size: dp(10)
                bold: True
                color: 0.627, 0.667, 0.871, 0.5
                halign: 'left'
                text_size: self.size
                letter_spacing: dp(1.5)
            Button:
                text: 'Clear'
                size_hint_x: None
                width: dp(50)
                font_size: dp(11)
                color: 0.627, 0.667, 0.871, 0.7
                background_normal: ''
                background_color: 0, 0, 0, 0
                on_release: root.clear_log()

        # Log scroll
        ScrollView:
            do_scroll_x: False
            canvas.before:
                Color:
                    rgba: 0.039, 0.047, 0.118, 1
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [dp(12)]
            BoxLayout:
                id: log_box
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                padding: dp(12), dp(10)
                spacing: dp(4)

        # Webhook status (compact)
        BoxLayout:
            size_hint_y: None
            height: dp(36)
            spacing: dp(8)
            Label:
                text: 'Webhook'
                font_size: dp(12)
                color: 0.627, 0.667, 0.871, 0.6
                size_hint_x: None
                width: dp(70)
                halign: 'left'
                text_size: self.size
            Label:
                id: webhook_status
                text: 'Off'
                font_size: dp(12)
                color: 0.49, 0.52, 0.72, 0.55
                halign: 'left'
                text_size: self.size
'''

Builder.load_string(KV)


class RejoinTab(Screen):
    def on_enter(self):
        from config_manager import config
        self.ids.game_label.text = config.get('game_name') or '—'
        self._update_btn_text()
        Clock.schedule_interval(self._tick, 2)

    def on_leave(self):
        Clock.unschedule(self._tick)

    def _tick(self, dt):
        from core.rejoin_loop import rejoin_loop
        self._update_btn_text()
        wh_enabled = False
        try:
            from config_manager import config
            wh_enabled = config.get('webhook_enabled', False)
        except Exception:
            pass
        self.ids.webhook_status.text = 'Active' if wh_enabled else 'Off'
        self.ids.webhook_status.color = (0, 0.8, 0.8, 1) if wh_enabled else (0.49, 0.52, 0.72, 0.55)

    def _update_btn_text(self):
        from core.rejoin_loop import rejoin_loop
        running = rejoin_loop.running
        self.ids.toggle_btn.text = 'Stop' if running else 'Start'
        self.ids.status_label.text = 'Running' if running else 'Idle'
        self.ids.status_label.color = (0, 0.8, 0.8, 1) if running else (0.957, 0.973, 1, 0.5)

    def toggle_rejoin(self):
        from core.rejoin_loop import rejoin_loop
        from config_manager import config
        if rejoin_loop.running:
            rejoin_loop.stop()
            self.add_log('Rejoin stopped.')
        else:
            rejoin_loop.set_log_callback(self.add_log)
            rejoin_loop.start(config)
            self.add_log('Rejoin started.')
        self._update_btn_text()

    def add_log(self, message):
        from kivy.uix.label import Label
        import time
        t = time.strftime('%H:%M:%S')
        entry = Label(
            text=f'[color=#4d5587][{t}][/color]  {message}',
            markup=True,
            font_size=dp(12),
            color=(0.78, 0.82, 1, 0.85),
            halign='left',
            size_hint_y=None,
            height=dp(22),
        )
        entry.bind(width=lambda inst, w: setattr(inst, 'text_size', (w, None)))
        box = self.ids.log_box
        box.add_widget(entry)
        if len(box.children) > 60:
            box.remove_widget(box.children[-1])

    def clear_log(self):
        self.ids.log_box.clear_widgets()
