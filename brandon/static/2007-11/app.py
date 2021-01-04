# -*- coding: utf-8 -*-

import grok

# These two simple classes know their name, and know a list
# of corresponding objects they are associated with.

class Character(grok.Model):
    def __init__(self, name):
        self.name = name
        self.battles = []

class Battle(grok.Model):
    def __init__(self, name, *characters):
        self.name = name
        self.characters = list(characters)
        for c in characters:
            c.battles.append(self)

# The Application creates some characters and battles
# manually, to make this example as simple as possible.

class MyApp(grok.Application, grok.Container):
    def __init__(self):
        super(MyApp, self).__init__()

        self['gandalf'] = gandalf = Character('Gandalf')
        self['aragorn'] = aragorn = Character('Aragorn')
        self['theoden'] = theoden = Character(u'Théoden')
        self['merry'] = merry = Character('Merry')
        self['pippin'] = pippin = Character('Pippin')

        self['helms_deep'] = Battle("Siege of Helm's Deep",
                                    aragorn, theoden)
        self['isengard'] = Battle("Destruction of Isengard",
                                  merry, pippin)
        self['helms_charge'] = Battle("Charge from Helm's Deep",
                                      gandalf, aragorn, theoden)
        self['minas_tirith'] = Battle("Siege of Minas Tirith",
                                      gandalf, pippin)
        self['pelennor'] = Battle("Battle of the Pelennor",
                                  aragorn, theoden, merry)

class Index(grok.View):
    grok.context(MyApp)

class Contents(grok.View):
    grok.context(MyApp)

class CharacterIndex(grok.View):
    grok.context(Character)
    grok.name('index')

class BattleIndex(grok.View):
    grok.context(Battle)
    grok.name('index')
