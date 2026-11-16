import Quickshell
import QtQuick

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
                            text: "RICE<span>"
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

                    Item { width: 1; height: 1; Layout.fillHeight: true }

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
                                text: "●  PROTOTYPE"
                                color: "#8fe0b8"
                                font.pixelSize: 9
                                font.bold: true
                                font.letterSpacing: 0.7
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
                                text: "RM  /  0.6"
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
                                    { label: "COMPONENTS", value: "02", note: "Declared entries" },
                                    { label: "PROTECTED", value: "01", note: "System / read-only" }
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
                                        text: "Caelestia + Hyprland"
                                        color: "#e5edf5"
                                        font.pixelSize: 13
                                        font.bold: true
                                    }

                                    Text {
                                        text: "READY"
                                        color: "#8fe0b8"
                                        font.pixelSize: 10
                                        font.bold: true
                                    }
                                }

                                Text {
                                    text: "1 ready   ·   1 skipped   ·   0 blocked     /     Preview only"
                                    color: root.muted
                                    font.pixelSize: 11
                                }
                            }
                        }

                        Text {
                            text: "This screen is a UI preview. Live system data and actions will be connected in a later release."
                            color: "#718092"
                            font.pixelSize: 10
                            wrapMode: Text.WordWrap
                        }
                    }

                    Column {
                        visible: root.currentPage !== "Overview"
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
                                    text: "The interface is scaffolded; backend integration is not connected yet."
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
