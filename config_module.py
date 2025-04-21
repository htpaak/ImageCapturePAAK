import os
import json
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

class ConfigManager:
    """설정 관리 클래스"""
    def __init__(self, config_file=None):
        """
        설정 관리자 초기화
        :param config_file: 설정 파일 경로 (None이면 기본 경로 사용)
        """
        # 설정 파일 저장 경로 설정 (사용자의 AppData\Local 폴더 내에 Snipix 폴더)
        user_home = os.path.expanduser("~")
        self.config_dir = os.path.join(user_home, "AppData", "Local", "Snipix")
        
        # 설정 폴더가 없으면 생성
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)
            print(f"Settings folder created: {self.config_dir}")
        
        # 설정 파일 경로 설정
        if config_file is None:
            self.config_file = os.path.join(self.config_dir, "settings.json")
        else:
            self.config_file = config_file
            
        print(f"Settings file path: {self.config_file}")
            
        self.default_settings = {
            "save_directory": os.path.join(os.path.expanduser("~"), "Pictures", "Screenshots"),
            "image_format": "png",
            "show_preview": True,
            "auto_copy_to_clipboard": False,
            "auto_save": True,
            "save_quality": 100  # PNG의 경우 압축 레벨 (0-100)
        }
        self.settings = self.load_settings()
        
        # 저장 디렉토리가 존재하지 않으면 생성
        save_dir = os.path.normpath(self.settings["save_directory"])  # 경로 정규화
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
            print(f"Save path created: {save_dir}")
        # 경로 정규화 후 다시 설정
        self.settings["save_directory"] = save_dir

    def load_settings(self):
        """
        설정 파일에서 설정 로드
        :return: 설정 딕셔너리
        """
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    # 기본 설정과 병합하여 누락된 설정 항목 보완
                    return {**self.default_settings, **settings}
            except (json.JSONDecodeError, IOError) as e:
                # 파일이 손상된 경우 기본 설정 반환
                print(f"Failed to read settings file: {e}")
                return self.default_settings
        else:
            # 설정 파일이 없으면 기본 설정 저장 후 반환
            print(f"Settings file not found, creating a new one: {self.config_file}")
            self.save_settings(self.default_settings)
            return self.default_settings

    def save_settings(self, settings=None):
        """
        설정을 파일에 저장
        :param settings: 저장할 설정 (None이면 현재 설정 사용)
        """
        if settings is None:
            settings = self.settings
        
        try:
            # 설정 파일 폴더가 존재하는지 다시 확인 (외부에서 삭제했을 수도 있음)
            config_dir = os.path.dirname(self.config_file)
            if not os.path.exists(config_dir):
                os.makedirs(config_dir)
                
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=4)
            print(f"Settings saved successfully: {self.config_file}")
        except IOError as e:
            # 파일 저장 실패 시 예외 처리
            print(f"Error occurred while saving settings file: {self.config_file} - {e}")

    def get_setting(self, key, default=None):
        """
        설정 값 조회
        :param key: 설정 키
        :param default: 키가 없을 경우 반환할 기본값
        :return: 설정 값
        """
        return self.settings.get(key, default)

    def update_setting(self, key, value):
        """
        설정 값 업데이트
        :param key: 설정 키
        :param value: 새 값
        """
        self.settings[key] = value
        self.save_settings() 