import os

# Simular entorno
__file__ = r"C:\Users\jauma\Desktop\gravity_isolated\modules\media_generator\__init__.py"
wf_folder = "workflows/simple/img2img"
s_file = "DefaultImg2Img.json"

res = os.path.normpath(os.path.join(os.path.dirname(__file__), wf_folder, s_file))
print(f"Resultado: {res}")

if os.sep == "\\":
    print("Sistema: Windows")
else:
    print("Sistema: POSIX")
