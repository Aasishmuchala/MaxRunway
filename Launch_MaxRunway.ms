/* Run this file with Scripting > Run Script in 3ds Max 2026. */
(
    local launcher = (getFilenamePath (getSourceFileName())) + "launch.py"
    if doesFileExist launcher then python.ExecuteFile launcher
    else messageBox "Keep Launch_MaxRunway.ms beside launch.py and the maxrunway folder."
)
