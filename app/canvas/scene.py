"""
OpenPipeFlow — PipeNetworkScene + PipeNetworkView

The scene owns the canonical collection of canvas items and exposes
signals that the main window listens to. It also drives the animation
timer for animated flow arrows.
"""

from __future__ import annotations
import copy
import time
from PyQt6.QtWidgets import (
    QGraphicsScene, QGraphicsView, QGraphicsItem, QRubberBand,
    QApplication
)
from PyQt6.QtCore import (
    Qt, QRectF, QPointF, QTimer, pyqtSignal, QLineF, QSizeF
)
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QTransform, QWheelEvent,
    QMouseEvent, QKeyEvent, QCursor, QUndoCommand
)

from app.canvas.items.node_item  import NodeItem
from app.canvas.items.pipe_item  import PipeItem
from app.canvas.items.valve_item import ValveItem
from app.canvas.items.pump_item  import PumpItem
from app.utils.constants import (
    GRID_SIZE_PX, MIN_ZOOM, MAX_ZOOM,
    ANIMATION_INTERVAL_MS
)
from app.utils.styles import COLOR
import app.project.id_generator as id_gen


# ---------------------------------------------------------------------------
# Undo command for deletion
# ---------------------------------------------------------------------------

class _DeleteCmd(QUndoCommand):
    """Undoable deletion of nodes and branches."""

    def __init__(self, scene, model, node_snaps, branch_snaps, node_ids, branch_ids):
        super().__init__("Delete")
        self._scene        = scene
        self._model        = model
        self._node_snaps   = node_snaps    # deep-copied NodeData list
        self._branch_snaps = branch_snaps  # deep-copied PipeData/ValveData/PumpData list
        self._node_ids     = node_ids
        self._branch_ids   = branch_ids

    def redo(self):
        self._scene._do_delete(self._node_ids, self._branch_ids)

    def undo(self):
        for nd in self._node_snaps:
            self._scene._restore_node(nd)
        for bd in self._branch_snaps:
            self._scene._restore_branch(bd)
        self._scene.network_changed.emit()


# ---------------------------------------------------------------------------
# Scene
# ---------------------------------------------------------------------------

class PipeNetworkScene(QGraphicsScene):
    """
    Manages all canvas items and coordinates user interaction modes.

    Modes: "select" | "add_junction" | "add_source" | "add_sink"
           | "add_pipe" | "add_valve" | "add_pump"
    """

    # Emitted when something changes (triggers debounced solver)
    network_changed = pyqtSignal()
    # Emitted when an element is selected (carries element_id or "" for none)
    element_selected = pyqtSignal(str)
    # Emitted when an element is double-clicked
    element_double_clicked = pyqtSignal(str)
    # Status bar message
    status_message = pyqtSignal(str)

    # ── Construction ───────────────────────────────────────────────────────

    def __init__(self, model, parent=None):
        super().__init__(parent)
        self._model = model
        self._mode  = "select"
        self._grid  = True
        self._snap  = True

        # State for drawing a pipe / valve / pump
        self._pipe_start_node: NodeItem | None = None
        self._temp_line_end: QPointF = QPointF()

        # Maps element_id → canvas item
        self._item_by_id: dict[str, QGraphicsItem] = {}

        self.setBackgroundBrush(QBrush(QColor(COLOR["canvas_bg"])))

        # Animation timer
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(ANIMATION_INTERVAL_MS)
        self._anim_timer.timeout.connect(self._tick_animation)
        self._last_tick_time = time.monotonic()
        self._anim_timer.start()

        # Undo stack
        from PyQt6.QtGui import QUndoStack
        self.undo_stack = QUndoStack(self)

    # ── Mode control ──────────────────────────────────────────────────────

    @property
    def mode(self) -> str:
        return self._mode

    def set_mode(self, mode: str):
        self._mode = mode
        self._pipe_start_node = None
        self.update()
        cursor_map = {
            "select":       Qt.CursorShape.ArrowCursor,
            "add_junction": Qt.CursorShape.CrossCursor,
            "add_source":   Qt.CursorShape.CrossCursor,
            "add_sink":     Qt.CursorShape.CrossCursor,
            "add_pipe":     Qt.CursorShape.CrossCursor,
            "add_valve":    Qt.CursorShape.CrossCursor,
            "add_pump":     Qt.CursorShape.CrossCursor,
            "add_orifice":  Qt.CursorShape.CrossCursor,
        }
        for view in self.views():
            view.setCursor(QCursor(cursor_map.get(mode, Qt.CursorShape.ArrowCursor)))
        hints = {
            "select":       "Select — click to select, drag to move",
            "add_junction": "Junction — click to place a junction node",
            "add_source":   "Source — click to place a pressure source (fixed-pressure inlet)",
            "add_sink":     "Sink — click to place a pressure sink (fixed-pressure outlet)",
            "add_pipe":     "Pipe — click first node then second node to draw a pipe",
            "add_valve":    "Valve — click once to drop (auto-creates inlet/outlet nodes)",
            "add_pump":     "Pump — click once to drop (auto-creates inlet/outlet nodes)",
            "add_orifice":  "Orifice — click once to drop (auto-creates inlet/outlet nodes)",
        }
        self.status_message.emit(hints.get(mode, mode))

    def toggle_grid(self, show: bool):
        self._grid = show
        self.update()

    def toggle_snap(self, snap: bool):
        self._snap = snap

    # ── Grid drawing ──────────────────────────────────────────────────────

    def drawBackground(self, painter: QPainter, rect: QRectF):
        super().drawBackground(painter, rect)
        if not self._grid:
            return

        grid = GRID_SIZE_PX
        pen = QPen(QColor(COLOR["grid"]))
        pen.setWidth(0)  # cosmetic pen (width 1 regardless of zoom)
        pen.setStyle(Qt.PenStyle.SolidLine)
        painter.setPen(pen)

        left   = int(rect.left())   - (int(rect.left())   % grid)
        top    = int(rect.top())    - (int(rect.top())    % grid)
        right  = int(rect.right())  + grid
        bottom = int(rect.bottom()) + grid

        for x in range(left, right, grid):
            painter.drawLine(x, int(rect.top()), x, int(rect.bottom()))
        for y in range(top, bottom, grid):
            painter.drawLine(int(rect.left()), y, int(rect.right()), y)

    # ── Snap-to-grid ──────────────────────────────────────────────────────

    def _snapped(self, pos: QPointF) -> QPointF:
        if not self._snap:
            return pos
        g = GRID_SIZE_PX
        return QPointF(round(pos.x() / g) * g, round(pos.y() / g) * g)

    # ── Mouse events ──────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        pos = self._snapped(event.scenePos())

        if event.button() == Qt.MouseButton.LeftButton:
            if self._mode == "select":
                super().mousePressEvent(event)
                items = self.selectedItems()
                if items:
                    self.element_selected.emit(
                        getattr(items[0], 'element_id', '')
                    )
                else:
                    self.element_selected.emit("")

            elif self._mode in ("add_junction", "add_source", "add_sink"):
                ntype = self._mode.replace("add_", "")
                # If clicking on an existing node, replace its type in-place
                existing = self._node_at(event.scenePos())
                if existing is not None:
                    self._replace_node_type(existing, ntype)
                else:
                    self._add_node(pos, ntype)

            elif self._mode in ("add_valve", "add_pump", "add_orifice"):
                # Single-click: drop the component at pos with auto inlet/outlet nodes
                branch_type = self._mode.replace("add_", "")
                self._add_component_at(pos, branch_type)

            elif self._mode == "add_pipe":
                # Two-click: first click = start node, second click = end node
                hit = self._node_at(event.scenePos())
                if hit is None:
                    hit = self._add_node(pos, "junction")
                if self._pipe_start_node is None:
                    self._pipe_start_node = hit
                    self.status_message.emit(
                        f"Start: {hit.element_name} — now click the end node"
                    )
                else:
                    if hit != self._pipe_start_node:
                        self._add_branch(self._pipe_start_node, hit, "pipe")
                    self._pipe_start_node = None
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        self._temp_line_end = event.scenePos()
        if self._pipe_start_node is not None:
            self.update()   # redraw rubber-band line
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)

    def drawForeground(self, painter: QPainter, rect: QRectF):
        """Draw rubber-band line while placing a pipe/valve/pump."""
        if self._pipe_start_node is not None and self._temp_line_end is not None:
            pen = QPen(QColor(COLOR["accent"]))
            pen.setWidth(2)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawLine(self._pipe_start_node.scenePos(),
                             self._temp_line_end)

    # ── Adding elements ───────────────────────────────────────────────────

    def _add_component_at(self, pos: QPointF, branch_type: str):
        """
        Drop a branch component (valve/pump/orifice) at pos.
        Auto-creates inlet and outlet junction nodes at ±60 px on either side.
        If an existing node is already near each port, reuse it.
        """
        from app.utils.constants import GRID_SIZE_PX
        offset = GRID_SIZE_PX * 3   # 60 px default (3 grid cells)
        inlet_pos  = self._snapped(QPointF(pos.x() - offset, pos.y()))
        outlet_pos = self._snapped(QPointF(pos.x() + offset, pos.y()))

        # Reuse a nearby node if one exists within snap radius
        # emit_changed=False to suppress intermediate solver triggers;
        # _add_branch will emit network_changed once at the end.
        start_node = self._node_near(inlet_pos, GRID_SIZE_PX)
        if start_node is None:
            start_node = self._add_node(inlet_pos, "junction", emit_changed=False)

        end_node = self._node_near(outlet_pos, GRID_SIZE_PX)
        if end_node is None:
            end_node = self._add_node(outlet_pos, "junction", emit_changed=False)

        self._add_branch(start_node, end_node, branch_type)
        self.status_message.emit(
            f"Placed {branch_type} — connect pipes to the inlet/outlet junction nodes"
        )

    def _add_node(self, pos: QPointF, node_type: str, emit_changed: bool = True):
        from app.project.model import NodeData
        nid  = id_gen.next_id(node_type)
        data = NodeData(id=nid, name=nid, node_type=node_type,
                        x=pos.x(), y=pos.y())
        if node_type == "source":
            data.pressure_bar = 3.0
        elif node_type == "sink":
            data.pressure_bar = 1.0

        self._model.nodes[nid] = data
        item = NodeItem(nid, nid, node_type)
        item.setPos(pos)
        item.double_clicked.connect(self.element_double_clicked)
        item.position_changed.connect(self._on_item_moved)
        self.addItem(item)
        self._item_by_id[nid] = item
        if emit_changed:
            self.network_changed.emit()
        return item

    def _add_branch(self, start_node: NodeItem, end_node: NodeItem,
                    branch_type: str):
        from app.project.model import PipeData, ValveData, PumpData
        bid = id_gen.next_id(branch_type)

        if branch_type == "pipe":
            # Auto-calculate length from pixel distance (1 px = 0.1 m)
            dx = end_node.scenePos().x() - start_node.scenePos().x()
            dy = end_node.scenePos().y() - start_node.scenePos().y()
            import math
            px_dist = math.sqrt(dx*dx + dy*dy)
            length_m = max(px_dist * 0.1, 0.5)

            data = PipeData(id=bid, name=bid, pipe_type="pipe",
                            start_node_id=start_node.element_id,
                            end_node_id=end_node.element_id,
                            length_m=length_m)
            self._model.pipes[bid] = data
            item = PipeItem(bid, bid, start_node, end_node)

        elif branch_type == "valve":
            data = ValveData(id=bid, name=bid,
                             start_node_id=start_node.element_id,
                             end_node_id=end_node.element_id)
            self._model.valves[bid] = data
            item = ValveItem(bid, bid, start_node, end_node)

        elif branch_type == "pump":
            data = PumpData(id=bid, name=bid,
                            start_node_id=start_node.element_id,
                            end_node_id=end_node.element_id)
            self._model.pumps[bid] = data
            item = PumpItem(bid, bid, start_node, end_node)

        elif branch_type == "orifice":
            bid = id_gen.next_id("orifice")
            data = ValveData(id=bid, name=bid,
                             start_node_id=start_node.element_id,
                             end_node_id=end_node.element_id,
                             valve_type="orifice",
                             k_factor=8.0,
                             diameter_m=0.05)
            self._model.valves[bid] = data
            item = ValveItem(bid, bid, start_node, end_node, "orifice")

        else:
            return

        item.double_clicked.connect(self.element_double_clicked)
        self.addItem(item)
        self._item_by_id[bid] = item

        # Register pipe with its nodes for geometry updates
        start_node.add_pipe(item)
        end_node.add_pipe(item)

        self.network_changed.emit()

    # ── Deletion (with undo support) ──────────────────────────────────────

    def delete_selected(self):
        """Delete selected items, pushing an undoable command to the undo stack."""
        selected = list(self.selectedItems())
        node_ids = [getattr(i, 'element_id', None)
                    for i in selected if isinstance(i, NodeItem)]
        branch_ids = [getattr(i, 'element_id', None)
                      for i in selected
                      if isinstance(i, PipeItem) and not isinstance(i, NodeItem)]
        node_ids   = [id_ for id_ in node_ids   if id_]
        branch_ids = [id_ for id_ in branch_ids if id_]

        if not node_ids and not branch_ids:
            return

        # Build deep-copy snapshots BEFORE deleting anything
        node_snaps = []
        branch_snap_ids = set(branch_ids)

        for nid in node_ids:
            nd = self._model.nodes.get(nid)
            if nd:
                node_snaps.append(copy.deepcopy(nd))
                # Also snapshot all branches connected to this node
                node_item = self._item_by_id.get(nid)
                if isinstance(node_item, NodeItem):
                    for pipe_item in node_item.connected_pipes:
                        pid = getattr(pipe_item, 'element_id', None)
                        if pid:
                            branch_snap_ids.add(pid)

        branch_snaps = []
        for bid in branch_snap_ids:
            bd = (self._model.pipes.get(bid)
                  or self._model.valves.get(bid)
                  or self._model.pumps.get(bid))
            if bd:
                branch_snaps.append(copy.deepcopy(bd))

        cmd = _DeleteCmd(self, self._model, node_snaps, branch_snaps,
                         node_ids, list(branch_snap_ids))
        self.undo_stack.push(cmd)   # push calls cmd.redo() immediately

    def _do_delete(self, node_ids, branch_ids):
        """Internal: physically remove nodes and branches from scene + model."""
        for eid in branch_ids:
            if eid in self._item_by_id:
                self._remove_branch_item_by_id(eid)

        for eid in node_ids:
            if eid not in self._item_by_id:
                continue
            node_item = self._item_by_id[eid]
            if isinstance(node_item, NodeItem):
                for pipe in list(node_item.connected_pipes):
                    pid = getattr(pipe, 'element_id', None)
                    if pid and pid in self._item_by_id:
                        self._remove_branch_item_by_id(pid)
                self._model.remove_node(eid)
                self._item_by_id.pop(eid, None)
                if node_item.scene() is self:
                    self.removeItem(node_item)

        self.network_changed.emit()

    def _restore_node(self, node_data):
        """Re-add a node to the scene and model from a deep-copied snapshot."""
        self._model.nodes[node_data.id] = node_data
        item = NodeItem(node_data.id, node_data.name, node_data.node_type)
        item.setPos(QPointF(node_data.x, node_data.y))
        item.double_clicked.connect(self.element_double_clicked)
        item.position_changed.connect(self._on_item_moved)
        self.addItem(item)
        self._item_by_id[node_data.id] = item

    def _restore_branch(self, branch_data):
        """Re-add a branch to the scene and model from a deep-copied snapshot."""
        from app.project.model import PipeData, ValveData, PumpData

        if isinstance(branch_data, PipeData):
            self._model.pipes[branch_data.id] = branch_data
            ItemClass = PipeItem
        elif isinstance(branch_data, ValveData):
            self._model.valves[branch_data.id] = branch_data
            ItemClass = ValveItem
        elif isinstance(branch_data, PumpData):
            self._model.pumps[branch_data.id] = branch_data
            ItemClass = PumpItem
        else:
            return

        s_item = self._item_by_id.get(branch_data.start_node_id)
        e_item = self._item_by_id.get(branch_data.end_node_id)
        if not isinstance(s_item, NodeItem) or not isinstance(e_item, NodeItem):
            return

        item = ItemClass(branch_data.id, branch_data.name, s_item, e_item)
        if isinstance(branch_data, ValveData):
            item.valve_type = branch_data.valve_type
            item.open_pct   = branch_data.open_pct
        elif isinstance(branch_data, PumpData):
            item.on_off = branch_data.on_off

        item.double_clicked.connect(self.element_double_clicked)
        self.addItem(item)
        self._item_by_id[branch_data.id] = item
        s_item.add_pipe(item)
        e_item.add_pipe(item)

    def _remove_branch_item(self, item: PipeItem):
        """Remove a branch item by reference (used by node deletion)."""
        eid = getattr(item, 'element_id', None)
        if eid:
            self._remove_branch_item_by_id(eid)

    def _remove_branch_item_by_id(self, eid: str):
        """Remove branch item and deregister from all nodes."""
        item = self._item_by_id.get(eid)
        if item is None:
            return
        # Deregister from connected node items
        for node_item in list(self._item_by_id.values()):
            if isinstance(node_item, NodeItem):
                node_item.remove_pipe(item)
        self._model.remove_branch(eid)
        self._item_by_id.pop(eid, None)
        if item.scene() is self:
            self.removeItem(item)

    # ── Node lookup ───────────────────────────────────────────────────────

    def _node_at(self, pos: QPointF) -> NodeItem | None:
        for item in self.items(pos):
            if isinstance(item, NodeItem):
                return item
        return None

    def _node_near(self, pos: QPointF, radius: float) -> NodeItem | None:
        """Return the nearest NodeItem within radius px, or None."""
        import math
        best = None
        best_dist = radius
        for item in self._item_by_id.values():
            if isinstance(item, NodeItem):
                p = item.scenePos()
                d = math.hypot(p.x() - pos.x(), p.y() - pos.y())
                if d <= best_dist:
                    best_dist = d
                    best = item
        return best

    # ── Node type replacement (prevents duplicate-on-top crash) ───────────

    def _replace_node_type(self, node_item: NodeItem, new_type: str):
        """
        Change an existing node's type in-place (e.g. junction → source).
        Preserves the node's ID, position, and all connected pipes.
        """
        eid = node_item.element_id
        if eid not in self._model.nodes:
            return
        node_data = self._model.nodes[eid]
        node_data.node_type = new_type
        if new_type == "source":
            node_data.pressure_bar = 3.0
        elif new_type == "sink":
            node_data.pressure_bar = 1.0

        # Remember connections and position
        pos = node_item.scenePos()
        connected_pipes = list(node_item.connected_pipes)

        # Swap out the canvas item (type changes how it renders)
        self.removeItem(node_item)
        new_item = NodeItem(eid, node_data.name, new_type)
        new_item.setPos(pos)
        new_item.double_clicked.connect(self.element_double_clicked)
        new_item.position_changed.connect(self._on_item_moved)
        self.addItem(new_item)
        self._item_by_id[eid] = new_item

        # Reconnect all pipes to the new item
        for pipe in connected_pipes:
            new_item.add_pipe(pipe)
            if pipe._start_node is node_item:
                pipe._start_node = new_item
            if pipe._end_node is node_item:
                pipe._end_node = new_item
            pipe.update_geometry()

        self.network_changed.emit()
        self.status_message.emit(
            f"{eid} converted to {new_type}"
        )

    # ── Position sync (model ↔ canvas) ────────────────────────────────────

    def _on_item_moved(self, element_id: str, x: float, y: float):
        if element_id in self._model.nodes:
            self._model.nodes[element_id].x = x
            self._model.nodes[element_id].y = y
        self.network_changed.emit()

    # ── Result display update ─────────────────────────────────────────────

    def update_results(self):
        """Push solver results from model into canvas items."""
        for eid, node_data in self._model.nodes.items():
            item = self._item_by_id.get(eid)
            if isinstance(item, NodeItem):
                item.set_result(node_data.result_pressure_bar)
                # Alarm check
                p = node_data.result_pressure_bar
                alarm = False
                if p is not None:
                    if (node_data.alarm_min_pressure_bar is not None
                            and p < node_data.alarm_min_pressure_bar):
                        alarm = True
                    if (node_data.alarm_max_pressure_bar is not None
                            and p > node_data.alarm_max_pressure_bar):
                        alarm = True
                item.alarm_active = alarm

        for branch_dict in (self._model.pipes, self._model.valves,
                             self._model.pumps):
            for eid, branch in branch_dict.items():
                item = self._item_by_id.get(eid)
                if isinstance(item, PipeItem):
                    item.set_result(
                        branch.result_velocity_ms,
                        branch.result_flow_m3s,
                        branch.result_delta_p_bar,
                        branch.result_reynolds,
                        branch.result_regime,
                    )
                    # Alarm check
                    alarm = False
                    v = branch.result_velocity_ms
                    dp = branch.result_delta_p_bar
                    if (v is not None and hasattr(branch, 'alarm_max_velocity_ms')
                            and branch.alarm_max_velocity_ms is not None
                            and v > branch.alarm_max_velocity_ms):
                        alarm = True
                    if (dp is not None and hasattr(branch, 'alarm_max_delta_p_bar')
                            and branch.alarm_max_delta_p_bar is not None
                            and dp > branch.alarm_max_delta_p_bar):
                        alarm = True
                    item.alarm_active = alarm

    # ── Rebuild canvas from model (used by load_project) ──────────────────

    def rebuild_from_model(self):
        """Clear the canvas and rebuild all items from the current model."""
        self.clear()
        self._item_by_id.clear()

        # Place node items
        for nid, node_data in self._model.nodes.items():
            item = NodeItem(nid, node_data.name, node_data.node_type)
            item.setPos(QPointF(node_data.x, node_data.y))
            item.double_clicked.connect(self.element_double_clicked)
            item.position_changed.connect(self._on_item_moved)
            self.addItem(item)
            self._item_by_id[nid] = item

        # Place branch items
        for bid, pipe in self._model.pipes.items():
            self._rebuild_branch(bid, pipe.start_node_id, pipe.end_node_id,
                                  PipeItem, pipe.name)
        for vid, valve in self._model.valves.items():
            item = self._rebuild_branch(vid, valve.start_node_id,
                                         valve.end_node_id, ValveItem,
                                         valve.name)
            if item:
                item.valve_type = valve.valve_type
                item.open_pct   = valve.open_pct
        for pid, pump in self._model.pumps.items():
            item = self._rebuild_branch(pid, pump.start_node_id,
                                         pump.end_node_id, PumpItem,
                                         pump.name)
            if item:
                item.on_off = pump.on_off

    def _rebuild_branch(self, bid, sn_id, en_id, ItemClass, name):
        s_item = self._item_by_id.get(sn_id)
        e_item = self._item_by_id.get(en_id)
        if not isinstance(s_item, NodeItem) or not isinstance(e_item, NodeItem):
            return None
        item = ItemClass(bid, name, s_item, e_item)
        item.double_clicked.connect(self.element_double_clicked)
        self.addItem(item)
        self._item_by_id[bid] = item
        s_item.add_pipe(item)
        e_item.add_pipe(item)
        return item

    # ── Animation ─────────────────────────────────────────────────────────

    def _tick_animation(self):
        now = time.monotonic()
        dt  = now - self._last_tick_time
        self._last_tick_time = now
        for item in self._item_by_id.values():
            if isinstance(item, PipeItem):
                item.advance_animation(dt)

    # ── Export canvas as PNG ───────────────────────────────────────────────

    def export_png(self, filepath: str):
        from PyQt6.QtGui import QImage, QPainter as QP
        rect = self.itemsBoundingRect().adjusted(-20, -20, 20, 20)
        img  = QImage(int(rect.width()), int(rect.height()),
                      QImage.Format.Format_ARGB32)
        img.fill(QColor(COLOR["canvas_bg"]))
        p = QP(img)
        self.render(p, source=rect)
        p.end()
        img.save(filepath)

    # ── Keyboard ──────────────────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.delete_selected()
        elif event.key() == Qt.Key.Key_Escape:
            self._pipe_start_node = None
            self.set_mode("select")
            self.update()
        else:
            super().keyPressEvent(event)

    # ── Public accessors ──────────────────────────────────────────────────

    def item_by_id(self, eid: str) -> QGraphicsItem | None:
        return self._item_by_id.get(eid)

    def select_item(self, eid: str):
        self.clearSelection()
        item = self._item_by_id.get(eid)
        if item:
            item.setSelected(True)


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------

class PipeNetworkView(QGraphicsView):
    """
    QGraphicsView with:
      - scroll-wheel zoom
      - middle-mouse pan
      - rubber-band selection (select mode only)
    """

    def __init__(self, scene: PipeNetworkScene, parent=None):
        super().__init__(scene, parent)
        self._scene = scene

        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(
            QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setBackgroundBrush(QBrush(QColor(COLOR["canvas_bg"])))
        self.setSceneRect(-5000, -5000, 10000, 10000)

        self._pan_active = False
        self._pan_start  = None
        self._zoom_level = 1.0

    def wheelEvent(self, event: QWheelEvent):
        factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
        new_zoom = self._zoom_level * factor
        if MIN_ZOOM <= new_zoom <= MAX_ZOOM:
            self.scale(factor, factor)
            self._zoom_level = new_zoom

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_active = True
            self._pan_start  = event.position().toPoint()
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
        elif (event.button() == Qt.MouseButton.LeftButton
              and self._scene.mode == "select"):
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._pan_active and self._pan_start is not None:
            delta = event.position().toPoint() - self._pan_start
            self._pan_start = event.position().toPoint()
            h = self.horizontalScrollBar()
            v = self.verticalScrollBar()
            h.setValue(h.value() - delta.x())
            v.setValue(v.value() - delta.y())
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_active = False
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        super().mouseReleaseEvent(event)

    def reset_view(self):
        self.resetTransform()
        self._zoom_level = 1.0
        self.centerOn(0, 0)
