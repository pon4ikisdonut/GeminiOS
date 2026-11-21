import QtQuick 2.15

Rectangle {
    id: root
    color: "#0B0D11"

    property int stage

    Image {
        id: logo
        source: "/usr/share/sddm/themes/geminios/assets/logo.png"
        width: 128
        height: 128
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.verticalCenter: parent.verticalCenter
        anchors.verticalCenterOffset: -48
        fillMode: Image.PreserveAspectFit
    }

    Rectangle {
        id: track
        width: 240
        height: 6
        radius: 3
        color: "#1D2026"
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: logo.bottom
        anchors.topMargin: 36

        Rectangle {
            height: parent.height
            radius: 3
            color: "#A8C7FA"
            width: Math.min(parent.width, (parent.width / 6) * Math.max(1, root.stage))
            Behavior on width { NumberAnimation { duration: 350; easing.type: Easing.InOutCubic } }
        }
    }

    Column {
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 44
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: 4

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "GeminiOS, powered by Linux"
            color: "#E2E2E9"
            font.family: "Roboto"
            font.pixelSize: 18
            font.weight: Font.DemiBold
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "With Love, With Gemini"
            color: "#A8C7FA"
            font.family: "Roboto"
            font.pixelSize: 14
        }
    }
}
