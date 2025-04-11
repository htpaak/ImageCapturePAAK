import sys
import os
import time
import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, 
                           QWidget, QLabel, QFileDialog, QHBoxLayout, QMessageBox,
                           QFrame, QSizePolicy, QToolTip, QStatusBar, QDesktopWidget,
                           QShortcut, QDialog, QListWidget, QListWidgetItem, QAbstractItemView)
from PyQt5.QtGui import QPixmap, QIcon, QPainter, QPainterPath, QPen, QColor, QBrush, QFont, QKeySequence, QCursor
from PyQt5.QtCore import Qt, QRect, QPoint, QRectF, QSize, QTimer, QEvent
import win32gui
import win32con

# utils.py에서 함수 가져오기
from utils import get_resource_path

class CaptureUI(QMainWindow):
    def __init__(self, capture_module):
        super().__init__()
        self.capture_module = capture_module
        self.is_selecting = False
        self.selection_start = QPoint()
        self.selection_end = QPoint()
        self.selection_rect = QRect()
        self.last_capture_path = None
        
        # 캡처 모듈의 저장 경로를 사용 (설정 파일에서 로드된 경로)
        self.default_save_dir = self.capture_module.save_dir
        
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
        # 창 크기 설정: 가로 크기를 1000px로 설정
        self.setGeometry(100, 100, 1000, 750)
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
        icon_path = get_resource_path(os.path.join('assets', 'icon.ico'))
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
        self.capture_btn.setFixedWidth(300)  # 버튼 가로 크기 제한
        self.capture_btn.setToolTip('Capture the entire screen')
        self.capture_btn.setIcon(QIcon.fromTheme('camera-photo'))
        self.capture_btn.clicked.connect(self.capture_full_screen)
        btn_layout.addWidget(self.capture_btn)

        # Area capture button
        self.area_btn = QPushButton('Rectangular Area Capture')
        self.area_btn.setMinimumHeight(90)  # 60 * 1.5 = 90
        self.area_btn.setFixedWidth(300)  # 버튼 가로 크기 제한
        self.area_btn.setToolTip('Drag to select an area to capture')
        self.area_btn.setIcon(QIcon.fromTheme('select-rectangular'))
        self.area_btn.clicked.connect(self.capture_area)
        btn_layout.addWidget(self.area_btn)
        
        # Window capture button
        self.window_btn = QPushButton('Window Capture')
        self.window_btn.setMinimumHeight(90)  # 60 * 1.5 = 90
        self.window_btn.setFixedWidth(300)  # 버튼 가로 크기 제한
        self.window_btn.setToolTip('Capture the active window')
        self.window_btn.setIcon(QIcon.fromTheme('window'))
        self.window_btn.clicked.connect(self.capture_window)
        btn_layout.addWidget(self.window_btn)

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
        
        # 프레임 크기 정책 설정 - 고정 비율로 설정
        preview_frame.setMinimumWidth(640)  # 최소 너비 설정
        preview_frame.setMinimumHeight(360)  # 16:9 비율에 맞게 설정
        
        # 프레임 크기 정책 설정 - Preferred로 설정해서 레이아웃 내에서는 크기 유지
        sizePolicy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        sizePolicy.setHeightForWidth(True)  # 너비에 따라 높이 비율 유지
        preview_frame.setSizePolicy(sizePolicy)
        
        # heightForWidth 메서드 재정의하여 16:9 비율 유지
        def height_for_width(width):
            return int(width * 9 / 16)  # 16:9 비율
            
        preview_frame.heightForWidth = height_for_width
        
        # 프레임 레이아웃 설정 - 여백 제거
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(0, 0, 0, 0)  # 여백 제거
        preview_layout.setSpacing(0)  # 간격 제거

        # Preview label
        self.preview_label = QLabel('The preview will be displayed here after capture')
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("color: #888888; font-size: 16px;")
        self.preview_label.setMinimumHeight(360)  # 16:9 비율에 맞게 설정
        
        # 레이블 크기 정책 설정 - 컨테이너를 채우도록 설정
        self.preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # 텍스트 줄바꿈 활성화
        self.preview_label.setWordWrap(True)
        
        # 레이블 배경색 설정
        self.preview_label.setAutoFillBackground(True)
        
        preview_layout.addWidget(self.preview_label)

        # Add preview frame
        main_layout.addWidget(preview_frame, 1)  # stretch factor를 1로 설정하여 확장되도록 함

        # 하단 영역 레이아웃 개선 - 경로 표시와 버튼을 분리
        bottom_layout = QVBoxLayout()
        bottom_layout.setSpacing(10)
        
        # 경로 표시 영역
        path_info_layout = QHBoxLayout()
        path_info_layout.setSpacing(5)
        
        # 경로 레이블 - 고정 너비 설정
        path_label_prefix = QLabel('Save Path:')
        path_label_prefix.setStyleSheet("font-size: 18px; color: #555555; padding: 8px 0;")
        path_label_prefix.setFixedWidth(100)
        path_info_layout.addWidget(path_label_prefix)
        
        # 경로 내용 (스크롤 가능한 영역)
        self.path_content = QLabel(self.default_save_dir)
        self.path_content.setStyleSheet("font-size: 18px; color: #555555; padding: 8px 0; background-color: #f9f9f9; border-radius: 4px;")
        self.path_content.setMinimumWidth(200)
        self.path_content.setTextInteractionFlags(Qt.TextSelectableByMouse)
        path_info_layout.addWidget(self.path_content, 1)  # 1은 stretch factor로, 공간이 있으면 확장됨
        
        # 경로 표시 영역 추가
        bottom_layout.addLayout(path_info_layout)
        
        # 버튼 영역
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        
        # 왼쪽에 스페이서 추가
        button_layout.addStretch(1)
        
        # Change Path 버튼
        self.path_btn = QPushButton('Change Path')
        self.path_btn.setMinimumHeight(68)
        self.path_btn.setFixedWidth(150)
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
        button_layout.addWidget(self.path_btn)
        
        # 윈도우 탐색기로 저장 디렉토리 열기 버튼
        self.open_folder_btn = QPushButton('Open Folder')
        self.open_folder_btn.setMinimumHeight(68)
        self.open_folder_btn.setFixedWidth(150)
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
        button_layout.addWidget(self.open_folder_btn)
        
        # Save 버튼
        self.save_btn = QPushButton('Save')
        self.save_btn.setMinimumHeight(68)
        self.save_btn.setFixedWidth(150)
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
        button_layout.addWidget(self.save_btn)
        
        # 버튼 영역 추가
        bottom_layout.addLayout(button_layout)
        
        # 전체 하단 레이아웃 추가
        main_layout.addLayout(bottom_layout)

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
        
        # 창 캡처 단축키 (F8)
        self.shortcut_window = QShortcut(QKeySequence('F8'), self)
        self.shortcut_window.activated.connect(self.capture_window)
        self.window_btn.setText('Window Capture (F8)')

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

    def capture_window(self):
        """마우스 호버로 캡처할 창을 선택"""
        self.statusBar().showMessage('Move mouse over a window and click to capture it')
        
        # 현재 창을 일시적으로 숨김
        self.hide()
        QApplication.processEvents()  # UI 즉시 갱신
        
        # 다른 창이 활성화될 시간 확보 (짧게 조정)
        time.sleep(0.2)
        
        # 창 선택 위젯 생성 및 표시
        self.window_selector = WindowSelector(self)
        
        # 위젯 초기화 및 표시
        QApplication.processEvents()  # UI 즉시 갱신
        self.window_selector.show()
        self.window_selector.activateWindow()
        self.window_selector.raise_()

    def process_window_selection(self, hwnd, title):
        """선택한 창 캡처 처리"""
        # 취소한 경우
        if hwnd is None:
            self.statusBar().showMessage('캡처가 취소되었습니다')
            self.show()
            self.activateWindow()
            self.raise_()
            return
        
        # 캡처 실행
        try:
            # 창이 유효한지 다시 확인
            if not win32gui.IsWindow(hwnd):
                print("유효하지 않은 창 핸들입니다.")
                self.statusBar().showMessage('유효하지 않은 창입니다. 다시 시도해주세요.')
                self.show()
                self.activateWindow()
                self.raise_()
                return
                
            # 창 정보 확인
            window_title = win32gui.GetWindowText(hwnd)
            print(f"캡처할 창: {window_title} (핸들: {hwnd})")
            
            # 선택한 창 캡처 (hwnd를 전달하여 해당 창만 캡처)
            self.last_capture_path = self.capture_module.capture_window(window_to_hide=self, hwnd=hwnd)
            
            # 창 보이기 및 활성화
            if not self.isVisible():
                self.show()
                self.activateWindow()
                self.raise_()
            
            # 미리보기 업데이트
            self.update_preview(self.last_capture_path)
            
            # 캡처된 창 이름 표시 (빈 문자열이면 기본 메시지 사용)
            window_name = window_title if window_title else title if title else "선택한 창"
            self.statusBar().showMessage(f'"{window_name}" 창 캡처가 완료되었습니다 - 저장 버튼을 눌러 이미지를 저장하세요')
            self.save_btn.setEnabled(True)
        except Exception as e:
            print(f"창 캡처 처리 중 오류 발생: {e}")
            if not self.isVisible():
                self.show()
                self.activateWindow()
                self.raise_()
            self.statusBar().showMessage(f'캡처 실패: {str(e)}')
            QMessageBox.warning(self, "캡처 오류", f"화면 캡처 중 오류가 발생했습니다: {str(e)}")

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
            # 이미지 로드
            pixmap = QPixmap(image_path)
            
            if pixmap.isNull():
                self.preview_label.setText('Cannot load image')
                self.preview_label.setStyleSheet("color: #888888; font-size: 16px;")
                return
            
            # 레이블 최대 크기 가져오기
            label_size = self.preview_label.size()
            
            # 레이블 크기에 맞게 이미지 스케일링 (꽉 차게 표시)
            scaled_pixmap = pixmap.scaled(
                label_size.width(),
                label_size.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            
            # 스케일링된 이미지 설정
            self.preview_label.setPixmap(scaled_pixmap)
            self.preview_label.setStyleSheet("background-color: black;")  # 검은색 배경 추가
            
            # 콘솔에 디버깅 정보 출력
            print(f"원본 이미지 크기: {pixmap.width()}x{pixmap.height()}, "
                  f"레이블 크기: {label_size.width()}x{label_size.height()}, "
                  f"스케일링된 이미지 크기: {scaled_pixmap.width()}x{scaled_pixmap.height()}")
        else:
            # 이미지를 찾을 수 없는 경우
            self.preview_label.setText('Cannot load image')
            self.preview_label.setStyleSheet("color: #888888; font-size: 16px; background-color: white;")

    def set_save_path(self):
        """Set save path"""
        dir_path = QFileDialog.getExistingDirectory(
            self, 'Select Save Location', 
            self.default_save_dir,
            QFileDialog.ShowDirsOnly
        )
        
        if dir_path:
            self.default_save_dir = dir_path
            self.path_content.setText(self.default_save_dir)
            
            # 캡처 모듈에 경로 변경 사항 전달 (설정 파일에도 저장됨)
            self.capture_module.set_save_directory(self.default_save_dir)
            
            self.statusBar().showMessage(f'Save path has been changed and saved to settings')
            print(f"저장 경로가 변경되었습니다: {self.default_save_dir}")

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
        # 창 크기가 변경되면 약간의 지연 후 프리뷰 업데이트
        if hasattr(self, 'last_capture_path') and self.last_capture_path and os.path.exists(self.last_capture_path):
            # QTimer를 사용하여 약간의 지연 후 업데이트 (레이아웃이 정착한 후)
            QTimer.singleShot(100, lambda: self.update_preview(self.last_capture_path))
        
        # 부모 클래스의 resizeEvent 호출
        super().resizeEvent(event)
        
    def changeEvent(self, event):
        """창 상태가 변경될 때 호출되는 이벤트 핸들러"""
        if event.type() == QEvent.WindowStateChange:
            # 창이 최대화되거나 복원될 때 프리뷰 업데이트
            if hasattr(self, 'last_capture_path') and self.last_capture_path and os.path.exists(self.last_capture_path):
                # 약간의 지연 후 업데이트 (창 상태 변경이 완료된 후)
                QTimer.singleShot(300, lambda: self.update_preview(self.last_capture_path))
        
        # 부모 클래스의 이벤트 핸들러 호출
        super().changeEvent(event)

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


class WindowSelector(QWidget):
    """마우스 호버로 캡처할 창을 선택하는 위젯"""
    def __init__(self, parent=None):
        super().__init__(None)
        self.parent = parent
        self.current_hwnd = None
        self.current_title = ""
        self.current_rect = None
        
        # 초기화 시 사용 가능한 창 목록 미리 가져오기
        self.window_list = []
        self.load_window_list()
        
        # UI 초기화
        self.initUI()
        
        # 타이머로 마우스 위치 추적 (간격을 더 길게 설정)
        self.hover_timer = QTimer(self)
        self.hover_timer.timeout.connect(self.check_mouse_position)
        self.hover_timer.start(300)  # 300ms 간격으로 마우스 추적 (깜빡임 최소화)
        
    def load_window_list(self):
        """사용 가능한 모든 창 목록을 미리 가져옴"""
        try:
            self.window_list = []
            
            def enum_windows_proc(hwnd, results):
                # 보이는 창만 추가
                if win32gui.IsWindowVisible(hwnd) and not win32gui.IsIconic(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    # 빈 제목이나 "Snipix" 포함 창은 제외
                    if title and "Snipix" not in title:
                        # 실제 창 영역 가져오기
                        try:
                            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
                            width = right - left
                            height = bottom - top
                            # 최소 크기 이상인 창만 추가
                            if width > 100 and height > 100:
                                # 창 핸들, 제목, 영역 저장
                                self.window_list.append({
                                    'hwnd': hwnd,
                                    'title': title,
                                    'rect': QRect(left, top, width, height)
                                })
                        except:
                            pass
                return True
                
            # 모든 창을 순회하며 목록 만들기
            win32gui.EnumWindows(enum_windows_proc, None)
            
            # 창 목록이 있는지 확인
            if self.window_list:
                print(f"감지된 창 목록: {len(self.window_list)}개")
            else:
                print("감지된 창이 없습니다.")
                
        except Exception as e:
            print(f"창 목록 로드 오류: {e}")
            
    def initUI(self):
        """UI 초기화"""
        # 전체 화면 크기로 설정
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(QApplication.primaryScreen().geometry())
        self.setCursor(Qt.CrossCursor)
        
        # 안내 텍스트 표시
        self.info_label = QLabel("마우스를 창 위에 올리면 해당 창이 강조되고, 클릭하면 창 전체가 캡처됩니다. ESC 키를 누르면 취소됩니다.", self)
        self.info_label.setStyleSheet("""
            background-color: rgba(0, 0, 0, 180); 
            color: white; 
            padding: 12px; 
            border-radius: 6px;
            font-size: 16px;
            font-weight: bold;
        """)
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setFixedWidth(600)  # 텍스트가 잘리지 않도록 너비 확장
        
        # 화면 하단에 표시
        rect = self.geometry()
        self.info_label.move(
            (rect.width() - self.info_label.width()) // 2,
            rect.height() - self.info_label.height() - 60
        )
        
    def find_window_at_position(self, pos):
        """마우스 위치에 있는 창 찾기"""
        for window in self.window_list:
            if window['rect'].contains(pos):
                return window
        return None
            
    def check_mouse_position(self):
        """마우스 위치에 있는 창 확인"""
        try:
            # 마우스 현재 위치 가져오기
            cursor_pos = QCursor.pos()
            
            # 마우스 위치에 있는 창 찾기
            window = self.find_window_at_position(cursor_pos)
            
            # 창을 찾았으면 정보 업데이트
            if window:
                # 이전과 같은 창이면 업데이트 불필요
                if self.current_hwnd == window['hwnd'] and self.current_rect:
                    return
                    
                # 새로운 창 정보 업데이트
                self.current_hwnd = window['hwnd']
                self.current_title = window['title']
                self.current_rect = window['rect']
                print(f"✓ 창 인식: '{window['title']}', 크기: {window['rect'].width()}x{window['rect'].height()}")
                self.update()
            else:
                # 창을 찾지 못했으면 초기화
                self.clear_current_window()
                
        except Exception as e:
            print(f"창 감지 오류: {e}")
            self.clear_current_window()

    def clear_current_window(self):
        """현재 창 정보 초기화"""
        if self.current_rect or self.current_hwnd:
            self.current_rect = None
            self.current_title = ""
            self.current_hwnd = None
            self.update()
    
    def paintEvent(self, event):
        """화면 표시"""
        painter = QPainter(self)
        
        # 전체 화면에 반투명한 오버레이 그리기
        painter.fillRect(self.rect(), QColor(0, 0, 0, 80))  # 더 어둡게 만들어서 선택된 창을 강조
        
        # 현재 창 강조 표시
        if self.current_rect and self.current_hwnd and self.current_title:
            # 선택된 창 영역은 더 투명하게
            highlight_area = QPainterPath()
            highlight_area.addRect(QRectF(self.current_rect))
            
            # 선택된 창 영역만 투명하게 하기 위한 Path 설정
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, 10))  # 매우 투명한 배경
            painter.drawRect(self.current_rect)
            
            # 테두리 그리기 (굵고 눈에 띄는 색상)
            pen = QPen(QColor(0, 180, 255), 4)  # 더 두꺼운 테두리
            painter.setPen(pen)
            painter.drawRect(self.current_rect)
            
            # 창 제목 표시 영역 (상단에 표시)
            title_bg_rect = QRect(
                self.current_rect.x(),
                max(0, self.current_rect.y() - 50),  # 창 위에 표시
                min(500, self.current_rect.width()),  # 창 너비를 넘지 않도록
                40  # 더 큰 높이
            )
            
            # 창 제목 배경 (어두운 배경)
            painter.setBrush(QColor(0, 0, 0, 180))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(title_bg_rect, 5, 5)  # 둥근 모서리
            
            # 창 제목 텍스트
            painter.setPen(QColor(255, 255, 255))
            font = painter.font()
            font.setPointSize(11)  # 더 큰 폰트
            font.setBold(True)
            painter.setFont(font)
            
            # 창 제목이 너무 길면 잘라서 표시
            display_title = self.current_title
            if len(display_title) > 50:
                display_title = display_title[:47] + "..."
                
            painter.drawText(title_bg_rect, Qt.AlignCenter, display_title)
            
            # 모서리 표시점 추가 (더 크고 눈에 띄게)
            corner_size = 10
            corner_color = QColor(0, 180, 255)
            painter.setBrush(QBrush(corner_color))
            painter.setPen(Qt.NoPen)
            
            # 왼쪽 상단
            painter.drawRect(QRect(
                self.current_rect.left() - corner_size//2, 
                self.current_rect.top() - corner_size//2, 
                corner_size, corner_size))
            
            # 오른쪽 상단
            painter.drawRect(QRect(
                self.current_rect.right() - corner_size//2, 
                self.current_rect.top() - corner_size//2, 
                corner_size, corner_size))
            
            # 왼쪽 하단
            painter.drawRect(QRect(
                self.current_rect.left() - corner_size//2, 
                self.current_rect.bottom() - corner_size//2, 
                corner_size, corner_size))
            
            # 오른쪽 하단
            painter.drawRect(QRect(
                self.current_rect.right() - corner_size//2, 
                self.current_rect.bottom() - corner_size//2, 
                corner_size, corner_size))
            
            # 창 크기 정보 표시 (오른쪽 하단에 표시)
            size_text = f"{self.current_rect.width()} × {self.current_rect.height()} px"
            size_bg_rect = QRect(
                self.current_rect.right() - 150,
                self.current_rect.bottom() + 10,
                150,
                30
            )
            
            # 크기 정보 배경
            painter.setBrush(QColor(0, 0, 0, 180))
            painter.drawRoundedRect(size_bg_rect, 5, 5)
            
            # 크기 정보 텍스트
            painter.setPen(QColor(255, 255, 255))
            font = painter.font()
            font.setPointSize(9)
            painter.setFont(font)
            painter.drawText(size_bg_rect, Qt.AlignCenter, size_text)
    
    def mousePressEvent(self, event):
        """마우스 클릭 시 창 캡처"""
        if event.button() == Qt.LeftButton:
            # 타이머 정지
            self.hover_timer.stop()
            
            # 현재 선택된 창 정보 저장
            selected_hwnd = self.current_hwnd
            selected_title = self.current_title
            
            # 선택기 숨김
            self.hide()
            QApplication.processEvents()
            
            # 현재 선택된 창이 있으면 캡처
            if self.parent and selected_hwnd and self.current_rect:
                # 선택된 창이 캡처될 시간을 확보하기 위해 약간 대기
                time.sleep(0.1)
                self.parent.process_window_selection(selected_hwnd, selected_title)
                # 캡처 처리 후 선택기 종료
                self.close()
            else:
                # 창을 선택하지 않았으면 취소로 처리
                if self.parent:
                    self.parent.show()
                    self.parent.activateWindow()
                    self.parent.raise_()
                    self.parent.process_window_selection(None, "")
                self.close()

    def keyPressEvent(self, event):
        """키 이벤트 처리"""
        # ESC 키 처리
        if event.key() == Qt.Key_Escape:
            self.hover_timer.stop()
            self.close()
            if self.parent:
                self.parent.show()
                self.parent.activateWindow()  # 부모 창을 강제로 활성화
                self.parent.raise_()  # 부모 창을 최상위로 가져옴
                self.parent.process_window_selection(None, "")

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