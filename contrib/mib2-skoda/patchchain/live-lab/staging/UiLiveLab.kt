package io.github.numberonebot.chairplay.ui

/** Small extension point for the existing authenticated localhost JSON API. */
fun interface UiLiveLab {
    fun request(body: Map<*, *>): Map<String, Any?>
}
