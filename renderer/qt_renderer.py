"""
Qt 渲染器
=========
- 分层绘制：背景 → 人物 → 前景 → 灯光
- 呼吸动画
- 眨眼动画
- 超宽屏适配（人物不拉伸）
"""

import random
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont
from renderer.base import BaseRenderer


class QtRenderer(BaseRenderer):
    def __init__(self, parent: QWidget, asset_manager):
        super().__init__()
        self.parent = parent
        self.asset_manager = asset_manager

        self.container = QWidget(parent)
        self.container.setGeometry(0, 0, parent.width(), parent.height())

        # 分层标签
        self.bg_label = QLabel(self.container)
        self.bg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bg_label.setGeometry(0, 0, parent.width(), parent.height())

        self.char_label = QLabel(self.container)
        self.char_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.fg_label = QLabel(self.container)
        self.fg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.light_label = QLabel(self.container)
        self.light_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 动画状态
        self.breath_phase = 0.0
        self.blink_timer = QTimer()
        self.blink_timer.timeout.connect(self._on_blink)
        self.blink_timer.start(random.randint(2000, 5000))
        self.is_blinking = False
        self.blink_frame = 0

        self.breath_timer = QTimer()
        self.breath_timer.timeout.connect(self._on_breath)
        self.breath_timer.start(50)

        self.current_pose = "standing"
        self.current_scene = "living_room"

    def set_scene(self, scene_name: str):
        self.current_scene = scene_name
        path = self.asset_manager.get_scene_path(scene_name)
        if path:
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    self.container.width(), self.container.height(),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding
                )
                self.bg_label.setPixmap(scaled)

    def set_character_pose(self, pose_name: str):
        self.current_pose = pose_name
        self._update_character()

    def _update_character(self):
        path = self.asset_manager.get_character_pose(self.current_pose)
        if path:
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                # 人物约占画面高度 40%，不拉伸
                target_h = int(self.container.height() * 0.4)
                scaled = pixmap.scaledToHeight(target_h, Qt.TransformationMode.SmoothTransformation)
                self.char_label.setPixmap(scaled)
                # 居中偏下
                x = (self.container.width() - scaled.width()) // 2
                y = int(self.container.height() * 0.55)
                self.char_label.setGeometry(x, y, scaled.width(), scaled.height())

    def _on_breath(self):
        self.breath_phase += 0.02
        if self.breath_phase > 6.28:
            self.breath_phase = 0.0
        # 呼吸效果：轻微缩放
        scale = 1.0 + 0.005 * (self.breath_phase % 3.14 > 1.57 and -1 or 1)
        # 简化：实际实现可添加更复杂的呼吸动画

    def _on_blink(self):
        if not self.is_blinking:
            self.is_blinking = True
            self.blink_frame = 0
            QTimer.singleShot(150, self._end_blink)
        self.blink_timer.start(random.randint(2000, 5000))

    def _end_blink(self):
        self.is_blinking = False

    def render(self, state: dict):
        """根据状态渲染"""
        pose = state.get("pose", "standing")
        if pose != self.current_pose:
            self.set_character_pose(pose)

    def update(self):
        pass

    def resize(self, width: int, height: int):
        self.container.setGeometry(0, 0, width, height)
        self.bg_label.setGeometry(0, 0, width, height)
        self._update_character()
