import QtQuick
import RinUI

Text {
    id: root
    property int px: 36
    property int weight: Configs.data.preferences.font_weight || 600

    font.family: AppCentral.getQFont(
        Configs.data.preferences.font,
        Utils.fontFamily
    ).family
    font.pixelSize: px
    font.weight: weight

    Behavior on px {
        NumberAnimation {
            duration: 400
            easing.type: Easing.OutQuint
        }
    }
}
