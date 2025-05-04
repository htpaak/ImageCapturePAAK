import sys
import os
# keyboard 라이브러리 임포트 제거
# import keyboard
# pywin32 관련 모듈 임포트
import ctypes
from ctypes import wintypes
import win32con
import win32gui
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtGui import QIcon
# QAbstractNativeEventFilter 임포트 추가
from PyQt5.QtCore import Qt, QAbstractNativeEventFilter
import traceback

# 로깅 설정 가져오기
from log_setup import setup_logging

# 유틸리티 함수 가져오기
from utils import get_resource_path

# 사용자 정의 모듈 가져오기
from capture_module import ScreenCapture
from gui_module import CaptureUI
from config_module import ConfigManager
from editor_module import ImageEditor # ImageEditor는 직접 사용되지 않지만, gui_module에서 필요할 수 있음

# --- 전역 단축키 처리 클래스 --- #
class HotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, ui_instance, hotkey_ids_map):
        super().__init__()
        self.ui = ui_instance
        self.id_to_key = {v: k for k, v in hotkey_ids_map.items()}
        print(f"[HotkeyFilter] Initialized with ID map: {self.id_to_key}")

    def nativeEventFilter(self, eventType, message):
        try:
            msg = wintypes.MSG.from_address(message.__int__())
        except ValueError:
             return False, 0

        if eventType == "windows_generic_MSG" and msg.message == win32con.WM_HOTKEY:
            hotkey_id = msg.wParam
            key_name = self.id_to_key.get(hotkey_id)
            print(f"[Hotkey Event] Native event filter caught WM_HOTKEY. ID: {hotkey_id:X}, Key: {key_name}") # ID 16진수 출력

            # 등록된 키 이름과 비교하여 해당하는 시그널 발생 (Alt+1/2/3 기준)
            if key_name == 'Alt+1':
                print("[Hotkey Event] Alt+1 pressed, emitting captureFullScreenRequested signal.")
                self.ui.captureFullScreenRequested.emit()
            elif key_name == 'Alt+2':
                print("[Hotkey Event] Alt+2 pressed, emitting captureAreaRequested signal.")
                self.ui.captureAreaRequested.emit()
            elif key_name == 'Alt+3':
                print("[Hotkey Event] Alt+3 pressed, emitting captureWindowRequested signal.")
                self.ui.captureWindowRequested.emit()

            return True, 0

        return False, 0

def main():
    # 로깅 설정 적용
    setup_logging()

    # High DPI 스케일링 활성화
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    # 애플리케이션 초기화
    app = QApplication(sys.argv)
    app.setApplicationName('ImageCapturePAAK')
    app.setQuitOnLastWindowClosed(False)

    # 설정 관리자 초기화
    config_manager = ConfigManager()

    # 캡처 모듈 초기화 및 설정 전달
    capture_module = ScreenCapture(config_manager)

    # UI 초기화
    ui = CaptureUI(capture_module)

    # --- 전역 단축키 ID 정의 및 등록 (Alt+1/2/3) --- #
    HOTKEY_IDS = {
        'Alt+1': 0xC001, # 전체 화면
        'Alt+2': 0xC002, # 영역
        'Alt+3': 0xC003  # 창
    }
    registered_hotkeys = {}

    # Modifier 설정 (Alt)
    MODIFIERS = win32con.MOD_ALT # Shift 제거

    print("Registering global hotkeys (Alt+1/2/3) using pywin32 (assuming success for filter)...") # 로그 메시지 수정
    try:
        # Alt+1 등록 (전체 화면, ID: 0xC001)
        if win32gui.RegisterHotKey(None, HOTKEY_IDS['Alt+1'], MODIFIERS, 0x31): # VK_1
            print(f"Registered hotkey Alt+1 (ID: {HOTKEY_IDS['Alt+1']:X})")
        else:
            error_code = ctypes.GetLastError()
            print(f"Warning: RegisterHotKey for Alt+1 returned False, but GetLastError is {error_code}. Proceeding anyway.")
        # 실패 여부와 관계없이 필터를 위해 등록 정보 추가 (진단용)
        registered_hotkeys['Alt+1'] = HOTKEY_IDS['Alt+1']

        # Alt+2 등록 (영역, ID: 0xC002)
        if win32gui.RegisterHotKey(None, HOTKEY_IDS['Alt+2'], MODIFIERS, 0x32): # VK_2
            print(f"Registered hotkey Alt+2 (ID: {HOTKEY_IDS['Alt+2']:X})")
        else:
            error_code = ctypes.GetLastError()
            print(f"Warning: RegisterHotKey for Alt+2 returned False, but GetLastError is {error_code}. Proceeding anyway.")
        # 실패 여부와 관계없이 필터를 위해 등록 정보 추가 (진단용)
        registered_hotkeys['Alt+2'] = HOTKEY_IDS['Alt+2']

        # Alt+3 등록 (창, ID: 0xC003)
        if win32gui.RegisterHotKey(None, HOTKEY_IDS['Alt+3'], MODIFIERS, 0x33): # VK_3
            print(f"Registered hotkey Alt+3 (ID: {HOTKEY_IDS['Alt+3']:X})")
        else:
            error_code = ctypes.GetLastError()
            print(f"Warning: RegisterHotKey for Alt+3 returned False, but GetLastError is {error_code}. Proceeding anyway.")
        # 실패 여부와 관계없이 필터를 위해 등록 정보 추가 (진단용)
        registered_hotkeys['Alt+3'] = HOTKEY_IDS['Alt+3']

        # 등록된 ID를 UI 객체에 전달
        ui.set_hotkey_ids(registered_hotkeys)

        # 네이티브 이벤트 필터 설치
        hotkey_filter = HotkeyFilter(ui, registered_hotkeys) 
        app.installNativeEventFilter(hotkey_filter)
        print("Installed native event filter for hotkeys.")

    except Exception as e:
        print(f"Error registering global hotkeys: {e}")
        traceback.print_exc()
        QMessageBox.warning(None, "Hotkey Error",
                            f"Failed to register global hotkeys: {e}\n"
                            "The application might not respond to hotkeys.")

    # 애플리케이션 아이콘 설정 (Windows에서만 동작)
    try:
        icon_path = get_resource_path(os.path.join('assets', 'icon.ico'))
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))
            ui.setWindowIcon(QIcon(icon_path))
            if sys.platform == 'win32':
                app_id = 'com.ImageCapturePAAK.screencapture'
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception as e:
        print(f"Error occurred during icon setup: {e}")

    # --- 시작 시 동작 결정 --- #
    start_in_tray = config_manager.get_setting("start_in_tray", True) # 설정값 읽기
    if not start_in_tray:
        # 트레이 시작이 아니면 UI 표시 및 중앙 정렬
        ui.show()
        ui.center_on_screen()
    # 트레이 시작인 경우, gui_module의 setup_tray_icon에서 아이콘이 표시됨
    # (메인 창은 show()되지 않음)

    # 애플리케이션 실행
    exit_code = app.exec_()

    # 종료 전 단축키 해제 로직은 gui_module.py의 exit_app에 구현됨

    sys.exit(exit_code)

if __name__ == "__main__":
    main() 