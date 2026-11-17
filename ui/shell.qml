import Quickshell
import QtQuick
import Quickshell.Io

FloatingWindow {
    id: root

    title: "Rice Manager"
    implicitWidth: 1120
    implicitHeight: 760
    minimumSize: Qt.size(900, 620)
    color: "#0b0f14"

    property string currentPage: "Overview"
    property color accent: "#8be9fd"
    property color muted: "#8995a5"
    property color panel: "#121923"
    property color border: "#243140"
    property var planData: ({})
    property string backendStatus: "LOADING"
    property string backendError: ""

    function refreshPlan() {
        backendStatus = "CHECKING"
        backendError = ""
        planProcess.running = true
    }

    function statusColor(status) {
        if (status === "ready") return "#8fe0b8"
        if (status === "skipped") return "#8be9fd"
        if (status.indexOf("blocked-") === 0) return "#ff7b86"
        return "#f0c674"
    }

    Process {
        id: planProcess
        command: [
            Quickshell.shellDir + "/../.venv/bin/rice-manager",
            "profile",
            "plan",
            Quickshell.shellDir + "/../examples/caelestia/manifest.json",
            "--json"
        ]
        running: true

        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    root.planData = JSON.parse(this.text)
                    root.backendStatus = "CONNECTED"
                    root.backendError = ""
                } catch (error) {
                    root.backendStatus = "INVALID DATA"
                    root.backendError = String(error)
                }
            }
        }

        stderr: StdioCollector {
            onStreamFinished: {
                if (this.text.trim().length > 0)
                    root.backendError = this.text.trim()
            }
        }

        onExited: (exitCode, exitStatus) => {
            if (exitCode !== 0)
                root.backendStatus = "BACKEND ERROR"
        }
    }

    Rectangle {
        anchors.fill: parent
        color: "#0b0f14"

        Row {
            anchors.fill: parent
            spacing: 0

            Rectangle {
                width: 226
                height: parent.height
                color: "#0e141c"

                Column {
                    anchors.fill: parent
                    anchors.margins: 20
                    spacing: 24

                    Column {
                        spacing: 5

                        Text {
                            text: "RICE"
                            color: root.accent
                            font.pixelSize: 23
                            font.bold: true
                        }

                        Text {
                            text: "MANAGER  /  ARCH LINUX"
                            color: root.muted
                            font.pixelSize: 9
                            font.letterSpacing: 1.5
                        }
                    }

                    Rectangle {
                        width: parent.width
                        height: 1
                        color: root.border
                    }

                    Column {
                        width: parent.width
                        spacing: 7

                        Text {
                            text: "WORKSPACE"
                            color: "#627184"
                            font.pixelSize: 9
                            font.bold: true
                            font.letterSpacing: 1.4
                            leftPadding: 8
                        }

                        Repeater {
                            model: ["Overview", "Profiles", "Components", "Backups", "Settings"]

                            delegate: Rectangle {
                                required property string modelData
                                width: 186
                                height: 40
                                radius: 7
                                color: root.currentPage === modelData ? "#1a2b38" : "transparent"
                                border.width: root.currentPage === modelData ? 1 : 0
                                border.color: "#315064"

                                Row {
                                    anchors.fill: parent
                                    anchors.leftMargin: 12
                                    spacing: 11

                                    Text {
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: {
                                            const icons = {
                                                "Overview": "⌂",
                                                "Profiles": "▤",
                                                "Components": "◈",
                                                "Backups": "⟲",
                                                "Settings": "⚙"
                                            }
                                            return icons[modelData]
                                        }
                                        color: root.currentPage === modelData ? root.accent : root.muted
                                        font.pixelSize: 16
                                    }

                                    Text {
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: modelData
                                        color: root.currentPage === modelData ? "#e6f2fa" : "#9aa8b8"
                                        font.pixelSize: 13
                                        font.bold: root.currentPage === modelData
                                    }
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: root.currentPage = modelData
                                }
                            }
                        }
                    }

                    Rectangle {
                        width: parent.width
                        height: 72
                        radius: 8
                        color: "#121c25"
                        border.width: 1
                        border.color: root.border

                        Column {
                            anchors.fill: parent
                            anchors.margins: 12
                            spacing: 5

                            Text {
                                text: "SAFETY MODE"
                                color: root.accent
                                font.pixelSize: 9
                                font.bold: true
                                font.letterSpacing: 1
                            }

                            Text {
                                text: "Read-only interface"
                                color: "#c1ccd7"
                                font.pixelSize: 12
                            }

                            Text {
                                text: "No system files modified"
                                color: root.muted
                                font.pixelSize: 10
                            }
                        }
                    }
                }
            }

            Rectangle {
                width: parent.width - 226
                height: parent.height
                color: "#0b0f14"

                Column {
                    anchors.fill: parent
                    anchors.margins: 34
                    spacing: 24

                    Row {
                        width: parent.width
                        height: 54

                        Column {
                            spacing: 5

                            Text {
                                text: root.currentPage
                                color: "#edf4fa"
                                font.pixelSize: 25
                                font.bold: true
                            }

                            Text {
                                text: "Manage your desktop environment, safely."
                                color: root.muted
                                font.pixelSize: 12
                            }
                        }

                        Item { width: 1; height: 1 }

                        Rectangle {
                            width: 112
                            height: 28
                            radius: 14
                            color: "#142a25"
                            border.width: 1
                            border.color: "#285647"

                            Text {
                                anchors.centerIn: parent
                                text: "●  " + root.backendStatus
                                color: root.backendStatus === "CONNECTED" ? "#8fe0b8" : "#f0c674"
                                font.pixelSize: 9
                                font.bold: true
                                font.letterSpacing: 0.7
                            }

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.refreshPlan()
                            }
                        }
                    }

                    Rectangle {
                        width: parent.width
                        height: 1
                        color: root.border
                    }

                    Column {
                        visible: root.currentPage === "Overview"
                        width: parent.width
                        spacing: 18

                        Rectangle {
                            width: parent.width
                            height: 174
                            radius: 12
                            color: "#111d28"
                            border.width: 1
                            border.color: "#284050"

                            Column {
                                anchors.left: parent.left
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.leftMargin: 24
                                spacing: 10

                                Text {
                                    text: "CURRENT WORKSPACE"
                                    color: root.accent
                                    font.pixelSize: 10
                                    font.bold: true
                                    font.letterSpacing: 1.4
                                }

                                Text {
                                    text: "Your rice. Your rules."
                                    color: "#edf4fa"
                                    font.pixelSize: 25
                                    font.bold: true
                                }

                                Text {
                                    text: "A safe control center for profiles, components and backups."
                                    color: "#9cabb9"
                                    font.pixelSize: 12
                                }
                            }

                            Text {
                                anchors.right: parent.right
                                anchors.bottom: parent.bottom
                                anchors.rightMargin: 22
                                anchors.bottomMargin: 14
                                text: "RM  /  0.9"
                                color: "#476174"
                                font.pixelSize: 11
                                font.bold: true
                            }
                        }

                        Row {
                            width: parent.width
                            spacing: 14

                            Repeater {
                                model: [
                                    { label: "PROFILES", value: "01", note: "Example manifest" },
                                    { label: "COMPONENTS", value: root.planData.items ? String(root.planData.items.length).padStart(2, "0") : "--", note: "Live manifest entries" },
                                    { label: "PROTECTED", value: root.planData.summary ? String(root.planData.summary.skipped).padStart(2, "0") : "--", note: "System / read-only" }
                                ]

                                delegate: Rectangle {
                                    required property var modelData
                                    width: (parent.width - 28) / 3
                                    height: 112
                                    radius: 10
                                    color: root.panel
                                    border.width: 1
                                    border.color: root.border

                                    Column {
                                        anchors.fill: parent
                                        anchors.margins: 15
                                        spacing: 7

                                        Text {
                                            text: modelData.label
                                            color: root.muted
                                            font.pixelSize: 9
                                            font.bold: true
                                            font.letterSpacing: 1
                                        }

                                        Text {
                                            text: modelData.value
                                            color: "#eaf4fb"
                                            font.pixelSize: 25
                                            font.bold: true
                                        }

                                        Text {
                                            text: modelData.note
                                            color: "#7e8d9d"
                                            font.pixelSize: 10
                                        }
                                    }
                                }
                            }
                        }

                        Rectangle {
                            width: parent.width
                            height: 130
                            radius: 10
                            color: root.panel
                            border.width: 1
                            border.color: root.border

                            Column {
                                anchors.fill: parent
                                anchors.margins: 18
                                spacing: 11

                                Text {
                                    text: "LATEST PREFLIGHT"
                                    color: root.accent
                                    font.pixelSize: 10
                                    font.bold: true
                                    font.letterSpacing: 1.2
                                }

                                Row {
                                    spacing: 10

                                    Text {
                                        text: "✓"
                                        color: "#8fe0b8"
                                        font.pixelSize: 16
                                    }

                                    Text {
                                        text: root.planData.profile ? root.planData.profile.name : "Loading profile manifest…"
                                        color: "#e5edf5"
                                        font.pixelSize: 13
                                        font.bold: true
                                    }

                                    Text {
                                        text: root.planData.blocked ? "BLOCKED" : (root.planData.profile ? "READY" : "WAITING")
                                        color: root.planData.blocked ? "#f0c674" : "#8fe0b8"
                                        font.pixelSize: 10
                                        font.bold: true
                                    }
                                }

                                Text {
                                    text: root.planData.summary
                                        ? "Ready " + root.planData.summary.ready + "   ·   Skipped " + root.planData.summary.skipped + "   ·   Blocked " + root.planData.summary.blocked + "   ·   Dry-run only"
                                        : (root.backendError.length > 0 ? root.backendError : "Waiting for Python backend…")
                                    color: root.muted
                                    font.pixelSize: 11
                                }
                            }
                        }

                        Text {
                            text: "Live preflight data from the Python core. Click the status badge above to refresh. No files are changed."
                            color: "#718092"
                            font.pixelSize: 10
                            wrapMode: Text.WordWrap
                        }
                    }

                    Column {
                        visible: root.currentPage === "Components"
                        width: parent.width
                        spacing: 14

                        Row {
                            width: parent.width
                            spacing: 12

                            Column {
                                spacing: 4
                                Text {
                                    text: "COMPONENT INVENTORY"
                                    color: root.accent
                                    font.pixelSize: 10
                                    font.bold: true
                                    font.letterSpacing: 1.3
                                }
                                Text {
                                    text: root.planData.profile
                                        ? root.planData.profile.name + "  /  " + root.planData.items.length + " manifest entries"
                                        : "Waiting for profile data…"
                                    color: root.muted
                                    font.pixelSize: 11
                                }
                            }

                            Item { width: 1; height: 1 }
                        }

                        Text {
                            visible: !(root.planData.items && root.planData.items.length > 0)
                            width: parent.width
                            text: root.backendError.length > 0
                                ? root.backendError
                                : "No component data available yet. Refresh the backend status above."
                            color: root.muted
                            font.pixelSize: 12
                            wrapMode: Text.WordWrap
                        }

                        Repeater {
                            model: root.planData.items ? root.planData.items : []

                            delegate: Rectangle {
                                required property var modelData
                                width: parent.width
                                height: 132
                                radius: 10
                                color: root.panel
                                border.width: 1
                                border.color: root.border

                                Column {
                                    anchors.fill: parent
                                    anchors.margins: 16
                                    spacing: 7

                                    Row {
                                        width: parent.width
                                        spacing: 10

                                        Text {
                                            width: parent.width - 104
                                            text: modelData.name
                                            color: "#eaf4fb"
                                            font.pixelSize: 14
                                            font.bold: true
                                            elide: Text.ElideRight
                                        }

                                        Rectangle {
                                            width: 88
                                            height: 22
                                            radius: 11
                                            color: "#18232e"
                                            border.width: 1
                                            border.color: root.statusColor(modelData.status)

                                            Text {
                                                anchors.centerIn: parent
                                                text: modelData.status.toUpperCase()
                                                color: root.statusColor(modelData.status)
                                                font.pixelSize: 9
                                                font.bold: true
                                                font.letterSpacing: 0.5
                                            }
                                        }
                                    }

                                    Text {
                                        text: modelData.component_id
                                        color: root.accent
                                        font.pixelSize: 10
                                    }

                                    Text {
                                        width: parent.width
                                        text: modelData.path
                                        color: "#b6c4d2"
                                        font.pixelSize: 11
                                        wrapMode: Text.WrapAnywhere
                                    }

                                    Text {
                                        width: parent.width
                                        text: modelData.detail
                                        color: root.muted
                                        font.pixelSize: 10
                                        wrapMode: Text.WordWrap
                                    }
                                }
                            }
                        }

                        Text {
                            text: "Read-only preflight data. No configuration files are changed by this page."
                            color: "#718092"
                            font.pixelSize: 10
                        }
                    }

                    Column {
                        visible: root.currentPage === "Profiles"
                        width: parent.width
                        spacing: 14

                        Row {
                            width: parent.width
                            spacing: 12

                            Column {
                                spacing: 4
                                Text {
                                    text: "PROFILE LIBRARY"
                                    color: root.accent
                                    font.pixelSize: 10
                                    font.bold: true
                                    font.letterSpacing: 1.3
                                }
                                Text {
                                    text: root.planData.profile ? "1 profile loaded from the example manifest" : "Waiting for profile data…"
                                    color: root.muted
                                    font.pixelSize: 11
                                }
                            }
                            Item { width: 1; height: 1 }
                        }

                        Rectangle {
                            width: parent.width
                            height: 222
                            radius: 11
                            color: "#111d28"
                            border.width: 1
                            border.color: "#284050"

                            Column {
                                anchors.fill: parent
                                anchors.margins: 20
                                spacing: 12

                                Row {
                                    width: parent.width
                                    spacing: 10

                                    Text {
                                        text: "▤"
                                        color: root.accent
                                        font.pixelSize: 20
                                    }

                                    Column {
                                        spacing: 3
                                        Text {
                                            text: root.planData.profile ? root.planData.profile.name : "Profile unavailable"
                                            color: "#edf4fa"
                                            font.pixelSize: 18
                                            font.bold: true
                                        }
                                        Text {
                                            text: root.planData.profile ? "ID  /  " + root.planData.profile.id : "No manifest loaded"
                                            color: root.muted
                                            font.pixelSize: 10
                                        }
                                    }

                                    Item { width: 1; height: 1 }

                                    Rectangle {
                                        width: 82
                                        height: 25
                                        radius: 12
                                        color: root.planData.profile && !root.planData.blocked ? "#142a25" : "#30251a"
                                        border.width: 1
                                        border.color: root.planData.profile && !root.planData.blocked ? "#285647" : "#68502d"
                                        Text {
                                            anchors.centerIn: parent
                                            text: root.planData.profile ? (root.planData.blocked ? "BLOCKED" : "LOADED") : "WAITING"
                                            color: root.planData.profile && !root.planData.blocked ? "#8fe0b8" : "#f0c674"
                                            font.pixelSize: 9
                                            font.bold: true
                                        }
                                    }
                                }

                                Rectangle {
                                    width: parent.width
                                    height: 1
                                    color: root.border
                                }

                                Row {
                                    width: parent.width
                                    spacing: 10

                                    Repeater {
                                        model: [
                                            { label: "COMPONENTS", value: root.planData.items ? String(root.planData.items.length).padStart(2, "0") : "--" },
                                            { label: "READY", value: root.planData.summary ? String(root.planData.summary.ready).padStart(2, "0") : "--" },
                                            { label: "SKIPPED", value: root.planData.summary ? String(root.planData.summary.skipped).padStart(2, "0") : "--" },
                                            { label: "BLOCKED", value: root.planData.summary ? String(root.planData.summary.blocked).padStart(2, "0") : "--" }
                                        ]

                                        delegate: Rectangle {
                                            required property var modelData
                                            width: (parent.width - 30) / 4
                                            height: 62
                                            radius: 7
                                            color: "#0c141d"
                                            border.width: 1
                                            border.color: root.border

                                            Column {
                                                anchors.centerIn: parent
                                                spacing: 5
                                                Text {
                                                    anchors.horizontalCenter: parent.horizontalCenter
                                                    text: modelData.value
                                                    color: "#eaf4fb"
                                                    font.pixelSize: 18
                                                    font.bold: true
                                                }
                                                Text {
                                                    anchors.horizontalCenter: parent.horizontalCenter
                                                    text: modelData.label
                                                    color: root.muted
                                                    font.pixelSize: 8
                                                    font.bold: true
                                                }
                                            }
                                        }
                                    }
                                }

                                Text {
                                    width: parent.width
                                    text: "Manifest  /  examples/caelestia/manifest.json"
                                    color: "#b6c4d2"
                                    font.pixelSize: 10
                                    wrapMode: Text.WrapAnywhere
                                }

                                Text {
                                    width: parent.width
                                    text: "Profile inventory and readiness are read from the Python preflight. Profile activation is not available."
                                    color: root.muted
                                    font.pixelSize: 10
                                    wrapMode: Text.WordWrap
                                }
                            }
                        }

                        Text {
                            text: "This build displays the configured example profile. Multi-profile discovery and switching are future work."
                            color: "#718092"
                            font.pixelSize: 10
                            wrapMode: Text.WordWrap
                        }
                    }

                    Column {
                        visible: root.currentPage !== "Overview" && root.currentPage !== "Components"
                        width: parent.width
                        spacing: 12

                        Text {
                            text: root.currentPage.toUpperCase()
                            color: root.accent
                            font.pixelSize: 10
                            font.bold: true
                            font.letterSpacing: 1.3
                        }

                        Rectangle {
                            width: parent.width
                            height: 150
                            radius: 10
                            color: root.panel
                            border.width: 1
                            border.color: root.border

                            Column {
                                anchors.centerIn: parent
                                spacing: 8

                                Text {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    text: "COMING NEXT"
                                    color: root.accent
                                    font.pixelSize: 11
                                    font.bold: true
                                    font.letterSpacing: 1
                                }

                                Text {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    text: root.currentPage + " workspace"
                                    color: "#e7eff7"
                                    font.pixelSize: 20
                                    font.bold: true
                                }

                                Text {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    text: "This workspace is scaffolded; its backend actions are not implemented yet."
                                    color: root.muted
                                    font.pixelSize: 11
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
