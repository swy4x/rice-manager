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
    property var profilesData: ({})
    property var libraryData: ({})
    property string libraryError: ""
    property string profilesError: ""
    property string selectedManifest: ""
    property string selectedProfileName: ""
    property var detailData: ({})
    property string detailError: ""
    property string importSource: ""
    property string importError: ""
    property var importPreview: ({})
    property bool importApplyRequested: false
    property string backendStatus: "LOADING"
    property string backendError: ""

    function refreshPlan() {
        backendStatus = "CHECKING"
        backendError = ""
        planProcess.running = true
        profilesProcess.running = true
        libraryProcess.running = true
        if (currentPage === "Profile Details" && selectedManifest.length > 0) {
            detailData = ({})
            detailError = ""
            detailProcess.running = true
        }
    }

    function openProfile(manifest, name) {
        selectedManifest = manifest
        selectedProfileName = name
        detailData = ({})
        detailError = ""
        currentPage = "Profile Details"
        detailProcess.running = true
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


    Process {
        id: profilesProcess
        command: [
            Quickshell.shellDir + "/../.venv/bin/rice-manager",
            "profile",
            "list",
            Quickshell.shellDir + "/../examples",
            "--json"
        ]
        running: true

        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    root.profilesData = JSON.parse(this.text)
                    root.profilesError = ""
                } catch (error) {
                    root.profilesError = String(error)
                }
            }
        }

        stderr: StdioCollector {
            onStreamFinished: {
                if (this.text.trim().length > 0)
                    root.profilesError = this.text.trim()
            }
        }
    }


    Process {
        id: libraryProcess
        command: [
            Quickshell.shellDir + "/../.venv/bin/rice-manager",
            "profile", "list",
            Quickshell.env("HOME") + "/.local/share/rice-manager/profiles",
            "--json"
        ]
        running: true

        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    root.libraryData = JSON.parse(this.text)
                    root.libraryError = ""
                } catch (error) {
                    root.libraryError = String(error)
                }
            }
        }

        stderr: StdioCollector {
            onStreamFinished: {
                if (this.text.trim().length > 0)
                    root.libraryError = this.text.trim()
            }
        }
    }

    Process {
        id: detailProcess
        command: [
            Quickshell.shellDir + "/../.venv/bin/rice-manager",
            "profile",
            "plan",
            root.selectedManifest,
            "--json"
        ]
        running: false

        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    root.detailData = JSON.parse(this.text)
                    root.detailError = ""
                } catch (error) {
                    root.detailError = String(error)
                }
            }
        }

        stderr: StdioCollector {
            onStreamFinished: {
                if (this.text.trim().length > 0)
                    root.detailError = this.text.trim()
            }
        }

        onExited: (exitCode, exitStatus) => {
            if (exitCode !== 0 && root.detailError.length === 0)
                root.detailError = "Profile details command failed."
        }
    }


    Process {
        id: importProcess
        command: [
            Quickshell.shellDir + "/../.venv/bin/rice-manager",
            "profile", "import", root.importSource,
            "--json"
        ].concat(root.importApplyRequested ? ["--apply"] : [])
        running: false

        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    root.importPreview = JSON.parse(this.text)
                    root.importError = ""
                    if (!root.importApplyRequested)
                        root.importError = "Preview ready. Review the file list before applying."
                    else {
                        root.importError = "Import completed successfully."
                        root.importApplyRequested = false
                        root.refreshPlan()
                    }
                } catch (error) {
                    root.importError = String(error)
                }
            }
        }

        stderr: StdioCollector {
            onStreamFinished: {
                if (this.text.trim().length > 0) {
                    root.importError = this.text.trim()
                    root.importApplyRequested = false
                }
            }
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
                            model: ["Overview", "Profiles", "Import", "Components", "Backups", "Settings"]

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
                                                "Import": "⇧",
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
                                text: "RM  /  0.14"
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
                                    text: root.profilesData.profiles
                                        ? root.profilesData.profiles.length + " discovered profile entries"
                                        : (root.profilesError.length > 0 ? root.profilesError : "Discovering manifests…")
                                    color: root.muted
                                    font.pixelSize: 11
                                }
                            }
                            Item { width: 1; height: 1 }
                        }

                        Repeater {
                            model: root.profilesData.profiles ? root.profilesData.profiles : []
                            delegate: Rectangle {
                                required property var modelData
                                width: parent.width
                                height: modelData.valid ? 164 : 86
                                radius: 10
                                color: root.panel
                                border.width: 1
                                border.color: modelData.valid ? root.border : "#684044"

                                Column {
                                    anchors.fill: parent
                                    anchors.margins: 16
                                    spacing: 9

                                    Row {
                                        width: parent.width
                                        spacing: 10
                                        Text {
                                            text: modelData.valid ? "▤" : "!"
                                            color: modelData.valid ? root.accent : "#ff7b86"
                                            font.pixelSize: 19
                                        }
                                        Column {
                                            spacing: 3
                                            Text {
                                                text: modelData.valid ? modelData.name : modelData.directory + "  /  INVALID"
                                                color: "#edf4fa"
                                                font.pixelSize: 15
                                                font.bold: true
                                            }
                                            Text {
                                                text: modelData.valid ? "ID  /  " + modelData.id + "     VERSION  /  " + modelData.version : modelData.manifest
                                                color: root.muted
                                                font.pixelSize: 9
                                            }
                                        }
                                        Item { width: 1; height: 1 }
                                        Text {
                                            text: modelData.valid ? (modelData.blocked ? "BLOCKED" : "VALID") : "INVALID"
                                            color: modelData.valid ? (modelData.blocked ? "#ff7b86" : "#8fe0b8") : "#ff7b86"
                                            font.pixelSize: 9
                                            font.bold: true
                                        }
                                    }

                                    Text {
                                        visible: modelData.valid
                                        width: parent.width
                                        text: modelData.description
                                        color: "#b6c4d2"
                                        font.pixelSize: 10
                                        wrapMode: Text.WordWrap
                                    }

                                    Row {
                                        visible: modelData.valid
                                        spacing: 18
                                        Text { text: "COMPONENTS  " + modelData.component_count; color: root.muted; font.pixelSize: 9 }
                                        Text { text: "READY  " + modelData.summary.ready; color: "#8fe0b8"; font.pixelSize: 9 }
                                        Text { text: "SKIPPED  " + modelData.summary.skipped; color: root.accent; font.pixelSize: 9 }
                                        Text { text: "BLOCKED  " + modelData.summary.blocked; color: modelData.summary.blocked > 0 ? "#ff7b86" : root.muted; font.pixelSize: 9 }
                                    }

                                    Text {
                                        visible: !modelData.valid
                                        width: parent.width
                                        text: modelData.error
                                        color: "#ff9aa2"
                                        font.pixelSize: 10
                                        wrapMode: Text.WordWrap
                                    }

                                    Text {
                                        width: parent.width
                                        text: modelData.manifest
                                        color: "#718092"
                                        font.pixelSize: 9
                                        wrapMode: Text.WrapAnywhere
                                    }
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    enabled: modelData.valid
                                    cursorShape: modelData.valid ? Qt.PointingHandCursor : Qt.ArrowCursor
                                    onClicked: root.openProfile(modelData.manifest, modelData.name)
                                }
                            }
                        }

                        Text {
                            visible: root.profilesData.profiles && root.profilesData.profiles.length === 0
                            text: "No profiles found. Add a profile folder containing manifest.json under examples/."
                            color: root.muted
                            font.pixelSize: 11
                            wrapMode: Text.WordWrap
                        }

                        Text {
                            text: "Discovery validates manifests and runs a read-only preflight. No profile is activated and no configuration files are changed."
                            color: "#718092"
                            font.pixelSize: 10
                            wrapMode: Text.WordWrap
                        }

                        Rectangle {
                            width: parent.width
                            height: 1
                            color: root.border
                        }

                        Column {
                            width: parent.width
                            spacing: 10
                            Text {
                                text: "MY PROFILE LIBRARY"
                                color: root.accent
                                font.pixelSize: 10
                                font.bold: true
                                font.letterSpacing: 1.3
                            }
                            Text {
                                text: root.libraryData.profiles
                                    ? root.libraryData.profiles.length + " imported profiles"
                                    : (root.libraryError.length > 0 ? "Library not created yet — import a profile to get started." : "Loading your library…")
                                color: root.muted
                                font.pixelSize: 11
                            }
                            Repeater {
                                model: root.libraryData.profiles ? root.libraryData.profiles : []
                                delegate: Rectangle {
                                    required property var modelData
                                    width: parent.width
                                    height: modelData.valid ? 116 : 76
                                    radius: 9
                                    color: root.panel
                                    border.width: 1
                                    border.color: modelData.valid ? root.border : "#684044"
                                    Column {
                                        anchors.fill: parent
                                        anchors.margins: 13
                                        spacing: 6
                                        Row {
                                            width: parent.width
                                            Text {
                                                text: modelData.valid ? modelData.name : modelData.directory + " / INVALID"
                                                color: "#edf4fa"
                                                font.pixelSize: 13
                                                font.bold: true
                                            }
                                            Item { width: 1; height: 1 }
                                            Text {
                                                text: modelData.valid ? (modelData.blocked ? "BLOCKED" : "VALID") : "INVALID"
                                                color: modelData.valid ? (modelData.blocked ? "#ff7b86" : "#8fe0b8") : "#ff7b86"
                                                font.pixelSize: 9
                                                font.bold: true
                                            }
                                        }
                                        Text {
                                            text: modelData.valid ? "ID / " + modelData.id + "    VERSION / " + modelData.version : modelData.error
                                            color: root.muted
                                            font.pixelSize: 10
                                            wrapMode: Text.WordWrap
                                        }
                                        Text {
                                            text: modelData.manifest
                                            color: "#718092"
                                            font.pixelSize: 9
                                            wrapMode: Text.WrapAnywhere
                                        }
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        enabled: modelData.valid
                                        cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                                        onClicked: root.openProfile(modelData.manifest, modelData.name)
                                    }
                                }
                            }
                        }
                        width: parent.width
                        spacing: 14

                        Text {
                            text: "IMPORT A LOCAL PROFILE"
                            color: root.accent
                            font.pixelSize: 10
                            font.bold: true
                            font.letterSpacing: 1.3
                        }
                        Text {
                            text: "Enter a folder containing manifest.json. Preview validates the manifest and lists every file. Nothing is copied until you explicitly apply."
                            color: root.muted
                            font.pixelSize: 11
                            wrapMode: Text.WordWrap
                        }
                        Rectangle {
                            width: parent.width
                            height: 46
                            radius: 7
                            color: "#101923"
                            border.width: 1
                            border.color: root.border
                            TextInput {
                                id: importPathInput
                                anchors.fill: parent
                                anchors.leftMargin: 12
                                anchors.rightMargin: 12
                                verticalAlignment: TextInput.AlignVCenter
                                color: "#e7eff7"
                                font.pixelSize: 12
                                selectByMouse: true
                                text: root.importSource
                                onTextChanged: {
                                    root.importSource = text
                                    root.importPreview = ({})
                                    root.importError = ""
                                }
                                clip: true
                            }
                        }
                        Row {
                            spacing: 10
                            Rectangle {
                                width: 112
                                height: 36
                                radius: 7
                                color: "#1a2b38"
                                border.width: 1
                                border.color: "#315064"
                                Text {
                                    anchors.centerIn: parent
                                    text: "PREVIEW"
                                    color: root.accent
                                    font.pixelSize: 10
                                    font.bold: true
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    enabled: root.importSource.trim().length > 0 && !importProcess.running
                                    cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                                    onClicked: {
                                        root.importPreview = ({})
                                        root.importError = ""
                                        root.importApplyRequested = false
                                        importProcess.running = true
                                    }
                                }
                            }
                            Rectangle {
                                width: 112
                                height: 36
                                radius: 7
                                color: "#173126"
                                border.width: 1
                                border.color: "#35664e"
                                opacity: root.importPreview.dry_run === true && !importProcess.running ? 1 : 0.45
                                Text {
                                    anchors.centerIn: parent
                                    text: "APPLY IMPORT"
                                    color: "#8fe0b8"
                                    font.pixelSize: 10
                                    font.bold: true
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    enabled: root.importPreview.dry_run === true && !importProcess.running
                                    cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                                    onClicked: {
                                        root.importApplyRequested = true
                                        root.importError = "Importing into the Rice Manager profile library…"
                                        importProcess.running = true
                                    }
                                }
                            }
                        }
                        Text {
                            width: parent.width
                            text: root.importError
                            color: root.importError.indexOf("successfully") >= 0 ? "#8fe0b8" : (root.importError.indexOf("Preview ready") >= 0 ? root.accent : "#ff9aa2")
                            font.pixelSize: 11
                            wrapMode: Text.WordWrap
                        }
                        Rectangle {
                            visible: root.importPreview.profile_id !== undefined
                            width: parent.width
                            height: 104 + (root.importPreview.files ? root.importPreview.files.length * 22 : 0)
                            radius: 9
                            color: root.panel
                            border.width: 1
                            border.color: root.border
                            Column {
                                anchors.fill: parent
                                anchors.margins: 14
                                spacing: 7
                                Text {
                                    text: root.importPreview.profile_name + "  /  " + root.importPreview.profile_id
                                    color: "#edf4fa"
                                    font.pixelSize: 14
                                    font.bold: true
                                }
                                Text {
                                    text: "DESTINATION  " + root.importPreview.destination
                                    color: root.muted
                                    font.pixelSize: 10
                                    wrapMode: Text.WrapAnywhere
                                }
                                Text {
                                    text: "FILES  " + root.importPreview.file_count + "    SIZE  " + root.importPreview.total_bytes + " bytes"
                                    color: root.accent
                                    font.pixelSize: 10
                                }
                                Repeater {
                                    model: root.importPreview.files ? root.importPreview.files : []
                                    delegate: Text {
                                        required property var modelData
                                        text: modelData.path + "  (" + modelData.size + " bytes)"
                                        color: "#b6c4d2"
                                        font.pixelSize: 10
                                        wrapMode: Text.WrapAnywhere
                                    }
                                }
                            }
                        }
                        Text {
                            text: "Library: ~/.local/share/rice-manager/profiles/  ·  Existing profiles are never overwritten. Imported files are stored separately; they are not installed or activated."
                            color: "#718092"
                            font.pixelSize: 10
                            wrapMode: Text.WordWrap
                        }
                    }

                    Column {
                        visible: root.currentPage === "Profile Details"
                        width: parent.width
                        spacing: 14

                        Row {
                            width: parent.width
                            spacing: 12

                            Rectangle {
                                width: 82
                                height: 30
                                radius: 6
                                color: "#18232e"
                                border.width: 1
                                border.color: root.border
                                Text {
                                    anchors.centerIn: parent
                                    text: "← BACK"
                                    color: root.accent
                                    font.pixelSize: 10
                                    font.bold: true
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: root.currentPage = "Profiles"
                                }
                            }

                            Column {
                                spacing: 4
                                Text {
                                    text: root.selectedProfileName
                                    color: "#edf4fa"
                                    font.pixelSize: 17
                                    font.bold: true
                                }
                                Text {
                                    text: root.selectedManifest
                                    color: root.muted
                                    font.pixelSize: 9
                                    wrapMode: Text.WrapAnywhere
                                }
                            }
                        }

                        Text {
                            visible: root.detailError.length > 0
                            width: parent.width
                            text: root.detailError
                            color: "#ff9aa2"
                            font.pixelSize: 11
                            wrapMode: Text.WordWrap
                        }

                        Row {
                            visible: root.detailData.summary !== undefined
                            spacing: 18
                            Text { text: "READY  " + (root.detailData.summary ? root.detailData.summary.ready : 0); color: "#8fe0b8"; font.pixelSize: 10 }
                            Text { text: "SKIPPED  " + (root.detailData.summary ? root.detailData.summary.skipped : 0); color: root.accent; font.pixelSize: 10 }
                            Text { text: "BLOCKED  " + (root.detailData.summary ? root.detailData.summary.blocked : 0); color: "#ff7b86"; font.pixelSize: 10 }
                        }

                        Repeater {
                            model: root.detailData.items ? root.detailData.items : []
                            delegate: Rectangle {
                                required property var modelData
                                width: parent.width
                                height: 166
                                radius: 10
                                color: root.panel
                                border.width: 1
                                border.color: root.statusColor(modelData.status)

                                Column {
                                    anchors.fill: parent
                                    anchors.margins: 14
                                    spacing: 6

                                    Row {
                                        width: parent.width
                                        Text {
                                            width: parent.width - 100
                                            text: modelData.name + "  /  " + modelData.component_id
                                            color: "#edf4fa"
                                            font.pixelSize: 12
                                            font.bold: true
                                            elide: Text.ElideRight
                                        }
                                        Text {
                                            text: modelData.status.toUpperCase()
                                            color: root.statusColor(modelData.status)
                                            font.pixelSize: 9
                                            font.bold: true
                                        }
                                    }

                                    Text {
                                        text: modelData.kind.toUpperCase() + "  ·  " + modelData.scope.toUpperCase()
                                            + (modelData.required ? "  ·  REQUIRED" : "  ·  OPTIONAL")
                                            + (modelData.read_only ? "  ·  READ-ONLY" : "")
                                        color: root.accent
                                        font.pixelSize: 9
                                    }
                                    Text {
                                        width: parent.width
                                        text: "DECLARED PATH  " + modelData.source
                                        color: "#b6c4d2"
                                        font.pixelSize: 10
                                        wrapMode: Text.WrapAnywhere
                                    }
                                    Text {
                                        width: parent.width
                                        text: "RESOLVED PATH  " + modelData.path
                                        color: "#b6c4d2"
                                        font.pixelSize: 10
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
                            visible: root.detailData.items && root.detailData.items.length === 0
                            text: "This profile has no component entries."
                            color: root.muted
                            font.pixelSize: 11
                        }

                        Text {
                            visible: Object.keys(root.detailData).length === 0 && root.detailError.length === 0
                            text: "Loading read-only profile details…"
                            color: root.muted
                            font.pixelSize: 11
                        }

                        Text {
                            text: "Profile details are generated from the validated manifest and a read-only preflight. No configuration files are changed."
                            color: "#718092"
                            font.pixelSize: 10
                            wrapMode: Text.WordWrap
                        }
                    }

                    Column {
                        visible: root.currentPage !== "Overview" && root.currentPage !== "Components" && root.currentPage !== "Profiles" && root.currentPage !== "Import" && root.currentPage !== "Profile Details"
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
