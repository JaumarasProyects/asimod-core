import os
from PIL import Image

def test_paths():
    paths = [
        "Resources/Styles/InvestigacionNeon/shared_bg.png",
        "Resources/Styles/InvestigacionNeon/main_bg.png",
        "Resources/Styles/InvestigacionNeon/chat_bg.png"
    ]
    
    print(f"Current Working Directory: {os.getcwd()}")
    
    for p in paths:
        exists = os.path.exists(p)
        abs_p = os.path.abspath(p)
        print(f"Path: {p}")
        print(f"  Exists: {exists}")
        print(f"  Absolute: {abs_p}")
        if exists:
            try:
                img = Image.open(p)
                print(f"  Load: Success ({img.size})")
            except Exception as e:
                print(f"  Load: Error - {e}")
        print("-" * 20)

if __name__ == "__main__":
    test_paths()
