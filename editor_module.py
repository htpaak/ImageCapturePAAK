import os
import sys
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QLabel, QAction, 
                            QToolBar, QFileDialog, QMessageBox, QApplication, QDesktopWidget, 
                            QToolButton, QMenu, QColorDialog, QComboBox, QLineEdit)
from PyQt5.QtGui import QPixmap, QImage, QIcon, QPainter, QPen, QColor, QPolygonF, QBrush, QFont, QFontMetrics
from PyQt5.QtCore import Qt, QSize, QRect, QPoint, QRectF, QSizeF, QLineF, QPointF
import math
# 사용자 정의 색상 선택기 import
from color_picker_module import CustomColorPicker 

class ImageCanvas(QWidget):
    """이미지를 직접 그리는 캔버스 위젯"""
    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self.editor = editor
        self.image = None
        self.text_input = None # 텍스트 입력 위젯 참조 추가
        
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

        # 하이라이트 오버레이 그리기 (오버레이 이미지가 있으면)
        if self.editor.highlight_overlay_image and not self.editor.highlight_overlay_image.isNull():
            # 오버레이 이미지를 동일한 target_rect에 그림
            painter.drawImage(target_rect, self.editor.highlight_overlay_image)
            # print("[PaintEvent] Overlay drawn") # 디버그용

        # 도구별 미리보기 그리기 (하이라이트는 오버레이로 대체됨)
        if self.editor.is_selecting and self.editor.selection_start_point and self.editor.selection_end_point:
            start_pt = self.editor.selection_start_point
            end_pt = self.editor.selection_end_point
            
            if self.editor.current_tool == 'mosaic':
                pen = QPen(Qt.white, 1, Qt.DashLine)
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)
                selection_rect_widget = QRect(start_pt, end_pt).normalized()
                painter.drawRect(selection_rect_widget)
            elif self.editor.current_tool == 'arrow':
                thickness_img_px = self.editor.current_arrow_thickness 
                print(f"[PaintEvent] Drawing temporary arrow: {start_pt} -> {end_pt}, Color: {self.editor.arrow_color.name()}, ImgThickness: {thickness_img_px}") 
                
                # 이미지 스케일 계산
                if img_size.width() > 0 and img_size.height() > 0: 
                    scale_x = scaled_size.width() / img_size.width()
                else:
                    scale_x = 1.0
                
                # 미리보기용 펜 두께 계산 (스케일 적용 후 반올림, 최소 1px)
                preview_thickness = max(1, round(thickness_img_px * scale_x)) # 반올림 후 최소 1 적용

                pen = QPen(self.editor.arrow_color, preview_thickness) # 스케일 적용 및 반올림된 두께 사용
                painter.setPen(pen)
                painter.setBrush(QBrush(self.editor.arrow_color)) 
                line = QLineF(start_pt, end_pt)
                painter.drawLine(line)
                
                # 화살촉 크기 계산 (이미지 기준 두께 사용 후 스케일 적용)
                arrow_size_img_px = 3.0 * thickness_img_px + 4 
                arrow_size_widget_px = arrow_size_img_px * scale_x 
                
                angle = math.atan2(-line.dy(), line.dx())
                arrow_p1 = line.p2() - QPointF(math.cos(angle + math.pi / 6) * arrow_size_widget_px,
                                              -math.sin(angle + math.pi / 6) * arrow_size_widget_px)
                arrow_p2 = line.p2() - QPointF(math.cos(angle - math.pi / 6) * arrow_size_widget_px,
                                              -math.sin(angle - math.pi / 6) * arrow_size_widget_px)
                arrow_head = QPolygonF([line.p2(), arrow_p1, arrow_p2])
                painter.drawPolygon(arrow_head)
            elif self.editor.current_tool == 'circle': # 원 그리기 미리보기 추가
                thickness_img_px = self.editor.current_circle_thickness
                # 이미지 스케일 계산 (화살표와 동일 로직 사용)
                if img_size.width() > 0 and img_size.height() > 0:
                    scale_x = scaled_size.width() / img_size.width()
                else:
                    scale_x = 1.0
                preview_thickness = max(1, round(thickness_img_px * scale_x))
                
                pen = QPen(self.editor.circle_color, preview_thickness, Qt.SolidLine)
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush) # 미리보기는 채우지 않음
                preview_rect_widget = QRect(start_pt, end_pt).normalized()
                painter.drawEllipse(preview_rect_widget)
            elif self.editor.current_tool == 'rectangle': # 사각형 그리기 미리보기 추가
                thickness_img_px = self.editor.current_rectangle_thickness
                # 이미지 스케일 계산 (원과 동일 로직 사용)
                if img_size.width() > 0 and img_size.height() > 0:
                    scale_x = scaled_size.width() / img_size.width()
                else:
                    scale_x = 1.0
                preview_thickness = max(1, round(thickness_img_px * scale_x))
                
                pen = QPen(self.editor.rectangle_color, preview_thickness, Qt.SolidLine)
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush) # 미리보기는 채우지 않음
                preview_rect_widget = QRect(start_pt, end_pt).normalized()
                painter.drawRect(preview_rect_widget)
            # Highlight 미리보기는 오버레이 방식으로 변경되었으므로 여기서는 제거

    # 마우스 이벤트 핸들러 추가
    def mousePressEvent(self, event):
        print("[Canvas] mousePressEvent received")
        tool = self.editor.current_tool
        if tool in ['mosaic', 'arrow', 'circle', 'rectangle', 'highlight', 'pen'] and event.button() == Qt.LeftButton:
            print(f"[Canvas] Activating selection/drawing for tool: {tool}")
            self.editor.is_selecting = True # 드래그/그리기 시작 플래그
            if tool == 'highlight':
                 # 오버레이 초기화
                 if self.editor.highlight_overlay_image:
                     self.editor.highlight_overlay_image.fill(Qt.transparent)
                 self.editor.stroke_points = [event.pos()] # 점 리스트 시작 (위젯 좌표)
            elif tool == 'pen':
                # Undo 상태 저장 (스트로크 시작 시 한 번만)
                self.editor.push_undo_state()
                # 첫 점 기록 (위젯 좌표 및 이미지 좌표)
                self.last_draw_point = event.pos()
                self.last_img_draw_point = self.map_widget_to_image(self.last_draw_point)
                # 첫 점을 바로 찍는 효과 (선택적)
                if self.last_img_draw_point:
                     self.editor.draw_pen_segment(self.last_img_draw_point, self.last_img_draw_point, self.editor.pen_color, self.editor.current_pen_thickness)
                     self.update() # 첫 점 표시
            else:
                self.editor.selection_start_point = event.pos()
                self.editor.selection_end_point = event.pos()
            print(f"[Canvas] State after press: is_selecting={self.editor.is_selecting}, tool={self.editor.current_tool}")
        elif tool == 'text' and event.button() == Qt.LeftButton and self.editor.is_adding_text:
            self.create_text_input(event.pos())
            self.editor.is_adding_text = False # 한 번 클릭으로 입력 상자 생성 후 비활성화
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # print("[Canvas] mouseMoveEvent received")
        if self.editor.is_selecting and self.editor.current_tool in ['mosaic', 'arrow', 'circle', 'rectangle', 'highlight', 'pen']:
            if self.editor.current_tool == 'highlight':
                self.editor.stroke_points.append(event.pos()) # 위젯 좌표 점 추가
                
                # 오버레이 클리어 및 전체 Polyline 다시 그리기
                if self.editor.highlight_overlay_image and len(self.editor.stroke_points) > 1:
                    self.editor.highlight_overlay_image.fill(Qt.transparent) # 오버레이 클리어
                    painter = QPainter(self.editor.highlight_overlay_image)
                    
                    # 이미지 좌표로 변환된 점 리스트 생성
                    img_points = [self.map_widget_to_image(p) for p in self.editor.stroke_points if p is not None]
                    valid_img_points = [p for p in img_points if p is not None]

                    if len(valid_img_points) > 1:
                        # draw_highlight_stroke와 동일한 펜 설정 사용
                        pen = QPen(self.editor.highlight_color, 
                                   self.editor.current_highlight_thickness, 
                                   Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                        painter.setPen(pen)
                        painter.setRenderHint(QPainter.Antialiasing)
                        
                        polygon = QPolygonF([QPointF(p) for p in valid_img_points])
                        painter.drawPolyline(polygon)
                    painter.end()
                
                self.update() # 미리보기 업데이트
            elif self.editor.current_tool == 'pen':
                current_pos = event.pos()
                img_current = self.map_widget_to_image(current_pos)
                # 이전 이미지 좌표와 현재 이미지 좌표가 모두 유효하면 선분 그리기
                if self.last_img_draw_point and img_current:
                    self.editor.draw_pen_segment(self.last_img_draw_point, img_current, self.editor.pen_color, self.editor.current_pen_thickness)
                # 현재 점을 다음 시작점으로 업데이트
                self.last_draw_point = current_pos
                self.last_img_draw_point = img_current
                # 변경된 이미지를 표시하도록 업데이트 요청
                self.update()
            else:
                self.editor.selection_end_point = event.pos()
                self.update() # 도형 미리보기 업데이트
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        print("[Canvas] mouseReleaseEvent received")
        # 텍스트 입력 중에는 release 이벤트 무시 (입력 완료는 QLineEdit에서 처리)
        if self.editor.current_tool == 'text' and self.text_input and self.text_input.isVisible():
             print("[Canvas] Mouse release ignored during text input.")
             super().mouseReleaseEvent(event)
             return

        if self.editor.is_selecting and event.button() == Qt.LeftButton and self.editor.current_tool in ['mosaic', 'arrow', 'circle', 'rectangle', 'highlight', 'pen']:
            tool = self.editor.current_tool
            self.editor.is_selecting = False # 여기서 플래그 해제
            
            if tool == 'highlight':
                # 마지막 점 추가
                if hasattr(self.editor, 'stroke_points'):
                    self.editor.stroke_points.append(event.pos())
                    if len(self.editor.stroke_points) > 1:
                        img_points = [self.map_widget_to_image(p) for p in self.editor.stroke_points if p is not None]
                        valid_img_points = [p for p in img_points if p is not None]
                        
                        if len(valid_img_points) > 1:
                            print(f"[MouseRelease] Calling draw_highlight_stroke on edited_image")
                            self.editor.push_undo_state()
                            self.editor.draw_highlight_stroke(valid_img_points, self.editor.highlight_color, self.editor.current_highlight_thickness)
                            # self.editor.update_canvas() # 아래쪽 공통 update에서 처리
                        else: print("Highlight stroke too short or invalid.")
                    else: print("Highlight stroke too short.")
                    # 오버레이 클리어
                    if self.editor.highlight_overlay_image:
                        self.editor.highlight_overlay_image.fill(Qt.transparent)
            elif tool == 'pen':
                # 펜은 Move에서 이미 그리므로 Release에서는 작업 없음
                print("[MouseRelease] Pen drawing finished.")
            else:
                # 기존 도형/모자이크 로직
                start_widget = self.editor.selection_start_point
                end_widget = event.pos() 
    
                if start_widget and end_widget:
                    print(f"[MouseRelease] Tool: {tool}, Start: {start_widget}, End: {end_widget}") # 디버그 출력
                    img_start = self.map_widget_to_image(start_widget)
                    img_end = self.map_widget_to_image(end_widget)
                    print(f"[MouseRelease] Mapped Coords: Start: {img_start}, End: {img_end}") # 디버그 출력
    
                    if img_start and img_end:
                        if tool == 'mosaic':
                            selection_rect_widget = QRect(start_widget, end_widget).normalized()
                            img_rect = QRect(img_start, img_end).normalized()
                            if img_rect.width() > 0 and img_rect.height() > 0:
                                print("[MouseRelease] Applying mosaic...") # 디버그 출력
                                self.editor.push_undo_state() 
                                self.editor.apply_mosaic(img_rect, self.editor.mosaic_level)
                                self.editor.update_canvas()
                            else:
                                print("Mosaic selection too small.")
                        elif tool == 'arrow':
                            if img_start != img_end:
                                 print(f"[MouseRelease] Calling draw_arrow: {img_start} -> {img_end}, Color: {self.editor.arrow_color.name()}, Thickness: {self.editor.current_arrow_thickness}") # 두께 정보 추가
                                 self.editor.push_undo_state()
                                 # draw_arrow 호출 시 현재 저장된 두께 사용
                                 self.editor.draw_arrow(img_start, img_end, self.editor.arrow_color, self.editor.current_arrow_thickness) 
                                 self.editor.update_canvas()
                            else:
                                 print("Arrow start and end points are the same.")
                        elif tool == 'circle': # 원 그리기 로직 추가
                            img_rect = QRect(img_start, img_end).normalized()
                            if img_rect.width() > 0 and img_rect.height() > 0:
                                print(f"[MouseRelease] Calling draw_circle: Rect: {img_rect}, Color: {self.editor.circle_color.name()}, Thickness: {self.editor.current_circle_thickness}")
                                self.editor.push_undo_state()
                                self.editor.draw_circle(img_rect, self.editor.circle_color, self.editor.current_circle_thickness)
                                self.editor.update_canvas()
                            else:
                                print("Circle selection too small.")
                        elif tool == 'rectangle': # 사각형 그리기 로직 추가
                            img_rect = QRect(img_start, img_end).normalized()
                            if img_rect.width() > 0 and img_rect.height() > 0:
                                print(f"[MouseRelease] Calling draw_rectangle: Rect: {img_rect}, Color: {self.editor.rectangle_color.name()}, Thickness: {self.editor.current_rectangle_thickness}")
                                self.editor.push_undo_state()
                                self.editor.draw_rectangle(img_rect, self.editor.rectangle_color, self.editor.current_rectangle_thickness)
                                self.editor.update_canvas()
                            else:
                                print("Rectangle selection too small.")

            # 공통 상태 초기화 및 커서 복원
            print("[MouseRelease] Resetting state and cursor.")
            self.editor.selection_start_point = None
            self.editor.selection_end_point = None
            if hasattr(self.editor, 'stroke_points'): self.editor.stroke_points = []
            self.last_draw_point = None        # 펜/하이라이트용 변수 초기화
            self.last_img_draw_point = None    # 펜/하이라이트용 변수 초기화
            if tool in ['arrow', 'mosaic', 'circle', 'rectangle', 'highlight', 'pen']: 
                 self.setCursor(Qt.ArrowCursor) 
            self.editor.update_undo_redo_actions()
            self.update() # 최종 상태 반영 (오버레이 제거 등)

        super().mouseReleaseEvent(event)

    def create_text_input(self, position):
        """지정된 위치에 QLineEdit 생성 및 표시"""
        if self.text_input is None:
            self.text_input = QLineEdit(self)
            self.text_input.returnPressed.connect(self.finish_text_input) # Enter 키 연결
            # 포커스 아웃 시에도 입력 완료 처리 (선택적)
            # self.text_input.editingFinished.connect(self.finish_text_input) 

        # 이전 입력 내용 클리어
        self.text_input.clear()

        # 폰트 설정 (에디터에서 가져옴)
        font = QFont()
        font.setPixelSize(self.editor.text_font_size) # 픽셀 크기로 설정
        self.text_input.setFont(font)
        print(f"[DEBUG] Setting QLineEdit font size to {self.editor.text_font_size} pixels.") # 로그 추가

        # 스타일 설정 (색상, 배경 등)
        text_color = self.editor.text_color.name()
        # 배경을 투명하게 설정하고 테두리 색상을 텍스트 색상과 동일하게 설정
        self.text_input.setStyleSheet(f"""
            QLineEdit {{
                color: {text_color};
                background-color: transparent; /* 배경 투명 */
                border: 1px solid {text_color}; /* 테두리 색상 변경 */
                padding: 2px;
            }}
        """)

        # 크기 자동 조절 및 위치 설정
        self.text_input.adjustSize() # 내용에 맞게 크기 조절 시도
        # 클릭 위치를 입력 상자의 좌상단 기준으로 설정
        input_pos = position 
        # 캔버스 경계 밖으로 나가지 않도록 조정
        input_pos.setX(max(0, min(input_pos.x(), self.width() - self.text_input.width())))
        input_pos.setY(max(0, min(input_pos.y(), self.height() - self.text_input.height())))
        self.text_input.move(input_pos)

        self.text_input.show()
        self.text_input.setFocus()
        print(f"[Canvas] Text input created at {input_pos} with font size {self.editor.text_font_size}")

    def finish_text_input(self):
        """텍스트 입력 완료 처리"""
        print("[DEBUG] finish_text_input called")
        if self.text_input and self.text_input.isVisible():
            try:
                text = self.text_input.text()
                position = self.text_input.pos() # 위젯 좌표
                print(f"[DEBUG] Text input finished. Raw Text: '{text}', Widget Position: {position}")
                
                self.text_input.hide()
                print("[DEBUG] Text input hidden.")

                if text:
                    print("[DEBUG] Text is not empty. Proceeding to draw.")
                    # 위젯 좌표를 이미지 좌표로 변환
                    # 텍스트 박스의 좌상단 좌표를 사용
                    print(f"[DEBUG] Calling map_widget_to_image with position: {position}")
                    img_position = self.map_widget_to_image(position)
                    print(f"[DEBUG] map_widget_to_image returned: {img_position}")
                    
                    if img_position:
                        print(f"[Canvas] Finishing text input. Text: '{text}', Image Pos: {img_position}")
                        
                        # 위젯 폰트 크기를 이미지 픽셀 크기로 변환
                        widget_font_size = self.editor.text_font_size
                        print(f"[DEBUG] Widget font size: {widget_font_size}")
                        # 같은 X 좌표에서 Y만 폰트 크기만큼 떨어진 점을 매핑
                        p1_widget = position
                        p2_widget = QPoint(position.x(), position.y() + widget_font_size)
                        p1_image = img_position # 이미 계산된 값 사용
                        print(f"[DEBUG] Mapping widget point p2: {p2_widget}")
                        p2_image = self.map_widget_to_image(p2_widget)
                        print(f"[DEBUG] Mapped image point p2: {p2_image}")
                        
                        image_font_size = widget_font_size # 기본값
                        if p1_image and p2_image:
                            delta_y = abs(p2_image.y() - p1_image.y())
                            if delta_y > 0: # 유효한 높이 차이
                                image_font_size = delta_y
                        print(f"[DEBUG] Calculated image font size: {image_font_size}")
                        
                        print("[DEBUG] Calling push_undo_state")
                        self.editor.push_undo_state() # Undo 상태 저장
                        print("[DEBUG] push_undo_state finished")
                        
                        # 이미지에 텍스트 그리기 호출 (계산된 이미지 폰트 크기 전달)
                        print(f"[DEBUG] Calling draw_text with img_position={img_position}, text='{text}', color={self.editor.text_color.name()}, size={image_font_size}")
                        self.editor.draw_text(img_position, text, self.editor.text_color, image_font_size)
                        print("[DEBUG] draw_text finished")
                        
                        print("[DEBUG] Calling update_canvas")
                        self.editor.update_canvas()
                        print("[DEBUG] update_canvas finished")
                    else:
                        print("[Canvas] Failed to map widget position to image position.")
                else:
                    print("[Canvas] Text input cancelled (empty text).")

                # 도구 및 커서 초기화
                print("[DEBUG] Resetting current tool and cursor.")
                self.editor.current_tool = None
                self.setCursor(Qt.ArrowCursor)
                print("[DEBUG] Updating undo/redo actions.")
                self.editor.update_undo_redo_actions()
                print("[DEBUG] finish_text_input completed successfully.")

            except Exception as e:
                print(f"[ERROR] Exception occurred in finish_text_input: {e}")
                import traceback
                traceback.print_exc() # 콘솔에 상세 스택 트레이스 출력
                # 에러 발생 시에도 커서 등은 초기화 시도
                try:
                    self.text_input.hide()
                    self.editor.current_tool = None
                    self.setCursor(Qt.ArrowCursor)
                except Exception as inner_e:
                    print(f"[ERROR] Exception during error handling in finish_text_input: {inner_e}")
        else:
            print("[DEBUG] finish_text_input called but text_input is None or not visible.")

class ImageEditor(QMainWindow):
    """이미지 편집 기능을 제공하는 창"""
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
        self.toolbar = QToolBar("Main Toolbar")
        self.toolbar.setIconSize(QSize(24, 24))
        self.toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        # Set font size for toolbar buttons
        self.toolbar.setStyleSheet("QToolButton { font-size: 8pt; }")
        self.addToolBar(self.toolbar)
        
        # 저장 버튼
        save_action = QAction(QIcon("assets/save_icon.svg"), "Save", self)
        save_action.setToolTip("Save image")
        self.toolbar.addAction(save_action)
        
        copy_action = QAction(QIcon("assets/copy_icon.svg"), "Copy", self)
        copy_action.setToolTip("Copy to clipboard")
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
        # reset_action.triggered.connect(self.reset_image) # 예시 연결
        self.toolbar.addAction(reset_action)
        
        self.toolbar.addSeparator()
        
        # 이미지 회전 버튼
        rotate_action = QAction(QIcon("assets/rotate_icon.svg"), "Rotate", self)
        rotate_action.setToolTip("Rotate image")
        self.toolbar.addAction(rotate_action)
        
        # 좌우 반전 버튼
        flip_h_action = QAction(QIcon("assets/flip_h_icon.svg"), "Flip H", self)
        flip_h_action.setToolTip("Flip horizontally")
        self.toolbar.addAction(flip_h_action)
        
        # 상하 반전 버튼
        flip_v_action = QAction(QIcon("assets/flip_v_icon.svg"), "Flip V", self)
        flip_v_action.setToolTip("Flip vertically")
        self.toolbar.addAction(flip_v_action)

        self.toolbar.addSeparator()

        # 그리기 도구 버튼들
        
        # 도구 선택 버튼
        select_action = QAction(QIcon("assets/select_icon.svg"), "Select", self)
        select_action.setToolTip("Select area")
        self.toolbar.addAction(select_action)
        
        # 자르기 버튼
        crop_action = QAction(QIcon("assets/crop_icon.svg"), "Crop", self)
        crop_action.setToolTip("Crop image")
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

# 테스트 코드 (독립 실행용)
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    test_image = None
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        test_image = sys.argv[1]
        
    editor = ImageEditor(test_image)
    editor.show()
    
    sys.exit(app.exec_()) 