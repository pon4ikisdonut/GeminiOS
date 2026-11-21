// GeminiOS Material Design 3 Floating Bottom Pill Panel Layout for KDE Plasma 6
var panel = new Panel("org.kde.panel");
panel.location = "bottom";
panel.height = 48;
panel.floating = true;
panel.hiding = "none";

var kickoff = panel.addWidget("org.kde.plasma.kickoff");
kickoff.currentConfigGroup = ["General"];
kickoff.writeConfig("icon", "geminios");

panel.addWidget("org.kde.plasma.marginsseparator");

var taskManager = panel.addWidget("org.kde.plasma.icontasks");
taskManager.currentConfigGroup = ["General"];
taskManager.writeConfig("launchers", [
    "applications:org.kde.dolphin.desktop",
    "applications:org.kde.konsole.desktop",
    "applications:systemsettings.desktop"
]);

panel.addWidget("org.kde.plasma.marginsseparator");
panel.addWidget("org.geminios.panelwidget");
panel.addWidget("org.kde.plasma.systemtray");
panel.addWidget("org.kde.plasma.digitalclock");
