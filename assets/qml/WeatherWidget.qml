import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ClassWidgets.Theme as CWTheme
import RinUI
import "components"

CWTheme.Widget {
    id: root
    clip: true

    padding: miniMode ? 16 : 24
    readonly property int screenWidth: miniMode ? 132 : 212
    implicitWidth: miniMode ? 164 : 260

    readonly property var cfg: backend && backend.settings ? backend.settings : ({})
    readonly property var payload: backend && backend.weather ? backend.weather : ({})
    readonly property var current: payload && payload.current ? payload.current : ({})
    readonly property var today: payload && payload.today ? payload.today : ({})
    readonly property var alerts: backend ? backend.alerts : []
    readonly property var hourly: payload && payload.hourly ? payload.hourly : []
    readonly property var precipitation: payload && payload.precipitation ? payload.precipitation : ({})
    readonly property var alertSlides: {
        var result = []
        var list = backend && backend.slides ? backend.slides : []
        for (var i = 0; i < list.length; i++) {
            if (list[i] && list[i].kind === "alert")
                result.push(list[i])
        }
        return result
    }
    readonly property var activeAlert: {
        var list = alerts || []
        if (list.length === 0)
            return ({})
        var index = Math.max(0, Math.min(Number(shown.index) || 0, list.length - 1))
        return list[index] || ({})
    }
    readonly property var activeSlide: {
        if (shown.kind === "alert") {
            var index = Math.max(0, Math.min(Number(shown.index) || 0, alertSlides.length - 1))
            return alertSlides.length > 0 ? alertSlides[index] : activeAlert
        }
        if (shown.kind === "precip")
            return precipitation
        if (shown.kind === "hourly" && hourly.length > 0)
            return hourly[Math.max(0, Math.min(Number(shown.index) || 0, hourly.length - 1))]
        if (shown.kind === "tomorrow")
            return tomorrow
        return current
    }
    readonly property bool isDaytimeNow: {
        var tick = clockTick
        var rise = today && today.sunrise ? String(today.sunrise) : ""
        var set = today && today.sunset ? String(today.sunset) : ""
        var riseMatch = /^(\d{1,2}):(\d{2})$/.exec(rise)
        var setMatch = /^(\d{1,2}):(\d{2})$/.exec(set)
        if (!riseMatch || !setMatch)
            return current.is_day !== false
        var now = new Date()
        var minutes = now.getHours() * 60 + now.getMinutes()
        var start = Number(riseMatch[1]) * 60 + Number(riseMatch[2])
        var end = Number(setMatch[1]) * 60 + Number(setMatch[2])
        return start <= end ? (minutes >= start && minutes < end)
                            : (minutes >= start || minutes < end)
    }
    readonly property string mainIcon: {
        var icon = current && current.icon ? String(current.icon) : "unknown"
        if (!today || !today.sunrise || !today.sunset)
            return icon
        var base = icon.replace(/_day$/, "").replace(/_night$/, "")
        return base !== icon ? base + (isDaytimeNow ? "_day" : "_night") : icon
    }
    readonly property bool available: backend
        ? (backend.hasWeather === true
            || (payload && payload.available === true)
            || (current && current.temp !== undefined && current.temp !== null))
        : false
    readonly property bool animationsEnabled: cfg.animation_enabled !== false
    readonly property string contentMode: cfg.widget_content_mode || "current"
    readonly property bool carousel: cfg.widget_carousel !== false
    readonly property bool showHourly: cfg.widget_show_hourly !== false
    readonly property bool showPrecip: cfg.widget_show_precip !== false
    readonly property bool showSummary: cfg.widget_show_summary !== false
    readonly property bool blankWhenHidden: cfg.widget_blank_when_hidden !== false
    readonly property int mainSeconds: Math.max(
        3, Number(cfg.widget_main_seconds || 8))
    readonly property int alertSeconds: Math.max(
        1, Number(cfg.cycle_interval || 3))
    readonly property bool tomorrowEnabled: cfg.widget_tomorrow_enabled !== false
    readonly property string tomorrowStart: cfg.widget_tomorrow_start || "20:00"
    readonly property string tomorrowEnd: cfg.widget_tomorrow_end || "23:59"
    readonly property var tomorrow: {
        var list = payload && payload.daily ? payload.daily : []
        for (var i = 0; i < list.length; i++) {
            if (list[i] && list[i].is_today === false)
                return list[i]
        }
        return list.length > 1 ? list[1] : ({})
    }
    property int clockTick: 0
    readonly property bool tomorrowReady: {
        var tick = clockTick
        var startMatch = /^(\d{1,2}):(\d{2})$/.exec(tomorrowStart)
        var endMatch = /^(\d{1,2}):(\d{2})$/.exec(tomorrowEnd)
        if (!startMatch || !endMatch || !tomorrowEnabled || !tomorrow || !tomorrow.text)
            return false
        var now = new Date()
        var current = now.getHours() * 60 + now.getMinutes()
        var start = Number(startMatch[1]) * 60 + Number(startMatch[2])
        var end = Number(endMatch[1]) * 60 + Number(endMatch[2])
        return start <= end ? (current >= start && current < end)
                            : (current >= start || current < end)
    }

    property var screens: []
    property string screensKey: ""
    property int screenIndex: 0
    property var shown: ({ kind: "unavailable" })
    property var pending: ({})
    property bool swapping: false
    property bool blanked: false

    readonly property int iconSize: miniMode ? 24 : 32
    readonly property int titlePx: miniMode ? 13 : 15
    readonly property int bodyPx: miniMode ? 10 : 11
    readonly property int temperaturePx: miniMode ? 26 : 34
    function headerSuffix() {
        var parts = []
        if (cfg.show_location !== false && backend && backend.locationText)
            parts.push(backend.locationText)
        if (cfg.show_provider === true && backend && backend.weather
                && backend.weather.provider && backend.weather.provider.name)
            parts.push(backend.weather.provider.name)
        return parts.length > 0 ? " · " + parts.join(" · ") : ""
    }

    readonly property string baseTitle: {
        var value = ""
        switch (shown.kind) {
        case "alert":
            value = root.activeAlert.level_text || "天气预警"
            break
        case "tomorrow":
            value = "明日天气"
            break
        case "hourly":
            value = "未来 3 小时"
            break
        case "precip":
            value = root.precipitation.title || "降水预报"
            break
        case "unavailable":
            value = "天气"
            break
        default:
            value = root.current.text || "天气"
        }
        return value + root.headerSuffix()
    }
    // The base Subtitle does not elide, so the visible header text is replaced
    // by a clipped pixel-marquee. This avoids per-character re-layout jitter.
    readonly property bool titleOverflow: titleText.contentWidth > titleMarqueeBox.width
    text: "\u200B"
    Item {
        id: titleMarqueeBox
        x: 0
        y: -28
        width: Math.max(70, root.width - root.padding * 2 - 30)
        height: 22
        clip: true
        z: 100
        visible: !root.blanked && !root.miniMode

        Text {
            id: titleText
            x: 0
            text: root.baseTitle
            color: Theme.isDark() ? "#FFFFFF" : "#17171A"
            opacity: 0.6
            font.family: (typeof Configs !== "undefined" && Configs.data.preferences.font)
                ? Configs.data.preferences.font : "Microsoft YaHei"
            font.pixelSize: 16
            font.weight: (typeof Configs !== "undefined"
                ? (Configs.data.preferences.font_weight || 600) : 600)
            wrapMode: Text.NoWrap
        }
    }

    SequentialAnimation {
        id: titleSlide
        running: root.titleOverflow && !root.blanked && !root.miniMode
        loops: Animation.Infinite
        NumberAnimation {
            target: titleText
            property: "x"
            from: 0
            to: -Math.max(0, titleText.contentWidth - titleMarqueeBox.width)
            duration: Math.max(2500, titleText.contentWidth * 22)
            easing.type: Easing.Linear
        }
        PauseAnimation { duration: 700 }
        NumberAnimation {
            target: titleText
            property: "x"
            to: 0
            duration: 350
            easing.type: Easing.OutCubic
        }
        onRunningChanged: if (!running) titleText.x = 0
    }
    onBaseTitleChanged: {
        titleText.x = 0
        if (titleSlide.running)
            titleSlide.restart()
    }

    actions: RowLayout {
        spacing: 6

        Text {
            visible: !root.blanked && root.shown.kind === "alert" && root.alerts.length > 1
            text: (root.shown.index + 1) + "/" + root.alerts.length
            font.pixelSize: root.bodyPx
            opacity: 0.65
            color: Theme.isDark() ? "#FFFFFF" : "#17171A"
        }
    }

    function hourlyIcon(item) {
        var icon = item && item.icon ? String(item.icon) : "unknown"
        var base = icon.replace(/_day$/, "").replace(/_night$/, "")
        if (base === icon || !today || !today.sunrise || !today.sunset)
            return icon
        var riseMatch = /^(\d{1,2}):(\d{2})$/.exec(String(today.sunrise))
        var setMatch = /^(\d{1,2}):(\d{2})$/.exec(String(today.sunset))
        var timeMatch = /(\d{1,2}):(\d{2})/.exec(String((item && (item.time || item.hour)) || ""))
        if (!riseMatch || !setMatch || !timeMatch)
            return icon
        var minutes = Number(timeMatch[1]) * 60 + Number(timeMatch[2])
        var start = Number(riseMatch[1]) * 60 + Number(riseMatch[2])
        var end = Number(setMatch[1]) * 60 + Number(setMatch[2])
        var daytime = start <= end ? (minutes >= start && minutes < end)
                                   : (minutes >= start || minutes < end)
        return base + (daytime ? "_day" : "_night")
    }

    function syncBlankState() {
        if (backend && backend.setWidgetBlanked) {
            backend.setWidgetBlanked(root.blanked && root.blankWhenHidden)
        }
    }

    function buildScreens() {
        var list = []
        if (blanked && blankWhenHidden) {
            list = [{ kind: "blank" }]
        } else if (!available) {
            list = [{ kind: "unavailable" }]
        } else if (miniMode) {
            list = [{ kind: "main" }]
        } else if (carousel) {
            // 轮播开启时，主屏、小时预报、降水和预警都在同一个队列中。
            list.push({ kind: "main" })
            if (tomorrowReady)
                list.push({ kind: "tomorrow" })
            if (showHourly && hourly.length >= 3)
                list.push({ kind: "hourly" })
            if (showPrecip && precipitation.active)
                list.push({ kind: "precip" })
            for (var i = 0; i < alerts.length; i++)
                list.push({ kind: "alert", index: i })
        } else if (alerts.length > 0) {
            // 关闭轮播后只保留主屏；预警仍然逐条显示。
            for (var j = 0; j < alerts.length; j++)
                list.push({ kind: "alert", index: j })
        } else {
            list.push({ kind: "main" })
        }
        var key = JSON.stringify(list)
        if (key === screensKey)
            return
        screensKey = key
        screens = list
        screenIndex = 0
        var force = (blanked && blankWhenHidden) || shown.kind === "blank"
        var animate = animationsEnabled && shown.kind !== "unavailable" && !force
        showScreen(list[0], animate)
        if (list.length > 1)
            rotator.restart()
        else
            rotator.stop()
    }

    function showScreen(next, animate) {
        if (!next)
            return
        if (!animate || !animationsEnabled) {
            swapAnim.stop()
            swapping = false
            pending = next
            shown = next
            contentBox.opacity = 1
            return
        }
        if (swapping) {
            pending = next
            return
        }
        pending = next
        swapping = true
        swapAnim.restart()
    }

    function nextScreen() {
        if (screens.length <= 1)
            return
        screenIndex = (screenIndex + 1) % screens.length
        showScreen(screens[screenIndex], animationsEnabled)
    }

    SequentialAnimation {
        id: swapAnim
        NumberAnimation {
            target: contentBox
            property: "opacity"
            from: 1
            to: 0
            duration: 320
            easing.type: Easing.InOutQuad
        }
        ScriptAction {
            script: {
                root.shown = root.pending
                contentBox.opacity = 0
            }
        }
        NumberAnimation {
            target: contentBox
            property: "opacity"
            from: 0
            to: 1
            duration: 480
            easing.type: Easing.OutCubic
        }
        ScriptAction {
            script: root.swapping = false
        }
        onFinished: {
            if (root.pending && (root.pending.kind !== root.shown.kind
                    || root.pending.index !== root.shown.index)) {
                root.shown = root.pending
            }
            contentBox.opacity = 1
            root.swapping = false
        }
    }

    Timer {
        id: rotator
        running: root.screens.length > 1 && !root.editMode && !root.blanked
        repeat: true
        interval: root.shown.kind === "alert"
            ? root.alertSeconds * 1000
            : root.mainSeconds * 1000
        onTriggered: root.nextScreen()
        onIntervalChanged: if (running) restart()
    }

    Timer {
        id: stateWatchdog
        interval: 1000
        repeat: true
        running: true
        onTriggered: {
            if (root.editMode || root.blanked)
                return
            if (root.available && (root.shown.kind === "unavailable" || root.shown.kind === "blank")) {
                root.buildScreens()
            } else if (!root.available && root.shown.kind !== "unavailable") {
                root.buildScreens()
            }
        }
    }

    Timer {
        interval: 30000
        running: true
        repeat: true
        onTriggered: root.clockTick += 1
    }

    Timer {
        id: hideTimer
        interval: 5000
        running: root.hide
        repeat: false
        onTriggered: {
            if (root.hide && root.blankWhenHidden)
                root.blanked = true
        }
    }

    onHideChanged: {
        if (!root.hide) {
            root.blanked = false
        } else if (!root.blankWhenHidden) {
            root.blanked = false
        }
    }

    onBlankedChanged: {
        syncBlankState()
        buildScreens()
    }
    onBlankWhenHiddenChanged: {
        if (!root.blankWhenHidden) {
            root.blanked = false
        } else if (root.hide) {
            hideTimer.restart()
        }
        syncBlankState()
    }

    Connections {
        target: root.backend
        enabled: root.backend !== null && root.backend !== undefined

        function onWeatherChanged() { root.buildScreens() }
        function onAlertsChanged() { root.buildScreens() }
        function onConfigChanged() {
            root.syncBlankState()
            root.buildScreens()
        }
    }

    onAvailableChanged: buildScreens()
    onAlertsChanged: buildScreens()
    onHourlyChanged: buildScreens()
    onPayloadChanged: buildScreens()
    onBackendChanged: buildScreens()
    onMiniModeChanged: buildScreens()
    onTomorrowReadyChanged: buildScreens()
    Component.onCompleted: {
        syncBlankState()
        buildScreens()
    }

    TapHandler {
        acceptedButtons: Qt.LeftButton
        enabled: !root.editMode
        onTapped: if (root.backend) root.backend.refreshNow()
    }

    Item {
        id: contentBox
        anchors.centerIn: parent
        width: root.screenWidth
        height: root.activeRowHeight
        opacity: 1
        visible: !(root.blanked && root.blankWhenHidden)

        // 主体：天气图标 + 温度 / 高低温
        RowLayout {
            id: mainRow
            anchors.centerIn: parent
            width: parent.width
            spacing: root.miniMode ? 8 : 10
            visible: root.shown.kind === "main"
            opacity: visible ? 1 : 0

            ColumnLayout {
                spacing: 1

                WeatherIcon {
                    box: root.iconSize
                    icon: root.mainIcon
                }

                RowLayout {
                    spacing: 2
                    visible: root.showSummary && !root.blanked
                        && (root.alerts.length > 0 || root.precipitation.active)
                    Layout.alignment: Qt.AlignLeft

                    WeatherIcon {
                        box: 12
                        icon: root.alerts.length > 0
                            ? "alert_summary"
                            : (root.precipitation.icon || "rain_light")
                    }
                    Text {
                        text: root.alerts.length > 0
                            ? ("× " + root.alerts.length)
                            : "降水"
                        color: root.alerts.length > 0
                            ? (Theme.isDark() ? "#FFB4AB" : "#B3261E")
                            : (Theme.isDark() ? "#9CCBFF" : "#0A5AD4")
                        font.pixelSize: 9
                        font.weight: 600
                    }
                }
            }

            Numeral {
                visible: root.contentMode !== "high_low"
                px: root.temperaturePx
                color: Theme.isDark() ? "#FFFFFF" : "#17171A"
                text: root.current.temp_text || "--°"
            }

            ColumnLayout {
                visible: root.contentMode === "high_low"
                spacing: 0
                Numeral {
                    px: root.titlePx
                    color: Theme.isDark() ? "#FFFFFF" : "#17171A"
                    text: "↑ " + (root.today.high_text || "--°")
                }
                Numeral {
                    px: root.titlePx
                    color: Theme.isDark() ? "#FFFFFF" : "#17171A"
                    opacity: 0.62
                    text: "↓ " + (root.today.low_text || "--°")
                }
            }

            Item { Layout.fillWidth: true }

            ColumnLayout {
                visible: root.contentMode !== "high_low" && !root.miniMode
                spacing: 0
                Text {
                    Layout.alignment: Qt.AlignRight
                    text: "最高 " + (root.today.high_text || "--°")
                    color: Theme.isDark() ? "#FFFFFF" : "#17171A"
                    font.pixelSize: root.bodyPx
                    font.weight: 600
                }
                Text {
                    Layout.alignment: Qt.AlignRight
                    text: "最低 " + (root.today.low_text || "--°")
                    color: Theme.isDark() ? "#D6D6DB" : "#4B4B52"
                    font.pixelSize: root.bodyPx
                    font.weight: 600
                }
            }
        }

        // 明日天气
        RowLayout {
            id: tomorrowRow
            anchors.centerIn: parent
            width: parent.width
            spacing: 10
            visible: root.shown.kind === "tomorrow"
            opacity: visible ? 1 : 0

            WeatherIcon {
                box: root.iconSize
                icon: root.tomorrow.icon || "unknown"
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 1
                Text {
                    Layout.fillWidth: true
                    text: "明日 " + (root.tomorrow.text || "天气")
                    color: Theme.isDark() ? "#FFFFFF" : "#17171A"
                    font.pixelSize: root.titlePx
                    font.weight: 600
                    elide: Text.ElideRight
                }
                Text {
                    Layout.fillWidth: true
                    text: "最高 " + (root.tomorrow.high_text || "--°")
                        + "  最低 " + (root.tomorrow.low_text || "--°")
                    color: Theme.isDark() ? "#D6D6DB" : "#4B4B52"
                    font.pixelSize: root.bodyPx
                    elide: Text.ElideRight
                }
            }
        }

        // 未来 3 小时
        RowLayout {
            id: hourlyRow
            anchors.centerIn: parent
            width: parent.width
            spacing: 4
            visible: root.shown.kind === "hourly"
            opacity: visible ? 1 : 0

            Repeater {
                model: root.hourly.slice(0, 3)
                delegate: RowLayout {
                    spacing: 4

                    Rectangle {
                        visible: index > 0
                        width: 1
                        height: 32
                        color: Theme.isDark() ? "#44FFFFFF" : "#22000000"
                    }

                    RowLayout {
                        spacing: 3
                        Layout.alignment: Qt.AlignVCenter
                        WeatherIcon {
                            box: root.iconSize
                            icon: root.hourlyIcon(modelData)
                        }
                        ColumnLayout {
                            spacing: 0
                            Numeral {
                                px: root.titlePx
                                color: Theme.isDark() ? "#FFFFFF" : "#17171A"
                                text: (modelData.temp_text || "--°")
                            }
                            Text {
                                text: modelData.hour || ""
                                color: Theme.isDark() ? "#D6D6DB" : "#4B4B52"
                                font.pixelSize: root.bodyPx
                            }
                        }
                    }
                }
            }
        }

        // 天气预警：一次一条，按顺序轮播
        RowLayout {
            id: alertRow
            anchors.centerIn: parent
            width: parent.width
            spacing: root.miniMode ? 8 : 11
            visible: root.shown.kind === "alert"
            opacity: visible ? 1 : 0

            Rectangle {
                width: root.iconSize
                height: root.iconSize
                radius: 9
                color: root.activeSlide.color || "#E81123"
                WeatherIcon {
                    anchors.centerIn: parent
                    box: root.iconSize * 0.7
                    icon: root.activeSlide.icon || "alert_generic"
                }
            }

            ColumnLayout {
                Layout.preferredWidth: root.miniMode ? 78 : 104
                spacing: 1
                Text {
                    Layout.fillWidth: true
                    text: root.activeSlide.title
                        || (root.activeAlert.type
                            ? (root.activeAlert.type + " " + (root.activeAlert.level_text || "")).trim()
                            : root.activeAlert.title)
                        || "天气预警"
                    color: Theme.isDark() ? "#FFFFFF" : "#17171A"
                    font.pixelSize: root.titlePx
                    font.weight: 650
                    elide: Text.ElideRight
                    wrapMode: Text.WordWrap
                    maximumLineCount: 1
                }
                Text {
                    Layout.fillWidth: true
                    text: root.activeSlide.meta
                        || [root.activeAlert.pub_time_text, root.activeAlert.sender]
                            .filter(function(item) { return !!item }).join(" · ")
                    color: Theme.isDark() ? "#D6D6DB" : "#4B4B52"
                    font.pixelSize: root.bodyPx
                    elide: Text.ElideRight
                    maximumLineCount: 1
                }
            }
        }

        // 降水预报：参考简洁大字样式，突出“多久后开始/停止”
        RowLayout {
            id: precipRow
            anchors.centerIn: parent
            width: parent.width
            spacing: 12
            visible: root.shown.kind === "precip"
            opacity: visible ? 1 : 0

            WeatherIcon {
                box: root.iconSize
                icon: root.precipitation.icon || "rain_light"
            }

            RowLayout {
                Layout.preferredWidth: root.miniMode ? 92 : 150
                spacing: 4

                Numeral {
                    px: root.miniMode ? 26 : 36
                    text: root.precipitation.value !== undefined
                        && root.precipitation.value !== null
                        ? root.precipitation.value
                        : (root.precipitation.pop !== undefined
                            ? root.precipitation.pop : "—")
                }

                Text {
                    Layout.alignment: Qt.AlignBottom
                    Layout.bottomMargin: 5
                    text: root.precipitation.unit
                        || (root.precipitation.pop !== undefined ? "%" : "")
                    color: Theme.isDark() ? "#D6D6DB" : "#4B4B52"
                    font.pixelSize: root.miniMode ? 10 : 12
                    font.weight: 600
                    elide: Text.ElideRight
                }
            }
        }

        // 隐藏后等待 5 秒的空白屏幕
        Item {
            id: blankScreen
            visible: root.shown.kind === "blank"
            width: 1
            height: 1
        }

        // 不可用
        RowLayout {
            id: unavailableRow
            anchors.centerIn: parent
            width: parent.width
            spacing: 10
            visible: root.shown.kind === "unavailable"
            opacity: visible ? 1 : 0

            WeatherIcon {
                box: root.iconSize
                icon: "unknown"
            }

            ColumnLayout {
                Layout.preferredWidth: root.miniMode ? 78 : 104
                spacing: 1
                Text {
                    Layout.fillWidth: true
                    text: root.backend && root.backend.errorText ? "天气获取失败" : "正在获取天气…"
                    color: Theme.isDark() ? "#FFFFFF" : "#17171A"
                    font.pixelSize: root.titlePx
                    font.weight: 600
                }
                Text {
                    Layout.fillWidth: true
                    text: root.backend && root.backend.errorText
                        ? "点击刷新或在设置中检查数据源"
                        : "请稍候…"
                    color: Theme.isDark() ? "#D6D6DB" : "#4B4B52"
                    font.pixelSize: root.bodyPx
                    elide: Text.ElideRight
                }
            }
        }
    }
}
