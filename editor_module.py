import os
import sys
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QLabel, QAction, 
                            QToolBar, QFileDialog, QMessageBox, QApplication, QDesktopWidget, 
                            QToolButton, QMenu)
from PyQt5.QtGui import QPixmap, QImage, QIcon, QPainter, QPen, QColor
from PyQt5.QtCore import Qt, QSize, QRect, QPoint, QRectF, QSizeF

class ImageCanvas(QWidget):
    """이미지를 직접 그리는 캔버스 위젯"""
    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self.editor = editor
        self.image = None
        
        # 배경 설정
        self.setStyleSheet("background-color: #282828;")
        self.setMinimumSize(600, 400)
        
    def setImage(self, image):
        """QImage 설정"""
        self.image = image
        
    def map_widget_to_image(self, widget_point):
        """위젯 좌표를 이미지 원본 좌표로 변환"""
        if not self.image or self.image.isNull():
            return None

        img_size = self.image.size()
        widget_rect = self.rect()
        scaled_size = img_size.scaled(widget_rect.size(), Qt.KeepAspectRatio)
        
        x_offset = (widget_rect.width() - scaled_size.width()) / 2
        y_offset = (widget_rect.height() - scaled_size.height()) / 2
        
        # QSize를 QSizeF로 변환하여 QRectF 생성
        target_rect = QRectF(QPoint(int(x_offset), int(y_offset)), QSizeF(scaled_size))

        if not target_rect.contains(widget_point):
            # 위젯 좌표가 이미지 표시 영역 밖에 있으면 None 반환 (또는 경계값으로 조정)
            # 여기서는 경계값으로 조정 시도
            adjusted_x = max(target_rect.left(), min(widget_point.x(), target_rect.right()))
            adjusted_y = max(target_rect.top(), min(widget_point.y(), target_rect.bottom()))
            widget_point = QPoint(int(adjusted_x), int(adjusted_y))
            # return None 

        relative_x = widget_point.x() - target_rect.left()
        relative_y = widget_point.y() - target_rect.top()

        scale_x = scaled_size.width() / img_size.width()
        scale_y = scaled_size.height() / img_size.height()

        if scale_x == 0 or scale_y == 0: return None # 0으로 나누기 방지

        img_x = relative_x / scale_x
        img_y = relative_y / scale_y
        
        # 이미지 경계 내로 강제 조정
        img_x = max(0, min(img_x, img_size.width() - 1))
        img_y = max(0, min(img_y, img_size.height() - 1))

        return QPoint(int(img_x), int(img_y))

    def paintEvent(self, event):
        """이미지를 직접 그리고 선택 영역 오버레이"""
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(40, 40, 40))
        
        if not self.image or self.image.isNull():
            return

        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        
        img_size = self.image.size()
        widget_rect = self.rect()
        scaled_size = img_size.scaled(widget_rect.size(), Qt.KeepAspectRatio)
        
        x = (widget_rect.width() - scaled_size.width()) / 2
        y = (widget_rect.height() - scaled_size.height()) / 2
        target_rect = QRect(QPoint(int(x), int(y)), scaled_size)
        
        painter.drawImage(target_rect, self.image)

        # 모자이크 도구 선택 중일 때 사각형 그리기
        if self.editor.is_selecting and self.editor.current_tool == 'mosaic':
            pen = QPen(Qt.white, 1, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            # selection_start_point와 selection_end_point가 None이 아닐 때만 그림
            if self.editor.selection_start_point and self.editor.selection_end_point:
                selection_rect_widget = QRect(self.editor.selection_start_point, 
                                              self.editor.selection_end_point).normalized()
                painter.drawRect(selection_rect_widget)

    # 마우스 이벤트 핸들러 추가
    def mousePressEvent(self, event):
        if self.editor.current_tool == 'mosaic' and event.button() == Qt.LeftButton:
            self.editor.is_selecting = True
            self.editor.selection_start_point = event.pos()
            self.editor.selection_end_point = event.pos()
            self.update()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.editor.is_selecting and self.editor.current_tool == 'mosaic':
            self.editor.selection_end_point = event.pos()
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.editor.is_selecting and self.editor.current_tool == 'mosaic' and event.button() == Qt.LeftButton:
            self.editor.is_selecting = False
            start_widget = self.editor.selection_start_point
            end_widget = event.pos() # Release 시점의 위치 사용

            if start_widget and end_widget: # None 체크
                selection_rect_widget = QRect(start_widget, end_widget).normalized()

                # 위젯 좌표를 이미지 좌표로 변환
                img_top_left = self.map_widget_to_image(selection_rect_widget.topLeft())
                img_bottom_right = self.map_widget_to_image(selection_rect_widget.bottomRight())

                if img_top_left and img_bottom_right:
                    img_rect = QRect(img_top_left, img_bottom_right).normalized()
                    
                    # 영역 크기가 유효한지 확인 (예: 최소 1x1 픽셀)
                    if img_rect.width() > 0 and img_rect.height() > 0:
                        # Undo 상태 저장 후 모자이크 적용
                        self.editor.push_undo_state() 
                        self.editor.apply_mosaic(img_rect, self.editor.mosaic_level)
                        self.editor.update_canvas() # 변경사항 반영
                    else:
                        print("선택 영역이 너무 작습니다.") # 사용자 피드백

            # 선택 상태 초기화 및 커서 복원
            self.editor.selection_start_point = None
            self.editor.selection_end_point = None
            self.setCursor(Qt.ArrowCursor) 
            self.update() # 마지막 사각형 지우기

        super().mouseReleaseEvent(event)

class ImageEditor(QMainWindow):
    """이미지 편집 기능을 제공하는 창"""
    # 모자이크 레벨 상수 정의
    MOSAIC_LEVELS = {'Weak': 5, 'Medium': 10, 'Strong': 20}

    def __init__(self, image_path=None, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.parent = parent
        self.original_image = None
        self.edited_image = None
        self.undo_stack = []
        self.redo_stack = [] # 다시 실행 스택 추가

        # 도구 상태 변수 추가
        self.current_tool = None
        self.mosaic_level = self.MOSAIC_LEVELS['Medium'] # 기본값 중간
        self.is_selecting = False
        self.selection_start_point = None
        self.selection_end_point = None
        
        # UI 초기화
        self.initUI()
        
        if image_path and os.path.exists(image_path):
            self.load_image(image_path)
            
        self.center_on_screen()
            
    def initUI(self):
        """UI 초기화"""
        self.setWindowTitle('Image Editor')
        self.setGeometry(100, 100, 900, 700)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # ImageCanvas 생성 시 self 참조 전달
        self.image_canvas = ImageCanvas(self) 
        main_layout.addWidget(self.image_canvas)
        
        self.createToolBar()

    # Undo/Redo 함수 추가
    def push_undo_state(self):
        """현재 이미지 상태를 Undo 스택에 저장"""
        if self.edited_image:
            # QImage는 깊은 복사가 필요할 수 있음
            self.undo_stack.append(QImage(self.edited_image)) 
            # 새로운 동작이 생기면 Redo 스택은 비워야 함
            self.redo_stack.clear() 
            # 스택 크기 제한 (선택적)
            # if len(self.undo_stack) > 20: self.undo_stack.pop(0)
            self.update_undo_redo_actions()

    def undo_action_triggered(self):
        """실행 취소"""
        if len(self.undo_stack) > 1: # 현재 상태 제외하고 이전 상태가 있어야 함
             # 현재 상태를 Redo 스택에 넣음
            current_state = self.undo_stack.pop()
            self.redo_stack.append(current_state)
             # 이전 상태를 가져와 적용
            self.edited_image = QImage(self.undo_stack[-1]) # 스택의 마지막(최신) 상태
            self.update_canvas()
            self.update_undo_redo_actions()
        elif len(self.undo_stack) == 1: # 원본 이미지만 남은 경우
            current_state = self.undo_stack.pop()
            self.redo_stack.append(current_state)
            self.edited_image = QImage(self.original_image) # 원본으로 복구
            self.update_canvas()
            self.update_undo_redo_actions()

    def redo_action_triggered(self):
        """다시 실행"""
        if self.redo_stack:
            # Redo 스택에서 상태를 가져옴
            redo_state = self.redo_stack.pop()
            # 현재 상태를 Undo 스택에 다시 넣음 (Redo 이전 상태)
            self.undo_stack.append(QImage(self.edited_image))
            # Redo 상태 적용
            self.edited_image = QImage(redo_state)
            self.update_canvas()
            self.update_undo_redo_actions()
            
    def update_undo_redo_actions(self):
        """Undo/Redo 액션 활성화/비활성화 업데이트"""
        # 'undo_action'과 'redo_action' 속성이 있는지 확인 후 상태 업데이트
        if hasattr(self, 'undo_action'):
             self.undo_action.setEnabled(len(self.undo_stack) > 0)
        if hasattr(self, 'redo_action'):
             self.redo_action.setEnabled(len(self.redo_stack) > 0)

    # 캔버스 업데이트 함수
    def update_canvas(self):
        """편집된 이미지로 캔버스를 업데이트"""
        if self.edited_image:
            self.image_canvas.setImage(self.edited_image)
            self.image_canvas.update() # QWidget의 update() 호출

    def createToolBar(self):
        """툴바 생성 및 버튼 추가 (모자이크 버튼 수정)"""
        toolbar = QToolBar("Edit Tools")
        toolbar.setIconSize(QSize(24, 24))
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.addToolBar(toolbar)
        
        # 저장 버튼
        save_action = QAction(QIcon("assets/save_icon.svg"), "Save", self)
        save_action.setToolTip("Save image")
        toolbar.addAction(save_action)
        
        copy_action = QAction(QIcon("assets/copy_icon.svg"), "Copy", self)
        copy_action.setToolTip("Copy to clipboard")
        toolbar.addAction(copy_action)
        
        toolbar.addSeparator()

        # 실행 취소 버튼 (undo_action_triggered 연결)
        self.undo_action = QAction(QIcon("assets/undo_icon.svg"), "Undo", self)
        self.undo_action.setToolTip("Undo last action")
        self.undo_action.triggered.connect(self.undo_action_triggered)
        self.undo_action.setEnabled(False) # 초기 비활성화
        toolbar.addAction(self.undo_action)
        
        # 다시 실행 버튼 (redo_action_triggered 연결)
        self.redo_action = QAction(QIcon("assets/redo_icon.svg"), "Redo", self)
        self.redo_action.setToolTip("Redo last action")
        self.redo_action.triggered.connect(self.redo_action_triggered)
        self.redo_action.setEnabled(False) # 초기 비활성화
        toolbar.addAction(self.redo_action)

        # 리셋 버튼 (기능 구현 필요)
        reset_action = QAction(QIcon("assets/reset_icon.svg"), "Reset", self)
        reset_action.setToolTip("Reset to original image")
        # reset_action.triggered.connect(self.reset_image) # 예시 연결
        toolbar.addAction(reset_action)
        
        toolbar.addSeparator()
        
        # 이미지 회전 버튼
        rotate_action = QAction(QIcon("assets/rotate_icon.svg"), "Rotate", self)
        rotate_action.setToolTip("Rotate image")
        toolbar.addAction(rotate_action)
        
        # 좌우 반전 버튼
        flip_h_action = QAction(QIcon("assets/flip_h_icon.svg"), "Flip H", self)
        flip_h_action.setToolTip("Flip horizontally")
        toolbar.addAction(flip_h_action)
        
        # 상하 반전 버튼
        flip_v_action = QAction(QIcon("assets/flip_v_icon.svg"), "Flip V", self)
        flip_v_action.setToolTip("Flip vertically")
        toolbar.addAction(flip_v_action)

        toolbar.addSeparator()

        # 그리기 도구 버튼들
        
        # 도구 선택 버튼
        select_action = QAction(QIcon("assets/select_icon.svg"), "Select", self)
        select_action.setToolTip("Select area")
        toolbar.addAction(select_action)
        
        # 자르기 버튼
        crop_action = QAction(QIcon("assets/crop_icon.svg"), "Crop", self)
        crop_action.setToolTip("Crop image")
        toolbar.addAction(crop_action)
        
        # 텍스트 추가 버튼
        text_action = QAction(QIcon("assets/text_icon.svg"), "Text", self)
        text_action.setToolTip("Add text")
        toolbar.addAction(text_action)
        
        # 펜 도구 버튼
        pen_action = QAction(QIcon("assets/pen_icon.svg"), "Pen", self)
        pen_action.setToolTip("Draw with pen")
        toolbar.addAction(pen_action)
        
        # 강조 도구 버튼
        highlight_action = QAction(QIcon("assets/highlight_icon.svg"), "Highlight", self)
        highlight_action.setToolTip("Highlight area")
        toolbar.addAction(highlight_action)
        
        # 도형 버튼 - 사각형
        rect_action = QAction(QIcon("assets/rectangle_icon.svg"), "Rectangle", self)
        rect_action.setToolTip("Draw rectangle")
        toolbar.addAction(rect_action)
        
        # 도형 버튼 - 원
        circle_action = QAction(QIcon("assets/circle_icon.svg"), "Circle", self)
        circle_action.setToolTip("Draw circle")
        toolbar.addAction(circle_action)
        
        # 화살표 버튼 (원 버튼 다음으로 이동)
        arrow_action = QAction(QIcon("assets/arrow_icon.svg"), "Arrow", self)
        arrow_action.setToolTip("Draw arrow")
        toolbar.addAction(arrow_action)
        
        # 모자이크 버튼 (QToolButton + QMenu)
        mosaic_button = QToolButton(self)
        mosaic_button.setIcon(QIcon("assets/mosaic_icon.svg"))
        mosaic_button.setText("Mosaic")
        mosaic_button.setToolTip("Apply mosaic effect")
        mosaic_button.setPopupMode(QToolButton.InstantPopup) # 클릭 시 바로 메뉴 표시
        mosaic_button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon) # 아이콘 아래 텍스트

        mosaic_menu = QMenu(mosaic_button)
        mosaic_button.setMenu(mosaic_menu)

        # 모자이크 레벨 액션 생성 및 메뉴에 추가
        weak_action = QAction("Weak", self)
        weak_action.triggered.connect(lambda: self.set_mosaic_tool('Weak'))
        mosaic_menu.addAction(weak_action)

        medium_action = QAction("Medium", self)
        medium_action.triggered.connect(lambda: self.set_mosaic_tool('Medium'))
        mosaic_menu.addAction(medium_action)

        strong_action = QAction("Strong", self)
        strong_action.triggered.connect(lambda: self.set_mosaic_tool('Strong'))
        mosaic_menu.addAction(strong_action)
        
        toolbar.addWidget(mosaic_button) # 툴바에 버튼 위젯 추가

    def set_mosaic_tool(self, level):
        """모자이크 도구 활성화 및 레벨 설정"""
        self.current_tool = 'mosaic'
        self.mosaic_level = self.MOSAIC_LEVELS[level]
        print(f"Mosaic tool activated with level: {level} (Block size: {self.mosaic_level})")
        # 커서 변경
        self.image_canvas.setCursor(Qt.CrossCursor)
        # 이전 선택 상태 초기화
        self.is_selecting = False
        self.selection_start_point = None
        self.selection_end_point = None
        self.image_canvas.update() # 혹시 이전 선택 영역 남아있을까봐 업데이트

    def apply_mosaic(self, img_rect, block_size):
        """지정된 영역에 모자이크 효과 적용 (이미지 좌표 기준)"""
        if not self.edited_image or self.edited_image.isNull() or not img_rect.isValid() or block_size <= 0:
            return

        # QImage는 직접 수정 가능
        painter = QPainter(self.edited_image)
        
        # 실제 이미지 경계와 교차하는 영역만 처리
        target_rect = img_rect.intersected(self.edited_image.rect())
        if not target_rect.isValid(): return

        # 평균 색상을 먼저 계산 (수정 중인 이미지에 영향받지 않도록)
        average_colors = {}
        source_image = QImage(self.edited_image) # 계산용 복사본

        for y in range(target_rect.top(), target_rect.bottom(), block_size):
            for x in range(target_rect.left(), target_rect.right(), block_size):
                # 현재 블록의 실제 영역 계산 (이미지 경계 및 target_rect 경계 고려)
                current_block_width = min(block_size, target_rect.right() - x)
                current_block_height = min(block_size, target_rect.bottom() - y)
                block_rect = QRect(x, y, current_block_width, current_block_height)

                if block_rect.width() <= 0 or block_rect.height() <= 0: continue

                total_r, total_g, total_b, count = 0, 0, 0, 0
                # 블록 내 픽셀 순회하며 평균 계산
                for block_y in range(block_rect.top(), block_rect.bottom()):
                    for block_x in range(block_rect.left(), block_rect.right()):
                        # source_image에서 색상 값 가져오기
                        pixel_color = QColor(source_image.pixel(block_x, block_y))
                        total_r += pixel_color.red()
                        total_g += pixel_color.green()
                        total_b += pixel_color.blue()
                        count += 1
                
                if count > 0:
                    avg_r = total_r // count
                    avg_g = total_g // count
                    avg_b = total_b // count
                    average_colors[(x, y)] = QColor(avg_r, avg_g, avg_b)

        # 계산된 평균 색상으로 블록 채우기
        for y in range(target_rect.top(), target_rect.bottom(), block_size):
            for x in range(target_rect.left(), target_rect.right(), block_size):
                if (x, y) in average_colors:
                    current_block_width = min(block_size, target_rect.right() - x)
                    current_block_height = min(block_size, target_rect.bottom() - y)
                    block_rect = QRect(x, y, current_block_width, current_block_height)
                    painter.fillRect(block_rect, average_colors[(x, y)])
        
        painter.end()
        print(f"Applied mosaic to rect: {target_rect} with block size: {block_size}")
        # self.update_canvas() # mouseReleaseEvent에서 호출됨

    def load_image(self, image_path):
        """이미지 로드 및 표시, Undo 스택 초기화"""
        if not os.path.exists(image_path):
            QMessageBox.warning(self, "Error", "Image file not found!")
            return False
            
        image = QImage(image_path)
        if image.isNull():
            QMessageBox.warning(self, "Error", "Failed to load image!")
            return False
            
        self.original_image = image
        self.edited_image = QImage(image) # 편집용 복사본 생성
        
        # Undo/Redo 스택 초기화 및 초기 상태 추가
        self.undo_stack = [QImage(self.original_image)] # 초기 상태는 원본
        self.redo_stack = []
        self.update_undo_redo_actions() # 버튼 상태 업데이트
        
        self.update_canvas() # 초기 이미지 표시
        
        filename = os.path.basename(image_path)
        self.setWindowTitle(f'Image Editor - {filename}')
        
        return True
        
    def resizeEvent(self, event):
        """창 크기 변경 시 이미지 표시 업데이트"""
        super().resizeEvent(event)
        self.update_canvas() # 리사이즈 시 캔버스 다시 그리도록 명시

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
    
    test_image = None
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        test_image = sys.argv[1]
        
    editor = ImageEditor(test_image)
    editor.show()
    
    sys.exit(app.exec_()) 