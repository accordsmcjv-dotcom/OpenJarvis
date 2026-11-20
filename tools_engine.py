import subprocess
import os
import platform
import datetime


def get_current_time():
    now = datetime.datetime.now()
    return {
        "date": now.strftime("%d-%m-%Y"),
        "time": now.strftime("%I:%M:%S %p"),
        "day": now.strftime("%A")
    }


def get_system_info():
    return {
        "platform": platform.system(),
        "android": os.getenv("ANDROID_ROOT", "Android"),
        "python": platform.python_version(),
        "architecture": platform.machine()
    }


def get_available_tools():
    """SHIVAM च्या API मधील प्रत्यक्ष उपलब्ध क्षमतांची यादी द्या."""
    return [
        {"name": "get_current_time", "description": "सध्याची तारीख, वेळ आणि वार मिळवा."},
        {"name": "get_system_info", "description": "Android डिव्हाइस आणि Python ची माहिती मिळवा."},
        {"name": "get_available_tools", "description": "SHIVAM ची उपलब्ध साधने आणि क्षमता तपासा."},
        {"name": "smart_calculate", "description": "बेरीज, वजाबाकी, गुणाकार, भागाकार आणि सुरक्षित गणिती उदाहरणे सोडवा."},
        {"name": "smart_unit_convert", "description": "लांबी, वजन, वेळ, तापमान आणि इतर समर्थित एककांचे रूपांतर करा."},
        {"name": "get_weather", "description": "बदनेरा-अमरावतीचे सध्याचे हवामान आणि अंदाज मिळवा."},
        {"name": "web_search", "description": "ताजी माहिती इंटरनेटवर शोधा."},
        {"name": "search_memory", "description": "जतन केलेली माहिती विषय किंवा Category नुसार शोधा."},
        {"name": "save_memory_item", "description": "वापरकर्त्याने स्पष्टपणे सांगितलेली दीर्घकालीन माहिती जतन करा."},
        {"name": "update_memory_item", "description": "वापरकर्त्याच्या स्पष्ट विनंतीनुसार आधीची Memory बदला."},
        {"name": "forget_memory_item", "description": "वापरकर्त्याच्या स्पष्ट विनंतीनुसार विशिष्ट Memory हटवा."},
        {"name": "memory_dashboard", "description": "Memory ची आकडेवारी आणि सुरक्षित नोंदींची स्थिती तपासा."},
        {"name": "detect_memory_conflicts", "description": "Memory मधील संभाव्य विरोधी नोंदी शोधा."},
        {"name": "recall_conversation_context", "description": "मागील संभाषणातील संबंधित संदर्भ शोधा."},
        {"name": "preview_memory_backup", "description": "जतन केलेल्या Memory Backup ची माहिती तपासा."},
        {"name": "memory_integrity_check", "description": "Memory आणि Category फाइलची सुसंगतता तपासा."},
        {"name": "list_memory_backups", "description": "उपलब्ध Memory Backup ची यादी दाखवा."},
        {"name": "add_note", "description": "नवीन नोंद किंवा टिपण जतन करा."},
        {"name": "list_notes", "description": "जतन केलेल्या नोंदींची यादी दाखवा."},
        {"name": "search_notes", "description": "नोंदींमध्ये शब्द किंवा विषय शोधा."},
        {"name": "delete_note", "description": "वापरकर्त्याच्या स्पष्ट विनंतीनुसार निवडलेली नोंद हटवा."},
        {"name": "open_android_app", "description": "वापरकर्त्याची मंजुरी मिळाल्यानंतर समर्थित Android App उघडा."},
    ]


def open_android_app(app_name):
    apps = {
        "chrome": ("Chrome", "com.android.chrome/com.google.android.apps.chrome.Main"),
        "youtube": ("YouTube", "com.google.android.youtube/.HomeActivity"),
        "gmail": ("Gmail", "com.google.android.gm/.ConversationListActivityGmail"),
        "whatsapp": ("WhatsApp", "com.whatsapp/.Main"),
        "camera": ("Camera", "com.android.camera/.Camera"),
        "settings": ("Settings", "com.android.settings/.Settings")
    }
    package_apps = {
        "maps": ("Google Maps", ["com.google.android.apps.maps"]),
        "calendar": ("Calendar", ["com.google.android.calendar", "com.android.calendar"]),
        "contacts": ("Contacts", ["com.google.android.contacts", "com.android.contacts"]),
        "messages": ("Messages", ["com.google.android.apps.messaging", "com.android.mms"]),
        "clock": ("Clock", ["com.google.android.deskclock", "com.android.deskclock"]),
        "files": ("Files", ["com.google.android.documentsui", "com.android.documentsui", "com.mi.android.globalFileexplorer"])
    }

    key = str(app_name).strip().lower()
    if key == "phone":
        command = ["am", "start", "-a", "android.intent.action.DIAL", "-d", "tel:"]
        label = "Phone"
    elif key in apps:
        label, activity = apps[key]
        command = ["am", "start", "-n", activity]
    elif key in package_apps:
        label, packages = package_apps[key]
        command = None
        for package in packages:
            probe = subprocess.run(["pm", "path", package], capture_output=True, text=True, timeout=5)
            if probe.returncode == 0 and probe.stdout.strip():
                command = ["monkey", "-p", package, "1"]
                break
        if command is None:
            return {"success": False, "app": label, "error": "हे App या फोनवर स्थापित नाही."}
    else:
        return {"success": False, "error": "हे App परवानगी यादीत नाही."}

    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=15)
        return {
            "success": result.returncode == 0 and "No activities found" not in result.stdout,
            "app": label,
            "message": result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
        }
    except Exception as error:
        return {"success": False, "app": label, "error": str(error)}


TOOL_REGISTRY = {
    "open_android_app": open_android_app,
    "get_current_time": get_current_time,
    "get_system_info": get_system_info,
    "get_available_tools": get_available_tools
}


def execute_tool(tool_name, arguments=None):
    tool = TOOL_REGISTRY.get(tool_name)

    if tool is None:
        return {"error": "हे Tool उपलब्ध नाही."}

    if arguments is None:
        arguments = {}

    if not isinstance(arguments, dict):
        return {"error": "Tool arguments अवैध आहेत."}

    try:
        if tool_name == "open_android_app":
            if set(arguments) != {"app_name"}:
                return {"error": "App चे नाव आवश्यक आहे."}
            app_name = arguments["app_name"]
            allowed = {"chrome", "youtube", "gmail", "whatsapp", "camera", "settings", "phone", "maps", "calendar", "contacts", "messages", "clock", "files"}
            if not isinstance(app_name, str) or app_name.lower().strip() not in allowed:
                return {"error": "हे App परवानगी यादीत नाही."}
            return {"result": tool(app_name)}

        if arguments:
            return {"error": "या Tool ला Arguments लागू नाहीत."}

        return {"result": tool()}

    except Exception as error:
        return {"error": str(error)}

