import threading

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.metrics import dp

from core.app_launcher import get_installed_packages, get_roblox_packages

KV = '''
<SetupPackageScreen>:
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
                text: 'Package Selection'
                font_size: dp(17)
                bold: True
                color: 0.957, 0.973, 1, 1
                halign: 'left'
                text_size: self.size

        # Count badge
        BoxLayout:
            size_hint_y: None
            height: dp(40)
            padding: dp(16), dp(6)
            Label:
                id: lbl_count
                text: '0 selected'
                font_size: dp(13)
                color: 0, 0.8, 0.8, 1
                halign: 'left'
                text_size: self.size

        # Package list
        ScrollView:
            do_scroll_x: False
            BoxLayout:
                id: pkg_list
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                padding: dp(14), dp(4)
                spacing: dp(7)

        # Bottom buttons
        BoxLayout:
            size_hint_y: None
            height: dp(62)
            padding: dp(14), dp(8)
            spacing: dp(10)
            canvas.before:
                Color:
                    rgba: 0.027, 0.035, 0.102, 1
                Rectangle:
                    pos: self.pos
                    size: self.size

            Button:
                text: 'Auto Roblox'
                font_size: dp(13)
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
                        radius: [dp(22)]
                on_release: root.auto_select()

            Button:
                text: 'Refresh'
                font_size: dp(13)
                color: 0.627, 0.667, 0.871, 0.7
                background_normal: ''
                background_color: 0, 0, 0, 0
                canvas.before:
                    Color:
                        rgba: 0.176, 0.180, 0.314, 0.25
                    RoundedRectangle:
                        pos: self.pos
                        size: self.size
                        radius: [dp(22)]
                on_release: root.load_packages()

            Button:
                text: 'Save'
                font_size: dp(13)
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
                        radius: [dp(22)]
                on_release: root.save_and_back()
'''

Builder.load_string(KV)


class PackageRow(BoxLayout):
    def __init__(self, package, selected, on_toggle, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'horizontal'
        self.size_hint_y = None
        self.height = dp(56)
        self.padding = (dp(14), dp(8))
        self.spacing = dp(10)
        self.package = package
        self._selected = selected
        self._on_toggle = on_toggle

        with self.canvas.before:
            from kivy.graphics import Color, RoundedRectangle
            self._bg_color = Color(0.051, 0.063, 0.149, 1)
            self._bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(12)])
        self.bind(pos=self._update_bg, size=self._update_bg)

        self.lbl = Label(
            text=package,
            font_size=dp(12),
            color=(0.784, 0.820, 1, 0.85),
            halign='left',
            text_size=(None, None),
        )
        self.lbl.bind(size=lambda *a: setattr(self.lbl, 'text_size', (self.lbl.width, None)))

        self.btn = Button(
            text='✓ ON' if selected else 'OFF',
            size_hint_x=None,
            width=dp(72),
            font_size=dp(12),
            bold=True,
            background_normal='',
            background_color=(0, 0, 0, 0),
        )
        self._update_btn()
        self.btn.bind(on_release=self._toggle)

        self.add_widget(self.lbl)
        self.add_widget(self.btn)

    def _update_bg(self, *a):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size

    def _toggle(self, *a):
        self._selected = not self._selected
        self._update_btn()
        self._on_toggle(self.package, self._selected)

    def _update_btn(self):
        if self._selected:
            self.btn.text = '✓ ON'
            self.btn.color = (0, 0.8, 0.8, 1)
        else:
            self.btn.text = 'OFF'
            self.btn.color = (0.49, 0.52, 0.72, 0.55)

    def set_selected(self, val):
        self._selected = val
        self._update_btn()


class SetupPackageScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._all_packages = []
        self._selected = set()
        self._rows = {}

    def on_enter(self):
        from config_manager import config
        self._selected = set(config.get('selected_packages', []))
        self.load_packages()

    def load_packages(self):
        self.ids.pkg_list.clear_widgets()
        self._rows = {}
        self.ids.lbl_count.text = 'Loading...'

        def _fetch():
            pkgs = get_installed_packages()
            Clock.schedule_once(lambda dt: self._populate(pkgs))

        threading.Thread(target=_fetch, daemon=True).start()

    def _populate(self, packages):
        self._all_packages = packages
        self.ids.pkg_list.clear_widgets()
        self._rows = {}
        for pkg in packages:
            row = PackageRow(
                package=pkg,
                selected=(pkg in self._selected),
                on_toggle=self._on_toggle,
            )
            self._rows[pkg] = row
            self.ids.pkg_list.add_widget(row)
        self._update_count()

    def _on_toggle(self, pkg, selected):
        if selected:
            self._selected.add(pkg)
        else:
            self._selected.discard(pkg)
        self._update_count()

    def _update_count(self):
        n = len(self._selected)
        self.ids.lbl_count.text = f'{n} package{"s" if n != 1 else ""} selected'

    def auto_select(self):
        roblox_pkgs = get_roblox_packages()
        for pkg in roblox_pkgs:
            self._selected.add(pkg)
        for pkg, row in self._rows.items():
            row.set_selected(pkg in self._selected)
        self._update_count()

    def save_and_back(self):
        from config_manager import config, save_config
        config['selected_packages'] = list(self._selected)
        save_config()
        self.go_back()

    def go_back(self):
        self.manager.current = 'main'
