import sys
from cliff.app import App
from cliff.commandmanager import CommandManager

class GearBox(App):
    def __init__(self):
        super(GearBox, self).__init__(description="TurboGears2 Gearbox toolset", 
                                      version='2.3',
                                      command_manager=CommandManager('gearbox.commands'))



def main():
    args = sys.argv[1:]
    gearbox = GearBox()
    return gearbox.run(args)

