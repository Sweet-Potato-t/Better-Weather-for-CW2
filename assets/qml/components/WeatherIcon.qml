import QtQuick

Item {
    id: root
    property string icon: "unknown"
    property real box: 38
    property real contentScale: 1
    implicitWidth: box
    implicitHeight: box

    Image {
        anchors.centerIn: parent
        width: root.box * root.contentScale
        height: root.box * root.contentScale
        source: Qt.resolvedUrl("../../icons/" + (root.icon || "unknown") + ".png")
        fillMode: Image.PreserveAspectFit
        smooth: true
        cache: true
        sourceSize.width: Math.ceil(root.box * root.contentScale * 2)
        sourceSize.height: Math.ceil(root.box * root.contentScale * 2)
    }
}
