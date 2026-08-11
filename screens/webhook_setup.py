from kivy.uix.screenmanager import Screen
from kivy.lang import Builder
from kivy.metrics import dp

from core.webhook_sender import webhook_sender

KV = '''
<WebhookSetupScreen>:
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
                text: 'Discord Webhook'
                font_size: dp(17)
                bold: True
                color: 0.957, 0.973, 1, 1
                halign: 'left'
                text_size: self.size

        ScrollView:
            do_scroll_x: False
            BoxLayout:
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                padding: dp(16), dp(14)
                spacing: dp(16)

                # URL
                BoxLayout:
                    orientation: 'vertical'
                    size_hint_y: None
                    height: dp(88)
                    spacing: dp(8)

                    Label:
                        text: 'WEBHOOK URL'
                        size_hint_y: None
                        height: dp(20)
                        font_size: dp(10)
                        bold: True
                        color: 0.627, 0.667, 0.871, 0.5
                        halign: 'left'
                        text_size: self.size
                        letter_spacing: dp(1.2)

                    TextInput:
                        id: inp_url
                        hint_text: 'https://discord.com/api/webhooks/...'
                        size_hint_y: None
                        height: dp(52)
                        font_size: dp(13)
                        multiline: False
                        background_color: 0.039, 0.047, 0.118, 1
                        foreground_color: 0.957, 0.973, 1, 1
                        cursor_color: 0, 0.8, 0.8, 1
                        hint_text_color: 0.49, 0.52, 0.72, 0.4
                        padding: dp(12), dp(14)

                # Interval
                BoxLayout:
                    orientation: 'vertical'
                    size_hint_y: None
                    height: dp(88)
                    spacing: dp(8)

                    Label:
                        text: 'SEND INTERVAL (SECONDS)'
                        size_hint_y: None
                        height: dp(20)
                        font_size: dp(10)
                        bold: True
                        color: 0.627, 0.667, 0.871, 0.5
                        halign: 'left'
                        text_size: self.size
                        letter_spacing: dp(1.2)

                    TextInput:
                        id: inp_interval
                        text: '60'
                        size_hint_y: None
                        height: dp(52)
                        font_size: dp(14)
                        multiline: False
                        background_color: 0.039, 0.047, 0.118, 1
                        foreground_color: 0.957, 0.973, 1, 1
                        cursor_color: 0, 0.8, 0.8, 1
                        padding: dp(12), dp(14)

                # Enable toggle row
                BoxLayout:
                    size_hint_y: None
                    height: dp(58)
                    spacing: dp(10)
                    padding: dp(16), dp(8)
                    canvas.before:
                        Color:
                            rgba: 0.051, 0.063, 0.149, 1
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [dp(14)]

                    Label:
                        text: 'Enable Webhook'
                        color: 0.784, 0.820, 1, 0.85
                        font_size: dp(14)
                        halign: 'left'
                        text_size: self.size
                        valign: 'middle'

                    Button:
                        id: btn_toggle
                        text: 'OFF'
                        size_hint_x: None
                        width: dp(72)
                        font_size: dp(13)
                        bold: True
                        background_normal: ''
                        background_color: 0, 0, 0, 0
                        on_release: root.toggle_enable()

                # Info
                Label:
                    text: 'Sends device stats and a screenshot to Discord at the configured interval while rejoin is active.'
                    size_hint_y: None
                    height: self.texture_size[1]
                    color: 0.627, 0.667, 0.871, 0.55
                    font_size: dp(12)
                    halign: 'left'
                    text_size: self.width, None
                    line_height: 1.4

                # Status
                Label:
                    id: lbl_status
                    text: ''
                    size_hint_y: None
                    height: dp(28)
                    color: 0, 0.8, 0.8, 1
                    font_size: dp(13)
                    halign: 'left'
                    text_size: self.size
                    valign: 'middle'

                # Buttons
                BoxLayout:
                    size_hint_y: None
                    height: dp(52)
                    spacing: dp(10)

                    Button:
                        text: 'Test Now'
                        font_size: dp(14)
                        bold: True
                        color: 0, 0.8, 0.8, 1
                        background_normal: ''
                        background_color: 0, 0, 0, 0
                        canvas.before:
                            Color:
                                rgba: 0, 0.8, 0.8, 0.12
                            RoundedRectangle:
                                pos: self.pos
                                size: self.size
                                radius: [dp(26)]
                        on_release: root.test_webhook()

                    Button:
                        text: 'Save'
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
                                radius: [dp(26)]
                        on_release: root.save()
'''

Builder.load_string(KV)


class WebhookSetupScreen(Screen):
    _enabled = False

    def on_enter(self):
        from config_manager import config
        self.ids.inp_url.text = config.get('webhook_url', '')
        self.ids.inp_interval.text = str(config.get('webhook_interval', 60))
        self._enabled = config.get('webhook_enabled', False)
        self._update_toggle()

    def toggle_enable(self):
        self._enabled = not self._enabled
        self._update_toggle()

    def _update_toggle(self):
        from kivy.graphics import Color, RoundedRectangle
        btn = self.ids.btn_toggle
        btn.canvas.before.clear()
        with btn.canvas.before:
            if self._enabled:
                Color(0, 0.8, 0.8, 1)
                btn.text = 'ON'
                btn.color = (0.031, 0.043, 0.078, 1)
            else:
                Color(0.176, 0.188, 0.380, 0.6)
                btn.text = 'OFF'
                btn.color = (0.49, 0.52, 0.72, 0.6)
            RoundedRectangle(pos=btn.pos, size=btn.size, radius=[dp(18)])

    def test_webhook(self):
        url = self.ids.inp_url.text.strip()
        if not url:
            self.ids.lbl_status.text = 'Enter a webhook URL first.'
            return
        self.ids.lbl_status.text = 'Sending test...'
        import time
        webhook_sender._start_time = time.time()
        webhook_sender.send_now(url)
        self.ids.lbl_status.text = 'Test sent! Check your Discord.'

    def save(self):
        from config_manager import config, save_config
        config['webhook_url'] = self.ids.inp_url.text.strip()
        config['webhook_enabled'] = self._enabled
        try:
            config['webhook_interval'] = int(self.ids.inp_interval.text.strip())
        except ValueError:
            config['webhook_interval'] = 60
        save_config()
        self.ids.lbl_status.text = 'Saved!'
        self.go_back()

    def go_back(self):
        self.manager.current = 'main'
