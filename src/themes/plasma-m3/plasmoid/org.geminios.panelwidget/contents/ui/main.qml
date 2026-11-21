import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.components as PlasmaComponents

PlasmoidItem {
    id: root
    property string aiMode: "Gemini Cloud"
    property color dotColor: "#A8C7FA"
    property string cloudModel: "gemini-3.5-flash-lite"

    function pollStatus() {
        var xhr = new XMLHttpRequest();
        xhr.open("GET", "http://127.0.0.1:11435/v1/status", true);
        xhr.onreadystatechange = function() {
            if (xhr.readyState === XMLHttpRequest.DONE) {
                if (xhr.status === 200) {
                    try {
                        var data = JSON.parse(xhr.responseText);
                        if (data.cloud_model) {
                            cloudModel = data.cloud_model;
                        }
                        if (data.cloud_configured) {
                            aiMode = "Gemini Cloud";
                            dotColor = "#A8C7FA";
                        } else if (data.fallback_enabled) {
                            aiMode = "Gemma Local";
                            dotColor = "#81C995";
                        } else {
                            aiMode = "Setup AI";
                            dotColor = "#FBBC05";
                        }
                    } catch (e) {
                        aiMode = "Gemini Cloud";
                        dotColor = "#A8C7FA";
                    }
                } else {
                    aiMode = "AI Offline";
                    dotColor = "#FFB4AB";
                }
            }
        };
        xhr.send();
    }

    Timer {
        interval: 15000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: root.pollStatus()
    }

    // ChromeOS Material Design 3 Pill Representation
    compactRepresentation: Item {
        id: compactItem
        implicitWidth: pillRect.width
        implicitHeight: 34

        Layout.minimumWidth: pillRect.width
        Layout.preferredWidth: pillRect.width
        Layout.maximumWidth: pillRect.width
        Layout.preferredHeight: 34
        Layout.alignment: Qt.AlignVCenter

        Rectangle {
            id: pillRect
            anchors.centerIn: parent
            width: contentRow.implicitWidth + 24
            height: 32
            radius: 16
            color: mouseArea.containsMouse ? "#2C313C" : "#1E222A"
            border.color: mouseArea.containsMouse ? root.dotColor : "#3D434F"
            border.width: 1

            Behavior on color { ColorAnimation { duration: 150 } }
            Behavior on border.color { ColorAnimation { duration: 150 } }

            RowLayout {
                id: contentRow
                anchors.centerIn: parent
                spacing: 7

                // Glowing AI status indicator dot
                Rectangle {
                    width: 8
                    height: 8
                    radius: 4
                    color: root.dotColor
                    Layout.alignment: Qt.AlignVCenter
                }

                // AI Mode Label (auto-sized, zero overflow)
                Text {
                    id: modeText
                    text: root.aiMode
                    color: "#E2E2E9"
                    font.family: "Roboto"
                    font.pixelSize: 12
                    font.weight: Font.Medium
                    verticalAlignment: Text.AlignVCenter
                    Layout.alignment: Qt.AlignVCenter
                }
            }

            MouseArea {
                id: mouseArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.expanded = !root.expanded
            }
        }
    }

    // Material 3 Dark Floating Card
    fullRepresentation: Rectangle {
        Layout.preferredWidth: 320
        Layout.preferredHeight: 180
        color: "#181A20"
        radius: 20
        border.color: "#353945"
        border.width: 1

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 18
            spacing: 12

            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Rectangle {
                    width: 32
                    height: 32
                    radius: 16
                    color: "#282C37"

                    Text {
                        anchors.centerIn: parent
                        text: "✦"
                        color: root.dotColor
                        font.pixelSize: 16
                    }
                }

                ColumnLayout {
                    spacing: 2
                    Text {
                        text: "GeminiOS System AI"
                        font.family: "Roboto"
                        font.bold: true
                        font.pixelSize: 14
                        color: "#E2E2E9"
                    }
                    Text {
                        text: root.aiMode + " (" + root.cloudModel + ")"
                        font.family: "Roboto"
                        font.pixelSize: 12
                        color: root.dotColor
                    }
                }
            }

            Text {
                text: "Global shortcut: Super+G to invoke Spotlight AI & Agent Mode.\nRun 'gemini <query>' in Konsole for instant answers."
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
                font.family: "Roboto"
                font.pixelSize: 12
                color: "#C4C6D0"
                lineHeight: 1.3
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignRight
                spacing: 8

                Rectangle {
                    width: 110
                    height: 32
                    radius: 16
                    color: refreshArea.containsMouse ? "#3A3F4D" : "#2A2E38"

                    Text {
                        anchors.centerIn: parent
                        text: "Check Status"
                        font.family: "Roboto"
                        font.pixelSize: 12
                        color: "#E2E2E9"
                    }

                    MouseArea {
                        id: refreshArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.pollStatus()
                    }
                }
            }
        }
    }
}
