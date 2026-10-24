import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ClassWidgets.Theme as CWTheme
import RinUI
import "components"

CWTheme.Widget {
    id: root

    padding: miniMode ? 16 : 24

    // 天气屏幕切换频繁，禁止父级主题的宽高弹性动画，避免隐藏/显示时掉帧。
    Behavior on implicitWidth { enabled: false }
    Behavior on height { enabled: false }

    readonly property var cfg: backend && backend.settings ? backend.settings : ({})
    readonly property var payload: backend && backend.weather ? backend.weather : ({})
    readonly property var current: payload && payload.current ? payload.current : ({})
    readonly property var today: payload && payload.today ? payload.today : ({})
    readonly property var alerts: backend ? backend.alerts : []
    readonly property var hourly: payload && payload.hourly ? payload.hourly : []
    readonly property bool available: backend ? backend.hasWeather : false
    readonly property bool animationsEnabled: cfg.animation_enabled !== false
    readonly property string contentMode: cfg.widget_content_mode || "current"
    readonly property bool carousel: cfg.widget_carousel !== false
    readonly property bool showHourly: cfg.widget_show_hourly !== false
    readonly property bool showPrecip: cfg.widget_show_precip !== false
    readonly property int mainSeconds: Math.max(
        3, Number(cfg.widget_main_seconds || 8))
    readonly property int alertSeconds: Math.max(
        1, Number(cfg.cycle_interval || 3))

    property var screens: []
    property string screensKey: ""
    property int screenIndex: 0
    property var shown: ({ kind: "unavailable" })
    property var pending: ({})
    property bool swapping: false

    readonly property int iconSize: miniMode ? 24 : 32
    readonly property int titlePx: miniMode ? 13 : 15
    readonly property int bodyPx: miniMode ? 10 : 11
    readonly property int temperaturePx: miniMode ? 26 : 34
    readonly property real activeRowWidth: {
        switch (shown.kind) {
        case "alert": return alertRow.implicitWidth
        case "hourly": return hourlyRow.implicitWidth
        case "precip": return precipRow.implicitWidth
        case "unavailable": return unavailableRow.implicitWidth
        default: return mainRow.implicitWidth
        }
    }
    readonly property real activeRowHeight: {
        switch (shown.kind) {
        case "alert": return alertRow.implicitHeight
        case "hourly": return hourlyRow.implicitHeight
        case "precip": return precipRow.implicitHeight
        case "unavailable": return unavailableRow.implicitHeight
        default: return mainRow.implicitHeight
        }
    }
    readonly property bool hasAlert: alerts.length > 0
    readonly property var activeAlert: {
        if (shown.kind !== "alert")
            return ({})
        return alerts[shown.index] || ({})
    }
    readonly property var activeSlide: {
        if (shown.kind !== "alert" || !backend)
            return ({})
        var list = backend.slides || []
        return list[shown.index] || ({})
    }
    readonly property var precipitation: {
        var maxPop = -1
        var next = ({})
        for (var i = 0; i < hourly.length; i++) {
            var item = hourly[i] || ({})
            var pop = Number(item.pop)
            if (!isNaN(pop) && pop > maxPop) {
                maxPop = pop
                next = item
            }
        }
        if (maxPop >= 40)
            return { active: true, pop: maxPop, hour: next.hour || "", icon: next.icon || "rain_light" }
        return { active: false, pop: 0, hour: "", icon: "rain_light" }
    }
    function headerSuffix() {
        var parts = []
        if (cfg.show_location !== false && backend && backend.locationText)
            parts.push(backend.locationText)
        if (cfg.show_provider === true && backend && backend.weather
                && backend.weather.provider && backend.weather.provider.name)
            parts.push(backend.weather.provider.name)
        return parts.length > 0 ? " · " + parts.join(" · ") : ""
    }

    text: {
        var value = ""
        switch (shown.kind) {
        case "alert":
            value = root.activeAlert.level_text || "天气预警"
            break
        case "hourly":
            value = "未来 3 小时"
            break
        case "precip":
            value = "降水提醒"
            break
        case "unavailable":
            value = "天气"
            break
        default:
            value = root.current.text || "天气"
        }
        value += root.headerSuffix()
        return value.length > 36 ? value.substring(0, 35) + "…" : value
    }

    actions: RowLayout {
        spacing: 6

        Text {
            visible: root.shown.kind === "alert" && root.alerts.length > 1
            text: (root.shown.index + 1) + "/" + root.alerts.length
            font.pixelSize: root.bodyPx
            opacity: 0.65
            color: Theme.isDark() ? "#FFFFFF" : "#17171A"
        }
    }

    function buildScreens() {
        var list = []
        if (!available) {
            list = [{ kind: "unavailable" }]
        } else if (carousel) {
            // 轮播开启时，主屏、小时预报、降水和预警都在同一个队列中。
            list.push({ kind: "main" })
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
        var animate = animationsEnabled && shown.kind !== "unavailable"
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
            duration: 160
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
            duration: 220
            easing.type: Easing.OutCubic
        }
        ScriptAction {
            script: root.swapping = false
        }
    }

    Timer {
        id: rotator
        running: root.screens.length > 1 && !root.editMode
        repeat: true
        interval: root.shown.kind === "alert"
            ? root.alertSeconds * 1000
            : root.mainSeconds * 1000
        onTriggered: root.nextScreen()
        onIntervalChanged: if (running) restart()
    }

    Connections {
        target: root.backend
        enabled: root.backend !== null && root.backend !== undefined

        function onWeatherChanged() { root.buildScreens() }
        function onAlertsChanged() { root.buildScreens() }
        function onConfigChanged() { root.buildScreens() }
    }

    onAvailableChanged: buildScreens()
    onAlertsChanged: buildScreens()
    onHourlyChanged: buildScreens()
    onBackendChanged: buildScreens()
    Component.onCompleted: buildScreens()

    TapHandler {
        acceptedButtons: Qt.LeftButton
        enabled: !root.editMode
        onTapped: if (root.backend) root.backend.refreshNow()
    }

    Item {
        id: contentBox
        anchors.centerIn: parent
        width: root.activeRowWidth
        height: root.activeRowHeight
        opacity: 1

        // 主体：天气图标 + 温度 / 高低温
        RowLayout {
            id: mainRow
            anchors.centerIn: parent
            spacing: root.miniMode ? 8 : 10
            visible: root.shown.kind === "main"
            opacity: visible ? 1 : 0

            WeatherIcon {
                box: root.iconSize
                icon: root.current.icon || "unknown"
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
                }
            }
        }

        // 未来 3 小时
        RowLayout {
            id: hourlyRow
            anchors.centerIn: parent
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
                            icon: modelData.icon || "unknown"
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

            Rectangle {
                Layout.preferredWidth: levelLabel.implicitWidth + 12
                Layout.preferredHeight: 21
                radius: 5
                color: root.activeSlide.color || "#E81123"
                Text {
                    id: levelLabel
                    anchors.centerIn: parent
                    text: root.activeSlide.value || "预警"
                    color: "#FFFFFF"
                    font.pixelSize: root.bodyPx
                    font.weight: 600
                }
            }

            ColumnLayout {
                Layout.preferredWidth: root.miniMode ? 130 : 170
                spacing: 1
                Text {
                    Layout.fillWidth: true
                    text: root.activeSlide.title || root.activeAlert.title || "天气预警"
                    color: Theme.isDark() ? "#FFFFFF" : "#17171A"
                    font.pixelSize: root.titlePx
                    font.weight: 650
                    elide: Text.ElideRight
                    wrapMode: Text.WordWrap
                    maximumLineCount: 1
                }
                Text {
                    Layout.fillWidth: true
                    text: root.activeSlide.meta || ""
                    color: Theme.isDark() ? "#D6D6DB" : "#4B4B52"
                    font.pixelSize: root.bodyPx
                    elide: Text.ElideRight
                    maximumLineCount: 1
                }
            }
        }

        // 降水提醒
        RowLayout {
            id: precipRow
            anchors.centerIn: parent
            spacing: 10
            visible: root.shown.kind === "precip"
            opacity: visible ? 1 : 0

            Rectangle {
                width: root.iconSize
                height: root.iconSize
                radius: 9
                color: "#0A5AD4"
                WeatherIcon {
                    anchors.centerIn: parent
                    box: root.iconSize * 0.72
                    icon: root.precipitation.icon || "rain_light"
                }
            }

            ColumnLayout {
                Layout.preferredWidth: root.miniMode ? 140 : 180
                spacing: 0
                Text {
                    Layout.fillWidth: true
                    text: "未来 3 小时有降水可能"
                    color: Theme.isDark() ? "#FFFFFF" : "#17171A"
                    font.pixelSize: root.titlePx
                    font.weight: 600
                    elide: Text.ElideRight
                }
                Text {
                    Layout.fillWidth: true
                    text: "最高降水概率 " + root.precipitation.pop + "%"
                        + (root.precipitation.hour ? " · " + root.precipitation.hour : "")
                    color: Theme.isDark() ? "#D6D6DB" : "#4B4B52"
                    font.pixelSize: root.bodyPx
                    elide: Text.ElideRight
                }
            }
        }

        // 不可用
        RowLayout {
            id: unavailableRow
            anchors.centerIn: parent
            spacing: 10
            visible: root.shown.kind === "unavailable"
            opacity: visible ? 1 : 0

            WeatherIcon {
                box: root.iconSize
                icon: "unknown"
            }

            ColumnLayout {
                Layout.preferredWidth: root.miniMode ? 130 : 170
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
