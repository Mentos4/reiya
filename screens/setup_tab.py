from kivy.uix.screenmanager import Screen
from kivy.lang import Builder
from kivy.metrics import dp

KV = '''
<SetupTile@BoxLayout>:
    title_text: ''
    sub_text: ''
    icon_text: ''
    target_screen: ''
    orientation: 'vertical'
    size_hint_y: None
    height: dp(110)
    spacing: dp(8)
    padding: dp(16)
    canvas.before:
        Color:
            rgba: 0.051, 0.063, 0.149, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(16)]
        Color:
            rgba: 0.176, 0.180, 0.314, 0.3
        Line:
            rounded_rectangle: self.x, self.y, self.width, self.height, dp(16)
            width: dp(1)
    Label:
        text: root.icon_text
        font_size: dp(26)
        size_hint_y: None
        height: dp(34)
        halign: 'left'
        text_size: self.size
    Label:
        text: root.title_text
        font_size: dp(14)
        bold: True
        color: 0.957, 0.973, 1, 0.95
        halign: 'left'
        text_size: self.size
        size_hint_y: None
        height: dp(22)
    Label:
        text: root.sub_text
        font_size: dp(11)
        color: 0.627, 0.667, 0.871, 0.65
        halign: 'left'
        text_size: self.width, None
        size_hint_y: None
        height: self.texture_size[1]

<SetupTab>:
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

        Label:
            text: 'Setup'
            font_size: dp(20)
            bold: True
            color: 0.957, 0.973, 1, 1
            halign: 'left'
            text_size: self.size
            size_hint_y: None
            height: dp(40)

        Label:
            text: 'Configure packages, games, webhooks\nand autoexecute files.'
            font_size: dp(13)
            color: 0.627, 0.667, 0.871, 0.7
            halign: 'left'
            text_size: self.width, None
            size_hint_y: None
            height: self.texture_size[1]
            line_height: 1.4

        # Grid of tiles
        GridLayout:
            cols: 2
            spacing: dp(10)
            size_hint_y: None
            height: self.minimum_height

            SetupTile:
                title_text: 'Package\nSelection'
                sub_text: 'Roblox APKs'
                icon_text: '📦'
                target_screen: 'setup_package'
                on_touch_down:
                    if self.collide_point(*args[1].pos): root.open('setup_package')

            SetupTile:
                title_text: 'Game &\nServer'
                sub_text: 'Game setup'
                icon_text: '🎮'
                target_screen: 'setup_game'
                on_touch_down:
                    if self.collide_point(*args[1].pos): root.open('setup_game')

            SetupTile:
                title_text: 'Discord\nWebhook'
                sub_text: 'Device alerts'
                icon_text: '🔔'
                target_screen: 'webhook_setup'
                on_touch_down:
                    if self.collide_point(*args[1].pos): root.open('webhook_setup')

            SetupTile:
                title_text: 'Autoexecute\nFiles'
                sub_text: 'Delta scripts'
                icon_text: '📝'
                target_screen: 'autoexecute'
                on_touch_down:
                    if self.collide_point(*args[1].pos): root.open('autoexecute')

        Widget:
'''

Builder.load_string(KV)


class SetupTab(Screen):
    def open(self, screen_name):
        from kivy.app import App
        sm = App.get_running_app().root
        sm.current = screen_name
