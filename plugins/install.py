# ==============================================================================
#  🎭 Cipher Elite - Advanced Plugin Manager (STABLE VERSION)
#  Safe Hot-Reload • Auto Dependency Install • No NoneType Errors
# ==============================================================================

import os
import sys
import ast
import asyncio
import importlib
import importlib.util
import site
from pathlib import Path
from telethon import events
from utils.utils import CipherElite
from utils.decorators import rishabh
from plugins.bot import add_handler

try:
    from plugins.bot import remove_handler
except ImportError:
    remove_handler = None

PLUGIN_DIR = "plugins"

PACKAGE_MAPPING = {
    "PIL": "Pillow",
    "cv2": "opencv-python",
    "skimage": "scikit-image",
    "google.generativeai": "google-generativeai",
    "google.genai": "google-generativeai",
    "genai": "google-generativeai",
    "bs4": "beautifulsoup4",
    "yaml": "PyYAML",
    "dateutil": "python-dateutil",
    "qrcode": "qrcode[pil]",
    "numpy": "numpy",
    "pandas": "pandas",
    "youtube_dl": "youtube_dl",
    "yt_dlp": "yt-dlp",
    "pydub": "pydub",
    "ffmpeg": "ffmpeg-python",
    "gtts": "gTTS"
}

# ------------------------------------------------------------------------------

def get_imports(source):
    tree = ast.parse(source)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for i in node.names:
                imports.add(i.name)
                imports.add(i.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
            imports.add(node.module.split(".")[0])
    return imports

def is_installed(module):
    if module in sys.builtin_module_names:
        return True
    try:
        return importlib.util.find_spec(module) is not None
    except Exception:
        return False

async def install_package(name):
    pip_name = PACKAGE_MAPPING.get(name, name)
    if pip_name in ["os", "sys", "math", "time", "json", "asyncio", "telethon", "utils", "plugins", "config"]:
        return True

    proc = await asyncio.create_subprocess_shell(
        f"{sys.executable} -m pip install {pip_name}",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL
    )
    await proc.communicate()

    importlib.invalidate_caches()
    try:
        site.addsitedir(site.getsitepackages()[0])
    except Exception:
        pass

    return proc.returncode == 0

def validate_code(path):
    try:
        src = Path(path).read_text(encoding="utf-8")
        ast.parse(src)
        return True, src
    except Exception as e:
        return False, str(e)

def get_plugin_key(source):
    try:
        tree = ast.parse(source)
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "add_handler":
                if n.args and isinstance(n.args[0], ast.Constant):
                    return n.args[0].value
    except Exception:
        pass
    return None

# ------------------------------------------------------------------------------

def init(client):
    add_handler(
        "developer",
        [
            ".install - Install or update plugin",
            ".uninstall <name> - Remove plugin"
        ],
        "CipherElite Plugin Manager"
    )

async def register_commands():

    @CipherElite.on(events.NewMessage(pattern=r"\.install$"))
    @rishabh()
    async def install_handler(event):
        await asyncio.sleep(0.4)

        reply = await event.get_reply_message()
        if not reply or not reply.file or not reply.file.name.endswith(".py"):
            await event.respond("Usage: Reply to a .py file with .install")
            return

        try:
            status = await event.respond("Analyzing plugin...")
        except Exception:
            return

        file_name = reply.file.name
        final_path = Path(PLUGIN_DIR) / file_name
        temp_path = Path(PLUGIN_DIR) / f"_tmp_{file_name}"
        module_name = f"plugins.{file_name[:-3]}"
        is_update = final_path.exists()

        try:
            await reply.download_media(file=temp_path)

            valid, data = validate_code(temp_path)
            if not valid:
                temp_path.unlink(missing_ok=True)
                await status.edit(f"Syntax error:\n{data}")
                return

            imports = get_imports(data)
            installed = 0

            for mod in imports:
                if mod in sys.builtin_module_names:
                    continue
                if mod in ["telethon", "utils", "plugins", "config", "google"]:
                    continue
                if not is_installed(mod):
                    ok = await install_package(mod)
                    if ok:
                        installed += 1

            if is_update:
                final_path.unlink(missing_ok=True)
            temp_path.rename(final_path)

            await status.edit("Activating plugin...")

            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
            else:
                importlib.import_module(module_name)

            module = sys.modules.get(module_name)
            if module:
                if hasattr(module, "init"):
                    module.init(event.client)
                if hasattr(module, "register_commands"):
                    await module.register_commands()

            msg = f"Plugin {'updated' if is_update else 'installed'}: {file_name}"
            if installed:
                msg += f"\nLibraries installed: {installed}"

            await status.edit(msg)

        except Exception as e:
            temp_path.unlink(missing_ok=True)
            try:
                await status.edit(f"Error: {e}")
            except Exception:
                pass

    # --------------------------------------------------------------------------

    @CipherElite.on(events.NewMessage(pattern=r"\.uninstall\s+(.+)"))
    @rishabh()
    async def uninstall_handler(event):
        await asyncio.sleep(0.3)

        name = event.pattern_match.group(1).strip()
        file_name = f"{name}.py" if not name.endswith(".py") else name
        path = Path(PLUGIN_DIR) / file_name
        module_name = f"plugins.{file_name[:-3]}"

        if not path.exists():
            await event.respond("Plugin not found.")
            return

        try:
            source = path.read_text(encoding="utf-8")
            key = get_plugin_key(source)

            path.unlink()
            sys.modules.pop(module_name, None)

            if key and remove_handler:
                remove_handler(key)

            await event.respond(f"Plugin removed: {file_name}")

        except Exception as e:
            await event.respond(f"Error: {e}")
