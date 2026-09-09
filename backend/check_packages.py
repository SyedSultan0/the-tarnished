"""
check_packages.py - Check if required packages are installed
Run this to see what's missing
"""

import sys
import importlib

# List of required packages
required_packages = {
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "pydantic_settings": "pydantic_settings",
    "twilio": "twilio",
    "fastai": "fastai",
    "torch": "torch",
    "pillow": "PIL",
    "numpy": "numpy",
    "requests": "requests",
    "python_multipart": "python_multipart",
    "python_dotenv": "python_dotenv",
}

print("=" * 60)
print("📦 CHECKING INSTALLED PACKAGES")
print("=" * 60)
print(f"Python version: {sys.version}")
print("")

missing_packages = []
installed_packages = []

for package_name, import_name in required_packages.items():
    try:
        module = importlib.import_module(import_name)
        version = getattr(module, "__version__", "unknown")
        installed_packages.append((package_name, version))
        print(f"✅ {package_name} v{version} - INSTALLED")
    except ImportError:
        missing_packages.append(package_name)
        print(f"❌ {package_name} - MISSING")

print("")
print("=" * 60)

if missing_packages:
    print(f"\n⚠️ MISSING PACKAGES ({len(missing_packages)}):")
    for pkg in missing_packages:
        print(f"   - {pkg}")
    
    print("\n📋 Install missing packages with:")
    
    # Group by type for better commands
    core = ["fastapi", "uvicorn", "python-multipart", "python-dotenv", "pydantic-settings"]
    ml = ["fastai", "pillow", "numpy"]
    whatsapp = ["twilio", "requests"]
    
    all_missing = [p for p in missing_packages if p in core or p in ml or p in whatsapp]
    
    if all_missing:
        print(f"\n   uv add {' '.join(all_missing)}")
    else:
        print(f"\n   uv add {' '.join(missing_packages)}")
    
else:
    print("\n✅ All required packages are installed!")
    print("\n📊 INSTALLED VERSIONS:")
    for pkg, ver in installed_packages:
        print(f"   {pkg}: {ver}")

print("")
print("=" * 60)