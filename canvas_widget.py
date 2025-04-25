import sys
import os
import math
import traceback
from PyQt5.QtWidgets import QWidget, QLineEdit
from PyQt5.QtGui import (QPixmap, QImage, QIcon, QPainter, QPen, QColor, 
                         QPolygonF, QBrush, QFont, QFontMetrics, QCursor, QPainterPath)
from PyQt5.QtCore import Qt, QSize, QRect, QPoint, QRectF, QSizeF, QLineF, QPointF

class ImageCanvas(QWidget):
    """이미지를 직접 그리는 캔버스 위젯"""
    # 핸들 크기 및 상태 상수 정의
    HANDLE_SIZE = 8
    HANDLE_HALF = HANDLE_SIZE // 2
    NO_HANDLE, TOP_LEFT, TOP_MIDDLE, TOP_RIGHT, MIDDLE_LEFT, MIDDLE_RIGHT, BOTTOM_LEFT, BOTTOM_MIDDLE, BOTTOM_RIGHT, MOVE_RECT = range(10)

    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self.editor = editor # ImageEditor 인스턴스 참조
        self.image = None
        self.text_input = None # 텍스트 입력 위젯 참조 추가
        self.dragging_handle = self.NO_HANDLE # 현재 드래그 중인 핸들 상태
        self.drag_start_pos = None # 드래그 시작 마우스 위치
        self.drag_start_rect = None # 드래그 시작 시 사각형 위치/크기
        
        # 배경 설정
        self.setStyleSheet("background-color: #282828;")
        self.setMouseTracking(True) # 마우스 이동 이벤트 추적 활성화 (커서 변경 위해)
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
            # 위젯 좌표가 이미지 표시 영역 밖에 있으면 경계값으로 조정
            adjusted_x = max(target_rect.left(), min(widget_point.x(), target_rect.right()))
            adjusted_y = max(target_rect.top(), min(widget_point.y(), target_rect.bottom()))
            widget_point = QPoint(int(adjusted_x), int(adjusted_y))

        relative_x = widget_point.x() - target_rect.left()
        relative_y = widget_point.y() - target_rect.top()

        # 0으로 나누기 방지 및 유효성 검사
        if img_size.width() <= 0 or img_size.height() <= 0 or scaled_size.width() <= 0 or scaled_size.height() <= 0:
             return None

        scale_x = scaled_size.width() / img_size.width()
        scale_y = scaled_size.height() / img_size.height()

        if scale_x == 0 or scale_y == 0: return None 

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
        # QRect 생성 시 정수 좌표 사용
        target_rect = QRect(int(x), int(y), scaled_size.width(), scaled_size.height())
        
        painter.drawImage(target_rect, self.image)

        # 자르기 영역 오버레이 그리기
        if self.editor.current_tool == 'crop' and self.editor.crop_rect_widget:
            self.draw_crop_overlay(painter, target_rect)

        # 하이라이트 오버레이 그리기 (오버레이 이미지가 있으면)
        if self.editor.highlight_overlay_image and not self.editor.highlight_overlay_image.isNull():
            painter.drawImage(target_rect, self.editor.highlight_overlay_image)

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
                
                if img_size.width() > 0 and img_size.height() > 0 and scaled_size.width() > 0: 
                    scale_x = scaled_size.width() / img_size.width()
                else:
                    scale_x = 1.0
                
                preview_thickness = max(1, round(thickness_img_px * scale_x)) 

                pen = QPen(self.editor.arrow_color, preview_thickness) 
                painter.setPen(pen)
                painter.setBrush(QBrush(self.editor.arrow_color)) 
                line = QLineF(start_pt, end_pt)
                painter.drawLine(line)
                
                arrow_size_img_px = 3.0 * thickness_img_px + 4 
                arrow_size_widget_px = arrow_size_img_px * scale_x 
                
                angle = math.atan2(-line.dy(), line.dx())
                arrow_p1 = line.p2() - QPointF(math.cos(angle + math.pi / 6) * arrow_size_widget_px,
                                              -math.sin(angle + math.pi / 6) * arrow_size_widget_px)
                arrow_p2 = line.p2() - QPointF(math.cos(angle - math.pi / 6) * arrow_size_widget_px,
                                              -math.sin(angle - math.pi / 6) * arrow_size_widget_px)
                arrow_head = QPolygonF([line.p2(), arrow_p1, arrow_p2])
                painter.drawPolygon(arrow_head)
            elif self.editor.current_tool == 'circle':
                thickness_img_px = self.editor.current_circle_thickness
                if img_size.width() > 0 and img_size.height() > 0 and scaled_size.width() > 0:
                    scale_x = scaled_size.width() / img_size.width()
                else:
                    scale_x = 1.0
                preview_thickness = max(1, round(thickness_img_px * scale_x))
                
                pen = QPen(self.editor.circle_color, preview_thickness, Qt.SolidLine)
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush) 
                preview_rect_widget = QRect(start_pt, end_pt).normalized()
                painter.drawEllipse(preview_rect_widget)
            elif self.editor.current_tool == 'rectangle': 
                thickness_img_px = self.editor.current_rectangle_thickness
                if img_size.width() > 0 and img_size.height() > 0 and scaled_size.width() > 0:
                    scale_x = scaled_size.width() / img_size.width()
                else:
                    scale_x = 1.0
                preview_thickness = max(1, round(thickness_img_px * scale_x))
                
                pen = QPen(self.editor.rectangle_color, preview_thickness, Qt.SolidLine)
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush) 
                preview_rect_widget = QRect(start_pt, end_pt).normalized()
                painter.drawRect(preview_rect_widget)

    def mousePressEvent(self, event):
        print("[Canvas] mousePressEvent received")
        tool = self.editor.current_tool
        
        # 자르기 도구 핸들링
        if tool == 'crop' and event.button() == Qt.LeftButton:
            handle = self.get_handle_at(event.pos())
            if handle != self.NO_HANDLE:
                self.dragging_handle = handle
                self.drag_start_pos = event.pos()
                self.drag_start_rect = QRect(self.editor.crop_rect_widget) # 값 복사 
                print(f"[Crop] Started dragging handle: {self.dragging_handle} from {self.drag_start_pos} with rect {self.drag_start_rect}")
                event.accept() 
                return 
            else:
                print("[Crop] Clicked outside handles.")

        # 텍스트 도구 처리
        elif tool == 'text' and event.button() == Qt.LeftButton and self.editor.is_adding_text:
            print(f"[DEBUG] mousePressEvent: Text tool active (is_adding_text={self.editor.is_adding_text})")
            try:
                self.create_text_input(event.pos())
                self.editor.is_adding_text = False 
                print("[DEBUG] mousePressEvent: Text input created and is_adding_text set to False.")
                event.accept()
                return
            except Exception as e:
                print(f"[ERROR] Exception during text input creation in mousePressEvent: {e}")
                traceback.print_exc()
                try:
                    self.editor.reset_tool_state() 
                except AttributeError:
                    self.editor.current_tool = None
                    self.editor.is_adding_text = False
                    self.setCursor(Qt.ArrowCursor)
                event.accept()
                return
            
        # 기존 도형/펜 그리기 처리
        elif tool in ['mosaic', 'arrow', 'circle', 'rectangle', 'highlight', 'pen'] and event.button() == Qt.LeftButton:
             print(f"[Canvas] Activating selection/drawing for tool: {tool}")
             self.editor.is_selecting = True
             if tool == 'highlight':
                 if self.editor.highlight_overlay_image:
                     self.editor.highlight_overlay_image.fill(Qt.transparent)
                 self.editor.stroke_points = [event.pos()]
             elif tool == 'pen':
                 self.editor.push_undo_state()
                 self.last_draw_point = event.pos()
                 self.last_img_draw_point = self.map_widget_to_image(self.last_draw_point)
                 if self.last_img_draw_point:
                      self.editor.draw_pen_segment(self.last_img_draw_point, self.last_img_draw_point, self.editor.pen_color, self.editor.current_pen_thickness)
                      self.update()
             else:
                 self.editor.selection_start_point = event.pos()
                 self.editor.selection_end_point = event.pos()
             print(f"[Canvas] State after press: is_selecting={self.editor.is_selecting}, tool={self.editor.current_tool}")
             event.accept()
             return

        super().mousePressEvent(event) 

    def mouseMoveEvent(self, event):
        pos = event.pos()
        
        # 자르기 핸들 드래그 처리
        if self.editor.current_tool == 'crop' and self.dragging_handle != self.NO_HANDLE:
            if not self.drag_start_pos or not self.drag_start_rect:
                 print("[WARN] Dragging crop handle without start info.")
                 self.dragging_handle = self.NO_HANDLE 
                 return
                 
            delta = pos - self.drag_start_pos
            new_rect = QRect(self.drag_start_rect) 
            min_size = 10 

            # 핸들 유형에 따라 사각형 조절
            if self.dragging_handle == self.MOVE_RECT:
                new_rect.translate(delta)
            elif self.dragging_handle == self.TOP_LEFT:
                new_rect.setTopLeft(self.drag_start_rect.topLeft() + delta)
            elif self.dragging_handle == self.TOP_MIDDLE:
                new_rect.setTop(self.drag_start_rect.top() + delta.y())
            elif self.dragging_handle == self.TOP_RIGHT:
                new_rect.setTopRight(self.drag_start_rect.topRight() + delta)
            elif self.dragging_handle == self.MIDDLE_LEFT:
                new_rect.setLeft(self.drag_start_rect.left() + delta.x())
            elif self.dragging_handle == self.MIDDLE_RIGHT:
                new_rect.setRight(self.drag_start_rect.right() + delta.x())
            elif self.dragging_handle == self.BOTTOM_LEFT:
                new_rect.setBottomLeft(self.drag_start_rect.bottomLeft() + delta)
            elif self.dragging_handle == self.BOTTOM_MIDDLE:
                new_rect.setBottom(self.drag_start_rect.bottom() + delta.y())
            elif self.dragging_handle == self.BOTTOM_RIGHT:
                new_rect.setBottomRight(self.drag_start_rect.bottomRight() + delta)

            valid_rect = new_rect.normalized()
            if valid_rect.width() < min_size:
                if self.dragging_handle in [self.TOP_LEFT, self.MIDDLE_LEFT, self.BOTTOM_LEFT]:
                    valid_rect.setLeft(valid_rect.right() - min_size)
                else:
                    valid_rect.setRight(valid_rect.left() + min_size)
            if valid_rect.height() < min_size:
                if self.dragging_handle in [self.TOP_LEFT, self.TOP_MIDDLE, self.TOP_RIGHT]:
                    valid_rect.setTop(valid_rect.bottom() - min_size)
                else:
                    valid_rect.setBottom(valid_rect.top() + min_size)
            
            # 캔버스 경계 내에 있도록 제한 (조금 더 복잡하게 구현 필요)
            # widget_bounds = self.rect().adjusted(1,1,-1,-1) # 안쪽 1px 여유
            # valid_rect.moveTo(max(widget_bounds.left(), valid_rect.left()), max(widget_bounds.top(), valid_rect.top()))
            # if valid_rect.right() > widget_bounds.right(): valid_rect.setRight(widget_bounds.right())
            # if valid_rect.bottom() > widget_bounds.bottom(): valid_rect.setBottom(widget_bounds.bottom())

            self.editor.crop_rect_widget = valid_rect
            self.update_cursor(pos) 
            self.update() 
            event.accept()
            return
        elif self.editor.current_tool == 'crop':
            self.update_cursor(pos)
            
        elif self.editor.is_selecting and self.editor.current_tool in ['mosaic', 'arrow', 'circle', 'rectangle', 'highlight', 'pen']:
             if self.editor.current_tool == 'highlight':
                 self.editor.stroke_points.append(event.pos())
                 if self.editor.highlight_overlay_image and len(self.editor.stroke_points) > 1:
                     self.editor.highlight_overlay_image.fill(Qt.transparent)
                     painter = QPainter(self.editor.highlight_overlay_image)
                     img_points = [self.map_widget_to_image(p) for p in self.editor.stroke_points if p is not None]
                     valid_img_points = [p for p in img_points if p is not None]
                     if len(valid_img_points) > 1:
                         pen = QPen(self.editor.highlight_color, self.editor.current_highlight_thickness, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                         painter.setPen(pen)
                         painter.setRenderHint(QPainter.Antialiasing)
                         polygon = QPolygonF([QPointF(p) for p in valid_img_points])
                         painter.drawPolyline(polygon)
                     painter.end()
                 self.update()
             elif self.editor.current_tool == 'pen':
                 current_pos = event.pos()
                 img_current = self.map_widget_to_image(current_pos)
                 if self.last_img_draw_point and img_current:
                     self.editor.draw_pen_segment(self.last_img_draw_point, img_current, self.editor.pen_color, self.editor.current_pen_thickness)
                 self.last_draw_point = current_pos
                 self.last_img_draw_point = img_current
                 self.update()
             else:
                 self.editor.selection_end_point = event.pos()
                 self.update()
             event.accept()
             return

        super().mouseMoveEvent(event) 

    def mouseReleaseEvent(self, event):
        print("[Canvas] mouseReleaseEvent received")
        
        if self.editor.current_tool == 'crop' and self.dragging_handle != self.NO_HANDLE:
            print(f"[Crop] Finished dragging handle: {self.dragging_handle}. Final rect: {self.editor.crop_rect_widget}")
            self.dragging_handle = self.NO_HANDLE
            self.drag_start_pos = None
            self.drag_start_rect = None
            self.update_cursor(event.pos()) 
            event.accept()
            return
            
        elif self.editor.current_tool == 'text' and self.text_input and self.text_input.isVisible():
             print("[Canvas] Mouse release ignored during text input.")
             super().mouseReleaseEvent(event) # 부모 이벤트 호출은 유지
             return # 여기서 종료

        elif self.editor.is_selecting and event.button() == Qt.LeftButton and self.editor.current_tool in ['mosaic', 'arrow', 'circle', 'rectangle', 'highlight', 'pen']:
             tool = self.editor.current_tool
             self.editor.is_selecting = False
             if tool == 'highlight':
                 if hasattr(self.editor, 'stroke_points'):
                     self.editor.stroke_points.append(event.pos())
                     if len(self.editor.stroke_points) > 1:
                         img_points = [self.map_widget_to_image(p) for p in self.editor.stroke_points if p is not None]
                         valid_img_points = [p for p in img_points if p is not None]
                         if len(valid_img_points) > 1:
                             print(f"[MouseRelease] Calling draw_highlight_stroke on edited_image")
                             self.editor.push_undo_state()
                             self.editor.draw_highlight_stroke(valid_img_points, self.editor.highlight_color, self.editor.current_highlight_thickness)
                         else: print("Highlight stroke too short or invalid.")
                     else: print("Highlight stroke too short.")
                     if self.editor.highlight_overlay_image:
                         self.editor.highlight_overlay_image.fill(Qt.transparent)
             elif tool == 'pen':
                 print("[MouseRelease] Pen drawing finished.")
             else:
                 start_widget = self.editor.selection_start_point
                 end_widget = event.pos()
                 if start_widget and end_widget:
                     print(f"[MouseRelease] Tool: {tool}, Start: {start_widget}, End: {end_widget}")
                     img_start = self.map_widget_to_image(start_widget)
                     img_end = self.map_widget_to_image(end_widget)
                     print(f"[MouseRelease] Mapped Coords: Start: {img_start}, End: {img_end}")
                     if img_start and img_end:
                         if tool == 'mosaic':
                             selection_rect_widget = QRect(start_widget, end_widget).normalized()
                             img_rect = QRect(img_start, img_end).normalized()
                             if img_rect.width() > 0 and img_rect.height() > 0:
                                 print("[MouseRelease] Applying mosaic...")
                                 self.editor.push_undo_state()
                                 self.editor.apply_mosaic(img_rect, self.editor.mosaic_level)
                                 self.editor.update_canvas()
                             else:
                                 print("Mosaic selection too small.")
                         elif tool == 'arrow':
                             if img_start != img_end:
                                  print(f"[MouseRelease] Calling draw_arrow: {img_start} -> {img_end}, Color: {self.editor.arrow_color.name()}, Thickness: {self.editor.current_arrow_thickness}")
                                  self.editor.push_undo_state()
                                  self.editor.draw_arrow(img_start, img_end, self.editor.arrow_color, self.editor.current_arrow_thickness)
                                  self.editor.update_canvas()
                             else:
                                  print("Arrow start and end points are the same.")
                         elif tool == 'circle':
                             img_rect = QRect(img_start, img_end).normalized()
                             if img_rect.width() > 0 and img_rect.height() > 0:
                                 print(f"[MouseRelease] Calling draw_circle: Rect: {img_rect}, Color: {self.editor.circle_color.name()}, Thickness: {self.editor.current_circle_thickness}")
                                 self.editor.push_undo_state()
                                 self.editor.draw_circle(img_rect, self.editor.circle_color, self.editor.current_circle_thickness)
                                 self.editor.update_canvas()
                             else:
                                 print("Circle selection too small.")
                         elif tool == 'rectangle': 
                             img_rect = QRect(img_start, img_end).normalized()
                             if img_rect.width() > 0 and img_rect.height() > 0:
                                 print(f"[MouseRelease] Calling draw_rectangle: Rect: {img_rect}, Color: {self.editor.rectangle_color.name()}, Thickness: {self.editor.current_rectangle_thickness}")
                                 self.editor.push_undo_state()
                                 self.editor.draw_rectangle(img_rect, self.editor.rectangle_color, self.editor.current_rectangle_thickness)
                                 self.editor.update_canvas()
                             else:
                                 print("Rectangle selection too small.")
             print("[MouseRelease] Resetting state and cursor.")
             self.editor.selection_start_point = None
             self.editor.selection_end_point = None
             if hasattr(self.editor, 'stroke_points'): self.editor.stroke_points = []
             self.last_draw_point = None       
             self.last_img_draw_point = None   
             if tool in ['arrow', 'mosaic', 'circle', 'rectangle', 'highlight', 'pen']: 
                  self.setCursor(Qt.ArrowCursor) 
             self.editor.update_undo_redo_actions()
             self.update()
             event.accept()
             return

        super().mouseReleaseEvent(event) 
        
    def update_cursor(self, pos):
        """마우스 위치에 따라 커서 모양 업데이트 (자르기 모드)"""
        if self.editor.current_tool != 'crop':
             # 핸들 드래그 중이 아닐 때만 기본 커서로 변경
             if self.dragging_handle == self.NO_HANDLE: 
                 self.setCursor(Qt.ArrowCursor) 
             return

        handle = self.get_handle_at(pos)
        
        if handle == self.TOP_LEFT or handle == self.BOTTOM_RIGHT:
            self.setCursor(Qt.SizeFDiagCursor)
        elif handle == self.TOP_RIGHT or handle == self.BOTTOM_LEFT:
            self.setCursor(Qt.SizeBDiagCursor)
        elif handle == self.TOP_MIDDLE or handle == self.BOTTOM_MIDDLE:
            self.setCursor(Qt.SizeVerCursor)
        elif handle == self.MIDDLE_LEFT or handle == self.MIDDLE_RIGHT:
            self.setCursor(Qt.SizeHorCursor)
        elif handle == self.MOVE_RECT:
            self.setCursor(Qt.SizeAllCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
            
    def create_text_input(self, position):
        """지정된 위치에 QLineEdit 생성 및 표시"""
        if self.text_input is None:
            self.text_input = QLineEdit(self)
            self.text_input.returnPressed.connect(self.finish_text_input) 

        self.text_input.clear()

        font = QFont()
        font.setPixelSize(self.editor.text_font_size) 
        self.text_input.setFont(font)
        print(f"[DEBUG] Setting QLineEdit font size to {self.editor.text_font_size} pixels.") 

        text_color = self.editor.text_color.name()
        self.text_input.setStyleSheet(f"""
            QLineEdit {{
                color: {text_color};
                background-color: transparent; 
                border: 1px solid {text_color}; 
                padding: 2px;
            }}
        """)

        self.text_input.adjustSize() 
        input_pos = position 
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
                position = self.text_input.pos() 
                print(f"[DEBUG] Text input finished. Raw Text: '{text}', Widget Position: {position}")
                
                self.text_input.hide()
                print("[DEBUG] Text input hidden.")

                if text:
                    print("[DEBUG] Text is not empty. Proceeding to draw.")
                    print(f"[DEBUG] Calling map_widget_to_image with position: {position}")
                    img_position = self.map_widget_to_image(position)
                    print(f"[DEBUG] map_widget_to_image returned: {img_position}")
                    
                    if img_position:
                        print(f"[Canvas] Finishing text input. Text: '{text}', Image Pos: {img_position}")
                        
                        widget_font_size = self.editor.text_font_size
                        print(f"[DEBUG] Widget font size: {widget_font_size}")
                        p1_widget = position
                        p2_widget = QPoint(position.x(), position.y() + widget_font_size)
                        p1_image = img_position 
                        print(f"[DEBUG] Mapping widget point p2: {p2_widget}")
                        p2_image = self.map_widget_to_image(p2_widget)
                        print(f"[DEBUG] Mapped image point p2: {p2_image}")
                        
                        image_font_size = widget_font_size 
                        if p1_image and p2_image:
                            delta_y = abs(p2_image.y() - p1_image.y())
                            if delta_y > 0: 
                                image_font_size = delta_y
                        print(f"[DEBUG] Calculated image font size: {image_font_size}")
                        
                        print("[DEBUG] Calling push_undo_state")
                        self.editor.push_undo_state() 
                        print("[DEBUG] push_undo_state finished")
                        
                        print(f"[DEBUG] Calling draw_text with img_position={img_position}, text='{text}', color={self.editor.text_color.name()}, size={image_font_size}")
                        self.editor.draw_text(img_position, text, self.editor.text_color, image_font_size) # ImageEditor의 draw_text 호출
                        print("[DEBUG] draw_text finished")
                        
                        print("[DEBUG] Calling update_canvas")
                        self.editor.update_canvas() # ImageEditor의 update_canvas 호출
                        print("[DEBUG] update_canvas finished")
                    else:
                        print("[Canvas] Failed to map widget position to image position.")
                else:
                    print("[Canvas] Text input cancelled (empty text).")

                print("[DEBUG] Resetting current tool and cursor.")
                self.editor.current_tool = None
                self.setCursor(Qt.ArrowCursor)
                print("[DEBUG] Updating undo/redo actions.")
                self.editor.update_undo_redo_actions() # ImageEditor의 메서드 호출
                print("[DEBUG] finish_text_input completed successfully.")

            except Exception as e:
                print(f"[ERROR] Exception occurred in finish_text_input: {e}")
                traceback.print_exc()
                try:
                    self.text_input.hide()
                    self.editor.current_tool = None
                    self.setCursor(Qt.ArrowCursor)
                except Exception as inner_e:
                    print(f"[ERROR] Exception during error handling in finish_text_input: {inner_e}")
        else:
            print("[DEBUG] finish_text_input called but text_input is None or not visible.")

    def get_handle_at(self, pos): 
        """주어진 위치에 어떤 핸들이 있는지 확인"""
        if not self.editor.crop_rect_widget: return self.NO_HANDLE

        r = self.editor.crop_rect_widget
        handles = self.get_handle_rects(r)

        if handles[self.TOP_LEFT].contains(pos): return self.TOP_LEFT
        if handles[self.TOP_MIDDLE].contains(pos): return self.TOP_MIDDLE
        if handles[self.TOP_RIGHT].contains(pos): return self.TOP_RIGHT
        if handles[self.MIDDLE_LEFT].contains(pos): return self.MIDDLE_LEFT
        if handles[self.MIDDLE_RIGHT].contains(pos): return self.MIDDLE_RIGHT
        if handles[self.BOTTOM_LEFT].contains(pos): return self.BOTTOM_LEFT
        if handles[self.BOTTOM_MIDDLE].contains(pos): return self.BOTTOM_MIDDLE
        if handles[self.BOTTOM_RIGHT].contains(pos): return self.BOTTOM_RIGHT
        if r.contains(pos): return self.MOVE_RECT 
        
        return self.NO_HANDLE

    def get_handle_rects(self, rect):
        """주어진 사각형의 핸들 위치(QRect) 리스트 반환"""
        x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
        cx = x + w // 2
        cy = y + h // 2
        
        return {
            self.TOP_LEFT: QRect(x - self.HANDLE_HALF, y - self.HANDLE_HALF, self.HANDLE_SIZE, self.HANDLE_SIZE),
            self.TOP_MIDDLE: QRect(cx - self.HANDLE_HALF, y - self.HANDLE_HALF, self.HANDLE_SIZE, self.HANDLE_SIZE),
            self.TOP_RIGHT: QRect(x + w - self.HANDLE_HALF, y - self.HANDLE_HALF, self.HANDLE_SIZE, self.HANDLE_SIZE),
            self.MIDDLE_LEFT: QRect(x - self.HANDLE_HALF, cy - self.HANDLE_HALF, self.HANDLE_SIZE, self.HANDLE_SIZE),
            self.MIDDLE_RIGHT: QRect(x + w - self.HANDLE_HALF, cy - self.HANDLE_HALF, self.HANDLE_SIZE, self.HANDLE_SIZE),
            self.BOTTOM_LEFT: QRect(x - self.HANDLE_HALF, y + h - self.HANDLE_HALF, self.HANDLE_SIZE, self.HANDLE_SIZE),
            self.BOTTOM_MIDDLE: QRect(cx - self.HANDLE_HALF, y + h - self.HANDLE_HALF, self.HANDLE_SIZE, self.HANDLE_SIZE),
            self.BOTTOM_RIGHT: QRect(x + w - self.HANDLE_HALF, y + h - self.HANDLE_HALF, self.HANDLE_SIZE, self.HANDLE_SIZE)
        }

    def draw_crop_overlay(self, painter, image_display_rect):
        """자르기 영역 오버레이 (반투명 배경, 선택 영역, 핸들) 그리기"""
        try:
            crop_rect = self.editor.crop_rect_widget
            if not crop_rect: return 

            painter.save()
            path = QPainterPath()
            path.addRect(QRectF(self.rect())) 
            path.addRect(QRectF(crop_rect)) 
            painter.setBrush(QColor(0, 0, 0, 128)) 
            painter.setPen(Qt.NoPen)
            painter.drawPath(path)
            painter.restore()

            painter.setPen(QPen(Qt.white, 1, Qt.DashLine)) 
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(crop_rect)

            painter.setPen(Qt.white)
            painter.setBrush(Qt.white)
            for handle_rect in self.get_handle_rects(crop_rect).values():
                painter.drawEllipse(handle_rect)
        except Exception as e:
            print(f"[ERROR] Exception in draw_crop_overlay: {e}")
            traceback.print_exc()
# End of ImageCanvas class definition (originally line 657) 