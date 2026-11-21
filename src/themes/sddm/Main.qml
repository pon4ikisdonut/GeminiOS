import QtQuick 2.15
import SddmComponents 2.0

Rectangle {
    id: root
    width: 1920
    height: 1080
    color: "#0B0D11"

    property string activeUser: {
        try {
            if (userModel && userModel.lastUser && userModel.lastUser.length > 0) {
                return userModel.lastUser;
            }
        } catch(e) {}
        return "gemini";
    }

    // Material 3 Dark ChromeOS Wallpaper
    Image {
        anchors.fill: parent
        source: config.background || "assets/background.png"
        fillMode: Image.PreserveAspectCrop
        opacity: 0.95
    }

    // Subtle dark vignette
    Rectangle {
        anchors.fill: parent
        color: "#000000"
        opacity: 0.35
    }

    // ChromeOS Top Center Clock & Date
    Column {
        anchors.top: parent.top
        anchors.topMargin: 56
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: 6

        Text {
            id: clockText
            anchors.horizontalCenter: parent.horizontalCenter
            color: "#F0F0F8"
            font.family: "Roboto"
            font.pixelSize: 72
            font.weight: Font.Light
            text: Qt.formatTime(new Date(), "HH:mm")
        }

        Text {
            id: dateText
            anchors.horizontalCenter: parent.horizontalCenter
            color: "#A8C7FA"
            font.family: "Roboto"
            font.pixelSize: 18
            font.weight: Font.Normal
            text: Qt.formatDate(new Date(), "dddd, d MMMM yyyy")
        }

        Timer {
            interval: 1000
            running: true
            repeat: true
            onTriggered: {
                clockText.text = Qt.formatTime(new Date(), "HH:mm")
                dateText.text = Qt.formatDate(new Date(), "dddd, d MMMM yyyy")
            }
        }
    }

    // Material Design 3 Dark ChromeOS Floating Login Card
    Rectangle {
        id: loginCard
        width: 400
        height: 380
        radius: 28
        color: "#E61A1C24"
        border.color: "#383C48"
        border.width: 1
        anchors.centerIn: parent

        Column {
            anchors.fill: parent
            anchors.margins: 28
            spacing: 14

            // Official Google G + Gemini Star Logo
            Image {
                anchors.horizontalCenter: parent.horizontalCenter
                source: config.logo || "assets/logo.png"
                width: 72
                height: 72
                fillMode: Image.PreserveAspectFit
                smooth: true
            }

            // Material 3 Username Pill Input
            Rectangle {
                width: parent.width
                height: 46
                radius: 23
                color: "#12141A"
                border.color: usernameInput.activeFocus ? "#A8C7FA" : "#44474E"
                border.width: usernameInput.activeFocus ? 2 : 1

                Behavior on border.color { ColorAnimation { duration: 150 } }

                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.left: parent.left
                    anchors.leftMargin: 18
                    text: "Username"
                    color: "#8E9099"
                    font.family: "Roboto"
                    font.pixelSize: 14
                    visible: usernameInput.text.length === 0
                }

                TextInput {
                    id: usernameInput
                    anchors.fill: parent
                    anchors.leftMargin: 18
                    anchors.rightMargin: 18
                    verticalAlignment: TextInput.AlignVCenter
                    color: "#F0F0F8"
                    selectionColor: "#A8C7FA"
                    selectedTextColor: "#062E6F"
                    font.family: "Roboto"
                    font.pixelSize: 14
                    text: root.activeUser
                    focus: false
                    Keys.onReturnPressed: passwordInput.focus = true
                    Keys.onEnterPressed: passwordInput.focus = true
                }
            }

            // Material 3 Password Pill Input (Single clean field without duplicate internal arrow)
            Rectangle {
                width: parent.width
                height: 46
                radius: 23
                color: "#12141A"
                border.color: passwordInput.activeFocus ? "#A8C7FA" : "#44474E"
                border.width: passwordInput.activeFocus ? 2 : 1

                Behavior on border.color { ColorAnimation { duration: 150 } }

                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.left: parent.left
                    anchors.leftMargin: 18
                    text: "Password"
                    color: "#8E9099"
                    font.family: "Roboto"
                    font.pixelSize: 14
                    visible: passwordInput.text.length === 0
                }

                TextInput {
                    id: passwordInput
                    anchors.fill: parent
                    anchors.leftMargin: 18
                    anchors.rightMargin: 18
                    verticalAlignment: TextInput.AlignVCenter
                    echoMode: TextInput.Password
                    color: "#F0F0F8"
                    selectionColor: "#A8C7FA"
                    selectedTextColor: "#062E6F"
                    font.family: "Roboto"
                    font.pixelSize: 14
                    focus: true
                    Keys.onReturnPressed: doLogin()
                    Keys.onEnterPressed: doLogin()
                }
            }

            // Single ChromeOS Sign-In Action Pill Button
            Rectangle {
                id: signInBtn
                width: parent.width
                height: 46
                radius: 23
                color: signInArea.containsMouse ? "#C2E7FF" : "#A8C7FA"

                Behavior on color { ColorAnimation { duration: 150 } }

                Text {
                    anchors.centerIn: parent
                    text: "Sign in"
                    color: "#062E6F"
                    font.family: "Roboto"
                    font.pixelSize: 15
                    font.weight: Font.DemiBold
                }

                MouseArea {
                    id: signInArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: doLogin()
                }
            }

            Text {
                id: errorMsg
                anchors.horizontalCenter: parent.horizontalCenter
                color: "#FFB4AB"
                font.family: "Roboto"
                font.pixelSize: 12
                text: ""
                wrapMode: Text.WordWrap
            }
        }
    }

    function doLogin() {
        var user = usernameInput.text.trim() || root.activeUser || "gemini";
        var sessIdx = sessionModel.lastIndex >= 0 ? sessionModel.lastIndex : 0;
        errorMsg.text = "";
        sddm.login(user, passwordInput.text, sessIdx);
    }

    Connections {
        target: sddm
        function onLoginFailed() {
            var user = usernameInput.text.trim() || root.activeUser || "gemini";
            errorMsg.text = "Incorrect credentials for '" + user + "'.";
            passwordInput.text = "";
            passwordInput.focus = true;
        }
    }

    // ChromeOS Bottom Status Bar / Signature
    Column {
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 28
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: 4

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "GeminiOS, powered by Linux"
            color: "#E2E2E9"
            font.family: "Roboto"
            font.pixelSize: 15
            font.weight: Font.DemiBold
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "With Love, With Gemini"
            color: "#A8C7FA"
            font.family: "Roboto"
            font.pixelSize: 13
        }
    }

    // ChromeOS Power Pills (Right Bottom Corner)
    Row {
        anchors.bottom: parent.bottom
        anchors.right: parent.right
        anchors.margins: 24
        spacing: 10

        Rectangle {
            width: 90
            height: 36
            radius: 18
            color: rebootArea.containsMouse ? "#3A3E4A" : "#242732"
            border.color: "#3B4050"
            border.width: 1

            Text {
                anchors.centerIn: parent
                text: "Restart"
                color: "#E2E2E9"
                font.family: "Roboto"
                font.pixelSize: 13
            }

            MouseArea {
                id: rebootArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: sddm.reboot()
            }
        }

        Rectangle {
            width: 100
            height: 36
            radius: 18
            color: powerArea.containsMouse ? "#5A2828" : "#242732"
            border.color: powerArea.containsMouse ? "#FFB4AB" : "#3B4050"
            border.width: 1

            Text {
                anchors.centerIn: parent
                text: "Shut down"
                color: "#FFB4AB"
                font.family: "Roboto"
                font.pixelSize: 13
                font.weight: Font.Medium
            }

            MouseArea {
                id: powerArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: sddm.powerOff()
            }
        }
    }
}
