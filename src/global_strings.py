
# region SettingsFrom
class _RuBaseStringsSF:
    """
    Базовые строки модуля LoginForm
    """
    """
        Базовые строки модуля LoginForm
        """
    name: str = "Настройки"
    settings_label: str = "Настройки программы"


# endregion


class String:
    """
    mf - MainForm
    sf - SettingsForm
    """
    lang = 'ru'
    sf: _RuBaseStringsSF = _RuBaseStringsSF()

    def __init__(self, lang: str = 'ru'):
        self.change_lang(lang)

    def change_lang(self, lang):
        self.lang = lang
        pass
