import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, FadeTransition
from kivy.core.window import Window

Window.clearcolor = (0.031, 0.043, 0.078, 1)

from config_manager import load_config
from screens.welcome       import WelcomeScreen,       MoonWidget
from screens.main_screen   import MainScreen
from screens.setup_package import SetupPackageScreen
from screens.setup_game    import SetupGameScreen
from screens.webhook_setup import WebhookSetupScreen
from screens.autoexecute   import AutoexecuteScreen
from screens.config_tool   import ConfigToolScreen


class ReiyaApp(App):
    title = 'Reiya Account Manager'

    def build(self):
        load_config()

        sm = ScreenManager(transition=FadeTransition(duration=0.25))
        sm.add_widget(WelcomeScreen(name='welcome'))
        sm.add_widget(MainScreen(name='main'))
        sm.add_widget(SetupPackageScreen(name='setup_package'))
        sm.add_widget(SetupGameScreen(name='setup_game'))
        sm.add_widget(WebhookSetupScreen(name='webhook_setup'))
        sm.add_widget(AutoexecuteScreen(name='autoexecute'))
        sm.add_widget(ConfigToolScreen(name='config_tool'))

        sm.current = 'welcome'
        return sm

    def on_stop(self):
        from config_manager import save_config
        save_config()
        from core.rejoin_loop import rejoin_loop
        from core.webhook_sender import webhook_sender
        rejoin_loop.stop()
        webhook_sender.stop()


if __name__ == '__main__':
    ReiyaApp().run()
