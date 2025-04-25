import sys
import os
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt
import ctypes
import traceback

# 로깅 설정 가져오기
from log_setup import setup_logging

# 유틸리티 함수 가져오기
from utils import get_resource_path

# 사용자 정의 모듈 가져오기
from capture_module import ScreenCapture
from gui_module import CaptureUI
from config_module import ConfigManager
from editor_module import ImageEditor

def main():
    # 로깅 설정 적용
    setup_logging()

    # High DPI 스케일링 활성화
    # QApplication 인스턴스 생성 전에 설정해야 합니다.
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    
    # 애플리케이션 초기화
    app = QApplication(sys.argv)
    app.setApplicationName('Snipix')
    
    # 설정 관리자 초기화
    config_manager = ConfigManager()
    
    # 캡처 모듈 초기화 및 설정 전달
    capture_module = ScreenCapture(config_manager)
    
    # UI 초기화
    ui = CaptureUI(capture_module)
    
    # 애플리케이션 아이콘 설정 (Windows에서만 동작)
    try:
        # 패키징 여부에 관계없이 작동하는 아이콘 경로 사용
        icon_path = get_resource_path(os.path.join('assets', 'icon.ico'))
        
        if os.path.exists(icon_path):
            # 앱 아이콘 설정
            app.setWindowIcon(QIcon(icon_path))
            # 창 제목 표시줄에도 아이콘 설정
            ui.setWindowIcon(QIcon(icon_path))
            
            # Windows 작업 표시줄 아이콘 설정 (Windows 전용)
            if sys.platform == 'win32':
                # 앱 ID 설정 - 작업 표시줄에서 아이콘을 그룹화하는 데 사용됨
                app_id = 'com.snipix.screencapture'
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception as e:
        print(f"Error occurred during icon setup: {e}")
    
    # UI 표시
    ui.show()
    ui.center_on_screen()
    
    # 애플리케이션 실행
    sys.exit(app.exec_())

if __name__ == "__main__":
    main() 