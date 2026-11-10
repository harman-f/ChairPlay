package io.github.numberonebot.chairplay

import io.github.numberonebot.chairplay.media.VideoWindow
import io.github.numberonebot.chairplay.ui.ChairPlayUi

/**
 * The settings in a window of their own (window.settings.separate): it shows the page, the car's button on CarPlay's
 * home screen brings it to the front, and taskkill asking it to close ends the app as CarPlay's window does, where its
 * own close button only hides it.
 */
internal fun settingsWindow(settings: VideoWindow, ui: ChairPlayUi, main: VideoWindow): VideoWindow {
    settings.child = ui.settingsView
    ui.onShowSettings = { settings.setShown(true) }
    settings.onOutsideClose = { main.close() }
    return settings
}
