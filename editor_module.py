import sys
import os
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QLabel, QAction, 
                            QToolBar, QFileDialog, QMessageBox, QApplication, QDesktopWidget, 
                            QToolButton, QMenu, QColorDialog, QComboBox, QLineEdit)
from PyQt5.QtGui import QPixmap, QImage, QIcon, QPainter, QPen, QColor, QPolygonF, QBrush, QFont, QFontMetrics, QCursor, QPainterPath, QTransform
from PyQt5.QtCore import Qt, QSize, QRect, QPoint, QRectF, QSizeF, QLineF, QPointF, pyqtSignal, QBuffer, QIODevice
import math
import traceback
import io
from PIL import Image
import win32clipboard
# 사용자 정의 색상 선택기 import
from color_picker_module import CustomColorPicker 
# 분리된 ImageCanvas import
from canvas_widget import ImageCanvas

class ImageEditor(QMainWindow):
    """이미지 편집 기능을 제공하는 창"""
    # 저장 완료 시그널 (저장된 파일 경로 전달)
    imageSaved = pyqtSignal(str)
    
    # 모자이크 레벨 상수 정의
    MOSAIC_LEVELS = {'Weak': 5, 'Medium': 10, 'Strong': 20}
    # 기본 화살표 두께 옵션
    # ARROW_THICKNESS_OPTIONS = ["1px", "2px", "3px", "5px", "8px"] 
    # 기본 폰트 크기 (두께 대신 사용)
    DEFAULT_FONT_SIZE = 12
    MAX_FONT_SIZE = 72

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
        self.is_adding_text = False # 텍스트 추가 상태 플래그
        self.crop_rect_widget = None # 자르기 영역 위젯 좌표 (QRect)
        self.selection_rect_widget = None # 새 선택 도구 영역 위젯 좌표 (QRect)
        self.selected_content_pixmap = None # 띄어낸 이미지 콘텐츠 (QPixmap)
        self.selected_content_rect_widget = None # 띄어낸 콘텐츠의 현재 위치/크기 (QRect)
        self.is_selection_active = False # 콘텐츠가 띄어진 활성 상태인지 여부
        
        # 화살표 색상/두께 변수
        self.arrow_color = QColor(Qt.red) 
        self.current_arrow_thickness = CustomColorPicker.DEFAULT_THICKNESS 
        
        # 원 색상/두께 변수 추가
        self.circle_color = QColor(Qt.blue) # 기본 파란색
        self.current_circle_thickness = CustomColorPicker.DEFAULT_THICKNESS # 기본 두께
        
        # 사각형 색상/두께 변수 추가
        self.rectangle_color = QColor(Qt.green) # 기본 초록색
        self.current_rectangle_thickness = CustomColorPicker.DEFAULT_THICKNESS # 기본 두께
        
        # 하이라이트 색상/두께 변수 추가
        self.highlight_color = QColor(255, 255, 0, 128) # 기본 노란색, 반투명 (Alpha 128)
        # 초기 선택값 12px에 대응하는 실제 그리기 두께 24px로 설정
        self.current_highlight_thickness = 24 
        self.highlight_overlay_image = None # 하이라이트 오버레이 이미지
        
        # 펜 색상/두께 변수 추가
        self.pen_color = QColor(Qt.red) # 기본 빨간색
        self.current_pen_thickness = CustomColorPicker.DEFAULT_THICKNESS # 기본 두께
        
        # 텍스트 색상/크기 변수 추가
        self.text_color = QColor(Qt.black) # 기본 검정색
        self.text_font_size = self.DEFAULT_FONT_SIZE # 기본 폰트 크기
        
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
        """실행 취소 (상태는 작업 *후* 저장됨)"""
        if len(self.undo_stack) > 1: # 현재 상태 외에 이전 상태가 있어야 함 (원본 상태는 Undo 불가)
            # 현재 상태(Undo할 상태)를 Undo 스택에서 제거하고 Redo 스택에 추가
            current_state = self.undo_stack.pop()
            self.redo_stack.append(current_state) # 작업 후 상태 저장

            # 이전 상태(이제 Undo 스택의 마지막 상태)를 편집 이미지로 복원
            previous_state = self.undo_stack[-1]
            self.edited_image = QImage(previous_state) # 복사본 사용

            self.update_canvas()
            self.update_undo_redo_actions()
        # else:
        #    print("[Undo] Cannot undo initial state.")

    def redo_action_triggered(self):
        """다시 실행 (상태는 작업 *후* 저장됨)"""
        if self.redo_stack:
            # Redo 스택에서 상태(복원할 작업 후 상태)를 가져옴
            redo_state = self.redo_stack.pop()
            # 가져온 상태를 다시 Undo 스택에 추가
            self.undo_stack.append(QImage(redo_state)) # 복사본 사용
            # Redo 상태 적용
            self.edited_image = QImage(redo_state) # 복사본 사용

            self.update_canvas()
            self.update_undo_redo_actions()
            
    def update_undo_redo_actions(self):
        """Undo/Redo 액션 활성화/비활성화 업데이트"""
        # 'undo_action'과 'redo_action' 속성이 있는지 확인 후 상태 업데이트
        if hasattr(self, 'undo_action'):
             # 원본 상태 외에 다른 상태가 있을 때만 Undo 활성화
             self.undo_action.setEnabled(len(self.undo_stack) > 1)
        if hasattr(self, 'redo_action'):
             self.redo_action.setEnabled(len(self.redo_stack) > 0)

    def reset_image(self):
        """이미지를 원본 상태로 되돌립니다."""
        if not self.original_image or self.original_image.isNull():
            print("[Reset] No original image to reset to.")
            return
        
        if self.edited_image and self.edited_image != self.original_image:
            print("[Reset] Resetting image to original state...")
            # Redo 스택을 비우고, Undo 스택에는 원본 이미지만 남김
            self.redo_stack.clear()
            self.undo_stack = [QImage(self.original_image)]
            self.edited_image = QImage(self.original_image)
            
            self.update_canvas()
            self.update_undo_redo_actions()
            # 모든 도구 상태 및 선택 상태 초기화
            self.reset_tool_state() 
            self.reset_selection_state()
            # 오버레이 이미지 초기화
            self.initialize_overlay()
            print("[Reset] Image reset successfully.")
        else:
            print("[Reset] Image is already in its original state.")

    # 캔버스 업데이트 함수
    def update_canvas(self):
        """편집된 이미지로 캔버스를 업데이트"""
        if self.edited_image:
            self.image_canvas.setImage(self.edited_image)
            self.image_canvas.update() # QWidget의 update() 호출

    def createToolBar(self):
        """툴바 생성 및 버튼 추가 (모자이크 버튼 수정)"""
        self.toolbar = QToolBar("Main Toolbar")
        self.toolbar.setIconSize(QSize(24, 24))
        self.toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        # Set font size for toolbar buttons
        self.toolbar.setStyleSheet("QToolButton { font-size: 8pt; }")
        self.addToolBar(self.toolbar)
        
        # 저장 버튼
        save_action = QAction(QIcon("assets/save_icon.svg"), "Save", self)
        save_action.setToolTip("Save image and close editor") # 툴큁 수정
        save_action.triggered.connect(self.save_image_and_close) # 시그널 연결
        self.toolbar.addAction(save_action)
        
        copy_action = QAction(QIcon("assets/copy_icon.svg"), "Copy", self)
        copy_action.setToolTip("Copy to clipboard")
        copy_action.triggered.connect(self.copy_to_clipboard) # 시그널 연결
        self.toolbar.addAction(copy_action)
        
        self.toolbar.addSeparator()

        # 실행 취소 버튼 (undo_action_triggered 연결)
        self.undo_action = QAction(QIcon("assets/undo_icon.svg"), "Undo", self)
        self.undo_action.setToolTip("Undo last action")
        self.undo_action.triggered.connect(self.undo_action_triggered)
        self.undo_action.setEnabled(False) # 초기 비활성화
        self.toolbar.addAction(self.undo_action)
        
        # 다시 실행 버튼 (redo_action_triggered 연결)
        self.redo_action = QAction(QIcon("assets/redo_icon.svg"), "Redo", self)
        self.redo_action.setToolTip("Redo last action")
        self.redo_action.triggered.connect(self.redo_action_triggered)
        self.redo_action.setEnabled(False) # 초기 비활성화
        self.toolbar.addAction(self.redo_action)

        # 리셋 버튼 (기능 구현 필요)
        reset_action = QAction(QIcon("assets/reset_icon.svg"), "Reset", self)
        reset_action.setToolTip("Reset to original image")
        reset_action.triggered.connect(self.reset_image) # 시그널 연결
        self.toolbar.addAction(reset_action)
        
        self.toolbar.addSeparator()
        
        # 이미지 회전 버튼
        rotate_action = QAction(QIcon("assets/rotate_icon.svg"), "Rotate", self)
        rotate_action.setToolTip("Rotate image 90 degrees clockwise")
        rotate_action.triggered.connect(self.rotate_image)
        self.toolbar.addAction(rotate_action)
        
        # 좌우 반전 버튼
        flip_h_action = QAction(QIcon("assets/flip_h_icon.svg"), "Flip H", self)
        flip_h_action.setToolTip("Flip horizontally")
        flip_h_action.triggered.connect(self.flip_horizontally) # 시그널 연결
        self.toolbar.addAction(flip_h_action)
        
        # 상하 반전 버튼
        flip_v_action = QAction(QIcon("assets/flip_v_icon.svg"), "Flip V", self)
        flip_v_action.setToolTip("Flip vertically")
        flip_v_action.triggered.connect(self.flip_vertically) # 시그널 연결
        self.toolbar.addAction(flip_v_action)

        self.toolbar.addSeparator()

        # 그리기 도구 버튼들
        
        # 도구 선택 버튼 (activate_select_tool 연결)
        select_action = QAction(QIcon("assets/select_icon.svg"), "Select", self)
        select_action.setToolTip("Select area")
        select_action.triggered.connect(self.activate_select_tool) # 시그널 연결
        self.toolbar.addAction(select_action)
        
        # 자르기 버튼 (activate_crop_tool 연결)
        crop_action = QAction(QIcon("assets/crop_icon.svg"), "Crop", self)
        crop_action.setToolTip("Crop image (Press Enter to confirm)")
        crop_action.triggered.connect(self.activate_crop_tool) # 시그널 연결
        self.toolbar.addAction(crop_action)
        
        # 텍스트 추가 버튼 (activate_text_tool 연결)
        text_action = QAction(QIcon("assets/text_icon.svg"), "Text", self)
        text_action.setToolTip("Add text (Select color and size)") # 툴팁 수정
        text_action.triggered.connect(self.activate_text_tool) # 시그널 연결
        self.toolbar.addAction(text_action)
        
        # 펜 도구 버튼
        pen_action = QAction(QIcon("assets/pen_icon.svg"), "Pen", self)
        pen_action.setToolTip("Draw with pen (Select color and thickness)") # 툴팁 수정
        pen_action.triggered.connect(self.activate_pen_tool) # 시그널 연결 추가
        self.toolbar.addAction(pen_action)
        
        # 강조 도구 버튼
        highlight_action = QAction(QIcon("assets/highlight_icon.svg"), "Highlight", self)
        highlight_action.setToolTip("Highlight area (Select color and thickness)")
        highlight_action.triggered.connect(self.activate_highlight_tool)
        self.toolbar.addAction(highlight_action)
        
        # 도형 버튼 - 사각형
        rect_action = QAction(QIcon("assets/rectangle_icon.svg"), "Rectangle", self)
        rect_action.setToolTip("Draw rectangle (Select color and thickness)")
        rect_action.triggered.connect(self.activate_rectangle_tool)
        self.toolbar.addAction(rect_action)
        
        # 도형 버튼 - 원
        circle_action = QAction(QIcon("assets/circle_icon.svg"), "Circle", self)
        circle_action.setToolTip("Draw circle (Select color and thickness)")
        circle_action.triggered.connect(self.activate_circle_tool) # 시그널 연결 추가
        self.toolbar.addAction(circle_action)
        
        # 화살표 버튼 (원 버튼 다음으로 이동)
        arrow_action = QAction(QIcon("assets/arrow_icon.svg"), "Arrow", self)
        arrow_action.setToolTip("Draw arrow (Select color and thickness)") # 툴크 수정
        arrow_action.triggered.connect(self.activate_arrow_tool)
        self.toolbar.addAction(arrow_action)
        
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
        
        self.toolbar.addWidget(mosaic_button) # 툴바에 버튼 위젯 추가

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
        self.is_adding_text = False # 다른 도구 선택 시 텍스트 추가 상태 해제
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

    def activate_rectangle_tool(self):
        """사각형 그리기 도구 활성화, 색상/두께 선택 및 커서 변경"""
        self.current_tool = 'rectangle'
        # CustomColorPicker 호출 시 현재 사각형의 색상/두께 전달
        color, thickness, ok = CustomColorPicker.getColorAndThickness(
            self.rectangle_color, self.current_rectangle_thickness, self
        )
        
        if ok:
            self.rectangle_color = color
            self.current_rectangle_thickness = thickness
            print(f"Rectangle tool activated. Color: {self.rectangle_color.name()}, Thickness: {self.current_rectangle_thickness}")
            self.image_canvas.setCursor(Qt.CrossCursor)
            self.is_selecting = False
            self.selection_start_point = None
            self.selection_end_point = None
            self.is_adding_text = False # 다른 도구 선택 시 텍스트 추가 상태 해제
            self.image_canvas.update()
        else:
            print("Rectangle tool activation cancelled.")
            self.current_tool = None
            self.image_canvas.setCursor(Qt.ArrowCursor)

    def activate_circle_tool(self):
        """원 그리기 도구 활성화, 색상/두께 선택 및 커서 변경"""
        self.current_tool = 'circle'
        # CustomColorPicker 호출 시 현재 원의 색상/두께 전달
        color, thickness, ok = CustomColorPicker.getColorAndThickness(
            self.circle_color, self.current_circle_thickness, self
        )
        
        if ok:
            self.circle_color = color
            self.current_circle_thickness = thickness
            print(f"Circle tool activated. Color: {self.circle_color.name()}, Thickness: {self.current_circle_thickness}")
            self.image_canvas.setCursor(Qt.CrossCursor)
            self.is_selecting = False
            self.selection_start_point = None
            self.selection_end_point = None
            self.is_adding_text = False # 다른 도구 선택 시 텍스트 추가 상태 해제
            self.image_canvas.update()
        else:
            print("Circle tool activation cancelled.")
            self.current_tool = None
            self.image_canvas.setCursor(Qt.ArrowCursor)

    def activate_arrow_tool(self):
        """화살표 도구 활성화, 색상/두께 선택 및 커서 변경"""
        self.current_tool = 'arrow'
        # CustomColorPicker 호출 시 현재 두께 전달, 반환값으로 두께 받음
        color, thickness, ok = CustomColorPicker.getColorAndThickness(
            self.arrow_color, self.current_arrow_thickness, self 
        ) 
        
        if ok:
            self.arrow_color = color
            # 반환된 두께로 업데이트
            self.current_arrow_thickness = thickness 
            print(f"Arrow tool activated. Color: {self.arrow_color.name()}, Thickness: {self.current_arrow_thickness}")
            self.image_canvas.setCursor(Qt.CrossCursor)
            self.is_selecting = False
            self.selection_start_point = None
            self.selection_end_point = None
            self.is_adding_text = False # 다른 도구 선택 시 텍스트 추가 상태 해제
            self.image_canvas.update()
        else: 
            print("Arrow tool activation cancelled.")
            self.current_tool = None 
            self.image_canvas.setCursor(Qt.ArrowCursor)

    def activate_pen_tool(self):
        """펜 도구 활성화, 색상/두께 선택 및 커서 변경"""
        self.current_tool = 'pen'
        # CustomColorPicker 호출 시 현재 펜 색상 및 두께 전달
        color, thickness, ok = CustomColorPicker.getColorAndThickness(
            self.pen_color, self.current_pen_thickness, self
        )
        
        if ok:
            self.pen_color = color
            self.current_pen_thickness = thickness
            print(f"Pen tool activated. Color: {self.pen_color.name()}, Thickness: {self.current_pen_thickness}")
            self.image_canvas.setCursor(Qt.CrossCursor) # 또는 Qt.PointingHandCursor 등
            self.is_selecting = False # 그리기 상태 초기화
            self.is_adding_text = False # 다른 도구 선택 시 텍스트 추가 상태 해제
            self.image_canvas.update()
        else:
            print("Pen tool activation cancelled.")
            self.current_tool = None
            self.image_canvas.setCursor(Qt.ArrowCursor)

    def activate_highlight_tool(self):
        """하이라이트 도구 활성화, 색상/두께 선택 및 커서 변경"""
        self.current_tool = 'highlight'
        # CustomColorPicker 호출 시 현재 하이라이트 색상(투명도 제외) 및 두께 전달
        # 색상 선택기에서는 투명도를 직접 설정하지 않으므로, 기본 색상의 RGB만 전달
        # 선택기 초기값 = 실제 두께 / 2 (최소 1)
        initial_thickness_for_picker = max(1, self.current_highlight_thickness // 2)
        initial_color_rgb = QColor(self.highlight_color.red(), self.highlight_color.green(), self.highlight_color.blue())
        color_rgb, selected_thickness, ok = CustomColorPicker.getColorAndThickness(
            initial_color_rgb, initial_thickness_for_picker, self
        )
        
        if ok:
            # 선택된 RGB 색상에 저장된 투명도(128)를 다시 적용
            self.highlight_color = QColor(color_rgb.red(), color_rgb.green(), color_rgb.blue(), 128)
            # 선택된 두께의 2배를 실제 그리기 두께로 설정
            self.current_highlight_thickness = selected_thickness * 2 
            print(f"Highlight tool activated. Selected Thickness (Picker): {selected_thickness}, Drawing Thickness (Actual): {self.current_highlight_thickness}, Color: {self.highlight_color.name(QColor.HexArgb)}")
            self.image_canvas.setCursor(Qt.CrossCursor) # 또는 다른 적절한 커서
            self.is_selecting = False # freehand drawing이므로 is_selecting 대신 다른 플래그 사용 가능성 있음
            self.is_adding_text = False # 다른 도구 선택 시 텍스트 추가 상태 해제
            self.stroke_points = [] # 스트로크 점 리스트 초기화
            self.image_canvas.update()
        else:
            print("Highlight tool activation cancelled.")
            self.current_tool = None
            self.image_canvas.setCursor(Qt.ArrowCursor)

    def activate_text_tool(self):
        """텍스트 도구 활성화, 색상/크기 선택 및 커서 변경"""
        self.current_tool = 'text'
        # CustomColorPicker 호출 (두께 대신 폰트 크기 선택)
        # getColorAndThickness 재사용, 두께 레이블이 폰트 크기임을 인지해야 함
        # Picker의 두께 범위를 폰트 크기에 맞게 조정 (1 ~ MAX_FONT_SIZE)
        # CustomColorPicker 클래스 자체를 수정하는 대신, 호출 시 범위 정보를 전달하거나,
        # 여기서는 일단 Picker의 기본 MAX_THICKNESS를 사용하고, 반환값을 검증.
        color, size, ok = CustomColorPicker.getColorAndThickness(
            self.text_color, self.text_font_size, self,
            # min_val=1, max_val=self.MAX_FONT_SIZE, # getColorAndThickness 수정 필요
            # thickness_label="Font Size:" # getColorAndThickness 수정 필요
        )

        if ok:
            self.text_color = color
            # 선택된 크기를 최대/최소 폰트 크기 내로 제한
            self.text_font_size = max(1, min(size, self.MAX_FONT_SIZE))
            print(f"Text tool activated. Color: {self.text_color.name()}, Font Size: {self.text_font_size}")
            self.image_canvas.setCursor(Qt.IBeamCursor) # 텍스트 입력 커서
            self.is_selecting = False # 다른 모드 비활성화
            self.is_adding_text = True # 텍스트 추가 모드 활성화
            self.selection_start_point = None
            self.selection_end_point = None
            self.image_canvas.update()
        else:
            print("Text tool activation cancelled.")
            self.current_tool = None
            self.image_canvas.setCursor(Qt.ArrowCursor)
            self.is_adding_text = False

    def activate_select_tool(self):
        """선택 도구 활성화"""
        print("[DEBUG] activate_select_tool called")
        self.current_tool = 'select'
        self.is_selecting = False # 영역 드래그 상태 초기화
        self.is_adding_text = False
        self.crop_rect_widget = None
        self.selection_rect_widget = None # 선택 영역 표시 초기화
        self.reset_selection_state() # 이전 활성 선택 초기화
        # is_selecting 플래그는 영역 드래그 시 ImageCanvas에서 True로 설정됨
        self.image_canvas.setCursor(Qt.CrossCursor) # 선택 커서
        print("Select tool activated.")
        self.image_canvas.update() # 이전 상태 지우기

    def activate_crop_tool(self):
        """자르기 도구 활성화"""
        print("[DEBUG] activate_crop_tool called")
        try:
            if not self.edited_image or self.edited_image.isNull(): 
                print("[DEBUG] No image loaded, cannot activate crop tool.")
                return
            
            self.current_tool = 'crop'
            print("[DEBUG] Crop tool set.")
            # 초기 자르기 영역 설정 (캔버스에 표시되는 이미지 영역 기준)
            # ImageCanvas의 paintEvent에서 사용된 target_rect 계산 로직 활용
            img_size = self.edited_image.size()
            widget_rect = self.image_canvas.rect()
            print(f"[DEBUG] Image size: {img_size}, Widget rect: {widget_rect}")
            if widget_rect.width() <= 0 or widget_rect.height() <= 0:
                print("[ERROR] Canvas widget size is invalid.")
                self.current_tool = None # 도구 설정 취소
                return
                
            scaled_size = img_size.scaled(widget_rect.size(), Qt.KeepAspectRatio)
            print(f"[DEBUG] Scaled image size: {scaled_size}")
            if scaled_size.width() <= 0 or scaled_size.height() <= 0:
                 print("[ERROR] Scaled image size is invalid.")
                 self.current_tool = None
                 return
                 
            x = (widget_rect.width() - scaled_size.width()) / 2
            y = (widget_rect.height() - scaled_size.height()) / 2
            # QRect 생성 시 정수 좌표 사용
            initial_crop_rect = QRect(int(x), int(y), scaled_size.width(), scaled_size.height())
            print(f"[DEBUG] Calculated initial rect (before adjust): {initial_crop_rect}")
            
            # 테두리 안쪽으로 약간 줄여서 시작 (선택적)
            initial_crop_rect.adjust(5, 5, -5, -5)
            print(f"[DEBUG] Adjusted initial rect: {initial_crop_rect}")

            # 생성된 사각형이 유효한지 한번 더 확인
            if not initial_crop_rect.isValid() or initial_crop_rect.width() <= 0 or initial_crop_rect.height() <= 0:
                 print(f"[ERROR] Initial crop rectangle is invalid after creation/adjustment.")
                 self.current_tool = None
                 return
                 
            self.crop_rect_widget = initial_crop_rect
            print(f"Crop tool activated. Initial rect set: {self.crop_rect_widget}")
            self.image_canvas.setCursor(Qt.ArrowCursor) # 핸들 위에서 커서 변경 예정
            self.is_selecting = False
            self.is_adding_text = False
            self.reset_selection_state() # 선택 활성 상태 초기화
            self.image_canvas.update() # 오버레이 표시
            print("[DEBUG] Crop overlay update requested.")
        except Exception as e:
            print(f"[ERROR] Exception in activate_crop_tool: {e}")
            traceback.print_exc()
            self.current_tool = None # 에러 시 도구 상태 초기화

    def apply_crop(self):
        """현재 crop_rect_widget 기준으로 이미지 자르기 수행"""
        print("[DEBUG] apply_crop called")
        try:
            if self.current_tool != 'crop' or not self.crop_rect_widget or not self.edited_image:
                print("[ApplyCrop] Crop tool not active or no crop rect/image.")
                return

            print(f"[ApplyCrop] Applying crop with widget rect: {self.crop_rect_widget}")
            
            # 위젯 좌표를 이미지 원본 좌표로 변환
            print("[DEBUG] Calling map_widget_rect_to_image_rect")
            img_rect = self.map_widget_rect_to_image_rect(self.crop_rect_widget)
            print(f"[DEBUG] map_widget_rect_to_image_rect returned: {img_rect}")
            
            if not img_rect or not img_rect.isValid() or img_rect.width() <= 0 or img_rect.height() <= 0:
                print("[ApplyCrop] Invalid image crop rectangle after mapping.")
                self.reset_tool_state() # 상태 초기화
                return
                
            # 이미지 경계와 교차하는 유효한 영역만 사용
            print("[DEBUG] Calculating intersection with image bounds")
            valid_img_rect = img_rect.intersected(self.edited_image.rect())
            print(f"[DEBUG] Valid intersected image rect: {valid_img_rect}")
            if not valid_img_rect.isValid() or valid_img_rect.width() <= 0 or valid_img_rect.height() <= 0:
                print("[ApplyCrop] Crop rectangle is outside image bounds.")
                self.reset_tool_state()
                return

            print(f"[ApplyCrop] Cropping to image rect: {valid_img_rect}")
            # try...except 블록을 중첩하여 자르기 자체의 오류 처리
            try:
                # self.push_undo_state() # 자르기 전 상태 저장 -> 작업 후로 이동
                print("[DEBUG] Calling edited_image.copy()")
                cropped_image = self.edited_image.copy(valid_img_rect)
                print("[DEBUG] edited_image.copy() finished")
                self.edited_image = cropped_image
                # self.original_image = QImage(self.edited_image) # 자른 후에는 원본도 업데이트 (선택적) -> 제거: 원본은 유지
                self.push_undo_state() # 작업 후 상태 저장
                print("[DEBUG] Calling update_canvas after crop")
                self.update_canvas()
                print("[DEBUG] Calling initialize_overlay after crop")
                self.initialize_overlay() # 오버레이 이미지 크기 재설정
                print("[ApplyCrop] Crop successful.")
            except Exception as e:
                print(f"[ApplyCrop] Error during cropping: {e}")
                traceback.print_exc()
                # 에러 발생 시 undo 스택 복구 시도 (주의 필요)
                print("[DEBUG] Attempting to restore undo stack after crop error")
                if self.undo_stack: self.undo_stack.pop()
            
            print("[DEBUG] Calling reset_tool_state after apply_crop")
            self.reset_tool_state()
            print("[DEBUG] Calling update_undo_redo_actions after apply_crop")
            self.update_undo_redo_actions()
            self.reset_selection_state() # 자르기 후 선택 상태 초기화
        except Exception as e:
            print(f"[ERROR] Exception in apply_crop outer block: {e}")
            traceback.print_exc()
            self.reset_tool_state() # 외부 블록 에러 시에도 초기화

    def map_widget_rect_to_image_rect(self, widget_rect):
        """위젯 좌표계의 QRect를 이미지 원본 좌표계의 QRect로 변환"""
        print(f"[DEBUG] map_widget_rect_to_image_rect called with widget_rect: {widget_rect}")
        try:
            if not self.image_canvas or not self.image_canvas.image or self.image_canvas.image.isNull():
                print("[ERROR] Cannot map rect, canvas or image is invalid.")
                return None

            # 좌상단과 우하단 점을 변환
            top_left_widget = widget_rect.topLeft()
            bottom_right_widget = widget_rect.bottomRight()
            print(f"[DEBUG] Mapping top-left: {top_left_widget}, bottom-right: {bottom_right_widget}")

            top_left_img = self.image_canvas.map_widget_to_image(top_left_widget)
            bottom_right_img = self.image_canvas.map_widget_to_image(bottom_right_widget)
            print(f"[DEBUG] Mapped top-left: {top_left_img}, bottom-right: {bottom_right_img}")

            if top_left_img and bottom_right_img:
                # 변환된 점으로 QRect 생성 (정규화 필요 없음, map_widget_to_image에서 경계 처리됨)
                img_rect = QRect(top_left_img, bottom_right_img).normalized()
                print(f"[DEBUG] Calculated image rect: {img_rect}")
                return img_rect
            else:
                print("[MapRect] Failed to map one or both corner points.")
                return None
        except Exception as e:
            print(f"[ERROR] Exception in map_widget_rect_to_image_rect: {e}")
            traceback.print_exc()
            return None
            
    def reset_tool_state(self):
         """현재 도구 상태 초기화 (자르기 완료/취소 후)"""
         self.current_tool = None
         self.crop_rect_widget = None
         self.image_canvas.setCursor(Qt.ArrowCursor)
         self.image_canvas.dragging_handle = ImageCanvas.NO_HANDLE
         self.image_canvas.update()

    def keyPressEvent(self, event):
        """키 입력 이벤트 처리 (Enter 키로 자르기 확인)"""
        try:
            if self.current_tool == 'crop' and event.key() in (Qt.Key_Return, Qt.Key_Enter):
                print("[DEBUG] Enter key pressed in crop mode.")
                self.apply_crop()
            # 활성 선택 상태에서 Enter 키 입력 시 병합
            elif self.is_selection_active and event.key() in (Qt.Key_Return, Qt.Key_Enter):
                 print("[DEBUG] Enter key pressed with active selection. Merging...")
                 self.merge_selection()
            else:
                super().keyPressEvent(event) # 다른 키 이벤트는 기본 처리
        except Exception as e:
            print(f"[ERROR] Exception in keyPressEvent: {e}")
            traceback.print_exc()

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
        
        # 오버레이 이미지 초기화 (로드된 이미지 크기 기준)
        self.initialize_overlay()
        
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

    def draw_arrow(self, img_start_pt, img_end_pt, color, thickness):
        """이미지에 화살표 그리기 (두께 파라미터 추가)"""
        print(f"[DrawArrow] Entered. Start: {img_start_pt}, End: {img_end_pt}, Color: {color.name()}, Thickness: {thickness}") # 두께 정보 추가
        if not self.edited_image or self.edited_image.isNull():
            print("[DrawArrow] Error: No edited image.") # 디버그 출력
            return

        painter = QPainter(self.edited_image)
        # thickness 파라미터 사용
        pen = QPen(color, thickness, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin) 
        painter.setPen(pen)
        painter.setBrush(QBrush(color)) 
        painter.setRenderHint(QPainter.Antialiasing)

        line = QLineF(img_start_pt, img_end_pt)
        painter.drawLine(line)

        # 두께에 비례하는 화살촉 크기
        arrow_size = 3.0 * thickness + 4 
        angle = math.atan2(-line.dy(), line.dx())

        arrow_p1 = line.p2() - QPointF(math.cos(angle + math.pi / 6) * arrow_size,
                                      -math.sin(angle + math.pi / 6) * arrow_size)
        arrow_p2 = line.p2() - QPointF(math.cos(angle - math.pi / 6) * arrow_size,
                                      -math.sin(angle - math.pi / 6) * arrow_size)
                                      
        arrow_head = QPolygonF([line.p2(), arrow_p1, arrow_p2])
        painter.drawPolygon(arrow_head)
        
        painter.end()
        print(f"[DrawArrow] Finished drawing.") # 디버그 출력

    def draw_circle(self, img_rect, color, thickness):
        """이미지에 원(타원) 그리기"""
        print(f"[DrawCircle] Entered. Rect: {img_rect}, Color: {color.name()}, Thickness: {thickness}")
        if not self.edited_image or self.edited_image.isNull():
            print("[DrawCircle] Error: No edited image.")
            return

        painter = QPainter(self.edited_image)
        pen = QPen(color, thickness, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush) # 원은 외곽선만 그림
        painter.setRenderHint(QPainter.Antialiasing)

        painter.drawEllipse(img_rect)
        
        painter.end()
        print(f"[DrawCircle] Finished drawing.")

    def draw_rectangle(self, img_rect, color, thickness):
        """이미지에 사각형 그리기"""
        print(f"[DrawRectangle] Entered. Rect: {img_rect}, Color: {color.name()}, Thickness: {thickness}")
        if not self.edited_image or self.edited_image.isNull():
            print("[DrawRectangle] Error: No edited image.")
            return

        painter = QPainter(self.edited_image)
        pen = QPen(color, thickness, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush) # 사각형은 외곽선만 그림
        painter.setRenderHint(QPainter.Antialiasing)

        painter.drawRect(img_rect)
        
        painter.end()
        print(f"[DrawRectangle] Finished drawing.")

    def draw_pen_segment(self, img_start_pt, img_end_pt, color, thickness):
        """이미지에 펜 선분(Segment) 그리기 (불투명)"""
        if not self.edited_image or self.edited_image.isNull() or not img_start_pt or not img_end_pt:
            return
        if img_start_pt == img_end_pt:
            return

        painter = QPainter(self.edited_image)
        # 펜 색상은 불투명 (Alpha 255)
        pen_color_opaque = QColor(color.red(), color.green(), color.blue(), 255)
        pen = QPen(pen_color_opaque, thickness, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        painter.setRenderHint(QPainter.Antialiasing)

        painter.drawLine(img_start_pt, img_end_pt)
        painter.end()

    def draw_highlight_stroke(self, img_points, color, thickness):
        """이미지에 하이라이트 획(Polyline) 그리기"""
        print(f"[DrawHighlight] Entered. Points: {len(img_points)}, Color: {color.name(QColor.HexArgb)}, Thickness: {thickness}")
        if not self.edited_image or self.edited_image.isNull() or len(img_points) < 2:
            print("[DrawHighlight] Error: No edited image or not enough points.")
            return

        painter = QPainter(self.edited_image)
        # QColor에 이미 투명도가 포함되어 있어야 함 (activate_highlight_tool에서 설정)
        pen = QPen(color, thickness, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Composition Mode 설정 (선택적, 기본값 SourceOver가 보통 적절)
        # painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

        # 이미지 좌표 점 리스트로 QPolygonF 생성
        polygon = QPolygonF([QPointF(p) for p in img_points])
        painter.drawPolyline(polygon)
        
        painter.end()
        print(f"[DrawHighlight] Finished drawing.")

    def initialize_overlay(self):
        """하이라이트 오버레이 이미지 초기화"""
        if self.edited_image and not self.edited_image.isNull():
            # ARGB32_Premultiplied가 투명도 처리에 더 효율적일 수 있음
            self.highlight_overlay_image = QImage(self.edited_image.size(), QImage.Format_ARGB32_Premultiplied)
            self.highlight_overlay_image.fill(Qt.transparent) # 투명하게 채움
            print("[Overlay] Initialized")
        else:
            self.highlight_overlay_image = None
            print("[Overlay] Cleared (no base image)")

    def draw_text(self, img_position, text, color, size):
        """이미지 상의 지정된 위치에 텍스트 그리기"""
        print(f"[DrawText] Entered. Pos: {img_position}, Text: '{text}', Color: {color.name()}, Size: {size}")
        if not self.edited_image or self.edited_image.isNull() or not text:
            print("[DrawText] Error: No edited image or empty text.")
            return

        painter = QPainter(self.edited_image)
        font = QFont()
        font.setPixelSize(size) # 픽셀 크기로 설정
        painter.setFont(font)
        painter.setPen(color) # 텍스트 색상 설정
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        # 폰트 메트릭스를 사용하여 텍스트 경계 계산
        fm = QFontMetrics(painter.font())
        bounding_rect = fm.boundingRect(text)

        # img_position을 좌상단으로 하고 계산된 크기를 갖는 QRect 생성
        # boundingRect는 때때로 음수 x/y를 가질 수 있으므로, 너비/높이만 사용
        target_rect = QRect(img_position, bounding_rect.size())
        # 필요하다면 약간의 패딩을 추가할 수 있음: target_rect.adjust(0, 0, 2, 2)

        # img_position을 좌상단 기준으로 텍스트 그리기 (QRect과 정렬 플래그 사용)
        painter.drawText(target_rect, Qt.AlignTop | Qt.AlignLeft, text)

        painter.end()
        print(f"[DrawText] Finished drawing text.")

    def flip_horizontally(self):
        """이미지를 수평으로 뒤집습니다."""
        if not self.edited_image or self.edited_image.isNull():
            print("[FlipH] No image to flip.")
            return
        
        try:
            print("[FlipH] Flipping horizontally...")
            # self.push_undo_state() # 뒤집기 전 상태 저장 -> 작업 후로 이동
            self.edited_image = self.edited_image.mirrored(True, False)
            self.push_undo_state() # 작업 후 상태 저장
            self.update_canvas()
            self.update_undo_redo_actions()
            # 오버레이 재설정 (선택적이지만 안전함)
            self.initialize_overlay() 
            print("[FlipH] Horizontal flip successful.")
        except Exception as e:
            print(f"[FlipH] Error during horizontal flip: {e}")
            traceback.print_exc()
            if self.undo_stack: self.undo_stack.pop() # 에러 시 undo 복구

    def flip_vertically(self):
        """이미지를 수직으로 뒤집습니다."""
        if not self.edited_image or self.edited_image.isNull():
            print("[FlipV] No image to flip.")
            return
            
        try:
            print("[FlipV] Flipping vertically...")
            # self.push_undo_state() # 뒤집기 전 상태 저장 -> 작업 후로 이동
            self.edited_image = self.edited_image.mirrored(False, True)
            self.push_undo_state() # 작업 후 상태 저장
            self.update_canvas()
            self.update_undo_redo_actions()
            # 오버레이 재설정
            self.initialize_overlay()
            print("[FlipV] Vertical flip successful.")
        except Exception as e:
            print(f"[FlipV] Error during vertical flip: {e}")
            traceback.print_exc()
            if self.undo_stack: self.undo_stack.pop() # 에러 시 undo 복구

    def lift_selection(self, widget_rect):
        """주어진 위젯 영역의 이미지를 띄어내어 활성 선택 상태로 만듦"""
        if not widget_rect or not widget_rect.isValid() or not self.edited_image:
            print("[LiftSelection] Invalid widget rectangle or no image.")
            return
            
        print(f"[LiftSelection] Attempting to lift from widget rect: {widget_rect}")
        img_rect = self.map_widget_rect_to_image_rect(widget_rect)
        
        if not img_rect or not img_rect.isValid():
            print("[LiftSelection] Failed to map widget rect to image rect.")
            return
            
        # 이미지 경계와 교차하는 유효한 영역만 사용
        valid_img_rect = img_rect.intersected(self.edited_image.rect())
        if not valid_img_rect.isValid() or valid_img_rect.width() <= 0 or valid_img_rect.height() <= 0:
            print("[LiftSelection] Selection rectangle is outside image bounds or invalid.")
            return

        print(f"[LiftSelection] Copying image data from: {valid_img_rect}")
        try:
            # self.push_undo_state() # 띄어내기 전 상태 저장 -> 작업 후로 이동
            # QPixmap으로 복사 (투명 배경 지원 위해)
            copied_image = self.edited_image.copy(valid_img_rect)
            self.selected_content_pixmap = QPixmap.fromImage(copied_image)
            
            # 원본 이미지에서 해당 영역 비우기 (선택적 - 여기서는 투명 처리 시도)
            painter = QPainter(self.edited_image)
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(valid_img_rect, Qt.transparent)
            painter.end()
            
            self.selected_content_rect_widget = widget_rect # 위젯 좌표 기준 사각형 저장
            self.is_selection_active = True # 활성 선택 상태로 전환
            self.selection_rect_widget = None # 영역 선택 표시는 제거
            self.current_tool = 'select_transform' # 이동/변형 모드로 전환 (가칭)
            self.image_canvas.setCursor(Qt.ArrowCursor) # 기본 커서 (핸들 위에서 변경됨)
            self.update_canvas() # 캔버스 업데이트 (띄어진 이미지 표시)
            print(f"[LiftSelection] Selection lifted successfully. Content rect: {self.selected_content_rect_widget}")

        except Exception as e:
            print(f"[LiftSelection] Error during lifting selection: {e}")
            traceback.print_exc()
            if self.undo_stack: self.undo_stack.pop() # 에러 시 undo 복구
            self.reset_selection_state()
            self.current_tool = None # 도구 초기화
            
    def reset_selection_state(self):
        """활성 선택 상태 관련 변수 초기화"""
        self.is_selection_active = False
        self.selected_content_pixmap = None
        self.selected_content_rect_widget = None
        # self.selection_rect_widget = None # 필요시 추가
        print("[DEBUG] Selection state reset.")
            
    def reset_tool_state(self):
        """현재 도구 상태 초기화 (자르기 완료/취소 후)"""
        self.current_tool = None
        self.crop_rect_widget = None
        self.image_canvas.setCursor(Qt.ArrowCursor)
        self.image_canvas.dragging_handle = ImageCanvas.NO_HANDLE
        self.image_canvas.update()

    def merge_selection(self):
        """활성화된 선택 콘텐츠를 주 이미지에 병합"""
        if not self.is_selection_active or not self.selected_content_pixmap or not self.selected_content_rect_widget:
            print("[MergeSelection] No active selection to merge.")
            return
            
        print(f"[MergeSelection] Merging selection at widget rect: {self.selected_content_rect_widget}")
        # 위젯 좌표계의 사각형을 이미지 좌표계로 변환해야 함
        img_target_rect = self.map_widget_rect_to_image_rect(self.selected_content_rect_widget)
        
        if not img_target_rect or not img_target_rect.isValid():
            print("[MergeSelection] Failed to map target rectangle to image coordinates.")
            # 병합 실패 시, 선택 상태는 유지할지 초기화할지 결정 필요
            # self.reset_selection_state() # 예: 실패 시 초기화
            return
            
        try:
            # self.push_undo_state() # 병합 전 상태 저장 -> 작업 후로 이동
            painter = QPainter(self.edited_image)
            # QPixmap을 QRect에 맞춰 그림 (source rect는 QPixmap 전체)
            painter.drawPixmap(img_target_rect, self.selected_content_pixmap, self.selected_content_pixmap.rect())
            painter.end()
            self.push_undo_state() # 작업 후 상태 저장
            print("[MergeSelection] Selection merged successfully.")
            self.update_canvas()
            self.update_undo_redo_actions()
            
        except Exception as e:
            print(f"[MergeSelection] Error during merging: {e}")
            traceback.print_exc()
            if self.undo_stack: self.undo_stack.pop() # 에러 시 undo 복구
            
        # 병합 성공/실패 여부와 관계없이 선택 상태는 초기화
        self.reset_selection_state()
        self.current_tool = None # 도구 선택도 초기화

    def rotate_image(self):
        """이미지를 시계 방향으로 90도 회전합니다."""
        if not self.edited_image or self.edited_image.isNull():
            print("[Rotate] No image to rotate.")
            return
            
        try:
            print("[Rotate] Rotating 90 degrees clockwise...")
            # self.push_undo_state() # 회전 전 상태 저장 -> 작업 후로 이동
            
            # QTransform을 사용하여 90도 회전 적용
            transform = QTransform()
            transform.rotate(90)
            self.edited_image = self.edited_image.transformed(transform, Qt.SmoothTransformation)
            
            self.push_undo_state() # 작업 후 상태 저장
            self.update_canvas()
            self.update_undo_redo_actions()
            # 회전 후 이미지 크기가 변경되므로 오버레이 재설정
            self.initialize_overlay()
            print("[Rotate] Rotation successful.")
        except Exception as e:
            print(f"[Rotate] Error during rotation: {e}")
            traceback.print_exc()
            if self.undo_stack: self.undo_stack.pop() # 에러 시 undo 복구

    def copy_to_clipboard(self):
        """편집된 이미지를 Pillow와 pywin32를 사용하여 클립보드에 복사합니다."""
        print("[DEBUG] copy_to_clipboard (Pillow/pywin32) called.")
        if self.edited_image and not self.edited_image.isNull():
            print(f"[DEBUG] edited_image is valid. Size: {self.edited_image.size()}, Format: {self.edited_image.format()}")
            try:
                # 1. QImage를 Pillow Image로 변환
                buffer = QBuffer()
                buffer.open(QIODevice.WriteOnly)
                # PNG로 저장하여 투명도 유지 시도
                self.edited_image.save(buffer, "PNG") 
                buffer.seek(0) # 버퍼 포인터를 시작으로 이동
                pil_image = Image.open(io.BytesIO(buffer.data()))
                buffer.close()
                print("[DEBUG] QImage converted to Pillow Image.")

                # 2. Pillow Image를 DIB 형식으로 변환 (BMP 저장 후 헤더 제거)
                output = io.BytesIO()
                # Pillow 이미지를 BMP 형식으로 메모리에 저장 (RGB 모드로 변환 필요할 수 있음)
                # pil_image = pil_image.convert("RGB") # 필요시 주석 해제
                pil_image.save(output, "BMP")
                bmp_data = output.getvalue()
                output.close()
                
                # BMP 파일 헤더(14바이트)를 제외한 DIB 데이터 추출
                # BMP 파일 구조상 DIB 데이터는 14바이트 이후부터 시작
                dib_data = bmp_data[14:] 
                print(f"[DEBUG] Pillow Image converted to DIB format (size: {len(dib_data)} bytes).")

                # 3. win32clipboard를 사용하여 DIB 데이터 복사
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32clipboard.CF_DIB, dib_data)
                win32clipboard.CloseClipboard()
                print("[Copy] Image copied to clipboard using Pillow and pywin32 (CF_DIB).")

            except Exception as e:
                print(f"[ERROR] Exception during clipboard operation (Pillow/pywin32): {e}")
                traceback.print_exc()
                # 실패 시 클립보드 닫기 시도
                try:
                    win32clipboard.CloseClipboard()
                except Exception as e_close:
                    print(f"[ERROR] Failed to close clipboard after error: {e_close}")
        else:
            if not self.edited_image:
                print("[DEBUG] edited_image is None.")
            elif self.edited_image.isNull():
                print("[DEBUG] edited_image is Null.")
            print("No valid image to copy.")

    def save_image_and_close(self):
        """편집된 이미지를 원본 파일에 저장하고 창을 닫습니다."""
        if not self.edited_image or self.edited_image.isNull():
            QMessageBox.warning(self, "Warning", "No edited image to save.")
            print("[Save] No image available to save.")
            return
            
        if not self.image_path:
            QMessageBox.warning(self, "Warning", "Original image path is unknown. Cannot save.")
            print("[Save] Original image path not set.")
            # 또는 여기서 Save As 로직 호출 고려
            return

        # 변경 사항이 있는지 확인 (선택적이지만 권장)
        # if self.edited_image == self.original_image:
        #     print("[Save] No changes detected. Closing without saving.")
        #     self.close() # 변경 없으면 그냥 닫기
        #     return
            
        try:
            print(f"[Save] Saving image to: {self.image_path}")
            save_success = self.edited_image.save(self.image_path)
            
            if save_success:
                print("[Save] Image saved successfully.")
                # 저장 성공 시 시그널 발생
                self.imageSaved.emit(self.image_path)
                self.close() # 창 닫기
            else:
                QMessageBox.critical(self, "Error", f"Failed to save image to:\n{self.image_path}")
                print(f"[Save] Failed to save image file.")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred while saving:\n{e}")
            print(f"[Save] Error saving image: {e}")
            traceback.print_exc()

# 테스트 코드 (독립 실행용)
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    test_image = None
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        test_image = sys.argv[1]
        
    editor = ImageEditor(test_image)
    editor.show()
    
    sys.exit(app.exec_()) 