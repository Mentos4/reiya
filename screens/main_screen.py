from kivy.uix.screenmanager import Screen, ScreenManager, SlideTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import StringProperty, BooleanProperty

KV = '''
<NavButton>:
    orientation: 'vertical'
    spacing: dp(2)
    padding: dp(6), dp(6)
    canvas.before:
        Color:
            rgba: (0, 0.8, 0.8, 1) if root.active else (0, 0, 0, 0)
        Rectangle:
            pos: self.x, self.top - dp(2)
            size: self.width, dp(2)
    Label:
        text: root.icon
        font_size: dp(22)
        size_hint_y: None
        height: dp(28)
        color: (0.96, 0.97, 1, 1) if root.active else (0.49, 0.52, 0.72, 0.55)
    Label:
        text: root.label_text
        font_size: dp(10)
        color: (0, 0.8, 0.8, 1) if root.active else (0.49, 0.52, 0.72, 0.55)
        size_hint_y: None
        height: dp(14)

<BottomNav>:
    size_hint_y: None
    height: dp(64)
    spacing: 0
    canvas.before:
        Color:
            rgba: 0.027, 0.035, 0.102, 1
        Rectangle:
            pos: self.pos
            size: self.size
        Color:
            rgba: 0.176, 0.180, 0.314, 0.35
        Rectangle:
            pos: self.x, self.top - dp(1)
            size: self.width, dp(1)

<MainScreen>:
    canvas.before:
        Color:
            rgba: 0.031, 0.043, 0.078, 1
        Rectangle:
            pos: self.pos
            size: self.size
    BoxLayout:
        orientation: 'vertical'
        ScreenManager:
            id: tab_manager
        BottomNav:
            id: bottom_nav
'''

Builder.load_string(KV)


class NavButton(BoxLayout):
    icon = StringProperty('')
    label_text = StringProperty('')
    active = BooleanProperty(False)

    def __init__(self, icon, label, tab_name, main_screen, **kwargs):
        self.icon = icon
        self.label_text = label
        self.tab_name = tab_name
        self.main_screen = main_screen
        super().__init__(**kwargs)
        self.bind(on_touch_down=self._on_touch)

    def _on_touch(self, instance, touch):
        if self.collide_point(*touch.pos):
            self.main_screen.switch_tab(self.tab_name)
            return True


class BottomNav(BoxLayout):
    pass


class MainScreen(Screen):
    _tabs_loaded = False

    def on_enter(self):
        if self._tabs_loaded:
            return
        self._tabs_loaded = True

        from screens.home_tab   import HomeTab
        from screens.rejoin_tab import RejoinTab
        from screens.setup_tab  import SetupTab
        from screens.config_tab import ConfigTab

        tabs = self.ids.tab_manager
        tabs.add_widget(HomeTab(name='home'))
        tabs.add_widget(RejoinTab(name='rejoin'))
        tabs.add_widget(SetupTab(name='setup'))
        tabs.add_widget(ConfigTab(name='config'))

        nav = self.ids.bottom_nav
        items = [
            ('⌂', 'Home',   'home'),
            ('↺', 'Rejoin', 'rejoin'),
            ('⚙', 'Setup',  'setup'),
            ('☰', 'Config', 'config'),
        ]
        for icon, label, tab in items:
            btn = NavButton(icon=icon, label=label, tab_name=tab, main_screen=self)
            nav.add_widget(btn)

        self.switch_tab('home')

    def switch_tab(self, tab_name):
        tabs = self.ids.tab_manager
        tabs.transition = SlideTransition(duration=0.15)
        tabs.current = tab_name
        for btn in self.ids.bottom_nav.children:
            btn.active = (btn.tab_name == tab_name)
