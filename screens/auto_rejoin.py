from kivy.uix.screenmanager import Screen
from kivy.lang import Builder
from kivy.app import App
from kivy.clock import Clock
from kivy.utils import platform

from core.rejoin_loop import rejoin_loop
from core.webhook_sender import webhook_sender

KV = '''
<AutoRejoinScreen>:
    canvas.before:
        Color:
            rgba: 0.04, 0.04, 0.04, 1
        Rectangle:
            pos: self.pos
            size: self.size

    BoxLayout:
        orientation: 'vertical'
        spacing: 0

        # Header
        BoxLayout:
            size_hint_y: None
            height: dp(52)
            padding: dp(8), dp(6)
            spacing: dp(8)
            canvas.before:
                Color:
                    rgba: 0.07, 0.07, 0.07, 1
                Rectangle:
                    pos: self.pos
                    size: self.size

            Button:
                text: '< Back'
                size_hint_x: None
                width: dp(70)
                font_size: dp(13)
                color: 0, 0.85, 0.85, 1
                background_normal: ''
                background_color: 0.12, 0.12, 0.12, 1
                on_release: root.go_back()

            Label:
                text: 'AUTO REJOIN'
                font_size: dp(18)
                bold: True
                color: 0, 0.85, 0.85, 1

        # Info cards
        GridLayout:
            cols: 2
            size_hint_y: None
            height: dp(80)
            padding: dp(10), dp(6)
            spacing: dp(8)

            InfoCard:
                id: card_game
                title: 'Game'
                value: 'Not set'

            InfoCard:
                id: card_packages
                title: 'Packages'
                value: '0 selected'

        # Interval input
        BoxLayout:
            size_hint_y: None
            height: dp(56)
            padding: dp(10), dp(6)
            spacing: dp(8)

            Label:
                text: 'Rejoin interval (min):'
                color: 0.7, 0.7, 0.7, 1
                font_size: dp(13)
                size_hint_x: 0.5
                halign: 'right'
                text_size: self.size
                valign: 'middle'

            TextInput:
                id: inp_interval
                text: '999999999999999999999'
                font_size: dp(13)
                multiline: False
                background_color: 0.1, 0.1, 0.1, 1
                foreground_color: 1, 1, 1, 1
                cursor_color: 0, 0.85, 0.85, 1
                size_hint_x: 0.5

        # Start / Stop button
        BoxLayout:
            size_hint_y: None
            height: dp(56)
            padding: dp(10), dp(4)

            Button:
                id: btn_start
                text: 'START AUTO REJOIN'
                font_size: dp(15)
                bold: True
                color: 0.04, 0.04, 0.04, 1
                background_normal: ''
                background_color: 0, 0.85, 0.85, 1
                on_release: root.toggle_rejoin()

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

        # Log output
        Label:
            text: 'Activity Log'
            size_hint_y: None
            height: dp(28)
            color: 0.5, 0.5, 0.5, 1
            font_size: dp(12)
            halign: 'left'
            text_size: self.width - dp(20), None
            padding_x: dp(12)

        ScrollView:
            id: scroll_log
            do_scroll_x: False
            Label:
                id: lbl_log
                text: 'Waiting to start...'
                font_size: dp(12)
                color: 0.75, 0.75, 0.75, 1
                size_hint_y: None
                height: self.texture_size[1]
                text_size: self.width, None
                padding: dp(12), dp(6)
                halign: 'left'
                valign: 'top'

<InfoCard@BoxLayout>:
    title: ''
    value: ''
    orientation: 'vertical'
    padding: dp(8)
    canvas.before:
        Color:
            rgba: 0.1, 0.1, 0.1, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(6)]
    Label:
        text: root.title
        font_size: dp(11)
        color: 0.5, 0.5, 0.5, 1
        halign: 'center'
        text_size: self.size
        valign: 'middle'
    Label:
        text: root.value
        font_size: dp(13)
        bold: True
        color: 0, 0.85, 0.85, 1
        halign: 'center'
        text_size: self.size
        valign: 'middle'
'''

Builder.load_string(KV)


class AutoRejoinScreen(Screen):
    _clock = None

    def on_enter(self):
        self._refresh_info()
        rejoin_loop.set_log_callback(self._on_log)
        self._sync_button()

    def _refresh_info(self):
        app = App.get_running_app()
        cfg = app.config_data
        game_name = cfg.get('game_name', 'Not set')
        packages = cfg.get('selected_packages', [])
        interval = cfg.get('rejoin_interval', 999999999999999999999)

        self.ids.card_game.value = game_name
        self.ids.card_packages.value = f'{len(packages)} selected'
        self.ids.inp_interval.text = str(interval)

    def _on_log(self, line):
        def _update(dt):
            lbl = self.ids.lbl_log
            lbl.text = lbl.text + '\n' + line
            # Auto scroll
            self.ids.scroll_log.scroll_y = 0
        Clock.schedule_once(_update)

    def _sync_button(self):
        btn = self.ids.btn_start
        if rejoin_loop.is_running():
            btn.text = 'STOP AUTO REJOIN'
            btn.background_color = (0.9, 0.2, 0.2, 1)
        else:
            btn.text = 'START AUTO REJOIN'
            btn.background_color = (0, 0.85, 0.85, 1)
            btn.color = (0.04, 0.04, 0.04, 1)

    def toggle_rejoin(self):
        app = App.get_running_app()
        cfg = app.config_data

        if rejoin_loop.is_running():
            rejoin_loop.stop()
            webhook_sender.stop()
            self._sync_button()
            return

        packages = cfg.get('selected_packages', [])
        if not packages:
            self._on_log('ERROR: No packages selected. Go to Setup Package first.')
            return

        game_id = cfg.get('game_id', '')
        if not game_id and cfg.get('game_method', 'all') == 'all':
            self._on_log('ERROR: No game set. Go to Setup Game & Private Server first.')
            return

        # Save interval
        try:
            interval = int(self.ids.inp_interval.text.strip())
            cfg['rejoin_interval'] = interval
        except ValueError:
            pass

        self.ids.lbl_log.text = ''

        ok = rejoin_loop.start(packages, cfg)
        if ok:
            # Start webhook if enabled
            if cfg.get('webhook_enabled') and cfg.get('webhook_url'):
                webhook_sender.start(
                    cfg['webhook_url'],
                    cfg.get('webhook_interval', 60),
                    get_status_cb=rejoin_loop.get_status
                )
        self._sync_button()

    def go_back(self):
        self.manager.current = 'main_menu'
