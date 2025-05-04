import os
import sys
import platform
import ctypes
from PIL import Image
from PyQt5.QtGui import QImage, QImageReader

# 리소스 경로를 얻는 함수 (패키징 여부에 관계없이 작동)
def get_resource_path(relative_path):
    """
    PyInstaller로 패키징된 경우와 일반 실행의 경우 모두에서 
    리소스 파일의 올바른 경로를 반환합니다.
    """
    try:
        # PyInstaller에 의해 생성된 임시 폴더 경로
        base_path = sys._MEIPASS
    except Exception:
        # 일반 Python 실행 시 스크립트 경로 사용
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)

def qimage_to_pil(qimage):
    """Converts a QImage to a PIL Image."""
    # QImage를 RGBA 형식으로 변환 (알파 채널 포함)
    qimage = qimage.convertToFormat(QImage.Format_RGBA8888)
    
    # QImage 데이터 버퍼 가져오기
    width = qimage.width()
    height = qimage.height()
    ptr = qimage.bits()
    ptr.setsize(qimage.byteCount())
    
    # 버퍼를 NumPy 배열로 변환 (메모리 복사 없이)
    # arr = np.array(ptr).reshape(height, width, 4) # NumPy 사용 시
    
    # 버퍼를 사용하여 PIL 이미지 생성 (메모리 복사)
    # 'RGBA' 모드와 데이터 순서(bytes)를 확인해야 할 수 있음
    # QImage.Format_RGBA8888은 보통 바이트 순서가 맞음
    pil_image = Image.frombytes("RGBA", (width, height), ptr.asstring())
    
    return pil_image 

def register_startup(enable: bool):
    """Windows 시작 프로그램에 애플리케이션을 등록하거나 해제합니다."""
    import winreg
    import sys
    import os

    app_name = "ImageCapturePAAK" # 레지스트리에 등록될 이름
    # 현재 실행 파일 경로 가져오기
    exe_path = sys.executable
    
    # .py 스크립트를 직접 실행하는 경우, 생성될 .exe 경로를 예상하기 어려움
    # 개발 중에는 .py 파일을 직접 등록하거나, 패키징 후 .exe 경로로 테스트 필요
    # 여기서는 sys.executable을 사용 (일반적으로 python.exe 또는 패키징된 exe)
    if not os.path.exists(exe_path):
         print(f"[Startup Error] Executable path not found: {exe_path}")
         return False

    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
        
        if enable:
            # 실행 경로에 --startup 인수를 추가하고 따옴표로 감싸기
            # 경로에 공백이 있을 경우를 대비
            startup_command = f'"{exe_path}" --startup'
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, startup_command)
            print(f"[Startup] Application registered to run on startup: {startup_command}")
        else:
            try:
                winreg.DeleteValue(key, app_name)
                print(f"[Startup] Application unregistered from startup.")
            except FileNotFoundError:
                # 키가 이미 없는 경우 무시
                print(f"[Startup] Application was not registered for startup.")
                pass 
                
        winreg.CloseKey(key)
        return True
        
    except OSError as e:
        print(f"[Startup Error] Failed to access registry: {e}")
        return False
    except Exception as e:
        print(f"[Startup Error] An unexpected error occurred: {e}")
        return False 