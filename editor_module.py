import os
import sys
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QLabel, QAction, 
                            QToolBar, QFileDialog, QMessageBox, QApplication, QDesktopWidget)
from PyQt5.QtGui import QPixmap, QImage, QIcon, QPainter, QPen, QColor
from PyQt5.QtCore import Qt, QSize, QRect, QPoint

class ImageCanvas(QWidget):
    """이미지를 직접 그리는 캔버스 위젯"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image = None
        
        # 배경 설정
        self.setStyleSheet("background-color: #282828;")
        self.setMinimumSize(600, 400)
        
    def setImage(self, image):
        """QImage 설정"""
        self.image = image
        self.update()
        
    def paintEvent(self, event):
        """이미지를 직접 그리기 - 풀스크린과 동일한 로직 적용"""
        painter = QPainter(self)
        
        # 항상 배경색 먼저 칠하기
        painter.fillRect(self.rect(), QColor(40, 40, 40))  # 어두운 회색 배경
        
        if not self.image or self.image.isNull():
            return

        # 안티앨리어싱 및 고품질 렌더링 설정
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        
        # 비율을 유지하면서 창 크기에 맞게 이미지 크기 계산
        img_size = self.image.size()
        widget_rect = self.rect()
        scaled_size = img_size.scaled(widget_rect.size(), Qt.KeepAspectRatio)
        
        # 중앙 위치 계산
        x = (widget_rect.width() - scaled_size.width()) / 2
        y = (widget_rect.height() - scaled_size.height()) / 2
        
        # 이미지를 중앙에 그리기
        target_rect = QRect(QPoint(int(x), int(y)), scaled_size)
        painter.drawImage(target_rect, self.image)

class ImageEditor(QMainWindow):
    """이미지 편집 기능을 제공하는 창"""
    def __init__(self, image_path=None, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.parent = parent
        self.original_image = None
        self.edited_image = None
        self.undo_stack = []  # 실행 취소를 위한 이전 상태 저장 스택
        
        # UI 초기화
        self.initUI()
        
        # 이미지 로드
        if image_path and os.path.exists(image_path):
            self.load_image(image_path)
            
        # 창을 화면 중앙에 표시
        self.center_on_screen()
            
    def initUI(self):
        """UI 초기화"""
        # 창 기본 설정
        self.setWindowTitle('Image Editor')
        self.setGeometry(100, 100, 900, 700)
        
        # 중앙 위젯 설정
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 메인 레이아웃
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 이미지 캔버스 직접 추가 (스크롤 영역 없이)
        self.image_canvas = ImageCanvas()
        main_layout.addWidget(self.image_canvas)
        
        # 툴바 생성
        self.createToolBar()
        
    def createToolBar(self):
        """툴바 생성 및 버튼 추가"""
        toolbar = QToolBar("Edit Tools")
        toolbar.setIconSize(QSize(24, 24))
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        # 저장 버튼
        save_action = QAction("Save", self)
        save_action.setToolTip("Save image")
        toolbar.addAction(save_action)
        
        # 복사 버튼
        copy_action = QAction("Copy", self)
        copy_action.setToolTip("Copy to clipboard")
        toolbar.addAction(copy_action)
        
        # 구분선 추가
        toolbar.addSeparator()
        
        # 실행 취소 버튼
        undo_action = QAction("Undo", self)
        undo_action.setToolTip("Undo last action")
        toolbar.addAction(undo_action)
        
        # 다시 실행 버튼
        redo_action = QAction("Redo", self)
        redo_action.setToolTip("Redo last action")
        toolbar.addAction(redo_action)
        
        # 리셋 버튼
        reset_action = QAction("Reset", self)
        reset_action.setToolTip("Reset to original image")
        toolbar.addAction(reset_action)
        
        # 구분선 추가
        toolbar.addSeparator()
        
        # 이미지 회전 버튼
        rotate_action = QAction("Rotate", self)
        rotate_action.setToolTip("Rotate image")
        toolbar.addAction(rotate_action)
        
        # 좌우 반전 버튼
        flip_h_action = QAction("Flip H", self)
        flip_h_action.setToolTip("Flip horizontally")
        toolbar.addAction(flip_h_action)
        
        # 상하 반전 버튼
        flip_v_action = QAction("Flip V", self)
        flip_v_action.setToolTip("Flip vertically")
        toolbar.addAction(flip_v_action)
        
        # 구분선 추가
        toolbar.addSeparator()
        
        # 그리기 도구 버튼들
        
        # 도구 선택 버튼
        select_action = QAction("Select", self)
        select_action.setToolTip("Select area")
        toolbar.addAction(select_action)
        
        # 자르기 버튼
        crop_action = QAction("Crop", self)
        crop_action.setToolTip("Crop image")
        toolbar.addAction(crop_action)
        
        # 텍스트 추가 버튼
        text_action = QAction("Text", self)
        text_action.setToolTip("Add text")
        toolbar.addAction(text_action)
        
        # 펜 도구 버튼
        pen_action = QAction("Pen", self)
        pen_action.setToolTip("Draw with pen")
        toolbar.addAction(pen_action)
        
        # 강조 도구 버튼
        highlight_action = QAction("Highlight", self)
        highlight_action.setToolTip("Highlight area")
        toolbar.addAction(highlight_action)
        
        # 도형 버튼 - 사각형
        rect_action = QAction("Rectangle", self)
        rect_action.setToolTip("Draw rectangle")
        toolbar.addAction(rect_action)
        
        # 도형 버튼 - 원
        circle_action = QAction("Circle", self)
        circle_action.setToolTip("Draw circle")
        toolbar.addAction(circle_action)
        
        # 화살표 버튼 (원 버튼 다음으로 이동)
        arrow_action = QAction("Arrow", self)
        arrow_action.setToolTip("Draw arrow")
        toolbar.addAction(arrow_action)
        
        # 모자이크 버튼 (화살표 버튼 다음으로 이동)
        mosaic_action = QAction("Mosaic", self)
        mosaic_action.setToolTip("Apply mosaic effect")
        toolbar.addAction(mosaic_action)
        
    def load_image(self, image_path):
        """이미지 로드 및 표시"""
        if not os.path.exists(image_path):
            QMessageBox.warning(self, "Error", "Image file not found!")
            return False
            
        # QImage로 직접 로드
        image = QImage(image_path)
        if image.isNull():
            QMessageBox.warning(self, "Error", "Failed to load image!")
            return False
            
        # 원본 및 편집용 이미지 저장
        self.original_image = image
        self.edited_image = QImage(image)
        
        # 캔버스에 이미지 설정
        self.image_canvas.setImage(self.edited_image)
        
        # 창 제목에 파일 이름 추가
        filename = os.path.basename(image_path)
        self.setWindowTitle(f'Image Editor - {filename}')
        
        return True
        
    def resizeEvent(self, event):
        """창 크기 변경 시 이미지 표시 업데이트"""
        super().resizeEvent(event)
        # 캔버스가 자동으로 repaint 됨

    def center_on_screen(self):
        """창을 화면 중앙에 배치합니다"""
        screen_geometry = QDesktopWidget().availableGeometry()
        window_geometry = self.frameGeometry()
        center_point = screen_geometry.center()
        window_geometry.moveCenter(center_point)
        self.move(window_geometry.topLeft())

# 테스트 코드 (독립 실행용)
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 테스트용 이미지가 있으면 해당 경로 사용
    test_image = None
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        test_image = sys.argv[1]
        
    editor = ImageEditor(test_image)
    editor.show()
    
    sys.exit(app.exec_()) 