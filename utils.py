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