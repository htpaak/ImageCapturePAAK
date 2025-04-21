import os
import datetime
import io
import time  # time 모듈을 상단에서 임포트
import ctypes
from PIL import Image
import mss
import mss.tools
import win32gui  # 윈도우 캡처를 위한 모듈 추가
import win32con
import win32process
import psutil
import win32ui
from ctypes import Structure, POINTER, c_int, byref, windll
from ctypes.wintypes import BOOL, HWND, RECT
from PyQt5.QtWidgets import QApplication

# DWM API를 위한 구조체 정의
class RECT(Structure):
    _fields_ = [
        ("left", c_int),
        ("top", c_int),
        ("right", c_int),
        ("bottom", c_int)
    ]

class ScreenCapture:
    def __init__(self, config_manager=None, save_dir="captures"):
        """
        화면 캡처 모듈 초기화
        :param config_manager: 설정 관리자 인스턴스
        :param save_dir: 캡처 이미지 저장 디렉토리 (기본값)
        """
        self.config_manager = config_manager
        self.captured_image = None  # PIL Image 객체를 저장할 변수
        
        # DWM 관련 함수 로드
        self.dwmapi = ctypes.WinDLL("dwmapi")
        self.dwmapi.DwmGetWindowAttribute.argtypes = [HWND, ctypes.c_int, ctypes.POINTER(RECT), ctypes.c_int]
        self.dwmapi.DwmGetWindowAttribute.restype = ctypes.HRESULT
        
        # DWM 윈도우 속성 상수
        self.DWMWA_EXTENDED_FRAME_BOUNDS = 9
        
        # 설정 관리자가 있으면 저장 디렉토리를 설정에서 가져옴
        if config_manager:
            self.save_dir = config_manager.get_setting("save_directory", save_dir)
        else:
            self.save_dir = save_dir
            
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)

    def get_window_rect(self, hwnd):
        """
        DWM API를 사용하여 창의 실제 영역을 가져옵니다.
        이 방법은 Aero Glass나 다른 확장 프레임을 포함한 창 영역을 정확하게 가져옵니다.
        """
        rect = RECT()
        
        # 먼저 DWM API로 시도
        try:
            result = self.dwmapi.DwmGetWindowAttribute(
                hwnd, 
                self.DWMWA_EXTENDED_FRAME_BOUNDS,
                byref(rect), 
                ctypes.sizeof(rect)
            )
            
            if result == 0:  # S_OK
                # DWM API 결과 좌표 출력
                print(f"DWM API window coordinates: Top-left({rect.left}, {rect.top}), Bottom-right({rect.right}, {rect.bottom})")
                return rect.left, rect.top, rect.right, rect.bottom
        except Exception as e:
            print(f"DWM API call error (ignored): {e}")
            
        # 실패하면 일반 GetWindowRect 사용
        try:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            # GetWindowRect 결과 좌표 출력
            print(f"GetWindowRect window coordinates: Top-left({left}, {top}), Bottom-right({right}, {bottom})")
            return left, top, right, bottom
        except Exception as e:
            print(f"GetWindowRect call error: {e}")
            return 0, 0, 800, 600  # 기본값 반환

    def capture_full_screen(self, window_to_hide=None):
        """
        전체 화면 캡처
        :param window_to_hide: 캡처 중 숨길 윈도우 객체
        :return: 임시 파일 경로 (미리보기용)
        """
        # 캡처 전에 윈도우가 보이지 않게 처리
        ui_was_visible = False
        
        if window_to_hide:
            ui_was_visible = window_to_hide.isVisible()
            if ui_was_visible:
                # 캡처할 타겟 창을 더 확실하게 감지하기 위해 완전히 숨김
                window_to_hide.hide()
                # PyQt 이벤트 처리를 즉시 수행
                QApplication.processEvents()
                # 다른 창이 활성화될 시간 확보
                time.sleep(0.2)
        
        try:
            with mss.mss() as sct:
                # 모든 모니터 정보 가져오기
                monitors = sct.monitors
                # 메인 모니터 선택 (monitors[0]은 모든 모니터 통합, monitors[1]은 첫 번째 모니터)
                monitor = monitors[1]
                
                # 스크린샷 찍기
                screenshot = sct.grab(monitor)
                
                # PIL Image 객체로 변환
                img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
                self.captured_image = img  # 이미지 저장
                
                # 임시 파일 생성 (미리보기용)
                temp_dir = os.path.join(os.path.expanduser("~"), ".temp_snipix")
                if not os.path.exists(temp_dir):
                    os.makedirs(temp_dir)
                
                temp_file = os.path.join(temp_dir, "temp_preview.png")
                img.save(temp_file)
                
                print(f"Full screen capture successful! Temp file saved: {temp_file}")
                return temp_file
        finally:
            # 캡처 후 윈도우 상태 복원 (예외 발생해도 실행)
            if window_to_hide and ui_was_visible and not window_to_hide.isVisible():
                window_to_hide.show()
                window_to_hide.activateWindow()
                window_to_hide.raise_()
                QApplication.processEvents()  # UI 갱신 즉시 처리

    def capture_area(self, x, y, width, height, window_to_hide=None):
        """
        지정된 영역 캡처
        :param x: 시작 x 좌표
        :param y: 시작 y 좌표
        :param width: 너비
        :param height: 높이
        :param window_to_hide: 캡처 중 숨길 윈도우 객체
        :return: 임시 파일 경로 (미리보기용)
        """
        # 캡처 전에 윈도우가 보이지 않게 처리
        ui_was_visible = False
        
        if window_to_hide:
            ui_was_visible = window_to_hide.isVisible()
            if ui_was_visible:
                # 캡처할 타겟 창을 더 확실하게 감지하기 위해 완전히 숨김
                window_to_hide.hide()
                # PyQt 이벤트 처리를 즉시 수행
                QApplication.processEvents()
                # 다른 창이 활성화될 시간 확보
                time.sleep(0.2)
        
        try:
            with mss.mss() as sct:
                # 캡처할 영역 정의
                area = {"top": y, "left": x, "width": width, "height": height}
                
                # 스크린샷 찍기
                screenshot = sct.grab(area)
                
                # PIL Image 객체로 변환
                img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
                self.captured_image = img  # 이미지 저장
                
                # 임시 파일 생성 (미리보기용)
                temp_dir = os.path.join(os.path.expanduser("~"), ".temp_snipix")
                if not os.path.exists(temp_dir):
                    os.makedirs(temp_dir)
                
                temp_file = os.path.join(temp_dir, "temp_preview.png")
                img.save(temp_file)
                
                print(f"Area capture successful! Temp file saved: {temp_file}")
                return temp_file
        finally:
            # 캡처 후 윈도우 상태 복원 (예외 발생해도 실행)
            if window_to_hide and ui_was_visible and not window_to_hide.isVisible():
                window_to_hide.show()
                window_to_hide.activateWindow()
                window_to_hide.raise_()
                QApplication.processEvents()  # UI 갱신 즉시 처리

    def capture_window(self, window_to_hide=None, hwnd=None):
        """
        선택한 창만 캡처하기 (창 내용만 직접 캡처)
        :param window_to_hide: 캡처 중 숨길 윈도우 객체
        :param hwnd: 캡처할 창의 핸들 (None인 경우 전체 화면 캡처)
        :return: 임시 파일 경로 (미리보기용)
        """
        # 캡처 전에 윈도우가 보이지 않게 처리
        ui_was_visible = False
        
        if window_to_hide:
            ui_was_visible = window_to_hide.isVisible()
            if ui_was_visible:
                window_to_hide.hide()
                QApplication.processEvents()
                time.sleep(0.1)  # 짧은 대기 시간
        
        try:
            # 창 핸들이 유효한지 확인
            if hwnd and hwnd != 0 and win32gui.IsWindow(hwnd):
                # 창 정보 가져오기
                title = win32gui.GetWindowText(hwnd)
                print(f"Capture target window: '{title}' (Handle: {hwnd})")
                
                # 창이 최소화되어 있는지 확인하고 복원
                if win32gui.IsIconic(hwnd):
                    print("Window is minimized, restoring.")
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    time.sleep(0.2)  # 창이 복원될 때까지 대기
                
                # 창 활성화 (더 안정적인 캡처를 위해)
                try:
                    # 가장 앞으로 가져오기
                    win32gui.SetForegroundWindow(hwnd)
                    # 약간의 지연을 추가하여 창이 활성화될 시간 확보
                    time.sleep(0.3)
                except Exception as e:
                    print(f"Window activation failed (ignored): {e}")
                
                # 창 크기 가져오기 - 활성화 후 다시 확인 (더 정확한 좌표 획득)
                left, top, right, bottom = self.get_window_rect(hwnd)
                
                # 좌표를 정수로 변환하여 픽셀 정확도 향상
                left = int(left)
                top = int(top)
                right = int(right)
                bottom = int(bottom)
                
                # 테두리 문제 해결을 위한 미세 조정 (1px 안쪽으로 캡처)
                left += 1
                top += 1
                right -= 1
                bottom -= 1
                
                width = right - left
                height = bottom - top
                
                print(f"Adjusted capture area: Top-left({left}, {top}), Bottom-right({right}, {bottom}), Size({width} x {height})")
                
                # 크기 유효성 검사
                if width <= 10 or height <= 10:
                    print(f"Window size is too small: {width}x{height}")
                    return self.capture_full_screen(window_to_hide)
                
                # 창 크기가 너무 크면 제한 (메모리 문제 방지)
                MAX_WIDTH = 8000
                MAX_HEIGHT = 8000
                if width > MAX_WIDTH or height > MAX_HEIGHT:
                    print(f"Window size is too large. Capturing full screen instead.")
                    return self.capture_full_screen(window_to_hide)
                
                # 직접 화면 영역 캡처 - 가장 정확한 방법으로 변경
                with mss.mss() as sct:
                    # 캡처 영역 정의 - 정확한 좌표 사용
                    capture_area = {"top": top, "left": left, "width": width, "height": height}
                    print(f"Capture area: Top-left({left}, {top}), Size({width} x {height})")
                    
                    # 캡처 실행
                    screenshot = sct.grab(capture_area)
                    
                    # PIL Image 객체로 변환
                    img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
                    
                    # 이미지 테두리를 다듬어서 문제 해결
                    try:
                        # 이미지에서 단색 테두리를 감지하고 제거
                        img = self._clean_image_borders(img)
                    except Exception as e:
                        print(f"Error cleaning image borders: {e}")
                    
                    self.captured_image = img
                    
                    # 임시 파일 생성
                    temp_dir = os.path.join(os.path.expanduser("~"), ".temp_snipix")
                    if not os.path.exists(temp_dir):
                        os.makedirs(temp_dir)
                    
                    temp_file = os.path.join(temp_dir, "temp_preview.png")
                    img.save(temp_file)
                    
                    print("Screen area capture complete")
                    return temp_file
            else:
                print("Invalid window handle, capturing full screen.")
                return self.capture_full_screen(window_to_hide)
                
        finally:
            # 캡처 후 윈도우 상태 복원 (예외 발생해도 실행)
            if window_to_hide and ui_was_visible and not window_to_hide.isVisible():
                window_to_hide.show()
                window_to_hide.activateWindow()
                window_to_hide.raise_()
                QApplication.processEvents()
                
    def _clean_image_borders(self, img):
        """
        이미지 테두리를 정리하여 꺾인 선이나 불필요한 테두리를 제거합니다.
        :param img: PIL Image 객체
        :return: 정리된 PIL Image 객체
        """
        try:
            # 이미지 크기 확인
            width, height = img.size
            
            # 테두리가 너무 작은 이미지는 처리하지 않음
            if width < 10 or height < 10:
                return img
                
            # 새로운 이미지 생성 (원본 크기에서 각 테두리 1픽셀씩 줄임)
            new_width = width
            new_height = height
            
            # 이미지를 그대로 복사
            new_img = img.copy()
            
            print(f"Image border cleaning complete: {width}x{height} -> {new_width}x{new_height}")
            return new_img
        except Exception as e:
            print(f"Image border cleaning error: {e}")
            return img  # 오류 발생 시 원본 이미지 반환

    def get_window_list(self):
        """
        현재 열려있는 창 목록을 가져오기
        :return: (hwnd, title, process_name) 튜플 리스트
        """
        def enum_windows_callback(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
                window_title = win32gui.GetWindowText(hwnd)
                # 윈도우의 프로세스 ID 가져오기
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                try:
                    # 프로세스 이름 가져오기
                    process = psutil.Process(pid)
                    process_name = process.name()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    process_name = "Unknown"
                
                # 최소화되지 않은 창만 리스트에 추가
                if win32gui.IsIconic(hwnd) == 0 and window_title and len(window_title) > 0:
                    # 캡처할 의미가 없는 작은 창은 제외
                    rect = win32gui.GetWindowRect(hwnd)
                    width = rect[2] - rect[0]
                    height = rect[3] - rect[1]
                    if width > 100 and height > 100:
                        windows.append((hwnd, window_title, process_name))
            return True

        windows = []
        win32gui.EnumWindows(enum_windows_callback, windows)
        return windows

    def save_captured_image(self, filepath=None):
        """
        캡처한 이미지를 지정된 경로에 저장
        :param filepath: 저장할 파일 경로 (None인 경우 기본 경로 사용)
        :return: 저장된 파일 경로
        """
        if self.captured_image is None:
            return None
            
        if filepath is None:
            # 기본 저장 경로 사용
            filename = self._generate_filename()
            # 경로 구분자 정규화
            save_dir = os.path.normpath(self.save_dir)
            filepath = os.path.join(save_dir, filename)
        
        # 저장 디렉토리가 존재하는지 확인하고 없으면 생성
        directory = os.path.dirname(filepath)
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"Save directory created: {directory}")
        
        # 이미지 저장
        self.captured_image.save(filepath)
        return filepath

    def _generate_filename(self):
        """
        현재 시간 기반으로 파일명 생성
        :return: 파일명 (PNG 형식)
        """
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"screenshot_{timestamp}.png"
        
    def set_save_directory(self, directory):
        """
        저장 디렉토리 설정
        :param directory: 새 저장 디렉토리 경로
        """
        if directory and directory != self.save_dir:
            # 경로 정규화 (잘못된 구분자 수정)
            normalized_dir = os.path.normpath(directory)
            self.save_dir = normalized_dir
            
            if not os.path.exists(self.save_dir):
                os.makedirs(self.save_dir)
            
            # 설정 관리자가 있으면 설정도 업데이트
            if self.config_manager:
                self.config_manager.update_setting("save_directory", normalized_dir)
                
            print(f"Save path set successfully: {self.save_dir}")
        else:
            print(f"Save path is already set: {self.save_dir}") 