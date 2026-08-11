from kivy.uix.screenmanager import Screen
from kivy.lang import Builder
from kivy.metrics import dp

KV = '''
<StatusPill@BoxLayout>:
    label_text: ''
    dot_color: 0, 0.8, 0.8, 1
    size_hint: None, None
    size: dp(90), dp(26)
    spacing: dp(5)
    padding: dp(10), dp(5)
    canvas.before:
        Color:
            rgba: 0, 0.8, 0.8, 0.12
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(13)]
        Color:
            rgba: 0, 0.8, 0.8, 0.35
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(13)]
            # border only via line below
    Widget:
        size_hint: None, None
        size: dp(7), dp(7)
        pos_hint: {'center_y': 0.5}
        canvas:
            Color:
                rgba: root.dot_color
            Ellipse:
                pos: self.pos
                size: self.size
    Label:
        text: root.label_text
        font_size: dp(10)
        bold: True
        color: 0, 0.8, 0.8, 1

<SetupCard@BoxLayout>:
    title_text: ''
    sub_text: ''
    icon_text: ''
    orientation: 'horizontal'
    size_hint_y: None
    height: dp(70)
    spacing: dp(14)
    padding: dp(16), dp(12)
    canvas.before:
        Color:
            rgba: 0.051, 0.063, 0.149, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(14)]
        Color:
            rgba: 0.176, 0.180, 0.314, 0.3
        Line:
            rounded_rectangle: self.x, self.y, self.width, self.height, dp(14)
            width: dp(1)
    BoxLayout:
        size_hint: None, None
        size: dp(42), dp(42)
        pos_hint: {'center_y': 0.5}
        canvas.before:
            Color:
                rgba: 0.486, 0.431, 0.878, 0.2
            RoundedRectangle:
                pos: self.pos
                size: self.size
                radius: [dp(12)]
        Label:
            text: root.icon_text
            font_size: dp(20)
    BoxLayout:
        orientation: 'vertical'
        spacing: dp(2)
        Label:
            text: root.title_text
            font_size: dp(14)
            bold: True
            color: 0.957, 0.973, 1, 1
            halign: 'left'
            text_size: self.width, None
        Label:
            text: root.sub_text
            font_size: dp(11)
            color: 0.627, 0.667, 0.871, 0.8
            halign: 'left'
            text_size: self.width, None

<HomeTab>:
    canvas.before:
        Color:
            rgba: 0.031, 0.043, 0.078, 1
        Rectangle:
            pos: self.pos
            size: self.size

    ScrollView:
        do_scroll_x: False
        BoxLayout:
            orientation: 'vertical'
            size_hint_y: None
            height: self.minimum_height
            padding: dp(18), dp(16), dp(18), dp(20)
            spacing: dp(16)

            # Header
            BoxLayout:
                size_hint_y: None
                height: dp(50)
                Label:
                    text: 'Reiya'
                    font_size: dp(22)
                    bold: True
                    color: 0.957, 0.973, 1, 1
                    halign: 'left'
                    text_size: self.size
                Label:
                    text: 'v1.0'
                    font_size: dp(13)
                    color: 0.627, 0.667, 0.871, 0.5
                    halign: 'right'
                    text_size: self.size

            # Status pills
            BoxLayout:
                size_hint_y: None
                height: dp(30)
                spacing: dp(8)
                StatusPill:
                    label_text: 'ACTIVE'
                StatusPill:
                    label_text: 'ROBLOX'
                    dot_color: 0.486, 0.431, 0.878, 1
                Widget:

            # Current game card
            BoxLayout:
                id: game_card
                orientation: 'vertical'
                size_hint_y: None
                height: dp(90)
                padding: dp(16), dp(14)
                spacing: dp(6)
                canvas.before:
                    Color:
                        rgba: 0.063, 0.043, 0.188, 1
                    RoundedRectangle:
                        pos: self.pos
                        size: self.size
                        radius: [dp(16)]
                    Color:
                        rgba: 0.486, 0.431, 0.878, 0.35
                    Line:
                        rounded_rectangle: self.x, self.y, self.width, self.height, dp(16)
                        width: dp(1)
                Label:
                    text: 'Current Game'
                    font_size: dp(10)
                    bold: True
                    color: 0.486, 0.431, 0.878, 1
                    halign: 'left'
                    text_size: self.size
                Label:
                    id: current_game_label
                    text: 'Not configured'
                    font_size: dp(17)
                    bold: True
                    color: 0.957, 0.973, 1, 0.9
                    halign: 'left'
                    text_size: self.width, None

            # Setup cards
            Label:
                text: 'Quick Setup'
                font_size: dp(12)
                bold: True
                color: 0.627, 0.667, 0.871, 0.55
                halign: 'left'
                text_size: self.size
                size_hint_y: None
                height: dp(20)
                letter_spacing: dp(1)

            SetupCard:
                title_text: 'Package Selection'
                sub_text: 'Choose Roblox APKs to manage'
                icon_text: '📦'
                on_touch_down:
                    if self.collide_point(*args[1].pos): root.go_setup()

            SetupCard:
                title_text: 'Game / Server'
                sub_text: 'Pick game or private server'
                icon_text: '🎮'
                on_touch_down:
                    if self.collide_point(*args[1].pos): root.go_setup()

            SetupCard:
                title_text: 'Discord Webhook'
                sub_text: 'Send live device updates'
                icon_text: '🔔'
                on_touch_down:
                    if self.collide_point(*args[1].pos): root.go_setup()

            Widget:
                size_hint_y: None
                height: dp(12)

            # Start Rejoin button
            Button:
                text: 'Start Auto Rejoin'
                size_hint_y: None
                height: dp(56)
                font_size: dp(16)
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
                        radius: [dp(28)]
                on_release: root.start_rejoin()
'''

Builder.load_string(KV)


class HomeTab(Screen):
    def on_enter(self):
        from config_manager import config
        game_name = config.get('game_name', '')
        label = self.ids.current_game_label
        label.text = game_name if game_name else 'Not configured'

    def go_setup(self):
        from screens.main_screen import MainScreen
        for screen in self.manager.parent.parent.screens if hasattr(self.manager, 'parent') else []:
            if isinstance(screen, MainScreen):
                screen.switch_tab('setup')
                return

    def start_rejoin(self):
        ms = self._get_main_screen()
        if ms:
            ms.switch_tab('rejoin')
        from core.rejoin_loop import rejoin_loop
        from config_manager import config
        if not rejoin_loop.running:
            rejoin_loop.start(config)

    def _get_main_screen(self):
        try:
            return self.manager.parent.parent
        except Exception:
            return None
