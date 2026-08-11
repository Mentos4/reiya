from kivy.uix.screenmanager import Screen
from kivy.lang import Builder
from kivy.app import App

KV = '''
<MainMenuScreen>:
    canvas.before:
        Color:
            rgba: 0.04, 0.04, 0.04, 1
        Rectangle:
            pos: self.pos
            size: self.size

    BoxLayout:
        orientation: 'vertical'
        spacing: 0

        # ── Header ──
        BoxLayout:
            size_hint_y: None
            height: dp(56)
            padding: dp(16), dp(8)
            canvas.before:
                Color:
                    rgba: 0.07, 0.07, 0.07, 1
                Rectangle:
                    pos: self.pos
                    size: self.size

            Label:
                text: 'ROBLOX MANAGER'
                font_size: dp(20)
                bold: True
                color: 0, 0.85, 0.85, 1
                halign: 'center'

        # ── Status bar ──
        GridLayout:
            cols: 2
            size_hint_y: None
            height: dp(72)
            padding: dp(12), dp(6)
            spacing: dp(4)
            canvas.before:
                Color:
                    rgba: 0.06, 0.06, 0.06, 1
                Rectangle:
                    pos: self.pos
                    size: self.size

            Label:
                id: lbl_webhook
                text: 'WEBHOOK: Disable'
                color: 1, 0.3, 0.3, 1
                font_size: dp(12)
                halign: 'left'
                text_size: self.size
                valign: 'middle'

            Label:
                id: lbl_autoblock
                text: 'AUTO BLOCK: Disable'
                color: 1, 0.3, 0.3, 1
                font_size: dp(12)
                halign: 'left'
                text_size: self.size
                valign: 'middle'

            Label:
                id: lbl_sorttab
                text: 'AUTO SORT TAB: Disable'
                color: 1, 0.3, 0.3, 1
                font_size: dp(12)
                halign: 'left'
                text_size: self.size
                valign: 'middle'

            Label:
                id: lbl_changeacc
                text: 'AUTO CHANGE ACC: Disable'
                color: 1, 0.3, 0.3, 1
                font_size: dp(12)
                halign: 'left'
                text_size: self.size
                valign: 'middle'

        # Divider
        Widget:
            size_hint_y: None
            height: dp(1)
            canvas:
                Color:
                    rgba: 0.2, 0.2, 0.2, 1
                Rectangle:
                    pos: self.pos
                    size: self.size

        # ── Menu list ──
        ScrollView:
            do_scroll_x: False
            GridLayout:
                cols: 1
                size_hint_y: None
                height: self.minimum_height
                padding: dp(10), dp(10)
                spacing: dp(8)

                RMButton:
                    text: '1   |  Start Auto Rejoin'
                    on_release: root.go_to('auto_rejoin')

                RMButton:
                    text: '2   |  Setup Package'
                    on_release: root.go_to('setup_package')

                RMButton:
                    text: '4   |  Setup Game & Private Server'
                    on_release: root.go_to('setup_game')

                RMButton:
                    text: '5   |  Setup Webhook'
                    on_release: root.go_to('webhook_setup')

                RMButton:
                    text: '6   |  Setup Autoexecute'
                    on_release: root.go_to('autoexecute')

                RMButton:
                    text: '10  |  Set Config Tool'
                    on_release: root.go_to('config_tool')

                Widget:
                    size_hint_y: None
                    height: dp(20)

<RMButton@Button>:
    size_hint_y: None
    height: dp(58)
    font_size: dp(15)
    color: 0, 0.85, 0.85, 1
    halign: 'left'
    text_size: self.width - dp(20), None
    padding_x: dp(16)
    background_normal: ''
    background_color: 0, 0, 0, 0
    canvas.before:
        Color:
            rgba: (0.14, 0.14, 0.14, 1) if self.state == 'normal' else (0.18, 0.18, 0.18, 1)
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(6)]
        Color:
            rgba: 0, 0.6, 0.6, 0.5
        Line:
            rounded_rectangle: [self.x, self.y, self.width, self.height, dp(6)]
            width: 1
'''

Builder.load_string(KV)


class MainMenuScreen(Screen):
    def on_enter(self):
        self._refresh_status()

    def _refresh_status(self):
        app = App.get_running_app()
        if not app:
            return
        cfg = app.config_data

        def label(key, name):
            enabled = cfg.get(key, False)
            text = f'{name}: {"Enable" if enabled else "Disable"}'
            color = (0, 0.9, 0.4, 1) if enabled else (1, 0.3, 0.3, 1)
            return text, color

        t, c = label('webhook_enabled', 'WEBHOOK')
        self.ids.lbl_webhook.text = t
        self.ids.lbl_webhook.color = c

        t, c = label('auto_block', 'AUTO BLOCK')
        self.ids.lbl_autoblock.text = t
        self.ids.lbl_autoblock.color = c

        t, c = label('auto_sort_tab', 'AUTO SORT TAB')
        self.ids.lbl_sorttab.text = t
        self.ids.lbl_sorttab.color = c

        t, c = label('auto_change_acc', 'AUTO CHANGE ACC')
        self.ids.lbl_changeacc.text = t
        self.ids.lbl_changeacc.color = c

    def go_to(self, screen):
        self.manager.current = screen
