import os
import sys

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