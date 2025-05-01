import sys
import os
import time
import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, 
                           QWidget, QLabel, QFileDialog, QHBoxLayout, QMessageBox,
                           QFrame, QSizePolicy, QToolTip, QStatusBar, QDesktopWidget,
                           QShortcut, QDialog, QListWidget, QListWidgetItem, QAbstractItemView,
                           QSystemTrayIcon, QAction, QMenu)
from PyQt5.QtGui import QPixmap, QIcon, QPainter, QPainterPath, QPen, QColor, QBrush, QFont, QKeySequence, QCursor, QImage
from PyQt5.QtCore import Qt, QRect, QPoint, QRectF, QSize, QTimer, QEvent, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices
import win32gui
import win32con
import win32process
import win32api  # 윈도우 API 추가
import traceback 
import logging # 로깅 모듈 임포트

# utils.py에서 함수 가져오기
from utils import get_resource_path, qimage_to_pil # qimage_to_pil 임포트 추가
# 편집기 모듈 가져오기
from editor_module import ImageEditor

# 클릭 가능한 피드백 라벨 클래스
class FeedbackLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setText("💬") # 이모지 텍스트 설정 (점 제거)
        self.setToolTip("Send feedback") # 툴 설정 (영어로 변경)
        self.setStyleSheet("font-size: 12px; padding-right: 5px;") # 스타일 설정 (우측 패딩 추가)
        # 마우스 클릭 이벤트 활성화 (기본값은 비활성화)
        self.setMouseTracking(True) 
        self.setCursor(Qt.PointingHandCursor) # 마우스 오버 시 손가락 커서

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # 깃허브 Discussions URL 열기
            url = QUrl("https://github.com/htpaak/ImageCapturePAAK/discussions")
            QDesktopServices.openUrl(url)
        super().mousePressEvent(event) # 기본 이벤트 처리

# 클래스 정의 앞에 와야 함
class FullScreenViewer(QWidget):
    """Displays an image in full screen mode using QPainter."""
    def __init__(self, image_path: str, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.image = QImage(self.image_path)
        if self.image.isNull():
             print(f"Error: Could not load image '{self.image_path}' for full screen.")
        self.initUI()

    def initUI(self):
        # Set window properties for full screen display
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setStyleSheet("background-color: black;") # Black background is important
        self.setGeometry(QApplication.primaryScreen().geometry()) # 화면 전체 크기로 설정

        # QLabel 제거
        # self.image_label = QLabel(self)
        # self.image_label.setAlignment(Qt.AlignCenter)
        # self.image_label.setScaledContents(True)
        # self.image_label.setGeometry(self.rect())

        # 레이아웃 제거
        # layout = QVBoxLayout(self)
        # layout.addWidget(self.image_label)
        # layout.setContentsMargins(0, 0, 0, 0)
        # self.setLayout(layout)

        # 초기 그리기를 위해 paintEvent 요청
        self.update()

    def paintEvent(self, event):
        """Paint the image directly using QPainter, maintaining aspect ratio."""
        painter = QPainter(self)

        # 항상 검은색 배경 먼저 칠하기
        painter.fillRect(self.rect(), Qt.black)

        if self.image.isNull():
            return # 이미지가 없으면 종료

        # Calculate target rectangle with aspect ratio preserved
        img_size = self.image.size()
        widget_rect = self.rect()
        scaled_size = img_size.scaled(widget_rect.size(), Qt.KeepAspectRatio)
        x = (widget_rect.width() - scaled_size.width()) / 2
        y = (widget_rect.height() - scaled_size.height()) / 2
        target_rect = QRect(QPoint(int(x), int(y)), scaled_size)

        # Set render hint for potentially better quality
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        # Draw the original QImage into the calculated target rectangle
        painter.drawImage(target_rect, self.image)

    def resizeEvent(self, event):
        """Handle window resize: trigger repaint."""
        # 라벨 크기 조정 제거
        # self.image_label.setGeometry(self.rect())
        # update_image_display 호출 제거
        self.update() # Request a repaint
        super().resizeEvent(event)

    def keyPressEvent(self, event):
        """Close the full screen viewer when ESC key is pressed."""
        if event.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

class CaptureUI(QMainWindow):
    # 캡처 요청 시그널 정의
    captureFullScreenRequested = pyqtSignal()
    captureAreaRequested = pyqtSignal()
    captureWindowRequested = pyqtSignal()

    def __init__(self, capture_module):
        super().__init__()
        self.capture_module = capture_module
        self.is_selecting = False
        self.selection_start = QPoint()
        self.selection_end = QPoint()
        self.selection_rect = QRect()
        self.last_capture_path = None
        self.last_saved_file_path = None
        self.fullscreen_viewer = None 
        # 창 상태 추적 변수 추가
        self._was_visible_before_capture = False 
        # 단축키 ID 저장 변수 초기화
        self.hotkey_ids = {}
        
        # 캡처 모듈의 저장 경로를 사용 (설정 파일에서 로드된 경로)
        self.default_save_dir = self.capture_module.save_dir
        
        # Create directory if it doesn't exist
        if not os.path.exists(self.default_save_dir):
            os.makedirs(self.default_save_dir)
            
        # Initialize UI
        self.initUI()
        
        # 단축키 설정
        # self.setup_shortcuts() # QShortcut 대신 전역 단축키 사용
        
        # 트레이 아이콘 설정
        self.setup_tray_icon()
        
        # 시그널-슬롯 연결
        self.captureFullScreenRequested.connect(self.capture_full_screen)
        self.captureAreaRequested.connect(self.capture_area)
        self.captureWindowRequested.connect(self.capture_window)

    def setup_tray_icon(self):
        """시스템 트레이 아이콘 설정"""
        icon_path = get_resource_path(os.path.join('assets', 'icon.ico'))
        if not os.path.exists(icon_path):
            print("Error: Tray icon not found at", icon_path)
            self.tray_icon = None
            return

        self.tray_icon = QSystemTrayIcon(QIcon(icon_path), self)
        self.tray_icon.setToolTip('ImageCapturePAAK')

        # 트레이 아이콘 메뉴 생성
        tray_menu = QMenu()
        show_action = QAction("Show", self)
        exit_action = QAction("Exit", self)

        show_action.triggered.connect(self.show_window)
        exit_action.triggered.connect(self.exit_app)

        tray_menu.addAction(show_action)
        tray_menu.addSeparator()
        tray_menu.addAction(exit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        
        # 앱 시작 시 트레이 아이콘 표시 (선택적, 닫을 때만 표시하려면 주석 처리)
        self.tray_icon.show() # 주석 제거

    def on_tray_icon_activated(self, reason):
        """트레이 아이콘 클릭 시 동작"""
        # 왼쪽 클릭 시 창 표시
        if reason == QSystemTrayIcon.Trigger:
            self.show_window()

    def show_window(self):
        """메인 창을 표시하고 활성화"""
        self.show()
        self.activateWindow()
        self.raise_()
        # 필요하다면 트레이 아이콘 숨김 (선택적)
        # self.tray_icon.hide()

    def exit_app(self):
        """애플리케이션 종료 및 단축키 해제"""
        print("[Exit] Unregistering hotkeys...")
        try:
            for key_name, key_id in self.hotkey_ids.items():
                win32gui.UnregisterHotKey(None, key_id)
                print(f"[Exit] Unregistered hotkey: {key_name} (ID: {key_id})")
        except Exception as e:
            print(f"[Exit] Error unregistering hotkeys: {e}")
        
        if self.tray_icon:
            self.tray_icon.hide()
        QApplication.quit()

    # closeEvent 재정의
    def closeEvent(self, event):
        """창 닫기 이벤트를 가로채 트레이로 최소화"""
        event.ignore() # 기본 닫기 동작 무시
        self.hide()    # 창 숨기기
        if self.tray_icon:
            self.tray_icon.show() # 트레이 아이콘 표시
            # 트레이 아이콘 메시지 표시 (선택적)
            self.tray_icon.showMessage(
                "ImageCapturePAAK",
                "Application minimized to tray. Use hotkeys (F8/F9/F10) to capture.",
                QSystemTrayIcon.Information,
                2000
            )

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
        self.setWindowTitle('ImageCapturePAAK')
        # 창 크기 설정
        self.setGeometry(100, 100, 400, 435) # 너비 수정: 500 -> 400
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
                font-size: 8px;
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
            pixmap = QPixmap(icon_path).scaled(47, 47, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon_label.setPixmap(pixmap)
        icon_label.setAlignment(Qt.AlignVCenter)  # 수직 가운데 정렬
        
        # Program title
        title_label = QLabel('ImageCapturePAAK')
        title_label.setStyleSheet("font-size: 27px; font-weight: bold; color: #333333;")
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
        guide_label.setStyleSheet("font-size: 15px; color: #555555; margin-bottom: 5px;")
        guide_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(guide_label)

        # Button layout
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)

        # Full screen capture button
        self.capture_btn = QPushButton('Screen Capture (Alt+1)') # 단축키 텍스트 변경
        self.capture_btn.setMinimumHeight(45)
        self.capture_btn.setFixedWidth(156)
        self.capture_btn.setToolTip('Capture the entire screen')
        self.capture_btn.setIcon(QIcon.fromTheme('camera-photo'))
        self.capture_btn.setStyleSheet("font-size: 8pt;")
        # 시그널 사용으로 변경
        self.capture_btn.clicked.connect(self.captureFullScreenRequested.emit)
        btn_layout.addWidget(self.capture_btn)

        # Area capture button
        self.area_btn = QPushButton('Area Capture (Alt+2)') # 단축키 텍스트 변경
        self.area_btn.setMinimumHeight(45)
        self.area_btn.setFixedWidth(156)
        self.area_btn.setToolTip('Drag to select an area to capture')
        self.area_btn.setIcon(QIcon.fromTheme('select-rectangular'))
        self.area_btn.setStyleSheet("font-size: 8pt;")
        # 시그널 사용으로 변경
        self.area_btn.clicked.connect(self.captureAreaRequested.emit)
        btn_layout.addWidget(self.area_btn)
        
        # Window capture button
        self.window_btn = QPushButton('Window Capture (Alt+3)') # 단축키 텍스트 변경
        self.window_btn.setMinimumHeight(45)
        self.window_btn.setFixedWidth(156)
        self.window_btn.setToolTip('Capture the active window')
        self.window_btn.setIcon(QIcon.fromTheme('window'))
        self.window_btn.setStyleSheet("font-size: 8pt;")
        # 시그널 사용으로 변경
        self.window_btn.clicked.connect(self.captureWindowRequested.emit)
        btn_layout.addWidget(self.window_btn)

        # Add button layout
        main_layout.addLayout(btn_layout)

        # Add separator line
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("background-color: #cccccc;")
        main_layout.addWidget(line)

        # Preview title and placeholder button layout
        preview_header_layout = QHBoxLayout()

        preview_title = QLabel('Captured Image Preview')
        preview_title.setStyleSheet("font-size: 14px; color: #333333;")
        preview_title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter) # 왼쪽 정렬
        preview_header_layout.addWidget(preview_title)

        preview_header_layout.addStretch(1) # 공간 확장

        # Copy 버튼 추가 (Edit 버튼 앞에)
        self.copy_btn = QPushButton('Copy')
        self.copy_btn.setFixedSize(80, 30)
        self.copy_btn.setToolTip('Copy the captured image to clipboard')
        self.copy_btn.setStyleSheet("font-size: 8pt;")
        self.copy_btn.clicked.connect(self.copy_image_to_clipboard) # 메서드 연결
        self.copy_btn.setEnabled(False) # 초기에는 비활성화
        preview_header_layout.addWidget(self.copy_btn)

        # Edit 버튼 추가
        self.edit_btn = QPushButton('Edit')
        self.edit_btn.setFixedSize(80, 30) # 크기 설정 (임의)
        self.edit_btn.setToolTip('Edit the captured image')
        self.edit_btn.setStyleSheet("font-size: 8pt;")
        self.edit_btn.clicked.connect(self.open_image_editor) # 편집기 열기 메서드 연결
        self.edit_btn.setEnabled(False) # 초기에는 비활성화
        preview_header_layout.addWidget(self.edit_btn) # 레이아웃에 추가

        # 작은 풀스크린 버튼 추가
        self.fullscreen_placeholder_btn = QPushButton('Full Screen (esc)') # 텍스트 수정
        self.fullscreen_placeholder_btn.setFixedSize(135, 30) # 너비 80 -> 100으로 수정
        self.fullscreen_placeholder_btn.setToolTip('Show preview in full screen (ESC)')
        self.fullscreen_placeholder_btn.setStyleSheet("font-size: 8pt;") # 폰트 크기 8pt 재추가
        self.fullscreen_placeholder_btn.clicked.connect(self.show_fullscreen_preview) # 버튼 클릭 연결
        self.fullscreen_placeholder_btn.setEnabled(False) # 초기에는 비활성화 # Edit 버튼 추가 후 비활성화 유지
        preview_header_layout.addWidget(self.fullscreen_placeholder_btn)

        main_layout.addLayout(preview_header_layout) # 제목 + 버튼 레이아웃 추가

        # Preview frame
        preview_frame = QFrame()
        preview_frame.setFrameShape(QFrame.StyledPanel)
        preview_frame.setFrameShadow(QFrame.Sunken)
        preview_frame.setStyleSheet("background-color: white; border: 1px solid #cccccc; border-radius: 4px;")
        
        # 프레임 크기 정책 설정 - 고정 비율로 설정
        preview_frame.setMinimumWidth(320)  # 최소 너비 수정: 640 -> 320
        preview_frame.setMinimumHeight(282)  # 최소 높이 수정: 240 -> 288 (1.2배)
        
        # 프레임 크기 정책 설정 - Preferred로 설정해서 레이아웃 내에서는 크기 유지
        sizePolicy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # sizePolicy.setHeightForWidth(True)  # 너비에 따라 높이 비율 유지 -> 주석 처리
        preview_frame.setSizePolicy(sizePolicy)
        
        # heightForWidth 메서드 재정의하여 16:9 비율 유지 -> 관련 코드 주석 처리
        # def height_for_width(width):
        #     return int(width * 9 / 16)  # 16:9 비율
            
        # preview_frame.heightForWidth = height_for_width
        
        # 프레임 레이아웃 설정 - 여백 제거
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(0, 0, 0, 0)  # 여백 제거
        preview_layout.setSpacing(0)  # 간격 제거

        # Preview label
        self.preview_label = QLabel('The preview will be displayed here after capture')
        self.preview_label.setObjectName("previewLabel") # 객체 이름 설정
        self.preview_label.setAlignment(Qt.AlignCenter)
        # 객체 이름 선택자로 스타일 적용
        self.preview_label.setStyleSheet("#previewLabel { color: #888888; font-size: 8pt; }") 
        self.preview_label.setMinimumHeight(282)  
        
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
        path_label_prefix.setStyleSheet("font-size: 14px; color: #555555; padding: 8px 0;")
        path_label_prefix.setFixedWidth(80) # 너비 수정: 50 -> 80 (텍스트 표시 공간 확보)
        path_info_layout.addWidget(path_label_prefix)
        
        # 경로 내용 (스크롤 가능한 영역)
        self.path_content = QLabel(self.default_save_dir)
        self.path_content.setStyleSheet("font-size: 14px; color: #555555; padding: 8px 0; background-color: #f9f9f9; border-radius: 4px;")
        self.path_content.setMinimumWidth(100) # 최소 너비 수정: 200 -> 100
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
        self.path_btn.setMinimumHeight(34) # 최소 높이 수정: 68 -> 34
        self.path_btn.setFixedWidth(98) # 너비 수정: 75 -> 98 (1.3배)
        self.path_btn.setToolTip('Change the save location for captured images')
        self.path_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(241, 196, 15, 0.8);
                font-size: 8pt; /* 폰트 크기 수정: 7pt -> 8pt */
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
        self.open_folder_btn.setMinimumHeight(34) # 최소 높이 수정: 68 -> 34
        self.open_folder_btn.setFixedWidth(98) # 너비 수정: 75 -> 98 (1.3배)
        self.open_folder_btn.setToolTip('Open the folder where the image was saved')
        self.open_folder_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(41, 128, 185, 0.8);
                font-size: 8pt; /* 폰트 크기 수정: 7pt -> 8pt */
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
        self.save_btn.setMinimumHeight(34) # 최소 높이 수정: 68 -> 34
        self.save_btn.setFixedWidth(98) # 너비 수정: 75 -> 98 (1.3배)
        self.save_btn.setToolTip('Save the captured image')
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(231, 76, 60, 0.8);
                font-size: 8pt; /* 폰트 크기 수정: 7pt -> 8pt */
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
        
        # 오른쪽 스페이서 추가
        button_layout.addStretch(1)
        
        # 버튼 영역 추가
        bottom_layout.addLayout(button_layout)
        
        # 전체 하단 레이아웃 추가
        main_layout.addLayout(bottom_layout)

        # --- 상태 표시줄 설정 --- #
        self.statusBar().setStyleSheet("QStatusBar { border-top: 1px solid #cccccc; }")
        self.statusBar().showMessage('Ready')
        
        # 피드백 라벨 생성 및 상태 표시줄 오른쪽에 추가
        feedback_label = FeedbackLabel(self)
        self.statusBar().addPermanentWidget(feedback_label)

    def _force_window_to_foreground(self):
        """윈도우 API를 사용하여 창을 강제로 최상위로 가져옵니다"""
        # 이전에 주석 처리되었던 함수 복원
        try:
            hwnd = int(self.winId())
            foreground_hwnd = win32gui.GetForegroundWindow()
            if hwnd == foreground_hwnd:
                return
            foreground_thread = win32process.GetWindowThreadProcessId(foreground_hwnd)[0]
            current_thread = win32api.GetCurrentThreadId()
            if foreground_thread != current_thread:
                win32process.AttachThreadInput(foreground_thread, current_thread, True)
                win32gui.BringWindowToTop(hwnd)
                win32gui.SetForegroundWindow(hwnd)
                win32process.AttachThreadInput(foreground_thread, current_thread, False)
            else:
                win32gui.SetForegroundWindow(hwnd)
            win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
            win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
            print("[Force Foreground] Forced window activation complete")
        except Exception as e:
            print(f"[Force Foreground] Error during window activation: {e}")

    def capture_full_screen(self):
        """Perform full screen capture"""
        print("[Capture Trigger] Full screen capture requested.") # 로그 추가
        self.statusBar().showMessage('Capturing full screen...')
        
        # 캡처 시작 전 상태 저장
        self._was_visible_before_capture = self.isVisible()
        print(f"[Capture Trigger] Window was visible before full screen capture: {self._was_visible_before_capture}")
        
        # 트레이 상태일 때는 window_to_hide를 None으로 전달
        window_to_hide = self if self._was_visible_before_capture else None
        self.last_capture_path = self.capture_module.capture_full_screen(window_to_hide=window_to_hide)
        print(f"[Capture Complete] Full screen capture attempted. Path: {self.last_capture_path}")
        
        # 캡처 후 창 상태 확인 및 처리
        if self._was_visible_before_capture: 
            print("[Capture Complete] Processing for previously visible window...")
            # 창 바로 표시 및 활성화
            if not self.isVisible():
                print("[Capture Complete] Window is hidden, showing now...")
                self.show()
                self.activateWindow()
                self.raise_()
                # 강제 활성화 추가
                QTimer.singleShot(100, self._force_window_to_foreground)
            
            # 미리보기 업데이트 (지연 없이 바로 실행) -> 지연 추가
            if self.last_capture_path:
                # QTimer.singleShot(50, lambda p=self.last_capture_path: self.update_preview(p))
                QTimer.singleShot(50, lambda: self.update_preview(self.last_capture_path))
                self.statusBar().showMessage('Full screen capture completed - Press Save button to save the image')
                self.save_btn.setEnabled(True)
            else:
                print("[Capture Complete] Capture failed (no path returned). Showing error message.")
                self.statusBar().showMessage('Full screen capture failed!')
                self.save_btn.setEnabled(False)
        else: 
            print("[Capture Complete] Processing for tray capture...")
            if self.last_capture_path: # 트레이 상태에서 캡처 성공
                # --- 자동 저장 호출 제거 --- #
                # print("[Tray Capture] Attempting auto-save for full screen...")
                # self.save_image() 
                
                # --- 메인 창 표시 및 활성화 --- #
                print("[Tray Capture] Capture successful, showing main window...")
                self.show()
                self.activateWindow()
                self.raise_()
                QTimer.singleShot(100, self._force_window_to_foreground)
                
                # --- 미리보기 업데이트 (지연 포함) --- #
                QTimer.singleShot(50, lambda: self.update_preview(self.last_capture_path))
                
                # --- 상태 표시줄 업데이트 및 버튼 활성화 --- #
                self.statusBar().showMessage('Full screen capture completed - Press Save or Edit')
                self.save_btn.setEnabled(True)
                # Edit 버튼 활성화는 update_preview에서 처리됩니다.

            else: # 트레이 상태에서 캡처 실패
                # 트레이 알림 제거 (오류는 로그로 확인)
                # if self.tray_icon: self.tray_icon.showMessage(...)
                 print(f"[Tray Capture] Full screen capture failed.")
                 # 실패 시 메인 창을 띄울 필요는 없음

    def capture_area(self):
        """Start area selection capture mode"""
        print("[Capture Trigger] Area capture requested.") # 로그 추가
        self.statusBar().showMessage('Rectangular area selection mode - Drag to select an area')
        
        # 캡처 시작 전 상태 저장
        self._was_visible_before_capture = self.isVisible()
        print(f"[Capture Trigger] Window was visible before area capture: {self._was_visible_before_capture}")
        
        # AreaSelector 생성
        self.area_selector = AreaSelector(self)
        
        # 메인 창이 보이는 경우에만 숨김
        if self._was_visible_before_capture:
            print("[Capture Trigger] Hiding main window for area selection.")
            self.hide()
        
        # Display area selector
        print("[Capture Trigger] Showing AreaSelector.")
        self.area_selector.show()
        self.area_selector.activateWindow()
        self.area_selector.raise_()

    def capture_window(self):
        """마우스 호버로 캡처할 창을 선택"""
        print("[Capture Trigger] Window capture requested.") # 로그 추가
        self.statusBar().showMessage('Move mouse over a window and click to capture it')
        
        # 캡처 시작 전 상태 저장
        self._was_visible_before_capture = self.isVisible()
        print(f"[Capture Trigger] Window was visible before window capture: {self._was_visible_before_capture}")
        
        # 메인 창이 보이는 경우에만 숨김
        if self._was_visible_before_capture:
            print("[Capture Trigger] Hiding main window for window selection.")
            self.hide()
            QApplication.processEvents() 
            time.sleep(0.2)
        
        # 창 선택 위젯 생성 및 표시
        print("[Capture Trigger] Showing WindowSelector.")
        logging.debug("[Capture Trigger] Creating and showing WindowSelector.") # 로그 추가
        self.window_selector = WindowSelector(self)
        QApplication.processEvents() 
        self.window_selector.show()
        self.window_selector.activateWindow()
        self.window_selector.raise_()

    def process_window_selection(self, hwnd, title):
        """선택한 창 캡처 처리"""
        print(f"[Capture Process] Window selection processed. HWND: {hwnd}, Title: '{title}'") # 로그 추가
        print(f"[Capture Process] Main window was visible before capture: {self._was_visible_before_capture}")
        
        # 취소한 경우
        if hwnd is None:
            self.statusBar().showMessage('Capture canceled')
            if self._was_visible_before_capture:
                print("[Capture Process] Capture canceled, showing main window.")
                self.show()
                self.activateWindow()
                self.raise_()
                QTimer.singleShot(100, self._force_window_to_foreground)
            return
        
        # 캡처 실행
        try:
            if not win32gui.IsWindow(hwnd):
                print("[Capture Process] Invalid window handle.")
                self.statusBar().showMessage('Invalid window. Please try again.')
                if self._was_visible_before_capture:
                    print("[Capture Process] Invalid handle, showing main window.")
                    self.show()
                    self.activateWindow()
                    self.raise_()
                    QTimer.singleShot(100, self._force_window_to_foreground)
                return
                
            window_title = win32gui.GetWindowText(hwnd)
            print(f"[Capture Process] Attempting capture for HWND: {hwnd}, Title: '{window_title}'")
            
            # 트레이 상태 고려하여 window_to_hide 전달
            window_to_hide_capture = self if self._was_visible_before_capture else None
            self.last_capture_path = self.capture_module.capture_window(window_to_hide=window_to_hide_capture, hwnd=hwnd)
            print(f"[Capture Complete] Window capture attempted. Path: {self.last_capture_path}")
            
            # 창 상태에 따라 처리 분기
            if self._was_visible_before_capture:
                print("[Capture Complete] Processing for previously visible window...")
                # 창 즉시 표시 및 활성화
                if not self.isVisible():
                    print("[Capture Complete] Window is hidden, showing now...")
                    self.show()
                    self.activateWindow()
                    self.raise_()
                    QTimer.singleShot(100, self._force_window_to_foreground)
                
                # 미리보기 업데이트 -> 지연 추가
                if self.last_capture_path:
                    # QTimer.singleShot(50, lambda p=self.last_capture_path: self.update_preview(p))
                    QTimer.singleShot(50, lambda: self.update_preview(self.last_capture_path))
                    window_name = window_title if window_title else "Selected window"
                    self.statusBar().showMessage(f'Capture of window "{window_name}" completed - Press Save button to save the image')
                    self.save_btn.setEnabled(True)
                else:
                    print("[Capture Complete] Capture failed (no path returned). Showing error message.")
                    self.statusBar().showMessage(f'Capture of window "{window_title}" failed!')
                    self.save_btn.setEnabled(False)

            else: # 트레이 상태에서 캡처한 경우
                print("[Capture Complete] Processing for tray capture...")
                if self.last_capture_path:
                    # --- 자동 저장 호출 제거 --- #
                    # print("[Tray Capture] Attempting auto-save for window capture...")
                    # self.save_image()

                    # --- 메인 창 표시 및 활성화 --- #
                    print("[Tray Capture] Window capture successful, showing main window...")
                    self.show()
                    self.activateWindow()
                    self.raise_()
                    QTimer.singleShot(100, self._force_window_to_foreground)

                    # --- 미리보기 업데이트 (지연 포함) --- #
                    QTimer.singleShot(50, lambda: self.update_preview(self.last_capture_path))

                    # --- 상태 표시줄 업데이트 및 버튼 활성화 --- #
                    # window_title 변수가 이 범위에서 사용 가능하도록 확인 또는 수정 필요
                    # -> try 블록 안에서 선언되었으므로, title 파라미터를 사용하도록 수정
                    window_name = title if title else "Selected window"
                    self.statusBar().showMessage(f'Capture of window "{window_name}" completed - Press Save or Edit')
                    self.save_btn.setEnabled(True)
                    # Edit 버튼 활성화는 update_preview에서 처리됩니다.

                else:
                    # 트레이 알림 제거 (오류는 로그로 확인)
                    # if self.tray_icon: self.tray_icon.showMessage(...)
                    # window_title 변수 사용 제거 또는 title 사용
                    print(f"[Tray Capture] Window capture failed for '{title if title else 'Unknown'}'.") 
                    # 실패 시 메인 창을 띄울 필요는 없음

        except Exception as e:
            print(f"[Capture Process] Error processing window capture: {e}")
            traceback.print_exc() # 상세 에러 로그 추가
            if self._was_visible_before_capture and not self.isVisible():
                print("[Capture Process] Error occurred, showing main window.")
                self.show()
                self.activateWindow()
                self.raise_()
                QTimer.singleShot(100, self._force_window_to_foreground)
            if self._was_visible_before_capture:
                self.statusBar().showMessage(f'Capture failed: {str(e)}')
            QMessageBox.warning(self, "Capture Error", f"An error occurred during screen capture: {str(e)}")

    def process_area_selection(self, rect):
        """Process area selection"""
        print(f"[Capture Process] Area selection processed. Rect: {rect}") # 로그 추가
        print(f"[Capture Process] Main window was visible before capture: {self._was_visible_before_capture}")

        # 유효하지 않은 선택 영역인 경우 처리
        if rect.width() <= 5 or rect.height() <= 5:
            self.statusBar().showMessage('Area selection too small or canceled.')
            if self._was_visible_before_capture:
                print("[Capture Process] Area too small, showing main window.")
                self.show()
            return
            
        print(f"[Capture Process] Attempting area capture for Rect: {rect}")
        # 트레이 상태 고려하여 window_to_hide 전달
        window_to_hide_capture = self if self._was_visible_before_capture else None
        self.last_capture_path = self.capture_module.capture_area(
            rect.x(), rect.y(), rect.width(), rect.height(), window_to_hide=window_to_hide_capture)
        print(f"[Capture Complete] Area capture attempted. Path: {self.last_capture_path}")
        
        # 창 상태에 따라 처리 분기
        if self._was_visible_before_capture:
            print("[Capture Complete] Processing for previously visible window...")
            # 창 즉시 표시 및 활성화
            if not self.isVisible():
                print("[Capture Complete] Window is hidden, showing now...")
                self.show()
                self.activateWindow()
                self.raise_()
                QTimer.singleShot(100, self._force_window_to_foreground)
                
            # 미리보기 업데이트 -> 지연 추가
            if self.last_capture_path:
                # QTimer.singleShot(50, lambda p=self.last_capture_path: self.update_preview(p))
                QTimer.singleShot(50, lambda: self.update_preview(self.last_capture_path))
                self.statusBar().showMessage('Area capture completed - Press Save button to save the image')
                self.save_btn.setEnabled(True)
            else:
                print("[Capture Complete] Capture failed (no path returned). Showing error message.")
                self.statusBar().showMessage('Area capture failed!')
                self.save_btn.setEnabled(False)
        else: # 트레이 상태에서 캡처한 경우
             print("[Capture Complete] Processing for tray capture...")
             if self.last_capture_path:
                 # --- 자동 저장 호출 제거 --- #
                 # print("[Tray Capture] Attempting auto-save for area capture...")
                 # self.save_image()

                 # --- 메인 창 표시 및 활성화 --- #
                 print("[Tray Capture] Area capture successful, showing main window...")
                 self.show()
                 self.activateWindow()
                 self.raise_()
                 QTimer.singleShot(100, self._force_window_to_foreground)

                 # --- 미리보기 업데이트 (지연 포함) --- #
                 QTimer.singleShot(50, lambda: self.update_preview(self.last_capture_path))

                 # --- 상태 표시줄 업데이트 및 버튼 활성화 --- #
                 self.statusBar().showMessage('Area capture completed - Press Save or Edit')
                 self.save_btn.setEnabled(True)
                 # Edit 버튼 활성화는 update_preview에서 처리됩니다.

             else:
                 # 트레이 알림 제거 (오류는 로그로 확인)
                 # if self.tray_icon: self.tray_icon.showMessage(...)
                 print(f"[Tray Capture] Area capture failed.")
                 # 실패 시 메인 창을 띄울 필요는 없음

    def update_preview(self, image_path):
        """Update captured image preview"""
        print(f"[Update Preview] Called with path: {image_path}") # 로그 추가
        if os.path.exists(image_path):
            # 이미지 로드
            pixmap = QPixmap(image_path)
            
            if pixmap.isNull():
                print("[Update Preview Error] Failed to load QPixmap.") # 로그 추가
                self.preview_label.setText('Cannot load image')
                self.preview_label.setStyleSheet("#previewLabel { color: #888888; font-size: 8pt; background-color: white; }") 
                self.edit_btn.setEnabled(False)
                self.fullscreen_placeholder_btn.setEnabled(False)
                self.copy_btn.setEnabled(False) # 복사 버튼 비활성화
                return
            
            print("[Update Preview] QPixmap loaded successfully.") # 로그 추가
            # 레이블 최대 크기 가져오기
            label_size = self.preview_label.size()
            print(f"[Update Preview] Preview label size: {label_size.width()}x{label_size.height()}") # 로그 추가
            
            # 레이블 크기에 맞게 이미지 스케일링 (꽉 차게 표시)
            scaled_pixmap = pixmap.scaled(
                label_size.width(),
                label_size.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            print(f"[Update Preview] Scaled pixmap size: {scaled_pixmap.width()}x{scaled_pixmap.height()}") # 로그 추가
            
            # 스케일링된 이미지 설정
            self.preview_label.setPixmap(scaled_pixmap)
            self.preview_label.setStyleSheet("#previewLabel { background-color: black; }") 
            print("[Update Preview] Pixmap set on label.") # 로그 추가
            
            # Edit 버튼 활성화
            self.edit_btn.setEnabled(True)
            self.fullscreen_placeholder_btn.setEnabled(True)
            self.copy_btn.setEnabled(True) # 복사 버튼 활성화
            
            # 콘솔에 디버깅 정보 출력 -> 로그로 대체
            # print(f"원본 이미지 크기: {pixmap.width()}x{pixmap.height()}, "
            #       f"레이블 크기: {label_size.width()}x{label_size.height()}, "
            #       f"스케일링된 이미지 크기: {scaled_pixmap.width()}x{scaled_pixmap.height()}")
        else:
            print(f"[Update Preview Error] Image path does not exist: {image_path}") # 로그 추가
            self.preview_label.setText('Cannot load image')
            self.preview_label.setStyleSheet("#previewLabel { color: #888888; font-size: 8pt; background-color: white; }") 
            self.edit_btn.setEnabled(False)
            self.fullscreen_placeholder_btn.setEnabled(False)
            self.copy_btn.setEnabled(False) # 복사 버튼 비활성화

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
            print(f"Save path has been changed: {self.default_save_dir}")

    def save_image(self):
        """Save captured image"""
        print("[Save Image Triggered]") # 함수 시작 로그 추가
        # Check if capture_module has the captured_image attribute and it's not None
        if not hasattr(self.capture_module, 'captured_image') or self.capture_module.captured_image is None:
            print("[Save Image Error] No captured image data found in capture_module.") # 로그 추가
            # Try loading from last_capture_path as a fallback
            if self.last_capture_path and os.path.exists(self.last_capture_path):
                print("[Save Image Fallback] Trying to load image from last_capture_path:", self.last_capture_path)
                try:
                    # Load QImage, convert to PIL, and set it in capture_module
                    q_img = QImage(self.last_capture_path)
                    if not q_img.isNull():
                        pil_img = qimage_to_pil(q_img)
                        self.capture_module.captured_image = pil_img # 여기서 다시 설정
                        print("[Save Image Fallback] Successfully loaded image from path and updated capture_module.")
                    else:
                        print("[Save Image Fallback Error] Failed to load QImage from path.")
                        # 트레이 모드에서는 QMessageBox 사용 부적절 -> 로그만 남김
                        # QMessageBox.warning(self, "Save Error", "Could not load the captured image data to save.")
                        return # 저장 실패
                except Exception as e:
                     print(f"[Save Image Fallback Error] Exception loading image from path: {e}")
                     # 트레이 모드에서는 QMessageBox 사용 부적절 -> 로그만 남김
                     # QMessageBox.warning(self, "Save Error", f"Error loading captured image: {e}")
                     return # 저장 실패
            else:
                print("[Save Image Error] No valid last_capture_path found either.")
                # 트레이 모드에서는 QMessageBox 사용 부적절 -> 로그만 남김
                # QMessageBox.warning(self, "Save Error", "There is no captured image to save.")
                return # 저장 실패

        # Fallback 후에도 capture_module.captured_image가 없는 경우 재확인
        if not hasattr(self.capture_module, 'captured_image') or self.capture_module.captured_image is None:
             print("[Save Image Error] Image data still missing after fallback attempt.")
             return # 최종 저장 실패

        # Now we should have self.capture_module.captured_image available
        print("[Save Image] Found captured image data in capture_module.")

        # Auto-generate filename (based on current date and time)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"
        
        # Create save path
        file_path = os.path.join(self.default_save_dir, filename)
        print(f"[Save Image] Generated save path: {file_path}")
        
        try:
            # 캡처 모듈의 저장 함수 호출
            print("[Save Image] Calling capture_module.save_captured_image...") # 호출 전 로그
            saved_path = self.capture_module.save_captured_image(file_path)
            if saved_path:
                self.last_saved_file_path = saved_path # 저장된 경로 저장
                print(f"[Save Image Success] Image saved: {saved_path}") # Log success
                # 상태 표시줄 메시지는 창이 보일 때만
                if self.isVisible():
                    self.statusBar().showMessage(f'Image saved: {saved_path}', 3000)
                
                # 트레이 알림 (저장 성공 시)
                if self.tray_icon and not self.isVisible(): # 트레이 모드에서만 알림
                     self.tray_icon.showMessage(
                         "ImageCapturePAAK",
                         f"Image saved: {os.path.basename(saved_path)}",
                         QSystemTrayIcon.Information,
                         2000
                     )

                # Capture module의 이미지 데이터도 업데이트 (Optional but good practice)
                try:
                    q_image = QImage(saved_path)
                    if not q_image.isNull():
                        pil_image = qimage_to_pil(q_image)
                        self.capture_module.captured_image = pil_image # 저장 후에도 최신 데이터 유지
                        print("[GUI] Capture module's internal image updated after save.")
                    else:
                        print("[GUI Error] Failed to load saved image into QImage for capture module update.")
                except Exception as e:
                    print(f"[GUI Error] Error updating capture module image after save: {e}")
            else:
                print("[Save Image Error] capture_module.save_captured_image returned None.")
                # 트레이 모드에서는 QMessageBox 사용 부적절
                # QMessageBox.warning(self, "Save Error", "Failed to save image.")
                # 트레이 알림 (저장 실패 시)
                if self.tray_icon and not self.isVisible():
                     self.tray_icon.showMessage(
                         "ImageCapturePAAK",
                         "Failed to save image!",
                         QSystemTrayIcon.Warning,
                         2000
                     )
        except Exception as e:
            print(f"[Save Image Error] Exception during saving: {e}") # Log exception
            traceback.print_exc() # Print full traceback
            # 트레이 모드에서는 QMessageBox 사용 부적절
            # QMessageBox.critical(self, "Save Error", f"An error occurred while saving the file: {str(e)}")
            # 트레이 알림 (저장 오류 시)
            if self.tray_icon and not self.isVisible():
                 self.tray_icon.showMessage(
                     "ImageCapturePAAK",
                     f"Error saving image: {e}",
                     QSystemTrayIcon.Critical,
                     3000
                 )

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
                if self.last_saved_file_path and os.path.exists(self.last_saved_file_path):
                    # 마지막 저장된 파일이 있으면 해당 파일을 선택하여 폴더 열기
                    subprocess.run(['explorer', '/select,', self.last_saved_file_path])
                    self.statusBar().showMessage(f'Opened folder and selected file: {self.last_saved_file_path}', 3000)
                else:
                    # 저장된 파일이 없으면 폴더만 열기
                    os.startfile(self.default_save_dir)
                    self.statusBar().showMessage(f'Opened folder: {self.default_save_dir}', 3000)
            elif platform.system() == "Darwin":
                # macOS (파일 선택 기능 미지원, 폴더만 열기)
                subprocess.call(["open", self.default_save_dir])
                self.statusBar().showMessage(f'Opened folder: {self.default_save_dir}', 3000)
            else:
                # Linux (파일 선택 기능 미지원, 폴더만 열기)
                subprocess.call(["xdg-open", self.default_save_dir])
                self.statusBar().showMessage(f'Opened folder: {self.default_save_dir}', 3000)
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open folder: {str(e)}")

    def show_fullscreen_preview(self):
        """Show the current preview image in full screen."""
        if self.fullscreen_viewer and self.fullscreen_viewer.isVisible():
            # 이미 전체 화면 뷰어가 떠 있다면 닫기 (ESC 누른 경우)
            # self.fullscreen_viewer.close() # FullScreenViewer 자체에서 ESC로 닫음
            # 여기서 별도 처리는 불필요할 수 있음
            return 
            
        if self.last_capture_path and os.path.exists(self.last_capture_path):
            pixmap = QPixmap(self.last_capture_path)
            if pixmap.isNull():
                self.statusBar().showMessage('Cannot load image for full screen preview.')
                return

            # Create and show the full screen viewer
            # 이전 뷰어가 남아있을 수 있으므로 새로 생성하기 전에 확인/정리
            if self.fullscreen_viewer:
                self.fullscreen_viewer.close()
                self.fullscreen_viewer = None
            
            self.fullscreen_viewer = FullScreenViewer(self.last_capture_path)
            # self.fullscreen_viewer.showFullScreen() # initUI에서 setGeometry 사용하므로 show() 호출
            self.fullscreen_viewer.show()
        else:
            self.statusBar().showMessage('No image captured to show in full screen.')

    def open_image_editor(self):
        """이미지 편집기 열기 (수정: edit_image 메서드 호출)"""
        if not self.last_capture_path:
            QMessageBox.warning(self, "Error", "No image captured to edit!")
            return
            
        # self.edit_image 메서드를 호출하여 편집기 열기 및 숨기기 로직 실행
        self.edit_image(self.last_capture_path)
        
        # 아래 코드는 edit_image 메서드로 이동되었으므로 주석 처리 또는 삭제
        # self.image_editor = ImageEditor(self.last_capture_path, self)
        # self.image_editor.imageSaved.connect(self.handle_image_saved)
        # self.image_editor.show()
        
        # 상태 표시줄 메시지 업데이트
        self.statusBar().showMessage("Image editor opened")

    def copy_image_to_clipboard(self):
        """현재 미리보기 이미지를 클립보드에 복사합니다."""
        if self.last_capture_path and os.path.exists(self.last_capture_path):
            try:
                pixmap = QPixmap(self.last_capture_path)
                if pixmap.isNull():
                    self.statusBar().showMessage('Failed to load image for copying', 3000)
                    return
                
                clipboard = QApplication.clipboard()
                clipboard.setImage(pixmap.toImage()) # QPixmap을 QImage로 변환하여 복사
                self.statusBar().showMessage('Image copied to clipboard', 3000)
                print(f"[Clipboard] Image copied from {self.last_capture_path}")

            except Exception as e:
                self.statusBar().showMessage(f'Error copying image: {e}', 3000)
                print(f"[Clipboard Error] Failed to copy image: {e}")
        else:
            self.statusBar().showMessage('No image to copy', 3000)

    def handle_image_saved(self, saved_path):
        """ImageEditor에서 이미지 저장 시 호출될 슬롯"""
        print(f"[GUI] Received imageSaved signal for: {saved_path}")
        self.last_capture_path = saved_path # 마지막 캡처 경로 업데이트
        self.last_saved_file_path = saved_path # 마지막 저장 경로도 업데이트 (동일하게 취급)
        self.update_preview(saved_path) # 프리뷰 업데이트
        # 혹시 전체 화면 뷰어가 열려 있다면 업데이트
        if self.fullscreen_viewer and self.fullscreen_viewer.isVisible():
             self.fullscreen_viewer.image = QImage(saved_path)
             self.fullscreen_viewer.update() # 다시 그리도록 요청
             
        # Capture module의 이미지 데이터도 업데이트
        try:
            q_image = QImage(saved_path)
            if not q_image.isNull():
                pil_image = qimage_to_pil(q_image)
                self.capture_module.captured_image = pil_image
                print("[GUI] Capture module's internal image updated.")
            else:
                print("[GUI] Failed to load saved image into QImage for capture module update.")
        except Exception as e:
            print(f"[GUI] Error updating capture module image: {e}")

    # --- edit_image 메서드 추가 ---
    def edit_image(self, image_path):
        """선택된 이미지를 편집기에 엽니다."""
        print(f"[GUI DEBUG] edit_image called with path: {image_path}")
        if image_path:
            try:
                # ImageEditor 인스턴스 생성 (parent=None)
                self.editor = ImageEditor(image_path, parent=None)
                # 편집기가 닫힐 때 메인 창을 다시 표시하도록 closed 시그널 연결
                self.editor.closed.connect(self.show)
                # 편집기에서 이미지가 저장될 때 handle_image_saved 슬롯 호출하도록 연결
                self.editor.imageSaved.connect(self.handle_image_saved)
                
                # 편집기 창을 먼저 표시
                self.editor.show()
                # 그 다음 메인 창 숨기기
                self.hide()

            except Exception as e:
                print(f"[GUI Error] Failed to open ImageEditor: {e}")
                traceback.print_exc()
                # 에디터 열기 실패 시 다시 메인 창 표시
                self.show()
                QMessageBox.warning(self, "Editor Error", f"Failed to open image editor: {e}")
        else:
            print("[GUI Warning] No image path provided to edit_image")

    # --- update_thumbnail 메서드 추가 (기능은 추후 구현) ---
    def update_thumbnail(self, image_path):
        """캡처 완료 후 썸네일을 업데이트합니다 (현재는 비어 있음)."""
        print(f"[GUI DEBUG] update_thumbnail called with path: {image_path}") # 로그 메시지 수정
        # TODO: 썸네일 업데이트 로직 구현 (필요시)
        pass

    # 단축키 ID 설정 메소드 추가
    def set_hotkey_ids(self, ids):
        """main.py에서 등록된 단축키 ID를 받아서 저장"""
        self.hotkey_ids = ids
        print(f"[Hotkey] Received hotkey IDs: {self.hotkey_ids}")

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
            logging.debug("[WindowSelector] Loading window list...") # 로그 추가
            
            def enum_windows_proc(hwnd, results):
                # 보이는 창만 추가
                if win32gui.IsWindowVisible(hwnd) and not win32gui.IsIconic(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    # 빈 제목이나 "ImageCapturePAAK" 포함 창은 제외
                    if title and "ImageCapturePAAK" not in title:
                        # 실제 창 영역 가져오기
                        try:
                            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
                            width = right - left
                            height = bottom - top
                            logging.debug(f"  - Found window: '{title}' ({width}x{height}) HWND: {hwnd}") # 로그 추가
                            # 최소 크기 이상인 창만 추가
                            if width > 100 and height > 100: # 주석 제거하여 복원
                                # 창 핸들, 제목, 영역 저장
                                self.window_list.append({
                                    'hwnd': hwnd,
                                    'title': title,
                                    'rect': QRect(left, top, width, height)
                                })
                                logging.debug(f"    -> Added to list (meets size requirement).") # 로그 추가
                            else:
                                logging.debug(f"    -> Skipped (doesn't meet size requirement).") # 로그 추가
                        except Exception as e_rect:
                            logging.warning(f"    -> Error getting rect for HWND {hwnd}: {e_rect}") # 로그 추가
                            pass
                return True
                
            # 모든 창을 순회하며 목록 만들기
            win32gui.EnumWindows(enum_windows_proc, None)
            
            # 창 목록이 있는지 확인
            if self.window_list:
                print(f"Detected window list: {len(self.window_list)} items")
            else:
                print("No windows detected.")
                
        except Exception as e:
            print(f"Error loading window list: {e}")
            
    def initUI(self):
        """UI 초기화"""
        # 전체 화면 크기로 설정
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(QApplication.primaryScreen().geometry())
        self.setCursor(Qt.CrossCursor)
        
        # 안내 텍스트 표시
        self.info_label = QLabel("Hover the mouse over a window to highlight it, click to capture the entire window. Press ESC to cancel.", self)
        self.info_label.setStyleSheet("""
            background-color: rgba(0, 0, 0, 180); 
            color: white; 
            padding: 12px; 
            border-radius: 6px;
            font-size: 15px;
            font-weight: bold;
        """)
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setFixedWidth(300)  # 너비 수정: 600 -> 300
        
        # 화면 하단에 표시
        rect = self.geometry()
        self.info_label.move(
            (rect.width() - self.info_label.width()) // 2,
            rect.height() - self.info_label.height() - 60
        )
        
    def find_window_at_position(self, pos):
        """마우스 위치에 있는 창 찾기 (가장 작은 창 우선)"""
        logging.debug(f"[WindowSelector] Finding window at physical position: {pos.x()},{pos.y()}")
        
        matching_windows = []
        for window in self.window_list:
            logging.debug(f"  - Checking against: '{window['title']}' Rect: {window['rect']}")
            if window['rect'].contains(pos):
                logging.debug(f"    -> Potential match.") # 로그 수정
                matching_windows.append(window)
        
        if not matching_windows:
            logging.debug("  -> No match found.")
            return None
            
        # 매칭된 창들 중에서 가장 작은 창 찾기
        smallest_window = min(matching_windows, key=lambda w: w['rect'].width() * w['rect'].height())
        logging.debug(f"  -> Smallest matching window selected: '{smallest_window['title']}'") # 로그 추가
        
        return smallest_window
            
    def check_mouse_position(self):
        """마우스 위치에 있는 창 확인"""
        try:
            # 마우스 현재 위치 가져오기 (논리적 좌표)
            logical_cursor_pos = QCursor.pos()
            logging.debug(f"[WindowSelector] Checking mouse. Logical pos: {logical_cursor_pos.x()},{logical_cursor_pos.y()}") # 로그 추가
            
            # 현재 화면의 devicePixelRatio 가져오기
            screen = QApplication.screenAt(logical_cursor_pos) # 마우스 커서가 있는 화면
            if not screen:
                screen = QApplication.primaryScreen() # 실패 시 주 화면 사용
            
            if screen:
                device_pixel_ratio = screen.devicePixelRatio()
            else:
                device_pixel_ratio = 1.0 # Fallback
            logging.debug(f"[WindowSelector] Device Pixel Ratio: {device_pixel_ratio}") # 로그 추가
                
            # 논리적 좌표를 물리적 픽셀 좌표로 변환
            physical_cursor_pos = QPoint(
                int(logical_cursor_pos.x() * device_pixel_ratio),
                int(logical_cursor_pos.y() * device_pixel_ratio)
            )
            logging.debug(f"[WindowSelector] Calculated physical pos: {physical_cursor_pos.x()},{physical_cursor_pos.y()}") # 로그 추가
            
            # 물리적 좌표로 마우스 위치에 있는 창 찾기
            window = self.find_window_at_position(physical_cursor_pos)
            logging.debug(f"[WindowSelector] Find result: {'Found' if window else 'None'}") # 로그 추가
            
            # 창을 찾았으면 정보 업데이트
            if window:
                # 이전과 같은 창이면 업데이트 불필요
                if self.current_hwnd == window['hwnd'] and self.current_rect:
                    return
                    
                # 새로운 창 정보 업데이트
                self.current_hwnd = window['hwnd']
                self.current_title = window['title']
                self.current_rect = window['rect']
                print(f"✓ Window recognized: '{window['title']}', Size: {window['rect'].width()}x{window['rect'].height()}")
                self.update()
            else:
                # 창을 찾지 못했으면 초기화
                self.clear_current_window()
                
        except Exception as e:
            print(f"Window detection error: {e}")
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
        painter.fillRect(self.rect(), QColor(0, 0, 0, 80))
        
        # 현재 창 강조 표시
        if self.current_rect and self.current_hwnd and self.current_title:
            # 현재 화면의 devicePixelRatio 가져오기
            screen = self.screen() # 위젯이 속한 화면 가져오기
            if not screen:
                screen = QApplication.primaryScreen() # 실패 시 주 화면 사용
            
            if screen:
                device_pixel_ratio = screen.devicePixelRatio()
            else:
                device_pixel_ratio = 1.0 # Fallback
                
            # 물리적 좌표(self.current_rect)를 논리적 좌표로 변환
            logical_rect = QRectF(
                self.current_rect.x() / device_pixel_ratio,
                self.current_rect.y() / device_pixel_ratio,
                self.current_rect.width() / device_pixel_ratio,
                self.current_rect.height() / device_pixel_ratio
            )

            # 선택된 창 영역은 더 투명하게 (논리적 좌표 사용)
            highlight_area = QPainterPath()
            highlight_area.addRect(logical_rect)
            
            # 선택된 창 영역만 투명하게 하기 위한 Path 설정 (논리적 좌표 사용)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, 10))  # 매우 투명한 배경
            painter.drawRect(logical_rect)
            
            # 테두리 그리기 (논리적 좌표 사용)
            pen = QPen(QColor(0, 180, 255), 4 / device_pixel_ratio) # DPI에 따라 굵기 조정
            painter.setPen(pen)
            painter.drawRect(logical_rect)
            
            # 창 제목 표시 영역 (논리적 좌표 기준)
            title_bg_rect = QRectF(
                logical_rect.x(),
                max(0, logical_rect.y() - (50 / device_pixel_ratio)), # 논리적 픽셀로 조정
                min(500 / device_pixel_ratio, logical_rect.width()), # 논리적 픽셀로 조정
                40 / device_pixel_ratio  # 논리적 픽셀로 조정
            )
            
            # 창 제목 배경 (어두운 배경)
            painter.setBrush(QColor(0, 0, 0, 180))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(title_bg_rect, 5 / device_pixel_ratio, 5 / device_pixel_ratio) # DPI에 따라 조정
            
            # 창 제목 텍스트
            painter.setPen(QColor(255, 255, 255))
            font = painter.font()
            # 폰트 크기는 논리적 픽셀 기준이므로 그대로 사용해도 될 수 있음
            # 필요시 font.setPointSizeF(12) 와 같이 조정
            font.setPointSize(12) 
            font.setBold(True)
            painter.setFont(font)
            
            # 창 제목이 너무 길면 잘라서 표시
            display_title = self.current_title
            if len(display_title) > 50:
                display_title = display_title[:47] + "..."
                
            painter.drawText(title_bg_rect, Qt.AlignCenter, display_title)
            
            # 모서리 표시점 추가 (논리적 좌표 기준)
            corner_size_logical = 10 / device_pixel_ratio # 논리적 크기
            corner_color = QColor(0, 180, 255)
            painter.setBrush(QBrush(corner_color))
            painter.setPen(Qt.NoPen)
            
            # 왼쪽 상단
            painter.drawRect(QRectF(
                logical_rect.left() - corner_size_logical / 2, 
                logical_rect.top() - corner_size_logical / 2, 
                corner_size_logical, corner_size_logical))
            
            # 오른쪽 상단
            painter.drawRect(QRectF(
                logical_rect.right() - corner_size_logical / 2, 
                logical_rect.top() - corner_size_logical / 2, 
                corner_size_logical, corner_size_logical))
            
            # 왼쪽 하단
            painter.drawRect(QRectF(
                logical_rect.left() - corner_size_logical / 2, 
                logical_rect.bottom() - corner_size_logical / 2, 
                corner_size_logical, corner_size_logical))
            
            # 오른쪽 하단
            painter.drawRect(QRectF(
                logical_rect.right() - corner_size_logical / 2, 
                logical_rect.bottom() - corner_size_logical / 2, 
                corner_size_logical, corner_size_logical))
            
            # 창 크기 정보 표시 (물리적 픽셀 기준, 위치는 논리적 좌표 기준)
            size_text = f"{self.current_rect.width()} × {self.current_rect.height()} px" # 실제 픽셀 크기 표시
            size_bg_width_logical = 150 / device_pixel_ratio
            size_bg_height_logical = 30 / device_pixel_ratio
            size_bg_rect = QRectF(
                logical_rect.right() - size_bg_width_logical,
                logical_rect.bottom() + (10 / device_pixel_ratio),
                size_bg_width_logical,
                size_bg_height_logical
            )
            
            # 크기 정보 배경
            painter.setBrush(QColor(0, 0, 0, 180))
            painter.drawRoundedRect(size_bg_rect, 5 / device_pixel_ratio, 5 / device_pixel_ratio)
            
            # 크기 정보 텍스트
            painter.setPen(QColor(255, 255, 255))
            font = painter.font()
            # 폰트 크기는 논리적 픽셀 기준
            font.setPointSize(11) 
            font.setBold(True)
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
        self.setAttribute(Qt.WA_TranslucentBackground)
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
            font.setPointSize(12) # 폰트 크기 수정: 8 -> 12 (1.5배)
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
            
            # Calculate selection area (logical pixels)
            selection_rect = QRect(self.selection_start, self.selection_end).normalized()

            # Get Device Pixel Ratio for scaling
            # AreaSelector는 최상위 위젯이므로 application에서 가져오거나 primaryScreen 사용
            screen = QApplication.primaryScreen()
            if screen:
                device_pixel_ratio = screen.devicePixelRatio()
            else:
                device_pixel_ratio = 1.0 # Fallback

            # Scale the rectangle coordinates to physical pixels
            physical_rect = QRect(
                int(selection_rect.x() * device_pixel_ratio),
                int(selection_rect.y() * device_pixel_ratio),
                int(selection_rect.width() * device_pixel_ratio),
                int(selection_rect.height() * device_pixel_ratio)
            )
            
            # Close window after selection is complete
            self.close()
            
            # Pass PHYSICAL selection information to parent (창 표시는 캡처 모듈에서 처리됨)
            if self.parent:
                # 선택 영역이 너무 작으면 메인 창을 직접 표시
                if physical_rect.width() < 10 or physical_rect.height() < 10:
                    self.parent.show()
                    self.parent.statusBar().showMessage('Area selection too small - canceled.')
                else:
                    # process_area_selection에는 이제 물리적 픽셀 좌표를 전달
                    self.parent.process_area_selection(physical_rect)

    def keyPressEvent(self, event):
        """Key event handling"""
        # Cancel with ESC key
        if event.key() == Qt.Key_Escape:
            self.close()
            if self.parent:
                self.parent.show()
                self.parent.statusBar().showMessage('Rectangular area selection canceled.') 