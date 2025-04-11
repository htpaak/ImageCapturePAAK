import sys
import os
import time
import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, 
                           QWidget, QLabel, QFileDialog, QHBoxLayout, QMessageBox,
                           QFrame, QSizePolicy, QToolTip, QStatusBar, QDesktopWidget,
                           QShortcut)
from PyQt5.QtGui import QPixmap, QIcon, QPainter, QPainterPath, QPen, QColor, QBrush, QFont, QKeySequence
from PyQt5.QtCore import Qt, QRect, QPoint, QRectF, QSize

class CaptureUI(QMainWindow):
    def __init__(self, capture_module):
        super().__init__()
        self.capture_module = capture_module
        self.is_selecting = False
        self.selection_start = QPoint()
        self.selection_end = QPoint()
        self.selection_rect = QRect()
        self.last_capture_path = None
        
        # Initialize save path before initUI method
        self.default_save_dir = os.path.join(os.path.expanduser("~"), "Pictures", "ScreenCaptures")
        
        # Create directory if it doesn't exist
        if not os.path.exists(self.default_save_dir):
            os.makedirs(self.default_save_dir)
            
        # Initialize UI
        self.initUI()
        
        # 단축키 설정
        self.setup_shortcuts()
        
        # Center the window on screen
        self.center_on_screen()

    def center_on_screen(self):
        """Center the window on the screen"""
        screen_geometry = QDesktopWidget().availableGeometry()
        window_geometry = self.frameGeometry()
        center_point = screen_geometry.center()
        window_geometry.moveCenter(center_point)
        self.move(window_geometry.topLeft())

    def initUI(self):
        """Initialize UI"""
        # Basic window settings
        self.setWindowTitle('Snipix')
        self.setGeometry(100, 100, 750, 750)  # 더 큰 창 크기로 설정
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QLabel {
                font-size: 16px;
            }
            QPushButton {
                background-color: rgba(52, 73, 94, 0.8);
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(52, 73, 94, 0.9);
            }
            QPushButton:pressed {
                background-color: rgba(52, 73, 94, 1.0);
            }
            QStatusBar {
                background-color: #e0e0e0;
                font-size: 15px;
            }
        """)

        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # 타이틀 레이아웃 (아이콘 + 텍스트)
        title_layout = QHBoxLayout()
        title_layout.setAlignment(Qt.AlignCenter)
        title_layout.setSpacing(10)  # 아이콘과 텍스트 사이 간격 조정
        
        # 아이콘 레이블
        icon_label = QLabel()
        icon_path = os.path.join('assets', 'icon.ico')
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path).scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon_label.setPixmap(pixmap)
        icon_label.setAlignment(Qt.AlignVCenter)  # 수직 가운데 정렬
        
        # Program title
        title_label = QLabel('Snipix')
        title_label.setStyleSheet("font-size: 28px; font-weight: bold; color: #333333;")
        title_label.setAlignment(Qt.AlignVCenter)  # 수직 가운데 정렬
        
        # 컨테이너 위젯을 생성하여 아이콘과 텍스트를 담음
        title_container = QWidget()
        title_inner_layout = QHBoxLayout(title_container)
        title_inner_layout.setContentsMargins(0, 0, 0, 0)  # 여백 제거
        title_inner_layout.setSpacing(12)
        title_inner_layout.addWidget(icon_label)
        title_inner_layout.addWidget(title_label)
        title_inner_layout.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        
        # 타이틀 레이아웃에 컨테이너 추가
        main_layout.addWidget(title_container, 0, Qt.AlignCenter)

        # Guide message
        guide_label = QLabel('Select the capture method you want')
        guide_label.setStyleSheet("font-size: 16px; color: #555555; margin-bottom: 5px;")
        guide_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(guide_label)

        # Button layout
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)

        # Full screen capture button
        self.capture_btn = QPushButton('Full Screen Capture')
        self.capture_btn.setMinimumHeight(90)  # 60 * 1.5 = 90
        self.capture_btn.setToolTip('Capture the entire screen')
        self.capture_btn.setIcon(QIcon.fromTheme('camera-photo'))
        self.capture_btn.clicked.connect(self.capture_full_screen)
        btn_layout.addWidget(self.capture_btn)

        # Area capture button
        self.area_btn = QPushButton('Rectangular Area Capture')
        self.area_btn.setMinimumHeight(90)  # 60 * 1.5 = 90
        self.area_btn.setToolTip('Drag to select an area to capture')
        self.area_btn.setIcon(QIcon.fromTheme('select-rectangular'))
        self.area_btn.clicked.connect(self.capture_area)
        btn_layout.addWidget(self.area_btn)

        # Add button layout
        main_layout.addLayout(btn_layout)

        # Add separator line
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("background-color: #cccccc;")
        main_layout.addWidget(line)

        # Preview title
        preview_title = QLabel('Captured Image Preview')
        preview_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #333333;")
        preview_title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(preview_title)

        # Preview frame
        preview_frame = QFrame()
        preview_frame.setFrameShape(QFrame.StyledPanel)
        preview_frame.setFrameShadow(QFrame.Sunken)
        preview_frame.setStyleSheet("background-color: white; border: 1px solid #cccccc; border-radius: 4px;")
        preview_layout = QVBoxLayout(preview_frame)

        # Preview label
        self.preview_label = QLabel('The preview will be displayed here after capture')
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("color: #888888; font-size: 16px;")
        self.preview_label.setMinimumHeight(420)  # 280 * 1.5 = 420
        self.preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        preview_layout.addWidget(self.preview_label)

        # Add preview frame
        main_layout.addWidget(preview_frame)

        # Save button layout
        save_layout = QHBoxLayout()
        save_layout.setSpacing(15)
        
        # Save path display label
        self.path_label = QLabel(f'Save Path: {self.default_save_dir}')
        self.path_label.setStyleSheet("font-size: 18px; color: #555555; padding: 8px 0;")
        save_layout.addWidget(self.path_label)
        
        # Set save path button
        self.path_btn = QPushButton('Change Path')
        self.path_btn.setMinimumHeight(68)  # 45 * 1.5 = 67.5
        self.path_btn.setMinimumWidth(150)
        self.path_btn.setToolTip('Change the save location for captured images')
        self.path_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(241, 196, 15, 0.8);
                font-size: 16px;
                color: white;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: rgba(241, 196, 15, 0.9);
            }
            QPushButton:pressed {
                background-color: rgba(241, 196, 15, 1.0);
            }
        """)
        self.path_btn.clicked.connect(self.set_save_path)
        save_layout.addWidget(self.path_btn)
        
        # 윈도우 탐색기로 저장 디렉토리 열기 버튼
        self.open_folder_btn = QPushButton('Open Folder')
        self.open_folder_btn.setMinimumHeight(68)  # 45 * 1.5 = 67.5
        self.open_folder_btn.setMinimumWidth(140)
        self.open_folder_btn.setToolTip('Open the save folder in file explorer')
        self.open_folder_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(41, 128, 185, 0.8);
                font-size: 16px;
                color: white;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: rgba(41, 128, 185, 0.9);
            }
            QPushButton:pressed {
                background-color: rgba(41, 128, 185, 1.0);
            }
        """)
        self.open_folder_btn.clicked.connect(self.open_save_folder)
        save_layout.addWidget(self.open_folder_btn)
        
        # Add spacer (for right alignment)
        save_layout.addStretch()
        
        # Save button
        self.save_btn = QPushButton('Save')
        self.save_btn.setMinimumHeight(68)  # 45 * 1.5 = 67.5
        self.save_btn.setMinimumWidth(140)
        self.save_btn.setToolTip('Save the captured image')
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(231, 76, 60, 0.8);
                font-size: 18px;
                color: white;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: rgba(231, 76, 60, 0.9);
            }
            QPushButton:pressed {
                background-color: rgba(231, 76, 60, 1.0);
            }
        """)
        self.save_btn.clicked.connect(self.save_image)
        self.save_btn.setEnabled(False)
        save_layout.addWidget(self.save_btn)
        
        # Add save button layout
        main_layout.addLayout(save_layout)

        # Status bar setup
        status_bar = QStatusBar()
        status_bar.setStyleSheet("padding: 10px; font-size: 22px; min-height: 40px;")
        self.setStatusBar(status_bar)
        self.statusBar().showMessage('Ready')

        # Tooltip font setup
        QToolTip.setFont(QFont('Arial', 14))

    def setup_shortcuts(self):
        """단축키를 설정합니다."""
        # 전체 캡처 단축키 (F10)
        self.shortcut_full = QShortcut(QKeySequence('F10'), self)
        self.shortcut_full.activated.connect(self.capture_full_screen)
        self.capture_btn.setText('Full Screen Capture (F10)')
        
        # 영역 캡처 단축키 (F9)
        self.shortcut_area = QShortcut(QKeySequence('F9'), self)
        self.shortcut_area.activated.connect(self.capture_area)
        self.area_btn.setText('Rectangular Area Capture (F9)')

    def capture_full_screen(self):
        """Perform full screen capture"""
        self.statusBar().showMessage('Capturing full screen...')
        
        # 캡처 모듈에 현재 창 객체를 전달하여 캡처 중 숨김 처리
        self.last_capture_path = self.capture_module.capture_full_screen(window_to_hide=self)
        
        # Update preview
        self.update_preview(self.last_capture_path)
        
        self.statusBar().showMessage('Full screen capture completed - Press Save button to save the image')
        self.save_btn.setEnabled(True)

    def capture_area(self):
        """Start area selection capture mode"""
        self.statusBar().showMessage('Rectangular area selection mode - Drag to select an area')
        
        # Create and display separate area selection window
        self.area_selector = AreaSelector(self)
        self.hide()  # Hide main window
        
        # 더 길게 대기하지 않아도 됨 (캡처 모듈에서 대기 처리)
        QApplication.processEvents()
        
        # Display area selector
        self.area_selector.show()
        self.area_selector.activateWindow()
        self.area_selector.raise_()

    def process_area_selection(self, rect):
        """Process area selection"""
        # 유효하지 않은 선택 영역인 경우 처리
        if rect.width() <= 5 or rect.height() <= 5:
            self.statusBar().showMessage('Area selection too small or canceled.')
            self.show()  # 메인 창 표시 확인
            return
            
        # 캡처 모듈에 현재 창 객체를 전달하여 캡처 중 숨김 처리
        self.last_capture_path = self.capture_module.capture_area(
            rect.x(), rect.y(), rect.width(), rect.height(), window_to_hide=self)
        
        # 창이 보이는지 확인
        if not self.isVisible():
            self.show()
            
        # Update preview
        self.update_preview(self.last_capture_path)
        self.statusBar().showMessage('Area capture completed - Press Save button to save the image')
        self.save_btn.setEnabled(True)

    def update_preview(self, image_path):
        """Update captured image preview"""
        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            # Scale image to fit label
            scaled_pixmap = pixmap.scaled(
                self.preview_label.width(), 
                self.preview_label.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.preview_label.setPixmap(scaled_pixmap)
            self.preview_label.setStyleSheet("")  # Reset style
        else:
            self.preview_label.setText('Cannot load image')
            self.preview_label.setStyleSheet("color: #888888; font-size: 16px;")

    def set_save_path(self):
        """Set save path"""
        dir_path = QFileDialog.getExistingDirectory(
            self, 'Select Save Location', 
            self.default_save_dir,
            QFileDialog.ShowDirsOnly
        )
        
        if dir_path:
            self.default_save_dir = dir_path
            self.path_label.setText(f'Save Path: {self.default_save_dir}')
            self.statusBar().showMessage(f'Save path has been changed')

    def save_image(self):
        """Save captured image"""
        if not hasattr(self.capture_module, 'captured_image') or self.capture_module.captured_image is None:
            QMessageBox.warning(self, "저장 오류", "저장할 캡처 이미지가 없습니다.")
            return
        
        # Auto-generate filename (based on current date and time)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"
        
        # Create save path
        file_path = os.path.join(self.default_save_dir, filename)
        
        try:
            # 캡처 모듈의 저장 함수 호출
            saved_path = self.capture_module.save_captured_image(file_path)
            if saved_path:
                # 상태 표시줄에 저장 완료 메시지 표시 (3초 후 자동 사라짐)
                self.statusBar().showMessage(f'이미지가 저장되었습니다: {saved_path}', 3000)
                
                # 저장 버튼 비활성화하지 않고 계속 활성화 상태 유지
            else:
                QMessageBox.warning(self, "저장 오류", "이미지 저장에 실패했습니다.")
        except Exception as e:
            QMessageBox.critical(self, "저장 오류", f"파일 저장 중 오류가 발생했습니다: {str(e)}")

    def resizeEvent(self, event):
        """Update preview when window size changes"""
        if hasattr(self, 'last_capture_path') and self.last_capture_path and os.path.exists(self.last_capture_path):
            self.update_preview(self.last_capture_path)
        super().resizeEvent(event)

    def open_save_folder(self):
        """저장 폴더를 파일 탐색기로 엽니다."""
        # 저장 폴더가 존재하는지 확인
        if not os.path.exists(self.default_save_dir):
            os.makedirs(self.default_save_dir)
            
        # 시스템에 맞는 명령으로 폴더 열기
        import subprocess
        import platform
        
        try:
            if platform.system() == "Windows":
                # Windows
                os.startfile(self.default_save_dir)
            elif platform.system() == "Darwin":
                # macOS
                subprocess.call(["open", self.default_save_dir])
            else:
                # Linux
                subprocess.call(["xdg-open", self.default_save_dir])
                
            self.statusBar().showMessage(f'폴더를 열었습니다: {self.default_save_dir}', 3000)
        except Exception as e:
            QMessageBox.warning(self, "오류", f"폴더를 열 수 없습니다: {str(e)}")


class AreaSelector(QWidget):
    """Widget for selecting screen area"""
    def __init__(self, parent=None):
        super().__init__(None)  # Create as top-level window without parent
        self.parent = parent
        self.initUI()
        self.selection_start = QPoint()
        self.selection_end = QPoint()
        self.is_selecting = False

    def initUI(self):
        """Initialize UI"""
        # Set window to full screen size
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setGeometry(QApplication.primaryScreen().geometry())
        
        # Set transparent background
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 50);")
        
        # Set cursor
        self.setCursor(Qt.CrossCursor)

    def paintEvent(self, event):
        """Paint event for displaying selection area"""
        painter = QPainter(self)
        
        # Draw semi-transparent overlay over entire screen
        painter.fillRect(self.rect(), QColor(0, 0, 0, 50))
        
        # If area is being selected, make that area transparent
        if self.is_selecting:  # 선택 시작점이 null인지 확인하지 않음
            selection_rect = QRect(self.selection_start, self.selection_end)
            selection_rect = selection_rect.normalized()
            
            # QRectF conversion (use QRectF instead of QRect)
            selection_rectf = QRectF(selection_rect)
            
            # Make selection area transparent
            mask = QPainterPath()
            mask.addRect(QRectF(self.rect()))
            inner = QPainterPath()
            inner.addRect(selection_rectf)
            mask = mask.subtracted(inner)
            painter.fillPath(mask, QColor(0, 0, 0, 100))
            
            # Make selected area more transparent
            painter.fillRect(selection_rect, QColor(255, 255, 255, 10))
            
            # Draw selection area border (thicker and more visible color)
            pen = QPen(QColor(0, 200, 255), 3)
            pen.setStyle(Qt.SolidLine)
            painter.setPen(pen)
            painter.drawRect(selection_rect)
            
            # Display selection area size
            size_text = f"{selection_rect.width()} x {selection_rect.height()}"
            size_bg_rect = QRect(selection_rect.bottomRight().x() - 150, 
                                selection_rect.bottomRight().y() + 10, 150, 30)
            
            # Size display background
            painter.fillRect(size_bg_rect, QColor(0, 0, 0, 180))
            
            # Size text drawing
            painter.setPen(QColor(255, 255, 255))
            font = painter.font()
            font.setPointSize(12)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(size_bg_rect, Qt.AlignCenter, size_text)
            
            # Corner markers
            corner_size = 10
            corner_color = QColor(0, 200, 255)
            painter.setBrush(QBrush(corner_color))
            painter.setPen(Qt.NoPen)
            
            # Top-left
            painter.drawRect(QRect(selection_rect.left() - corner_size//2, 
                                selection_rect.top() - corner_size//2, 
                                corner_size, corner_size))
            # Top-right
            painter.drawRect(QRect(selection_rect.right() - corner_size//2, 
                                selection_rect.top() - corner_size//2, 
                                corner_size, corner_size))
            # Bottom-left
            painter.drawRect(QRect(selection_rect.left() - corner_size//2, 
                                selection_rect.bottom() - corner_size//2, 
                                corner_size, corner_size))
            # Bottom-right
            painter.drawRect(QRect(selection_rect.right() - corner_size//2, 
                                selection_rect.bottom() - corner_size//2, 
                                corner_size, corner_size))

    def mousePressEvent(self, event):
        """Mouse button press event"""
        if event.button() == Qt.LeftButton:
            self.selection_start = event.pos()
            self.selection_end = self.selection_start
            self.is_selecting = True

    def mouseMoveEvent(self, event):
        """Mouse movement event"""
        if self.is_selecting:
            self.selection_end = event.pos()
            self.update()  # Refresh display

    def mouseReleaseEvent(self, event):
        """Mouse button release event"""
        if event.button() == Qt.LeftButton and self.is_selecting:
            self.selection_end = event.pos()
            self.is_selecting = False
            
            # Calculate selection area
            selection_rect = QRect(self.selection_start, self.selection_end).normalized()
            
            # Close window after selection is complete
            self.close()
            
            # Pass selection information to parent (창 표시는 캡처 모듈에서 처리됨)
            if self.parent:
                # 선택 영역이 너무 작으면 메인 창을 직접 표시
                if selection_rect.width() < 10 or selection_rect.height() < 10:
                    self.parent.show()
                    self.parent.statusBar().showMessage('Area selection too small - canceled.')
                else:
                    self.parent.process_area_selection(selection_rect)

    def keyPressEvent(self, event):
        """Key event handling"""
        # Cancel with ESC key
        if event.key() == Qt.Key_Escape:
            self.close()
            if self.parent:
                self.parent.show()
                self.parent.statusBar().showMessage('Rectangular area selection canceled.') 