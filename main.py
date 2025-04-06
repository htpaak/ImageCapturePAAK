import sys
import os
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon

# 사용자 정의 모듈 가져오기
from capture_module import ScreenCapture
from gui_module import CaptureUI
from config_module import ConfigManager

def main():
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
        # 만약 아이콘 파일이 있다면 사용
        if os.path.exists('icon.ico'):
            app.setWindowIcon(QIcon('icon.ico'))
    except Exception:
        pass
    
    # UI 표시
    ui.show()
    
    # 애플리케이션 실행
    sys.exit(app.exec_())

if __name__ == "__main__":
    main() 