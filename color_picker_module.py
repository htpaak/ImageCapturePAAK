import sys
from PyQt5.QtWidgets import (QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QSlider, QSpinBox, QLineEdit, QPushButton, QApplication, QGridLayout,
                             QStyleFactory)
from PyQt5.QtGui import QColor, QPainter, QPixmap, QImage, QMouseEvent, QPen
from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QRect

class ColorSpectrumWidget(QWidget):
    """색상 스펙트럼 및 명도/채도 선택 영역 위젯"""
    colorSelected = pyqtSignal(QColor)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(200, 200)
        self._hue = 0 # 0-359
        self._saturation = 255 # 0-255
        self._value = 255 # 0-255
        self._hue_pixmap = self._generate_hue_spectrum()
        self._sv_pixmap = self._generate_sv_spectrum()
        self._current_pos = QPoint(self.width()-1, 0) # 초기 위치 (우상단 = 최대 채도, 최대 명도)

    def _generate_hue_spectrum(self):
        """HUE 스펙트럼 이미지 생성"""
        width = 20 # 스펙트럼 너비
        height = self.height()
        if height <= 0: height = 200 # 초기 높이
        
        img = QImage(width, height, QImage.Format_RGB32)
        painter = QPainter(img)
        
        for y in range(height):
            hue = int((y / height) * 360)
            color = QColor.fromHsv(hue, 255, 255)
            painter.setPen(color)
            painter.drawLine(0, y, width, y)
            
        painter.end()
        return QPixmap.fromImage(img)

    def _generate_sv_spectrum(self):
        """채도(S)/명도(V) 선택 영역 이미지 생성"""
        width = self.width() - 30 # Hue 슬라이더 영역 제외
        height = self.height()
        if width <= 0 or height <= 0: return QPixmap() # 크기 0 방지
            
        img = QImage(width, height, QImage.Format_RGB32)
        
        for y in range(height):
            for x in range(width):
                saturation = int((x / width) * 255)
                value = 255 - int((y / height) * 255)
                color = QColor.fromHsv(self._hue, saturation, value)
                img.setPixelColor(x, y, color)
                
        return QPixmap.fromImage(img)

    def paintEvent(self, event):
        painter = QPainter(self)
        
        # SV 영역 그리기
        sv_rect = QRect(0, 0, self.width() - 30, self.height())
        if not self._sv_pixmap.isNull():
             painter.drawPixmap(sv_rect.topLeft(), self._sv_pixmap)
             
        # Hue 영역 그리기
        hue_rect = QRect(self.width() - 20, 0, 20, self.height())
        if not self._hue_pixmap.isNull():
            painter.drawPixmap(hue_rect.topLeft(), self._hue_pixmap)

        # 현재 선택 포인터 그리기 (SV 영역)
        painter.setPen(QPen(Qt.white if self._value > 128 else Qt.black, 1))
        painter.setBrush(Qt.NoBrush)
        # self._current_pos가 SV 영역 내에 있도록 보정
        pointer_x = max(0, min(self._current_pos.x(), sv_rect.width() - 1))
        pointer_y = max(0, min(self._current_pos.y(), sv_rect.height() - 1))
        painter.drawEllipse(QPoint(pointer_x, pointer_y), 5, 5)
        
        # 현재 Hue 선택 포인터 그리기 (Hue 슬라이더 위)
        hue_y = int((self._hue / 360) * hue_rect.height())
        painter.setPen(QPen(Qt.black, 2))
        painter.drawLine(hue_rect.left(), hue_y, hue_rect.right(), hue_y)
        
    def resizeEvent(self, event):
        # 크기 변경 시 스펙트럼 다시 생성
        self._hue_pixmap = self._generate_hue_spectrum()
        self._sv_pixmap = self._generate_sv_spectrum()
        # 현재 위치 비율 유지 시도 (간단 버전)
        sv_width = self.width() - 30
        sv_height = self.height()
        if sv_width > 0 and sv_height > 0 :
             self._current_pos.setX(int((self._saturation / 255) * sv_width))
             self._current_pos.setY(int((1 - self._value / 255) * sv_height))
        self.update()
        
    def mousePressEvent(self, event: QMouseEvent):
        self._handle_mouse_event(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() & Qt.LeftButton:
            self._handle_mouse_event(event)

    def _handle_mouse_event(self, event: QMouseEvent):
        pos = event.pos()
        sv_rect = QRect(0, 0, self.width() - 30, self.height())
        hue_rect = QRect(self.width() - 20, 0, 20, self.height())

        if sv_rect.contains(pos):
            # SV 영역 클릭/드래그
            self._current_pos = pos
            self._saturation = int((pos.x() / sv_rect.width()) * 255)
            self._value = 255 - int((pos.y() / sv_rect.height()) * 255)
            # 경계값 보정
            self._saturation = max(0, min(self._saturation, 255))
            self._value = max(0, min(self._value, 255))
            self.update()
            self._emit_color()
        elif hue_rect.contains(pos):
            # Hue 영역 클릭/드래그
            self._hue = int((pos.y() / hue_rect.height()) * 360)
            self._hue = max(0, min(self._hue, 359))
            # Hue 변경 시 SV 스펙트럼 다시 생성 및 업데이트
            self._sv_pixmap = self._generate_sv_spectrum()
            self.update()
            self._emit_color()
            
    def setHue(self, hue):
        """외부에서 Hue 설정"""
        if 0 <= hue < 360 and self._hue != hue:
            self._hue = hue
            self._sv_pixmap = self._generate_sv_spectrum()
            self.update()
            self._emit_color()

    def setSaturationValue(self, saturation, value):
         """외부에서 Saturation, Value 설정"""
         if 0 <= saturation <= 255 and 0 <= value <= 255:
             changed = False
             if self._saturation != saturation:
                 self._saturation = saturation
                 changed = True
             if self._value != value:
                 self._value = value
                 changed = True
                 
             if changed:
                 sv_width = self.width() - 30
                 sv_height = self.height()
                 if sv_width > 0 and sv_height > 0 :
                      self._current_pos.setX(int((self._saturation / 255) * sv_width))
                      self._current_pos.setY(int((1 - self._value / 255) * sv_height))
                 self.update()
                 self._emit_color()

    def setColor(self, color: QColor):
        """외부에서 QColor 설정"""
        h, s, v, _ = color.getHsv()
        if h == -1: h = 0 # 무채색일 경우 hue는 0으로
        
        hue_changed = self._hue != h
        sv_changed = self._saturation != s or self._value != v

        self._hue = h
        self._saturation = s
        self._value = v
        
        if hue_changed:
            self._sv_pixmap = self._generate_sv_spectrum()
            
        if hue_changed or sv_changed:
            sv_width = self.width() - 30
            sv_height = self.height()
            if sv_width > 0 and sv_height > 0 :
                 self._current_pos.setX(int((self._saturation / 255) * sv_width))
                 self._current_pos.setY(int((1 - self._value / 255) * sv_height))
            self.update()
            # setColor는 외부 설정이므로, 내부 변경 시그널을 발생시키지 않을 수 있음
            # 필요하다면 self._emit_color() 호출

    def currentColor(self) -> QColor:
        return QColor.fromHsv(self._hue, self._saturation, self._value)

    def _emit_color(self):
        self.colorSelected.emit(self.currentColor())


class CustomColorPicker(QDialog):
    """사용자 정의 색상 선택 대화상자 (두께 선택: 슬라이더 + 스핀박스)"""
    DEFAULT_THICKNESS = 8 # 기본 두께 값
    MAX_THICKNESS = 72   # 최대 두께 값 (32에서 72로 변경)

    def __init__(self, initial_color=QColor(Qt.red), initial_thickness=DEFAULT_THICKNESS, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Color and Thickness")
        self.setMinimumWidth(350)

        self._selected_color = initial_color
        # 초기 두께 유효성 검사
        self._selected_thickness = max(1, min(initial_thickness, self.MAX_THICKNESS)) 

        # --- 위젯 생성 ---
        self.spectrum_widget = ColorSpectrumWidget(self)
        self.preview_widget = QLabel()
        self.preview_widget.setMinimumSize(60, 60) 
        self.preview_widget.setAlignment(Qt.AlignCenter)
        self._update_preview()

        # 두께 선택 (슬라이더 + 스핀박스)
        self.thickness_label = QLabel("Thickness:")
        self.thickness_label.setStyleSheet("font-size: 8pt;")
        self.thickness_slider = QSlider(Qt.Horizontal)
        self.thickness_slider.setRange(1, self.MAX_THICKNESS)
        self.thickness_spinbox = QSpinBox()
        self.thickness_spinbox.setStyleSheet("font-size: 8pt;")
        self.thickness_spinbox.setRange(1, self.MAX_THICKNESS)
        self.thickness_spinbox.setSuffix(" px") # 접미사 추가

        # HSV 슬라이더/스핀박스
        self.hue_label = QLabel("Hue:")
        self.hue_label.setStyleSheet("font-size: 8pt;")
        self.hue_slider = QSlider(Qt.Horizontal)
        self.hue_slider.setRange(0, 359)
        self.hue_spinbox = QSpinBox()
        self.hue_spinbox.setStyleSheet("font-size: 8pt;")
        self.hue_spinbox.setRange(0, 359)
        self.sat_label = QLabel("Sat:")
        self.sat_label.setStyleSheet("font-size: 8pt;")
        self.sat_slider = QSlider(Qt.Horizontal)
        self.sat_slider.setRange(0, 255)
        self.sat_spinbox = QSpinBox()
        self.sat_spinbox.setStyleSheet("font-size: 8pt;")
        self.sat_spinbox.setRange(0, 255)
        self.val_label = QLabel("Val:")
        self.val_label.setStyleSheet("font-size: 8pt;")
        self.val_slider = QSlider(Qt.Horizontal)
        self.val_slider.setRange(0, 255)
        self.val_spinbox = QSpinBox()
        self.val_spinbox.setStyleSheet("font-size: 8pt;")
        self.val_spinbox.setRange(0, 255)
        self.red_label = QLabel("Red:")
        self.red_label.setStyleSheet("font-size: 8pt;")
        self.red_spinbox = QSpinBox()
        self.red_spinbox.setStyleSheet("font-size: 8pt;")
        self.red_spinbox.setRange(0, 255)
        self.green_label = QLabel("Green:")
        self.green_label.setStyleSheet("font-size: 8pt;")
        self.green_spinbox = QSpinBox()
        self.green_spinbox.setStyleSheet("font-size: 8pt;")
        self.green_spinbox.setRange(0, 255)
        self.blue_label = QLabel("Blue:")
        self.blue_label.setStyleSheet("font-size: 8pt;")
        self.blue_spinbox = QSpinBox()
        self.blue_spinbox.setStyleSheet("font-size: 8pt;")
        self.blue_spinbox.setRange(0, 255)

        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("Cancel")

        # Apply original style with modified font size
        original_button_style = """
            QPushButton {
                background-color: rgba(52, 73, 94, 0.8);
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 8pt; /* Modified from 16px */
                font-weight: bold;
                padding: 5px 10px; /* Added padding for better look */
            }
            QPushButton:hover {
                background-color: rgba(52, 73, 94, 0.9);
            }
            QPushButton:pressed {
                background-color: rgba(52, 73, 94, 1.0);
            }
        """
        self.ok_button.setStyleSheet(original_button_style)
        self.cancel_button.setStyleSheet(original_button_style)

        # --- 레이아웃 재구성 ---
        main_layout = QVBoxLayout(self)
        top_layout = QHBoxLayout() 
        main_layout.addLayout(top_layout)
        top_layout.addWidget(self.spectrum_widget, 1) 
        right_controls_layout = QVBoxLayout()
        top_layout.addLayout(right_controls_layout)

        # 오른쪽 상단: 미리보기만
        right_controls_layout.addWidget(self.preview_widget, 0, Qt.AlignCenter) 
        right_controls_layout.addSpacing(10)

        # 값 조절 컨트롤 (그리드 레이아웃)
        grid_layout = QGridLayout()
        right_controls_layout.addLayout(grid_layout)
        
        # 두께 슬라이더/스핀박스 추가
        grid_layout.addWidget(self.thickness_label, 0, 0)
        grid_layout.addWidget(self.thickness_slider, 0, 1)
        grid_layout.addWidget(self.thickness_spinbox, 0, 2)
        
        # HSV (행 번호 조정)
        grid_layout.addWidget(self.hue_label, 1, 0)
        grid_layout.addWidget(self.hue_slider, 1, 1)
        grid_layout.addWidget(self.hue_spinbox, 1, 2)
        grid_layout.addWidget(self.sat_label, 2, 0)
        grid_layout.addWidget(self.sat_slider, 2, 1)
        grid_layout.addWidget(self.sat_spinbox, 2, 2)
        grid_layout.addWidget(self.val_label, 3, 0)
        grid_layout.addWidget(self.val_slider, 3, 1)
        grid_layout.addWidget(self.val_spinbox, 3, 2)
        
        # RGB (행 번호 조정)
        grid_layout.addWidget(self.red_label, 4, 0)
        grid_layout.addWidget(self.red_spinbox, 4, 1, 1, 2) 
        grid_layout.addWidget(self.green_label, 5, 0)
        grid_layout.addWidget(self.green_spinbox, 5, 1, 1, 2)
        grid_layout.addWidget(self.blue_label, 6, 0)
        grid_layout.addWidget(self.blue_spinbox, 6, 1, 1, 2)

        right_controls_layout.addStretch() 
        button_layout = QHBoxLayout()
        main_layout.addLayout(button_layout)
        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)

        # --- 시그널 연결 ---
        self.spectrum_widget.colorSelected.connect(self.update_controls)
        
        # 두께 슬라이더/스핀박스 연결
        self.thickness_slider.valueChanged.connect(self.thickness_spinbox.setValue)
        self.thickness_spinbox.valueChanged.connect(self.thickness_slider.setValue)
        self.thickness_spinbox.valueChanged.connect(self._update_thickness) # 스핀박스 값 변경 시 _selected_thickness 업데이트
        
        # HSV 슬라이더/스핀박스 연결
        self.hue_slider.valueChanged.connect(self.hue_spinbox.setValue)
        self.hue_spinbox.valueChanged.connect(self.hue_slider.setValue)
        self.sat_slider.valueChanged.connect(self.sat_spinbox.setValue)
        self.sat_spinbox.valueChanged.connect(self.sat_slider.setValue)
        self.val_slider.valueChanged.connect(self.val_spinbox.setValue)
        self.val_spinbox.valueChanged.connect(self.val_slider.setValue)
        self.hue_spinbox.valueChanged.connect(self._update_color_from_hsv)
        self.sat_spinbox.valueChanged.connect(self._update_color_from_hsv)
        self.val_spinbox.valueChanged.connect(self._update_color_from_hsv)
        self.red_spinbox.valueChanged.connect(self._update_color_from_rgb)
        self.green_spinbox.valueChanged.connect(self._update_color_from_rgb)
        self.blue_spinbox.valueChanged.connect(self._update_color_from_rgb)

        # 버튼 연결
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        
        # --- 초기값 설정 ---
        self.setColor(initial_color)
        # 두께 초기값 설정
        self.thickness_slider.setValue(self._selected_thickness)
        self.thickness_spinbox.setValue(self._selected_thickness)

    def setColor(self, color: QColor):
        """대화상자의 현재 색상 설정 및 모든 컨트롤 업데이트"""
        self._selected_color = color
        self.spectrum_widget.setColor(color)
        self.update_controls(color) # 모든 컨트롤 업데이트
        
    def _update_preview(self):
        """색상 미리보기 업데이트"""
        self.preview_widget.setStyleSheet(f"background-color: {self._selected_color.name()}; border: 1px solid black;")

    def update_controls(self, color: QColor):
        """색상 변경에 따라 모든 관련 컨트롤 값 업데이트 (재귀 방지 포함)"""
        # 초기화 시 값 설정을 막는 중복 방지 코드 제거
        # if self._selected_color == color: return 
             
        self._selected_color = color
        self._update_preview()

        controls_to_block = [
            self.hue_slider, self.hue_spinbox, self.sat_slider, self.sat_spinbox,
            self.val_slider, self.val_spinbox, self.red_spinbox, self.green_spinbox,
            self.blue_spinbox
        ]
        for control in controls_to_block: control.blockSignals(True)
        h, s, v, _ = color.getHsv()
        if h == -1: h = 0 
        self.hue_slider.setValue(h)
        self.hue_spinbox.setValue(h)
        self.sat_slider.setValue(s)
        self.sat_spinbox.setValue(s)
        self.val_slider.setValue(v)
        self.val_spinbox.setValue(v)
        
        self.red_spinbox.setValue(color.red())
        self.green_spinbox.setValue(color.green())
        self.blue_spinbox.setValue(color.blue())
        
        for control in controls_to_block: control.blockSignals(False)
        
        if self.sender() != self.spectrum_widget: 
             self.spectrum_widget.setColor(color)

    def _update_color_from_hsv(self):
        """HSV 컨트롤 값으로 색상 업데이트"""
        h = self.hue_spinbox.value()
        s = self.sat_spinbox.value()
        v = self.val_spinbox.value()
        new_color = QColor.fromHsv(h, s, v)
        self.update_controls(new_color) # 모든 컨트롤 동기화

    def _update_color_from_rgb(self):
        """RGB 컨트롤 값으로 색상 업데이트"""
        r = self.red_spinbox.value()
        g = self.green_spinbox.value()
        b = self.blue_spinbox.value()
        new_color = QColor(r, g, b)
        self.update_controls(new_color)

    def _update_thickness(self, value):
        """슬라이더/스핀박스 변경 시 두께 업데이트"""
        # 스핀박스 값은 접미사 없이 정수형으로 받음
        thickness = value 
        # 유효 범위 확인 (1 ~ MAX_THICKNESS)
        thickness = max(1, min(thickness, self.MAX_THICKNESS))
        if self._selected_thickness != thickness:
             self._selected_thickness = thickness
             print(f"Thickness updated to: {self._selected_thickness}")
             # 슬라이더/스핀박스 값 동기화 (시그널 블록킹 고려)
             self.thickness_slider.blockSignals(True)
             self.thickness_spinbox.blockSignals(True)
             self.thickness_slider.setValue(thickness)
             self.thickness_spinbox.setValue(thickness)
             self.thickness_slider.blockSignals(False)
             self.thickness_spinbox.blockSignals(False)

    def selectedColor(self) -> QColor:
        """선택된 최종 색상 반환"""
        return self._selected_color
        
    def selectedThickness(self) -> int:
        return self._selected_thickness

    @staticmethod
    def getColorAndThickness(initial_color=QColor(Qt.red), initial_thickness=DEFAULT_THICKNESS, parent=None) -> tuple[QColor, int, bool]: 
        dialog = CustomColorPicker(initial_color, initial_thickness, parent)
        result = dialog.exec_()
        color = dialog.selectedColor()
        thickness = dialog.selectedThickness()
        return color, thickness, result == QDialog.Accepted 

# 테스트용 실행 코드
if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # 사용자 정의 색상 및 두께 선택기 테스트
    initial_color = QColor(Qt.blue)
    initial_thick = 5
    # 수정된 메서드 호출
    selected_color, selected_thickness, ok = CustomColorPicker.getColorAndThickness(initial_color, initial_thick)

    if ok:
        print(f"Selected color: {selected_color.name()}, Thickness: {selected_thickness}px")
    else:
        print("Selection cancelled.")
        
    sys.exit() 