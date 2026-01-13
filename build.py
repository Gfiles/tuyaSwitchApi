import os
import subprocess
from datetime import datetime
import sys
import platform
import re

# --- Configuration ---
# Import version from the main app to keep it in one place.
#from ydPlayerNew import VERSION
VERSION = datetime.now().strftime("%Y.%m.%d")

APP_NAME = "tuyaServer"
DEVELOPER_NAME = "Gavin Goncalves"  # <-- IMPORTANT: Change this to your name/company
MAIN_SCRIPT = "app.py"
FILE_DESCRIPTION = "Controle Wifi Devices that are tuya compatibles"

# --- Update version in main script ---
print(f"Updating version in {MAIN_SCRIPT} to {VERSION}...")
try:
    with open(MAIN_SCRIPT, 'r', encoding='utf-8') as f:
        content = f.read()

    # Use regex to find and replace the version line: VERSION = "..."
    new_content, count = re.subn(
        r'^(VERSION\s*=\s*["\']).*?(["\'])',  # Regex to find VERSION = "..." or '...'
        fr'\g<1>{VERSION}\g<2>',             # Replace with the new version, keeping original quotes
        content,
        count=1,                             # Replace only the first occurrence
        flags=re.MULTILINE                   # Ensure ^ matches start of line
    )

    if count > 0:
        with open(MAIN_SCRIPT, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Successfully updated version in {MAIN_SCRIPT}.")
    else:
        print(f"Warning: Could not find a VERSION line to update in {MAIN_SCRIPT}.")
except Exception as e:
    print(f"An error occurred while updating version in {MAIN_SCRIPT}: {e}")
    
# --- Architecture-specific modifications ---
machine_arch = platform.machine().lower()
if machine_arch in ('aarch64', 'arm64'):
    print(f"ARM architecture ({machine_arch}) detected. Appending suffix to app name.")
    APP_NAME += "_arm64"
elif sys.platform.startswith('linux') and machine_arch in ('x86_64', 'i686', 'x86'):
    print(f"Linux x86 architecture ({machine_arch}) detected. Appending suffix to app name.")
    APP_NAME += "_deb"

# --- PyInstaller Build Command ---
if sys.platform == 'win32':
    pyinstaller_command = [
        'pyinstaller', 
        '--name', APP_NAME, 
        '--onefile', 
        '--clean', 
        '--add-data', 'templates*;.', 
        '--add-data', 'icon.png;.',
        '--icon=icon.png',
        MAIN_SCRIPT
    ]
    """
    pyinstaller_command = [
        '.venv\Scripts\pyinstaller', '--name', APP_NAME, '--onefile', '--clean', '--add-data', 'devcon.exe;.', '--add-data', 'icon.png;.', '--icon=icon.png',
        MAIN_SCRIPT
    ]
    """
else:
    pyinstaller_command = [
        'pyinstaller', 
        '--name', APP_NAME, 
        '--onefile', 
        '--clean',
        '--add-data', 'templates*:.', 
        '--add-data', 'icon.png:.',
        '--icon=icon.png',
        MAIN_SCRIPT
    ]


version_file_path = "version.txt"

# --- Platform-specific modifications for Windows ---
if sys.platform == 'win32':
    print("Windows platform detected. Adding version info and windowed mode.")
    # --- Generate Version File ---
    now = datetime.now()
    major, minor, patch = map(int, VERSION.split('.'))
    build = now.hour * 10000 + now.minute * 100 + now.second

    version_info_content = f"""
# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({major}, {minor}, {patch}, {build}),
    prodvers=({major}, {minor}, {patch}, {build}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'{DEVELOPER_NAME}'),
        StringStruct(u'FileDescription', u'{FILE_DESCRIPTION}'),
        StringStruct(u'FileVersion', u'{VERSION}.{build}'),
        StringStruct(u'InternalName', u'{APP_NAME}'),
        StringStruct(u'LegalCopyright', u'© {DEVELOPER_NAME}. All rights reserved.'),
        StringStruct(u'OriginalFilename', u'{APP_NAME}.exe'),
        StringStruct(u'ProductName', u'{APP_NAME}'),
        StringStruct(u'ProductVersion', u'{VERSION}')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""
    with open(version_file_path, "w", encoding="utf-8") as f:
        f.write(version_info_content)
    print(f"Generated '{version_file_path}' with version {VERSION}")

    pyinstaller_command.extend(['--version-file', version_file_path])
else:
    print(f"{sys.platform} platform detected. Building standard executable.")

# --- Run PyInstaller ---
print("\nRunning PyInstaller...")
try:
    subprocess.run(pyinstaller_command, check=True, text=True, capture_output=True)
    print("Build successful!")

    if sys.platform == 'win32':
        executable_path = os.path.join('dist', f'{APP_NAME}.exe')
    else:
        executable_path = os.path.join('dist', APP_NAME)
    print(f"Executable created at: {executable_path}")
except subprocess.CalledProcessError as e:
    print(f"Build failed!\nError:\n{e.stderr}")
finally:
    # Clean up the version file only if it was created (on Windows)
    if sys.platform == 'win32' and os.path.exists(version_file_path):
        os.remove(version_file_path)
