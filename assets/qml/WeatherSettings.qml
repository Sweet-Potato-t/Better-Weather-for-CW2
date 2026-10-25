import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI

FluentPage {
    id: root
    title: "Better Weather"

    // The host passes pluginId when the page is opened.  Keeping a concrete
    // default also makes the page work when it is previewed directly.
    property string pluginId: "com.sweetpotato.weather"
    property var backend: PluginBackendBridge.get_backend(pluginId)
    property var cfg: backend && backend.settings ? backend.settings : ({})
    property var apiData: backend && backend.weather ? backend.weather : ({})
    property var current: apiData && apiData.current ? apiData.current : ({})
    property var today: apiData && apiData.today ? apiData.today : ({})
    property var alerts: backend ? backend.alerts : []
    property var daily: apiData && apiData.daily ? apiData.daily : []
    property var detailItems: apiData && apiData.details ? apiData.details : []
    property string currentProvider: cfg.source || "open-meteo"
    property bool syncing: false
    property int versionClicks: 0

    spacing: 12

    function iconSource(name) {
        return Qt.resolvedUrl("../icons/" + ((name || "unknown").toString()) + ".png")
    }

    function numberText(value) {
        return (value === null || value === undefined) ? "--" : String(value)
    }

    function providerKeyHint(providerId) {
        if (providerId === "qweather")
            return "在 dev.qweather.com 创建项目和 API Key，并从控制台设置页复制你的 API Host；公共域名已逐步停用。"
        if (providerId === "openweathermap")
            return "需要 One Call 3.0 权限；免费账号可能需要单独订阅。"
        if (providerId === "weatherapi")
            return "在 weatherapi.com 注册后填写 Key，免费额度通常足够个人使用。"
        if (providerId === "caiyun")
            return "在 dashboard.caiyunapp.com 创建 Token。"
        return ""
    }

    function openAlertDetail(data) {
        alertDialog.alertData = data || ({})
        alertDialog.open()
    }

    function keyHint(providerId) {
        var base = root.providerKeyHint(providerId)
        var field = providerId === "qweather" ? "qweather_api_key"
            : providerId === "openweathermap" ? "openweathermap_api_key"
            : providerId === "weatherapi" ? "weatherapi_api_key" : "caiyun_api_key"
        return cfg[field + "_set"] ? base + "（当前已加密保存）" : base
    }

    function keyPlaceholder(providerId) {
        var field = providerId === "qweather" ? "qweather_api_key"
            : providerId === "openweathermap" ? "openweathermap_api_key"
            : providerId === "weatherapi" ? "weatherapi_api_key" : "caiyun_api_key"
        return cfg[field + "_set"] ? "已加密保存，输入新值可替换" : "输入 " + providerId + " API Key"
    }

    function syncControls() {
        if (!backend)
            return
        syncing = true
        providerCombo.currentIndex = backend.providerIndex
        strategyCombo.currentIndex = Math.max(
            0, ["auto", "ip", "device"].indexOf(cfg.location_strategy || "auto"))
        unitCombo.currentIndex = (cfg.temperature_unit === "fahrenheit") ? 1 : 0
        refreshSpin.value = Number(cfg.refresh_interval || 15)
        cycleSpin.value = Number(cfg.cycle_interval || 3)
        timeoutSpin.value = Number(cfg.timeout || 12)
        autoSwitch.checked = cfg.auto_location !== false
        fallbackSwitch.checked = cfg.fallback_enabled !== false
        animationSwitch.checked = cfg.animation_enabled !== false
        showLocationSwitch.checked = cfg.show_location !== false
        showProviderSwitch.checked = cfg.show_provider === true
        widgetContentCombo.currentIndex = cfg.widget_content_mode === "high_low" ? 1 : 0
        widgetHourlySwitch.checked = cfg.widget_show_hourly !== false
        tomorrowSwitch.checked = cfg.widget_tomorrow_enabled !== false
        if (!tomorrowStartField.activeFocus)
            tomorrowStartField.text = cfg.widget_tomorrow_start || "20:00"
        if (!tomorrowEndField.activeFocus)
            tomorrowEndField.text = cfg.widget_tomorrow_end || "23:59"
        widgetPrecipSwitch.checked = cfg.widget_show_precip !== false
        widgetCarouselSwitch.checked = cfg.widget_carousel !== false
        widgetSecondsSpin.value = Number(cfg.widget_main_seconds || 8)
        if (!qweatherKeyField.activeFocus) qweatherKeyField.text = ""
        if (!qweatherHostField.activeFocus) qweatherHostField.text = cfg.qweather_host || ""
        if (!owmKeyField.activeFocus) owmKeyField.text = ""
        if (!weatherApiKeyField.activeFocus) weatherApiKeyField.text = ""
        if (!caiyunKeyField.activeFocus) caiyunKeyField.text = ""
        if (!manualLatField.activeFocus) manualLatField.text = Number(cfg.manual_lat || 0).toFixed(4)
        if (!manualLonField.activeFocus) manualLonField.text = Number(cfg.manual_lon || 0).toFixed(4)
        if (!manualNameField.activeFocus) manualNameField.text = cfg.manual_city || ""
        syncing = false
    }

    Component.onCompleted: syncControls()

    Connections {
        target: root.backend
        enabled: root.backend !== null && root.backend !== undefined
        function onConfigChanged() { root.syncControls() }
    }

    // ------------------------------------------------------------------
    // Current conditions
    // ------------------------------------------------------------------

    Frame {
        Layout.fillWidth: true
        padding: 20
        radius: 8

        ColumnLayout {
            anchors.fill: parent
            spacing: 14

            RowLayout {
                Layout.fillWidth: true
                spacing: 18

                Image {
                    Layout.preferredWidth: 74
                    Layout.preferredHeight: 74
                    source: root.iconSource(current.icon)
                    fillMode: Image.PreserveAspectFit
                    smooth: true
                    sourceSize.width: 148
                    sourceSize.height: 148
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2

                    RowLayout {
                        spacing: 10
                        Text {
                            text: current.temp_text || "--°"
                            font.pixelSize: 46
                            font.weight: 650
                        }
                        ColumnLayout {
                            spacing: 0
                            Text {
                                text: current.text || "暂无数据"
                                font.pixelSize: 18
                                font.weight: 600
                            }
                            Text {
                                color: Colors.proxy.textSecondaryColor
                                text: today.high_text && today.low_text
                                    ? ("最高 " + today.high_text + "   最低 " + today.low_text)
                                    : "正在获取天气数据"
                                font.pixelSize: 13
                            }
                        }
                    }

                    RowLayout {
                        spacing: 6
                        Text {
                            text: backend && backend.locationText ? backend.locationText : "未获取位置"
                            font.pixelSize: 13
                            elide: Text.ElideRight
                            Layout.maximumWidth: 300
                        }
                        Text {
                            visible: current.pressure !== null && current.pressure !== undefined
                            color: Colors.proxy.textSecondaryColor
                            text: "· " + (current.pressure || "--") + " hPa"
                            font.pixelSize: 12
                        }
                    }
                }

                Item { Layout.fillWidth: true }

                ColumnLayout {
                    spacing: 4
                    Layout.alignment: Qt.AlignTop

                    Text {
                        color: Colors.proxy.textSecondaryColor
                        text: backend && backend.statusText ? backend.statusText : "正在准备"
                        font.pixelSize: 12
                        horizontalAlignment: Text.AlignRight
                        Layout.alignment: Qt.AlignRight
                    }
                    Text {
                        color: Colors.proxy.textSecondaryColor
                        text: apiData.provider && apiData.provider.name
                            ? ("数据源：" + apiData.provider.name) : ""
                        font.pixelSize: 12
                        horizontalAlignment: Text.AlignRight
                        Layout.alignment: Qt.AlignRight
                    }
                    Text {
                        color: Colors.proxy.textSecondaryColor
                        text: backend && backend.locationSourceText
                            ? ("定位：" + backend.locationSourceText) : ""
                        font.pixelSize: 12
                        horizontalAlignment: Text.AlignRight
                        Layout.alignment: Qt.AlignRight
                    }
                    BusyIndicator {
                        visible: backend && backend.loading
                        running: visible
                        Layout.preferredWidth: 20
                        Layout.preferredHeight: 20
                        Layout.alignment: Qt.AlignRight
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                height: 1
                color: Colors.proxy.dividerStrokeColor || "#22000000"
                visible: detailItems.length > 0
            }

            GridLayout {
                Layout.fillWidth: true
                columns: root.width < 780 ? 2 : 4
                columnSpacing: 24
                rowSpacing: 10
                visible: detailItems.length > 0

                Repeater {
                    model: root.detailItems
                    delegate: RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        Icon {
                            name: modelData.icon || "ic_fluent_weather_sunny_20_regular"
                            size: 16
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0
                            Text {
                                color: Colors.proxy.textSecondaryColor
                                text: modelData.label || ""
                                font.pixelSize: 11
                            }
                            Text {
                                text: modelData.value || "--"
                                font.pixelSize: 13
                                font.weight: 600
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                        }
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                visible: daily.length > 0

                Repeater {
                    model: root.daily
                    delegate: Frame {
                        Layout.fillWidth: true
                        padding: 10
                        radius: 6

                        ColumnLayout {
                            anchors.fill: parent
                            spacing: 2
                            Text {
                                text: modelData.weekday || modelData.date || ""
                                font.pixelSize: 12
                                font.weight: 600
                                Layout.alignment: Qt.AlignHCenter
                            }
                            Image {
                                Layout.preferredWidth: 30
                                Layout.preferredHeight: 30
                                Layout.alignment: Qt.AlignHCenter
                                source: root.iconSource(modelData.icon)
                                fillMode: Image.PreserveAspectFit
                                sourceSize.width: 60
                                sourceSize.height: 60
                            }
                            Text {
                                text: modelData.text || ""
                                color: Colors.proxy.textSecondaryColor
                                font.pixelSize: 10
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                                horizontalAlignment: Text.AlignHCenter
                            }
                            Text {
                                text: (modelData.high_text || root.numberText(modelData.high)) + " / "
                                    + (modelData.low_text || root.numberText(modelData.low))
                                font.pixelSize: 11
                                Layout.alignment: Qt.AlignHCenter
                            }
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                visible: backend && backend.errorText !== ""
                height: visible ? errorRow.implicitHeight + 18 : 0
                radius: 6
                color: Qt.alpha("#E81123", 0.10)
                border.width: 1
                border.color: Qt.alpha("#E81123", 0.35)

                RowLayout {
                    id: errorRow
                    anchors.fill: parent
                    anchors.margins: 9
                    spacing: 8
                    Text {
                        text: "!"
                        color: "#E81123"
                        font.pixelSize: 15
                        font.weight: 700
                    }
                    Text {
                        Layout.fillWidth: true
                        text: backend && backend.errorText ? backend.errorText : ""
                        color: "#C50F1F"
                        font.pixelSize: 12
                        wrapMode: Text.WordWrap
                    }
                }
            }
        }
    }

    // ------------------------------------------------------------------
    // Alerts
    // ------------------------------------------------------------------

    ColumnLayout {
        Layout.fillWidth: true
        spacing: 8

        RowLayout {
            Layout.fillWidth: true
            Text {
                text: "天气预警"
                font.pixelSize: 17
                font.weight: 650
            }
            Rectangle {
                visible: alerts.length > 0
                width: countLabel.implicitWidth + 12
                height: 20
                radius: 10
                color: Qt.alpha("#E81123", 0.12)
                Text {
                    id: countLabel
                    anchors.centerIn: parent
                    text: String(alerts.length)
                    color: "#C50F1F"
                    font.pixelSize: 11
                    font.weight: 600
                }
            }
            Item { Layout.fillWidth: true }
            Text {
                visible: alerts.length === 0
                color: Colors.proxy.textSecondaryColor
                text: "当前没有生效中的预警"
                font.pixelSize: 12
            }
        }

        Repeater {
            model: root.alerts
            delegate: Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 68
                radius: 8
                color: Qt.alpha(modelData.color || "#E81123", 0.10)
                border.width: 1
                border.color: Qt.alpha(modelData.color || "#E81123", 0.45)

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 12

                    Rectangle {
                        width: 38
                        height: 38
                        radius: 8
                        color: modelData.color || "#E81123"
                        Image {
                            anchors.centerIn: parent
                            width: 25
                            height: 25
                            source: root.iconSource(modelData.icon || "alert_generic")
                            fillMode: Image.PreserveAspectFit
                            sourceSize.width: 50
                            sourceSize.height: 50
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Text {
                            Layout.fillWidth: true
                            text: modelData.title || "天气预警"
                            font.pixelSize: 14
                            font.weight: 650
                            elide: Text.ElideRight
                            maximumLineCount: 1
                        }
                        Text {
                            Layout.fillWidth: true
                            color: Colors.proxy.textSecondaryColor
                            text: [modelData.level_text, modelData.sender, modelData.pub_time_text]
                                .filter(function(item) { return !!item }).join(" · ")
                            font.pixelSize: 11
                            elide: Text.ElideRight
                            maximumLineCount: 1
                        }
                    }

                    Text {
                        text: "查看详情  ›"
                        color: modelData.color || "#E81123"
                        font.pixelSize: 12
                        font.weight: 600
                    }
                }

                TapHandler {
                    onTapped: root.openAlertDetail(modelData)
                }
            }
        }
    }

    // ------------------------------------------------------------------
    // Settings: data source
    // ------------------------------------------------------------------

    SettingExpander {
        Layout.fillWidth: true
        title: "天气数据源"
        description: "选择天气服务。无需 API Key 的源可直接使用；带 Key 的源通常提供更完整的预警。"

        SettingItem {
            title: "数据源"
            description: backend && backend.providers[providerCombo.currentIndex]
                ? backend.providers[providerCombo.currentIndex].description : ""

            ComboBox {
                id: providerCombo
                Layout.preferredWidth: 260
                model: backend ? backend.providers.map(function(item) { return item.name }) : []
                currentIndex: backend ? backend.providerIndex : 0
                onActivated: {
                    if (backend && backend.providers[index])
                        backend.setOption("source", backend.providers[index].id)
                }
            }
        }

        SettingItem {
            title: "和风天气 API Key / JWT"
            visible: root.currentProvider === "qweather"
            description: root.keyHint("qweather")

            TextField {
                id: qweatherKeyField
                Layout.preferredWidth: 300
                placeholderText: root.keyPlaceholder("qweather")
                echoMode: TextInput.Password
                selectByMouse: true
                onEditingFinished: {
                    if (backend && text.trim().length > 0) {
                        backend.setOption("qweather_api_key", text)
                        text = ""
                    }
                }
            }
        }

        SettingItem {
            title: "OpenWeatherMap API Key"
            visible: root.currentProvider === "openweathermap"
            description: root.keyHint("openweathermap")

            TextField {
                id: owmKeyField
                Layout.preferredWidth: 300
                placeholderText: root.keyPlaceholder("openweathermap")
                echoMode: TextInput.Password
                selectByMouse: true
                onEditingFinished: {
                    if (backend && text.trim().length > 0) {
                        backend.setOption("openweathermap_api_key", text)
                        text = ""
                    }
                }
            }
        }

        SettingItem {
            title: "WeatherAPI Key"
            visible: root.currentProvider === "weatherapi"
            description: root.keyHint("weatherapi")

            TextField {
                id: weatherApiKeyField
                Layout.preferredWidth: 300
                placeholderText: root.keyPlaceholder("weatherapi")
                echoMode: TextInput.Password
                selectByMouse: true
                onEditingFinished: {
                    if (backend && text.trim().length > 0) {
                        backend.setOption("weatherapi_api_key", text)
                        text = ""
                    }
                }
            }
        }

        SettingItem {
            title: "彩云天气 Token"
            visible: root.currentProvider === "caiyun"
            description: root.keyHint("caiyun")

            TextField {
                id: caiyunKeyField
                Layout.preferredWidth: 300
                placeholderText: root.keyPlaceholder("caiyun")
                echoMode: TextInput.Password
                selectByMouse: true
                onEditingFinished: {
                    if (backend && text.trim().length > 0) {
                        backend.setOption("caiyun_api_key", text)
                        text = ""
                    }
                }
            }
        }

        SettingItem {
            title: "和风天气 API Host"
            visible: root.currentProvider === "qweather"
            description: "填写控制台-设置中的专属 API Host，例如 abcxyz.qweatherapi.com；请不要使用 devapi/api.qweather.com 等公共域名。"

            TextField {
                id: qweatherHostField
                Layout.preferredWidth: 300
                placeholderText: "你的 API Host，例如 abcxyz.qweatherapi.com"
                onEditingFinished: if (backend) backend.setOption("qweather_host", text)
            }
        }

        SettingItem {
            title: "自动故障转移"
            description: "当前数据源失败时，自动尝试其他无需 Key 的数据源，避免小组件空白。"

            Switch {
                id: fallbackSwitch
                onToggled: if (!root.syncing && backend) backend.setOption("fallback_enabled", checked)
            }
        }

        SettingItem {
            title: "刷新间隔"
            description: "单位：分钟。建议 10–30 分钟，过短可能触发免费接口限流。"

            SpinBox {
                id: refreshSpin
                Layout.preferredWidth: 150
                from: 1
                to: 1440
                editable: true
                onValueModified: if (!root.syncing && backend) backend.setOption("refresh_interval", value)
            }
        }

        SettingItem {
            title: "请求超时"
            description: "单位：秒。网络较慢时可适当调大。"

            SpinBox {
                id: timeoutSpin
                Layout.preferredWidth: 150
                from: 5
                to: 45
                editable: true
                onValueModified: if (!root.syncing && backend) backend.setOption("timeout", value)
            }
        }
    }

    // ------------------------------------------------------------------
    // Settings: location
    // ------------------------------------------------------------------

    SettingExpander {
        Layout.fillWidth: true
        title: "定位"
        description: "自动通过设备定位或公网 IP 获取位置；关闭后可手动搜索城市。"

        SettingItem {
            title: "自动获取位置"
            description: "设备定位不可用时自动回退到公网 IP。"

            Switch {
                id: autoSwitch
                onToggled: if (!root.syncing && backend) backend.setOption("auto_location", checked)
            }
        }

        SettingItem {
            title: "自动定位方式"
            visible: cfg.auto_location !== false
            description: "自动：优先设备定位，失败后使用公网 IP。"

            ComboBox {
                id: strategyCombo
                Layout.preferredWidth: 210
                model: ["自动（设备优先）", "仅公网 IP", "仅设备定位"]
                currentIndex: Math.max(0, ["auto", "ip", "device"].indexOf(cfg.location_strategy || "auto"))
                onActivated: {
                    if (!backend) return
                    backend.setOption("location_strategy", ["auto", "ip", "device"][index])
                }
            }
        }

        SettingItem {
            title: "设备定位状态"
            visible: cfg.auto_location !== false
            description: backend ? backend.deviceStatusText : ""

            Button {
                text: "重新定位"
                onClicked: if (backend) backend.relocate()
            }
        }

        // Manual location
        ColumnLayout {
            Layout.fillWidth: true
            Layout.topMargin: 4
            spacing: 8
            visible: cfg.auto_location === false

            Text {
                text: "手动选择位置"
                font.pixelSize: 14
                font.weight: 600
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                TextField {
                    id: searchField
                    Layout.fillWidth: true
                    placeholderText: "搜索城市，例如：杭州、上海、New York"
                    onAccepted: if (backend) backend.searchLocations(text)
                }
                Button {
                    text: "搜索"
                    enabled: backend && !backend.searching
                    onClicked: if (backend) backend.searchLocations(searchField.text)
                }
            }

            Text {
                visible: backend && backend.searching
                color: Colors.proxy.textSecondaryColor
                text: "正在搜索…"
                font.pixelSize: 12
            }
            Text {
                visible: backend && backend.searchError !== ""
                color: "#C50F1F"
                text: backend ? backend.searchError : ""
                font.pixelSize: 12
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

            Repeater {
                model: backend ? backend.searchResults : []
                delegate: Button {
                    Layout.fillWidth: true
                    text: modelData.display_name || modelData.name || ""
                    onClicked: if (backend) backend.chooseSearchResult(index)
                }
            }

            Text {
                color: Colors.proxy.textSecondaryColor
                text: "当前手动位置：" + (cfg.manual_city || "未选择")
                    + "（" + Number(cfg.manual_lat || 0).toFixed(3) + ", "
                    + Number(cfg.manual_lon || 0).toFixed(3) + "）"
                font.pixelSize: 11
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

            Rectangle {
                Layout.fillWidth: true
                height: 1
                color: Colors.proxy.dividerStrokeColor || "#22000000"
            }

            Text {
                text: "高级：手动坐标"
                font.pixelSize: 12
                font.weight: 600
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                TextField {
                    id: manualNameField
                    Layout.fillWidth: true
                    placeholderText: "地点名称（可选）"
                }
                TextField {
                    id: manualLatField
                    Layout.preferredWidth: 110
                    placeholderText: "纬度"
                    inputMethodHints: Qt.ImhFormattedNumbersOnly
                }
                TextField {
                    id: manualLonField
                    Layout.preferredWidth: 110
                    placeholderText: "经度"
                    inputMethodHints: Qt.ImhFormattedNumbersOnly
                }
                Button {
                    text: "应用坐标"
                    onClicked: {
                        if (!backend) return
                        var lat = Number(manualLatField.text)
                        var lon = Number(manualLonField.text)
                        if (isNaN(lat) || isNaN(lon) || lat < -90 || lat > 90 || lon < -180 || lon > 180)
                            return
                        backend.setManualLocation(lat, lon, manualNameField.text)
                    }
                }
            }
        }
    }

    // ------------------------------------------------------------------
    // Settings: widget behaviour
    // ------------------------------------------------------------------

    SettingExpander {
        Layout.fillWidth: true
        title: "小组件显示"
        description: "统一控制所有 Better Weather 小组件的内容、轮播和预警显示。"

        SettingItem {
            title: "主屏显示"
            description: "所有 Better Weather 小组件共用；选择实时温度或当日最高 / 最低温。"

            ComboBox {
                id: widgetContentCombo
                Layout.preferredWidth: 170
                model: ["实时温度", "最高 / 最低温"]
                onActivated: if (backend)
                    backend.setOption("widget_content_mode", index === 1 ? "high_low" : "current")
            }
        }

        SettingItem {
            title: "明日天气"
            description: "到达设定时间后，在轮播中加入明日天气屏幕。"

            Switch {
                id: tomorrowSwitch
                onToggled: if (!root.syncing && backend)
                    backend.setOption("widget_tomorrow_enabled", checked)
            }
        }

        SettingItem {
            title: "明日天气开始时间"
            description: "24 小时制，格式 HH:mm；到达开始时间后显示明日天气。"

            TextField {
                id: tomorrowStartField
                Layout.preferredWidth: 150
                placeholderText: "20:00"
                inputMask: "00:00"
                onEditingFinished: if (backend && text.length === 5)
                    backend.setOption("widget_tomorrow_start", text)
            }
        }

        SettingItem {
            title: "明日天气结束时间"
            description: "到达结束时间后隐藏明日天气；结束时间早于开始时间时按跨午夜处理。"

            TextField {
                id: tomorrowEndField
                Layout.preferredWidth: 150
                placeholderText: "23:59"
                inputMask: "00:00"
                onEditingFinished: if (backend && text.length === 5)
                    backend.setOption("widget_tomorrow_end", text)
            }
        }

        SettingItem {
            title: "未来 3 小时"
            description: "在小组件轮播中加入逐小时预报屏幕；数据源没有逐小时数据时不显示。"

            Switch {
                id: widgetHourlySwitch
                onToggled: if (!root.syncing && backend)
                    backend.setOption("widget_show_hourly", checked)
            }
        }

        SettingItem {
            title: "降水提醒"
            description: "未来 3 小时降水概率较高时，加入降水提醒屏幕。"

            Switch {
                id: widgetPrecipSwitch
                onToggled: if (!root.syncing && backend)
                    backend.setOption("widget_show_precip", checked)
            }
        }

        SettingItem {
            title: "内容屏幕轮播"
            description: "开启后主屏、未来 3 小时、降水提醒和天气预警一起轮播；关闭后只显示主屏（有预警时仅轮播预警）。"

            Switch {
                id: widgetCarouselSwitch
                onToggled: if (!root.syncing && backend)
                    backend.setOption("widget_carousel", checked)
            }
        }

        SettingItem {
            title: "主屏停留时长"
            description: "单位：秒。主屏与小时预报、降水提醒之间切换的间隔。"

            SpinBox {
                id: widgetSecondsSpin
                Layout.preferredWidth: 150
                from: 3
                to: 60
                editable: true
                onValueModified: if (!root.syncing && backend)
                    backend.setOption("widget_main_seconds", value)
            }
        }

        SettingItem {
            title: "切换动画"
            description: "在主屏、小时预报、降水提醒与预警之间使用淡入淡出过渡。"

            Switch {
                id: animationSwitch
                onToggled: if (!root.syncing && backend) backend.setOption("animation_enabled", checked)
            }
        }

        SettingItem {
            title: "预警轮播间隔"
            description: "单位：秒。多条预警时逐条切换的间隔。"

            SpinBox {
                id: cycleSpin
                Layout.preferredWidth: 150
                from: 1
                to: 300
                editable: true
                onValueModified: if (!root.syncing && backend) backend.setOption("cycle_interval", value)
            }
        }

        SettingItem {
            title: "显示位置"
            description: "在小组件标题栏显示当前城市或地区。"

            Switch {
                id: showLocationSwitch
                onToggled: if (!root.syncing && backend) backend.setOption("show_location", checked)
            }
        }

        SettingItem {
            title: "显示数据源"
            description: "在小组件标题栏显示当前使用的天气服务。"

            Switch {
                id: showProviderSwitch
                onToggled: if (!root.syncing && backend) backend.setOption("show_provider", checked)
            }
        }

        SettingItem {
            title: "温度单位"
            description: "切换后立即重新渲染已有数据。"

            ComboBox {
                id: unitCombo
                Layout.preferredWidth: 150
                model: ["摄氏度（°C）", "华氏度（°F）"]
                currentIndex: cfg.temperature_unit === "fahrenheit" ? 1 : 0
                onActivated: {
                    if (!backend) return
                    backend.setOption("temperature_unit", index === 1 ? "fahrenheit" : "celsius")
                }
            }
        }
    }

    // ------------------------------------------------------------------
    // Data source capabilities
    // ------------------------------------------------------------------

    SettingExpander {
        Layout.fillWidth: true
        title: "数据源能力"
        description: "各天气源对插件功能的支持情况；✓ 支持，— 不支持或尚未接入。"

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 4

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Text { Layout.preferredWidth: 140; text: "天气源"; font.pixelSize: 11; font.weight: 600; color: Colors.proxy.textSecondaryColor }
                Text { Layout.preferredWidth: 64; text: "当前"; horizontalAlignment: Text.AlignHCenter; font.pixelSize: 11; font.weight: 600; color: Colors.proxy.textSecondaryColor }
                Text { Layout.preferredWidth: 64; text: "明日"; horizontalAlignment: Text.AlignHCenter; font.pixelSize: 11; font.weight: 600; color: Colors.proxy.textSecondaryColor }
                Text { Layout.preferredWidth: 64; text: "3 小时"; horizontalAlignment: Text.AlignHCenter; font.pixelSize: 11; font.weight: 600; color: Colors.proxy.textSecondaryColor }
                Text { Layout.preferredWidth: 64; text: "降水"; horizontalAlignment: Text.AlignHCenter; font.pixelSize: 11; font.weight: 600; color: Colors.proxy.textSecondaryColor }
                Text { Layout.preferredWidth: 64; text: "预警"; horizontalAlignment: Text.AlignHCenter; font.pixelSize: 11; font.weight: 600; color: Colors.proxy.textSecondaryColor }
            }

            Repeater {
                model: backend ? backend.providers : []
                delegate: RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Text { Layout.preferredWidth: 140; text: modelData.name || ""; font.pixelSize: 11; elide: Text.ElideRight }
                    Text { Layout.preferredWidth: 64; text: modelData.supports_current ? "✓" : "—"; horizontalAlignment: Text.AlignHCenter; font.pixelSize: 12; color: modelData.supports_current ? "#2E9E5B" : "#999999" }
                    Text { Layout.preferredWidth: 64; text: modelData.supports_tomorrow ? "✓" : "—"; horizontalAlignment: Text.AlignHCenter; font.pixelSize: 12; color: modelData.supports_tomorrow ? "#2E9E5B" : "#999999" }
                    Text { Layout.preferredWidth: 64; text: modelData.supports_hourly ? "✓" : "—"; horizontalAlignment: Text.AlignHCenter; font.pixelSize: 12; color: modelData.supports_hourly ? "#2E9E5B" : "#999999" }
                    Text { Layout.preferredWidth: 64; text: modelData.supports_precipitation ? "✓" : "—"; horizontalAlignment: Text.AlignHCenter; font.pixelSize: 12; color: modelData.supports_precipitation ? "#2E9E5B" : "#999999" }
                    Text { Layout.preferredWidth: 64; text: modelData.supports_alerts ? "✓" : "—"; horizontalAlignment: Text.AlignHCenter; font.pixelSize: 12; color: modelData.supports_alerts ? "#2E9E5B" : "#999999" }
                }
            }
        }
    }

    // ------------------------------------------------------------------
    // About
    // ------------------------------------------------------------------

    SettingExpander {
        Layout.fillWidth: true
        title: "关于"
        description: "版本、仓库和致谢信息。"

        SettingItem {
            id: versionItem
            title: "插件版本"
            description: backend && backend.pluginVersion ? backend.pluginVersion : "未知"
            clickable: true
            onClicked: {
                root.versionClicks += 1
                if (root.versionClicks >= 10) {
                    root.versionClicks = 0
                    Qt.openUrlExternally("https://www.bilibili.com/video/BV1jE421A7qK")
                }
            }
        }

        SettingItem {
            title: "插件仓库"
            Text {
                Layout.fillWidth: true
                textFormat: Text.RichText
                text: '<a href="https://github.com/Sweet-Potato-t/Better-Weather-for-CW2">https://github.com/Sweet-Potato-t/Better-Weather-for-CW2</a>'
                color: "#0A5AD4"
                onLinkActivated: Qt.openUrlExternally(link)
            }
        }

        Text {
            Layout.fillWidth: true
            Layout.leftMargin: 18
            Layout.rightMargin: 18
            Layout.topMargin: 4
            Layout.bottomMargin: 0
            text: "此插件由Sweet_Potato使用Deepseek V4.1 Flash 1017编写，由口天一大化石提供独家Token支持"
            wrapMode: Text.NoWrap
            font.pixelSize: 10
            color: Colors.proxy.textSecondaryColor
        }
    }

    // ------------------------------------------------------------------
    // Footer actions
    // ------------------------------------------------------------------

    RowLayout {
        Layout.fillWidth: true
        Layout.topMargin: 4
        Layout.bottomMargin: 18
        spacing: 10

        Button {
            text: "立即刷新"
            enabled: backend && !backend.loading
            onClicked: if (backend) backend.refreshNow()
        }
        Button {
            text: "重新定位并刷新"
            enabled: backend && !backend.loading
            onClicked: if (backend) backend.relocate()
        }
        Item { Layout.fillWidth: true }
        Text {
            color: Colors.proxy.textSecondaryColor
            text: backend && backend.statusText ? backend.statusText : ""
            font.pixelSize: 12
        }
    }

    // ------------------------------------------------------------------
    // Alert detail dialog
    // ------------------------------------------------------------------

    Dialog {
        id: alertDialog
        objectName: "alertDialog"
        property var alertData: ({})
        title: alertData && alertData.title ? alertData.title : "天气预警"
        modal: true
        width: Math.min(620, Overlay.overlay ? Overlay.overlay.width - 80 : 620)
        height: Math.min(
            520,
            Overlay.overlay ? Overlay.overlay.height - 80 : 520,
            Math.max(300, alertContent.implicitHeight + 130)
        )
        standardButtons: Dialog.Close
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

        background: Rectangle {
            anchors.fill: parent
            radius: 8
            color: Theme.isDark() ? "#2B2B2B" : "#F8F8F8"
            border.width: 1
            border.color: Theme.isDark() ? "#4A4A4A" : "#D8D8D8"
        }

        contentItem: Flickable {
            id: alertFlick
            clip: true
            implicitWidth: 560
            implicitHeight: 430
            contentWidth: width
            contentHeight: alertContent.height
            boundsBehavior: Flickable.StopAtBounds

            Column {
                id: alertContent
                width: alertFlick.width
                spacing: 12

                RowLayout {
                    width: parent.width
                    spacing: 12

                    Rectangle {
                        width: 46
                        height: 46
                        radius: 9
                        color: alertDialog.alertData.color || "#E81123"
                        Image {
                            anchors.centerIn: parent
                            width: 30
                            height: 30
                            source: root.iconSource(alertDialog.alertData.icon || "alert_generic")
                            fillMode: Image.PreserveAspectFit
                            sourceSize.width: 60
                            sourceSize.height: 60
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Text {
                            Layout.fillWidth: true
                            text: alertDialog.alertData.title || "天气预警"
                            font.pixelSize: 18
                            font.weight: 650
                            wrapMode: Text.WordWrap
                            textFormat: Text.PlainText
                        }
                        Text {
                            Layout.fillWidth: true
                            color: alertDialog.alertData.color || "#C50F1F"
                            text: alertDialog.alertData.level_text || ""
                            font.pixelSize: 13
                            font.weight: 600
                            textFormat: Text.PlainText
                        }
                    }
                }

                Rectangle {
                    width: parent.width
                    height: 1
                    color: Colors.proxy.dividerStrokeColor || "#22000000"
                }

                Text {
                    width: parent.width
                    text: alertDialog.alertData.description || "该预警没有提供详细说明。"
                    wrapMode: Text.WordWrap
                    textFormat: Text.PlainText
                    font.pixelSize: 13
                    lineHeight: 1.45
                    lineHeightMode: Text.ProportionalHeight
                }

                RowLayout {
                    width: parent.width
                    spacing: 12
                    Text {
                        Layout.preferredWidth: 78
                        color: Colors.proxy.textSecondaryColor
                        text: "发布单位"
                        font.pixelSize: 12
                    }
                    Text {
                        Layout.fillWidth: true
                        text: alertDialog.alertData.sender || "—"
                        font.pixelSize: 12
                        wrapMode: Text.WordWrap
                        textFormat: Text.PlainText
                    }
                }

                RowLayout {
                    width: parent.width
                    spacing: 12
                    Text {
                        Layout.preferredWidth: 78
                        color: Colors.proxy.textSecondaryColor
                        text: "发布时间"
                        font.pixelSize: 12
                    }
                    Text {
                        Layout.fillWidth: true
                        text: alertDialog.alertData.pub_time || "—"
                        font.pixelSize: 12
                        wrapMode: Text.WordWrap
                        textFormat: Text.PlainText
                    }
                }

                RowLayout {
                    width: parent.width
                    spacing: 12
                    Text {
                        Layout.preferredWidth: 78
                        color: Colors.proxy.textSecondaryColor
                        text: "生效时间"
                        font.pixelSize: 12
                    }
                    Text {
                        Layout.fillWidth: true
                        text: (alertDialog.alertData.start_time || "—")
                            + "  →  " + (alertDialog.alertData.end_time || "—")
                        font.pixelSize: 12
                        wrapMode: Text.WordWrap
                        textFormat: Text.PlainText
                    }
                }

                RowLayout {
                    width: parent.width
                    spacing: 12
                    Text {
                        Layout.preferredWidth: 78
                        color: Colors.proxy.textSecondaryColor
                        text: "数据来源"
                        font.pixelSize: 12
                    }
                    Text {
                        Layout.fillWidth: true
                        text: alertDialog.alertData.source_name
                            || alertDialog.alertData.source || "—"
                        font.pixelSize: 12
                        textFormat: Text.PlainText
                    }
                }
            }
        }
    }
}
