import os
import datetime
import io
from PIL import Image
import mss
import mss.tools

class ScreenCapture:
    def __init__(self, config_manager=None, save_dir="captures"):
        """
        화면 캡처 모듈 초기화
        :param config_manager: 설정 관리자 인스턴스
        :param save_dir: 캡처 이미지 저장 디렉토리 (기본값)
        """
        self.config_manager = config_manager
        self.captured_image = None  # PIL Image 객체를 저장할 변수
        
        # 설정 관리자가 있으면 저장 디렉토리를 설정에서 가져옴
        if config_manager:
            self.save_dir = config_manager.get_setting("save_directory", save_dir)
        else:
            self.save_dir = save_dir
            
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)

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
                window_to_hide.hide()
                # 윈도우가 완전히 숨겨질 때까지 대기
                import time
                time.sleep(0.3)
        
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
                
                return temp_file
        finally:
            # 캡처 후 윈도우 상태 복원 (예외 발생해도 실행)
            if window_to_hide and ui_was_visible:
                window_to_hide.show()

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
                window_to_hide.hide()
                # 윈도우가 완전히 숨겨질 때까지 대기
                import time
                time.sleep(0.3)
        
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
                
                return temp_file
        finally:
            # 캡처 후 윈도우 상태 복원 (예외 발생해도 실행)
            if window_to_hide and ui_was_visible:
                window_to_hide.show()

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
            filepath = os.path.join(self.save_dir, filename)
        
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
            self.save_dir = directory
            if not os.path.exists(self.save_dir):
                os.makedirs(self.save_dir)
            
            # 설정 관리자가 있으면 설정도 업데이트
            if self.config_manager:
                self.config_manager.update_setting("save_directory", directory) 