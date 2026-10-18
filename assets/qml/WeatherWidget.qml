import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ClassWidgets.Theme as CWTheme
import RinUI

CWTheme.Widget {
    id: root

    implicitWidth: 300
    height: miniMode ? 58 : 108
    padding: miniMode ? 14 : 20

    readonly property var cfg: backend && backend.settings ? backend.settings : ({})
    readonly property var apiData: backend && backend.weather ? backend.weather : ({})
    readonly property var current: apiData && apiData.current ? apiData.current : ({})
    readonly property bool hasAlert: backend ? backend.hasAlerts : false
    readonly property bool animationsEnabled: cfg.animation_enabled !== false
    readonly property int slideCount: backend && backend.slides ? backend.slides.length : 0

    property int slideIndex: 0
    property string slidesKey: ""
    property bool swapping: false
    property var pendingSlide: ({})
    property var shownSlide: ({
        kind: "weather",
        icon: "unknown",
        value: "--°",
        title: "正在获取天气",
        meta: "请稍候…",
        color: "#0078D4",
        severity: 0
    })

    text: {
        if (!backend || !backend.hasWeather)
            return "天气"
        var parts = []
        if (cfg.show_location && backend.locationText)
            parts.push(backend.locationText)
        if (cfg.show_provider && apiData.provider && apiData.provider.name)
            parts.push(apiData.provider.name)
        var value = parts.join(" · ") || "天气"
        return value.length > 26 ? value.substring(0, 25) + "…" : value
    }

    backgroundColor: hasAlert && shownSlide.kind === "alert"
        ? (Theme.isDark()
            ? Qt.darker(shownSlide.color, 0.55)
            : Qt.lighter(shownSlide.color, 1.85))
        : (Theme.isDark() ? Qt.alpha("#1E1D22", 0.65) : Qt.alpha("#FBFAFF", 0.7))

    borderColor: hasAlert && shownSlide.kind === "alert"
        ? Qt.alpha(shownSlide.color, 0.85)
        : (Theme.isDark() ? Qt.alpha("#fff", 0.4) : Qt.alpha("#fff", 1))

    function iconSource(name) {
        var key = (name || "unknown").toString()
        return Qt.resolvedUrl("../icons/" + key + ".png")
    }

    function slideKey(list) {
        if (!list || list.length === 0)
            return ""
        var parts = []
        for (var i = 0; i < list.length; i++) {
            var item = list[i] || {}
            parts.push([item.kind, item.icon, item.value, item.title, item.meta, item.color].join("|"))
        }
        return parts.join("||")
    }

    function showSlide(next, animate) {
        if (!next)
            return
        if (!animate || !animationsEnabled) {
            shownSlide = next
            contentBox.opacity = 1
            return
        }
        if (swapping) {
            pendingSlide = next
            return
        }
        pendingSlide = next
        swapping = true
        swapAnim.restart()
    }

    function syncSlides() {
        var list = backend ? backend.slides : null
        if (!list || list.length === 0) {
            list = [{
                kind: "weather",
                icon: "unknown",
                value: "--°",
                title: backend && backend.errorText ? "天气获取失败" : "正在获取天气",
                meta: backend && backend.errorText ? "打开设置检查网络或数据源" : "请稍候…",
                color: "#0078D4",
                severity: 0
            }]
        }
        var nextKey = slideKey(list)
        if (nextKey === slidesKey)
            return
        slidesKey = nextKey
        slideIndex = 0
        var shouldAnimate = animationsEnabled && shownSlide
            && shownSlide.title !== "正在获取天气"
            && shownSlide.title !== "天气获取失败"
        showSlide(list[0], shouldAnimate)
    }

    function nextSlide() {
        var list = backend ? backend.slides : null
        if (!list || list.length <= 1)
            return
        slideIndex = (slideIndex + 1) % list.length
        showSlide(list[slideIndex], animationsEnabled)
    }

    function restartCycleTimer() {
        if (root.slideCount > 1)
            cycleTimer.restart()
        else
            cycleTimer.stop()
    }

    SequentialAnimation {
        id: swapAnim
        NumberAnimation {
            target: contentBox
            property: "opacity"
            from: 1
            to: 0
            duration: 180
            easing.type: Easing.InOutQuad
        }
        ScriptAction {
            script: {
                root.shownSlide = root.pendingSlide
                contentBox.opacity = 0
            }
        }
        NumberAnimation {
            target: contentBox
            property: "opacity"
            from: 0
            to: 1
            duration: 240
            easing.type: Easing.OutCubic
        }
        ScriptAction {
            script: root.swapping = false
        }
    }

    Timer {
        id: cycleTimer
        interval: Math.max(1, Number(root.cfg.cycle_interval || 3)) * 1000
        repeat: true
        running: root.slideCount > 1 && !root.editMode
        onTriggered: root.nextSlide()
        onIntervalChanged: root.restartCycleTimer()
    }

    Connections {
        target: root.backend
        enabled: root.backend !== null && root.backend !== undefined

        function onSlidesChanged() {
            root.syncSlides()
            root.restartCycleTimer()
        }

        function onConfigChanged() {
            root.restartCycleTimer()
        }
    }

    Component.onCompleted: {
        syncSlides()
        restartCycleTimer()
    }
    onBackendChanged: {
        syncSlides()
        restartCycleTimer()
    }

    Item {
        id: contentBox
        anchors.fill: parent
        opacity: 1

        RowLayout {
            anchors.fill: parent
            spacing: root.miniMode ? 9 : 13

            Rectangle {
                visible: root.shownSlide.kind === "alert"
                Layout.preferredWidth: 4
                Layout.fillHeight: true
                radius: 2
                color: root.shownSlide.color || "#E81123"
            }

            Image {
                id: weatherIcon
                Layout.preferredWidth: root.miniMode ? 32 : 46
                Layout.preferredHeight: root.miniMode ? 32 : 46
                Layout.alignment: Qt.AlignVCenter
                source: root.iconSource(root.shownSlide.icon)
                fillMode: Image.PreserveAspectFit
                smooth: true
                cache: true
                sourceSize.width: root.miniMode ? 64 : 96
                sourceSize.height: root.miniMode ? 64 : 96
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignVCenter
                spacing: 1

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 7

                    Text {
                        id: temperature
                        visible: root.shownSlide.kind !== "alert"
                        text: root.shownSlide.value || "--°"
                        color: Theme.isDark() ? "#FFFFFF" : "#17171A"
                        font.pixelSize: root.miniMode ? 25 : 31
                        font.weight: 650
                    }

                    Rectangle {
                        visible: root.shownSlide.kind === "alert"
                        Layout.preferredHeight: 20
                        Layout.preferredWidth: levelLabel.implicitWidth + 12
                        radius: 5
                        color: root.shownSlide.color || "#E81123"

                        Text {
                            id: levelLabel
                            anchors.centerIn: parent
                            text: root.shownSlide.value || "预警"
                            color: "#FFFFFF"
                            font.pixelSize: 11
                            font.weight: 600
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        text: root.shownSlide.title || ""
                        color: Theme.isDark() ? "#FFFFFF" : "#17171A"
                        font.pixelSize: root.shownSlide.kind === "alert"
                            ? (root.miniMode ? 13 : 15)
                            : (root.miniMode ? 13 : 14)
                        font.weight: 600
                        elide: Text.ElideRight
                        wrapMode: root.shownSlide.kind === "alert" ? Text.WordWrap : Text.NoWrap
                        maximumLineCount: root.shownSlide.kind === "alert"
                            ? (root.miniMode ? 1 : 2) : 1
                    }
                }

                Text {
                    Layout.fillWidth: true
                    text: root.shownSlide.meta || ""
                    color: Theme.isDark() ? "#D6D6DB" : "#4B4B52"
                    font.pixelSize: root.miniMode ? 10 : 12
                    elide: Text.ElideRight
                    maximumLineCount: 1
                }
            }
        }
    }
}
