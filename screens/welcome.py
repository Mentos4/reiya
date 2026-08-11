from kivy.uix.screenmanager import Screen
from kivy.uix.widget import Widget
from kivy.lang import Builder
from kivy.animation import Animation
from kivy.properties import NumericProperty
from kivy.clock import Clock
from kivy.metrics import dp

KV = '''
<MoonWidget>:
    canvas.before:
        PushMatrix
        Scale:
            origin: self.center
            x: root.breath_scale
            y: root.breath_scale
    canvas:
        # Outer halo
        Color:
            rgba: 0.55, 0.67, 1, 0.15
        Ellipse:
            pos: self.x - dp(30), self.y - dp(30)
            size: self.width + dp(60), self.height + dp(60)
        # Inner halo
        Color:
            rgba: 0.55, 0.67, 1, 0.25
        Ellipse:
            pos: self.x - dp(14), self.y - dp(14)
            size: self.width + dp(28), self.height + dp(28)
        # Moon body
        Color:
            rgba: 0.957, 0.973, 1, 1
        Ellipse:
            pos: self.pos
            size: self.size
        # Shadow for depth
        Color:
            rgba: 0.235, 0.314, 0.627, 0.18
        Ellipse:
            pos: self.x + self.width * 0.25, self.y
            size: self.width * 0.75, self.height * 0.75
        # Left eye
        Color:
            rgba: 0.353, 0.416, 0.604, 1
        Line:
            bezier:
                self.center_x - dp(22), self.center_y + dp(8),
                self.center_x - dp(15), self.center_y + dp(16),
                self.center_x - dp(8),  self.center_y + dp(8)
            width: dp(2.2)
        # Right eye
        Line:
            bezier:
                self.center_x + dp(8),  self.center_y + dp(8),
                self.center_x + dp(15), self.center_y + dp(16),
                self.center_x + dp(22), self.center_y + dp(8)
            width: dp(2.2)
    canvas.after:
        PopMatrix

<WelcomeScreen>:
    canvas.before:
        Color:
            rgba: 0.031, 0.043, 0.078, 1
        Rectangle:
            pos: self.pos
            size: self.size
        # Bottom gradient purple
        Color:
            rgba: 0.051, 0.039, 0.157, 0.9
        Rectangle:
            pos: self.x, self.y
            size: self.width, self.height * 0.48
        # Mid gradient indigo
        Color:
            rgba: 0.102, 0.063, 0.251, 0.6
        Rectangle:
            pos: self.x, self.y + self.height * 0.15
            size: self.width, self.height * 0.25

    BoxLayout:
        orientation: 'vertical'
        padding: 0

        # Top — wordmark
        Label:
            text: 'REIYA ACCOUNT MANAGER'
            size_hint_y: None
            height: dp(48)
            font_size: dp(10)
            bold: True
            color: 0.627, 0.725, 1, 0.45
            letter_spacing: dp(2)

        # Moon area
        RelativeLayout:
            size_hint_y: 0.5

            MoonWidget:
                id: moon
                size_hint: None, None
                size: dp(155), dp(155)
                pos_hint: {'center_x': 0.5, 'center_y': 0.58}

        # Content
        BoxLayout:
            orientation: 'vertical'
            size_hint_y: 0.5
            padding: dp(28), dp(10), dp(28), dp(38)
            spacing: dp(10)

            # Badge
            BoxLayout:
                size_hint_y: None
                height: dp(28)
                spacing: dp(6)

                Widget:
                    size_hint_x: None
                    width: dp(6)
                    canvas:
                        Color:
                            rgba: 0, 0.8, 0.8, 1
                        Ellipse:
                            pos: self.x, self.center_y - dp(3)
                            size: dp(6), dp(6)

                Label:
                    text: 'AUTO REJOIN'
                    font_size: dp(10)
                    bold: True
                    color: 0, 0.8, 0.8, 1
                    letter_spacing: dp(1.5)
                    halign: 'left'
                    text_size: self.size
                    valign: 'middle'

                Widget:

            # Headline
            Label:
                text: "Always in game,\nnever left behind."
                font_size: dp(26)
                bold: True
                color: 1, 1, 1, 1
                halign: 'left'
                text_size: self.width, None
                size_hint_y: None
                height: self.texture_size[1]

            # Sub
            Label:
                text: "Reiya keeps all your Roblox sessions running\naround the clock — set it once, stay in game."
                font_size: dp(13)
                color: 0.784, 0.824, 1, 0.8
                halign: 'left'
                text_size: self.width, None
                size_hint_y: None
                height: self.texture_size[1]
                line_height: 1.4

            Widget:
                size_hint_y: None
                height: dp(4)

            # Button
            Button:
                text: 'Get started'
                size_hint_y: None
                height: dp(52)
                font_size: dp(16)
                bold: True
                color: 0.239, 0.180, 0.541, 1
                background_normal: ''
                background_color: 0, 0, 0, 0
                canvas.before:
                    Color:
                        rgba: 0.95, 0.93, 1, 1
                    RoundedRectangle:
                        pos: self.pos
                        size: self.size
                        radius: [dp(26)]
                on_release: root.get_started()
'''

Builder.load_string(KV)


class MoonWidget(Widget):
    breath_scale = NumericProperty(1.0)

    def on_parent(self, *args):
        Clock.schedule_once(self._start_breathe, 1.1)

    def _start_breathe(self, dt):
        anim = (
            Animation(breath_scale=1.052, duration=2.1, t='in_out_sine') +
            Animation(breath_scale=1.0,   duration=2.1, t='in_out_sine')
        )
        anim.repeat = True
        anim.start(self)


class WelcomeScreen(Screen):
    def get_started(self):
        self.manager.current = 'main'
