package io.github.numberonebot.chairplay.config

import java.util.Properties

/** Independent desktop window preferences; none changes the iPhone's session. */
class WindowOnTop(settings: Properties) {
    val main = settings.booleanSetting("window.always.on.top", false)
    val altscreen = settings.booleanSetting("altscreen.always.on.top", false)

    /** window.settings.separate: the settings in a window of their own, CarPlay's window always showing CarPlay. */
    val separateSettings = settings.booleanSetting("window.settings.separate", false)
}
