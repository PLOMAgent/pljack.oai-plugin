import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

Panel {
  id: root
  moduleName: "pljack.oai-plugin"
  ipcTarget: "pljack.oai-plugin"
  manageIpc: false

  property var anchorItem: null
  property var hostWidget: null
  readonly property var barIdentity: hostWidget || root
  readonly property string configFile: Quickshell.env("HOME") + "/.config/omarchy/screensaver-text.json"
  property string editText: ""
  property string secondsText: ""
  property int lockSeconds: 300
  property string errorMessage: ""
  property bool confirmUninstall: false
  readonly property color contentForeground: bar ? bar.foreground : Color.foreground
  readonly property string contentFontFamily: bar ? bar.fontFamily : Style.font.family

  function minutesLabel(seconds) {
    if (!/^[0-9]+$/.test(seconds) || Number(seconds) < 1) return ""
    var minutes = Math.round(Number(seconds) / 60 * 100) / 100
    return "≈ " + minutes + (minutes === 1 ? " minute" : " minutes")
  }

  function open() {
    errorMessage = ""
    confirmUninstall = false
    editText = ""
    loadProcess.running = true
    timeoutProcess.running = true
    dependencyProcess.running = true
    controller.show()
  }

  function close() { controller.hide() }
  function toggle() { if (opened) close(); else open() }

  function saveAndLaunch() {
    if (saveProcess.running || restoreProcess.running || uninstallProcess.running) return
    if (!editText.trim()) {
      errorMessage = "Enter some text first."
      return
    }
    if (!/^[0-9]+$/.test(secondsText) || Number(secondsText) < 1 || Number(secondsText) > 86400) {
      errorMessage = "Enter a number of seconds from 1 to 86400."
      return
    }
    if (Number(secondsText) >= lockSeconds) {
      errorMessage = "Screensaver must start before lock (" + lockSeconds + "s)."
      return
    }
    errorMessage = ""
    saveProcess.command = [
      "python3",
      Quickshell.env("HOME") + "/.config/omarchy/plugins/pljack.oai-plugin/screensaver_text.py",
      editText,
      secondsText
    ]
    saveProcess.running = true
  }

  function restoreDefault() {
    if (saveProcess.running || restoreProcess.running || uninstallProcess.running) return
    errorMessage = ""
    restoreProcess.running = true
  }

  function scheduleUninstall() {
    if (!confirmUninstall || saveProcess.running || restoreProcess.running || uninstallProcess.running) return
    errorMessage = ""
    uninstallProcess.running = true
  }

  Process {
    id: loadProcess
    command: ["python3", Quickshell.env("HOME") + "/.config/omarchy/plugins/pljack.oai-plugin/screensaver_text.py", "--read-text"]
    stdout: SplitParser {
      onRead: function(line) { root.editText = line }
    }
    onExited: function(exitCode) {
      if (exitCode !== 0) root.errorMessage = "Could not read screensaver text."
    }
  }

  Process {
    id: timeoutProcess
    command: ["python3", Quickshell.env("HOME") + "/.config/omarchy/plugins/pljack.oai-plugin/screensaver_text.py", "--read-timeouts"]
    stdout: SplitParser {
      onRead: function(line) {
        try {
          var timeouts = JSON.parse(line)
          root.secondsText = String(timeouts.screensaver)
          root.lockSeconds = Number(timeouts.lock)
        } catch (e) { root.errorMessage = "Could not read idle settings." }
      }
    }
    onExited: function(exitCode) {
      if (exitCode !== 0) root.errorMessage = "Could not read idle settings."
    }
  }

  Process {
    id: dependencyProcess
    command: ["python3", Quickshell.env("HOME") + "/.config/omarchy/plugins/pljack.oai-plugin/screensaver_text.py", "--check-figlet"]
    onExited: function(exitCode) {
      if (exitCode === 3) root.errorMessage = "figlet is missing. Install with: omarchy pkg add figlet"
      else if (exitCode === 4) root.errorMessage = "Bundled screensaver font is missing. Reinstall or update the plugin."
    }
  }

  Process {
    id: saveProcess
    onExited: function(exitCode) {
      if (exitCode === 0) root.close()
      else if (exitCode === 3) root.errorMessage = "figlet is missing. Install with: omarchy pkg add figlet"
      else if (exitCode === 4) root.errorMessage = "Bundled screensaver font is missing. Reinstall or update the plugin."
      else root.errorMessage = "Could not save or launch the screensaver."
    }
  }

  Process {
    id: restoreProcess
    command: ["python3", Quickshell.env("HOME") + "/.config/omarchy/plugins/pljack.oai-plugin/screensaver_text.py", "--restore"]
    onExited: function(exitCode) {
      if (exitCode === 0) {
        root.editText = "Omarchy"
        root.secondsText = "150"
        root.close()
      } else root.errorMessage = "Could not restore the default screensaver."
    }
  }

  Process {
    id: uninstallProcess
    command: ["python3", Quickshell.env("HOME") + "/.config/omarchy/plugins/pljack.oai-plugin/screensaver_text.py", "--uninstall"]
    onExited: function(exitCode) {
      if (exitCode === 0) root.close()
      else root.errorMessage = "Could not schedule plugin uninstall."
    }
  }

  KeyboardPanel {
    id: panel
    anchorItem: root.anchorItem
    owner: root.barIdentity
    bar: root.bar
    open: root.opened
    centerOnBar: false
    contentWidth: Style.space(420)
    contentHeight: Style.space(root.confirmUninstall ? 379 : 329)

    ColumnLayout {
      anchors.fill: parent
      anchors.margins: Style.space(14)
      spacing: Style.space(12)

      RowLayout {
        Layout.fillWidth: true
        spacing: Style.space(8)

        Text {
          text: "Screensaver Text"
          color: root.contentForeground
          font.family: root.contentFontFamily
          font.pixelSize: 16
          font.bold: true
        }
        Item { Layout.fillWidth: true }
        Rectangle {
          Layout.preferredWidth: Style.space(94)
          Layout.preferredHeight: Style.space(30)
          visible: !root.confirmUninstall
          radius: 4
          color: Qt.darker(Color.popups.background, 1.15)
          border.color: Color.accent
          border.width: 1
          Text {
            anchors.centerIn: parent
            text: "Uninstall"
            color: root.contentForeground
            font.family: root.contentFontFamily
            font.pixelSize: 13
          }
          MouseArea {
            anchors.fill: parent
            enabled: !saveProcess.running && !restoreProcess.running && !uninstallProcess.running
            cursorShape: Qt.PointingHandCursor
            onClicked: root.confirmUninstall = true
          }
        }
      }

      Text {
        Layout.fillWidth: true
        visible: root.confirmUninstall
        text: "Uninstall restores stock artwork and the 150-second timeout."
        wrapMode: Text.WordWrap
        color: root.contentForeground
        font.family: root.contentFontFamily
        font.pixelSize: 12
      }

      RowLayout {
        Layout.fillWidth: true
        visible: root.confirmUninstall
        spacing: Style.space(8)
        Text {
          Layout.fillWidth: true
          text: "Reset & remove?"
          color: root.contentForeground
          font.family: root.contentFontFamily
          font.pixelSize: 13
        }
        Rectangle {
          Layout.preferredWidth: Style.space(104)
          Layout.preferredHeight: Style.space(30)
          radius: 4
          color: Color.accent
          Text {
            anchors.centerIn: parent
            text: uninstallProcess.running ? "Removing..." : "Yes, remove"
            color: Color.popups.background
            font.family: root.contentFontFamily
            font.pixelSize: 12
          }
          MouseArea {
            anchors.fill: parent
            enabled: !uninstallProcess.running
            cursorShape: Qt.PointingHandCursor
            onClicked: root.scheduleUninstall()
          }
        }
        Rectangle {
          Layout.preferredWidth: Style.space(65)
          Layout.preferredHeight: Style.space(30)
          radius: 4
          color: Qt.darker(Color.popups.background, 1.15)
          border.color: Color.accent
          border.width: 1
          Text {
            anchors.centerIn: parent
            text: "Keep"
            color: root.contentForeground
            font.family: root.contentFontFamily
            font.pixelSize: 12
          }
          MouseArea {
            anchors.fill: parent
            enabled: !uninstallProcess.running
            cursorShape: Qt.PointingHandCursor
            onClicked: root.confirmUninstall = false
          }
        }
      }

      Rectangle {
        Layout.fillWidth: true
        Layout.preferredHeight: Style.space(40)
        radius: 4
        color: Qt.darker(Color.popups.background, 1.3)
        border.color: Color.accent
        border.width: 2

        TextInput {
          anchors.fill: parent
          anchors.margins: Style.space(8)
          text: root.editText
          color: root.contentForeground
          selectionColor: Color.accent
          selectedTextColor: root.contentForeground
          font.family: root.contentFontFamily
          font.pixelSize: 14
          selectByMouse: true
          verticalAlignment: TextInput.AlignVCenter
          onTextChanged: root.editText = text
          Keys.onReturnPressed: root.saveAndLaunch()
          Keys.onEscapePressed: root.close()
        }
      }

      Text {
        text: "Seconds Before Screen Saver"
        color: root.contentForeground
        font.family: root.contentFontFamily
        font.pixelSize: 14
      }

      Rectangle {
        Layout.fillWidth: true
        Layout.preferredHeight: Style.space(40)
        radius: 4
        color: Qt.darker(Color.popups.background, 1.3)
        border.color: Color.accent
        border.width: 2

        TextInput {
          anchors.fill: parent
          anchors.margins: Style.space(8)
          text: root.secondsText
          color: root.contentForeground
          selectionColor: Color.accent
          selectedTextColor: root.contentForeground
          font.family: root.contentFontFamily
          font.pixelSize: 14
          selectByMouse: true
          verticalAlignment: TextInput.AlignVCenter
          inputMethodHints: Qt.ImhDigitsOnly
          maximumLength: 5
          validator: IntValidator { bottom: 1; top: 86400 }
          onTextChanged: root.secondsText = text
          Keys.onReturnPressed: root.saveAndLaunch()
          Keys.onEscapePressed: root.close()
        }
      }

      Text {
        Layout.fillWidth: true
        Layout.topMargin: -Style.space(8)
        text: root.minutesLabel(root.secondsText)
        visible: text !== ""
        color: root.contentForeground
        opacity: 0.7
        font.family: root.contentFontFamily
        font.pixelSize: 12
      }

      Text {
        Layout.fillWidth: true
        text: root.errorMessage
        wrapMode: Text.WordWrap
        color: Color.accent
        visible: root.errorMessage !== ""
        font.family: root.contentFontFamily
        font.pixelSize: 12
      }

      Item { Layout.fillHeight: true }

      RowLayout {
        Layout.alignment: Qt.AlignLeft
        Layout.bottomMargin: 20
        spacing: Style.space(10)

        Rectangle {
          Layout.preferredWidth: Style.space(135)
          Layout.preferredHeight: Style.space(34)
          radius: 4
          color: Color.accent
          opacity: saveProcess.running || restoreProcess.running ? 0.6 : 1.0

          Text {
            anchors.centerIn: parent
            text: saveProcess.running ? "Saving..." : "Save & Preview"
            color: Color.popups.background
            font.family: root.contentFontFamily
            font.pixelSize: 13
          }
          MouseArea {
            anchors.fill: parent
            enabled: !saveProcess.running && !restoreProcess.running
            cursorShape: Qt.PointingHandCursor
            onClicked: root.saveAndLaunch()
          }
        }

        Rectangle {
          Layout.preferredWidth: Style.space(135)
          Layout.preferredHeight: Style.space(34)
          radius: 4
          color: Qt.darker(Color.popups.background, 1.15)
          border.color: Color.accent
          border.width: 1
          opacity: restoreProcess.running || saveProcess.running ? 0.6 : 1.0

          Text {
            anchors.centerIn: parent
            text: restoreProcess.running ? "Restoring..." : "Restore Default"
            color: root.contentForeground
            font.family: root.contentFontFamily
            font.pixelSize: 13
          }
          MouseArea {
            anchors.fill: parent
            enabled: !restoreProcess.running && !saveProcess.running
            cursorShape: Qt.PointingHandCursor
            onClicked: root.restoreDefault()
          }
        }

        Rectangle {
          Layout.preferredWidth: Style.space(80)
          Layout.preferredHeight: Style.space(34)
          radius: 4
          color: Qt.darker(Color.popups.background, 1.15)
          border.color: Color.accent
          border.width: 1

          Text {
            anchors.centerIn: parent
            text: "Cancel"
            color: root.contentForeground
            font.family: root.contentFontFamily
            font.pixelSize: 13
          }
          MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: root.close()
          }
        }
      }
    }
  }
}
