import math
import pygame
import pygame.gfxdraw
from pygame import Surface, Rect
from pygame.mask import MaskType as Mask, Mask as mask_from_size, from_surface as mask_from_surface
from typing import *
from vector import Vector

HITBOX_RESOLUTION = 40
DUMMY_SURFACE = Surface((0, 0))

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
HIGHLIGHT_COLOR = (255, 255, 0)
SELECT_COLOR = (0, 255, 0)
HITBOX_COLOR = (255, 0, 255)

POINT_RADIUS = 0.065
POINT_SELECTED_RADIUS = POINT_RADIUS * 1.2
POINT_COLOR = (255, 255, 255)
ADD_POINT_COLOR = (80, 80, 255)
HITBOX_CENTER_WIDTH = 3
SHAPE_HIGHLIGHTED_WIDTH = 2

ANCHOR_RADIUS = 0.16
ANCHOR_COLOR = (235, 0, 50)
DYNAMIC_ANCHOR_COLOR = (222, 168, 62)
ANCHOR_BORDER = (0, 0, 0)

PIN_RADIUS = 0.125
STATIC_PIN_COLOR = (0, 0, 0)

TERRAIN_MAIN_WIDTH = 25.25
TERRAIN_SMALL_WIDTH = 4.0
TERRAIN_BASE_HEIGHT = 5.0
TERRAIN_BORDER_WIDTH = 2
WATER_EDGE_WIDTH = 1

PILLAR_WIDTH = 1.0
PILLAR_COLOR = (195, 171, 149, 150)
PILLAR_BORDER = (105, 98, 91, 150)
PILLAR_BORDER_WIDTH = 1

NumberTuple = Tuple[Union[int, float], ...]
ClosestPoint = Tuple[Vector, float, int]


def scale(min_width: int, zoom: int, factor=30) -> int:
	"""Scales the width of a line to the zoom level"""
	return max(min_width, round(zoom / (factor / min_width)))


def rect_hitbox_mask(rect: Sequence[float], zoom: int) -> Mask:
	w, h = max(1, round(rect[2] / zoom * HITBOX_RESOLUTION)), max(1, round(rect[3] / zoom * HITBOX_RESOLUTION))
	return mask_from_size((w, h), True)


class LayoutObject:
	"""Acts as a wrapper for the dictionary that represents an object in the layout."""
	list_name: str = None

	def __init__(self, dictionary):
		self._dict = dictionary

	def render(self, display: Surface, camera: Vector, zoom: int, args=None):
		raise NotImplementedError(f"{type(self).render}")

	@property
	def dictionary(self) -> dict:
		return self._dict

	@property
	def pos(self) -> Vector:
		return Vector(self._dict["m_Pos"])
	@pos.setter
	def pos(self, value: Vector):
		value.to_dict(self._dict["m_Pos"])


class SelectableObject(LayoutObject):
	"""A LayoutObject that can be selected and moved around"""
	def __init__(self, dictionary: dict):
		super().__init__(dictionary)
		self.selected = False
		self._hitbox: Optional[Mask] = None
		self._center_offset = Vector(0, 0)
		self._last_zoom: int = 1
		self._last_camera = Vector(0, 0)

	def render(self, display: Surface, camera: Vector, zoom: float, args=None):
		self._last_zoom = zoom
		self._last_camera = tuple(camera)

	def collidepoint(self, point: Vector) -> bool:
		size, center = self._hitbox.get_size(), self.pos[:2]
		x = round((point[0] / self._last_zoom - self._last_camera[0] - center[0] + self._center_offset[0])
		          * HITBOX_RESOLUTION + size[0] / 2)
		y = round((point[1] / self._last_zoom + self._last_camera[1] + center[1] + self._center_offset[1])
		          * HITBOX_RESOLUTION + size[1] / 2)
		return self._hitbox.get_at((x, y)) if 0 <= x < size[0] and 0 <= y < size[1] else False

	def colliderect(self, rect: Vector, mask: Mask = None) -> bool:
		size, center = self._hitbox.get_size(), self.pos[:2]
		x = round((rect[0] / self._last_zoom - self._last_camera[0] - center[0] + self._center_offset[0])
		          * HITBOX_RESOLUTION + size[0] / 2)
		y = round((rect[1] / self._last_zoom + self._last_camera[1] + center[1] + self._center_offset[1])
		          * HITBOX_RESOLUTION + size[1] / 2)
		if mask is None:
			mask = rect_hitbox_mask(rect, self._last_zoom)
		return bool(self._hitbox.overlap(mask, (x, y)))


LayoutT = TypeVar("LayoutT", bound=LayoutObject)
class LayoutList(Sequence[LayoutT]):
	"""Acts a wrapper for a list of dictionaries in the layout, allowing you to treat them as objects"""
	def __init__(self, cls: Type[LayoutT], layout: dict):
		self.cls = cls
		self._dictlist = layout[cls.list_name]
		if cls is CustomShape:
			anchorsList = [Anchor(a) for a in layout[Anchor.list_name]]
			self._objlist = [CustomShape(o, anchorsList) for o in self._dictlist]
		else:
			self._objlist = [cls(o) for o in self._dictlist]

	def append(self, elem: LayoutT):
		self._dictlist.append(elem.dictionary)
		self._objlist.append(elem)

	def extend(self, elems: Sequence[LayoutT]):
		self._dictlist.extend([e.dictionary for e in elems])
		self._objlist.extend(elems)

	def remove(self, elem: LayoutT):
		self._dictlist.remove(elem.dictionary)
		self._objlist.remove(elem)

	def clear(self):
		self._dictlist.clear()
		self._objlist.clear()

	def __len__(self) -> int:
		return self._objlist.__len__()

	def __iter__(self) -> Iterator[LayoutT]:
		return self._objlist.__iter__()

	def __getitem__(self, item: Union[int, slice]) -> Union[LayoutT, List[LayoutT]]:
		return self._objlist.__getitem__(item)


class Anchor(LayoutObject):
	list_name = "m_Anchors"

	def __init__(self, dictionary):
		super().__init__(dictionary)

	def render(self, display: Surface, camera: Vector, zoom: int, dynamic_anchor_ids=tuple()):
		color = ANCHOR_COLOR
		for dyn_anc_id in dynamic_anchor_ids:
			if self.id == dyn_anc_id:
				color = DYNAMIC_ANCHOR_COLOR
				break
		rect = (round(zoom * (self.pos[0] + camera[0] - ANCHOR_RADIUS)),
		        round(zoom * -(self.pos[1] + camera[1] + ANCHOR_RADIUS)),
		        round(zoom * ANCHOR_RADIUS * 2),
		        round(zoom * ANCHOR_RADIUS * 2))
		pygame.draw.rect(display, color, rect)
		pygame.draw.rect(display, ANCHOR_BORDER, rect, max(1, round(rect[2] / 15)))

	@property
	def id(self) -> str:
		return self._dict["m_Guid"]
	@id.setter
	def id(self, value: str):
		self._dict["m_Guid"] = value


class TerrainStretch(LayoutObject):
	list_name = "m_TerrainStretches"

	def __init__(self, dictionary):
		super().__init__(dictionary)

	def render(self, display: Surface, camera: Vector, zoom: int, color=WHITE):
		if self.width == TERRAIN_MAIN_WIDTH:  # main terrain
			x = zoom * (self.pos[0] - (0 if self.flipped else self.width) + camera[0])
		else:
			x = zoom * (self.pos[0] - self.width / 2 * (-1 if self.flipped else 1) + camera[0])
		rect = (round(x), round(zoom * -(self.height + camera[1])), round(zoom * self.width), round(zoom * self.height))
		pygame.draw.rect(display, color, rect, scale(TERRAIN_BORDER_WIDTH, zoom))

	@property
	def flipped(self) -> bool:
		return self._dict["m_Flipped"]
	@flipped.setter
	def flipped(self, value: bool):
		self._dict["m_Flipped"] = value

	@property
	def width(self) -> float:
		return TERRAIN_MAIN_WIDTH if self._dict["m_TerrainIslandType"] == 0 else TERRAIN_SMALL_WIDTH

	@property
	def height(self) -> float:
		return TERRAIN_BASE_HEIGHT + self.pos[1]


class WaterBlock(LayoutObject):
	list_name = "m_WaterBlocks"

	def __init__(self, dictionary):
		super().__init__(dictionary)

	def render(self, display: Surface, camera: Vector, zoom: int, color=WHITE):
		start = (zoom * (self.pos[0] - self.width/2 + camera[0]), zoom * -(self.height + camera[1]))
		end = (zoom * (self.pos[0] + self.width/2 + camera[0]), zoom * -(self.height + camera[1]))
		pygame.draw.line(display, color, start, end, scale(WATER_EDGE_WIDTH, zoom))

	@property
	def width(self) -> float:
		return self._dict["m_Width"]
	@width.setter
	def width(self, value: float):
		self._dict["m_Width"] = value

	@property
	def height(self) -> float:
		return self._dict["m_Height"]
	@height.setter
	def height(self, value: float):
		self._dict["m_Height"] = value


class Pillar(SelectableObject):
	list_name = "m_Pillars"

	def __init__(self, dictionary):
		super().__init__(dictionary)
		self.rect = Rect(0, 0, 0, 0)

	def render(self, display: Surface, camera: Vector, zoom: int, draw_hitboxes=False):
		super().render(display, camera, zoom)
		self.rect = Rect(round(zoom * (self.pos[0] - PILLAR_WIDTH / 2 + camera[0])),
		                 round(zoom * -(self.pos[1] + self.height + camera[1])),
		                 round(zoom * PILLAR_WIDTH),
		                 round(zoom * self.height))
		pygame.gfxdraw.box(display, self.rect, PILLAR_COLOR)
		if self.selected:
			# We don't know how to make it antialiased
			pygame.draw.rect(display, HIGHLIGHT_COLOR, self.rect, scale(SHAPE_HIGHLIGHTED_WIDTH, zoom, 60))
		else:
			pygame.gfxdraw.rectangle(display, self.rect, PILLAR_BORDER)
		if draw_hitboxes:
			pygame.draw.rect(display, HITBOX_COLOR, self.rect, 1)
			center_width = scale(HITBOX_CENTER_WIDTH, zoom)
			center_start = (round(zoom * (self.pos[0] + camera[0]) - center_width / 2),
			                round(zoom * -(self.pos[1] + camera[1])))
			center_end = (center_start[0] + center_width, center_start[1])
			pygame.draw.line(display, HITBOX_COLOR, center_start, center_end, center_width)

	def collidepoint(self, point):
		return self.rect.collidepoint(*point)

	def colliderect(self, rect, mask=None):
		return self.rect.colliderect(rect)

	@property
	def height(self) -> float:
		return self._dict["m_Height"]
	@height.setter
	def height(self, value: float):
		self._dict["m_Height"] = value


class ShapeRenderArgs:
	def __init__(self, draw_points: bool, draw_hitboxes: bool, holding_shift: bool,
	             mouse_pos: Vector, mouse_change: Vector):
		self.draw_points = draw_points
		self.mouse_pos = mouse_pos
		self.mouse_change = mouse_change
		self.holding_shift = holding_shift
		self.draw_hitboxes = draw_hitboxes
		self.top_point: Optional[CustomShapePoint] = None
		self.selected_point: Optional[CustomShapePoint] = None
		self.moused_over_point: Optional[CustomShapePoint] = None


class CustomShape(SelectableObject):
	list_name = "m_CustomShapes"

	def __init__(self, dictionary: dict, anchors: Sequence[Anchor] = None):
		super().__init__(dictionary)
		self.bounding_box = Rect(0, 0, 0, 0)
		self.point_hitboxes: List[CustomShapePoint] = []
		self.anchors: List[Anchor] = []
		self.selected_point_index: Optional[int] = None
		self.add_point_closest: ClosestPoint = (Vector(), 0, 0)
		self.add_point_hitbox = Rect(0, 0, 0, 0)
		if anchors:
			for dyn_anc_id in self.dynamic_anchor_ids:
				for anchor in anchors:
					if anchor.id == dyn_anc_id:
						self.anchors.append(anchor)
		self.calculate_hitbox()

	def calculate_hitbox(self, align_center=False):
		points_base = self.points
		# Calculate bounding rect
		leftmost, rightmost, topmost, bottommost = 1000, -1000, 1000, -1000
		for point in points_base:
			leftmost = min(leftmost, point[0])
			rightmost = max(rightmost, point[0])
			topmost = min(topmost, point[1])
			bottommost = max(bottommost, point[1])
		width, height = rightmost - leftmost, bottommost - topmost

		# Adjust center
		basepos = self.pos
		center = Vector(leftmost + width / 2 + basepos[0], topmost + height / 2 + basepos[1])
		if align_center:
			center.to_dict(self._dict["m_Pos"])
			self.points = (points_base := [point + basepos - center for point in points_base])
			leftmost, rightmost = [x + basepos[0] - center[0] for x in (leftmost, rightmost)]
			topmost, bottommost = [y + basepos[1] - center[1] for y in (topmost, bottommost)]
			self._center_offset = (0, 0)
		else:
			self._center_offset = (basepos[0] - center[0], basepos[1] - center[1])

		# Create hitbox bitmap
		points_hitbox = [(round(HITBOX_RESOLUTION * (point[0] - leftmost)),
		                  round(-HITBOX_RESOLUTION * (point[1] + topmost)))
		                 for point in points_base]
		surface = Surface((HITBOX_RESOLUTION * width + 1, HITBOX_RESOLUTION * height + 1), pygame.SRCALPHA, 32)
		pygame.draw.polygon(surface, BLACK, points_hitbox)
		self._hitbox = mask_from_surface(surface)

	def render(self, display: Surface, camera: Vector, zoom: int, args: ShapeRenderArgs = None):
		"""Draws the shape on the screen and calculates attributes like bounding_box.
		It also searches for a single point to be selected, which is saved to the args object."""
		super().render(display, camera, zoom)
		basepos = self.pos[:2]
		points_pixels = [zoom * (point + basepos + camera).flip_y() for point in self.points]
		border_color = tuple(self.color[i] * 0.75 for i in range(3))
		pygame.gfxdraw.filled_polygon(display, points_pixels, self.color)
		pygame.gfxdraw.aapolygon(display, points_pixels, border_color)

		for pin in self.static_pins:
			rect = [round(zoom * (pin["x"] + camera[0])), round(zoom * -(pin["y"] + camera[1]))]
			pygame.gfxdraw.aacircle(display, rect[0], rect[1], round(zoom * PIN_RADIUS), STATIC_PIN_COLOR)
			pygame.gfxdraw.filled_circle(display, rect[0], rect[1], round(zoom * PIN_RADIUS), STATIC_PIN_COLOR)

		if self.selected:
			# We don't know how to make it antialiased
			pygame.draw.polygon(display, HIGHLIGHT_COLOR, points_pixels, scale(SHAPE_HIGHLIGHTED_WIDTH, zoom, 60))

		self.point_hitboxes = []
		self.add_point_hitbox = None
		self.bounding_box = pygame.draw.polygon(DUMMY_SURFACE, WHITE, points_pixels)

		if args.draw_points:
			max_radius = round(zoom * POINT_SELECTED_RADIUS)
			self.bounding_box.left -= max_radius
			self.bounding_box.top -= max_radius
			self.bounding_box.width += max_radius * 2
			self.bounding_box.height += max_radius * 2
			for i, p in enumerate(points_pixels):
				self.point_hitboxes.append(CustomShapePoint(p, i, round(zoom * POINT_SELECTED_RADIUS)))
			for i, point in enumerate(self.point_hitboxes):
				if i == self.selected_point_index:
					args.selected_point = point
					break
			if not args.holding_shift:
				for i, point in enumerate(self.point_hitboxes):
					if point.collidepoint(args.mouse_pos):
						args.moused_over_point = point
						break
		if args.draw_hitboxes:
			pygame.draw.rect(display, HITBOX_COLOR, self.bounding_box, 1)
			center_width = scale(HITBOX_CENTER_WIDTH, zoom)
			center_start = (round(zoom * (self.pos[0] + camera[0]) - center_width / 2),
			                round(zoom * -(self.pos[1] + camera[1])))
			center_end = (center_start[0] + center_width, center_start[1])
			pygame.draw.line(display, HITBOX_COLOR, center_start, center_end, center_width)

	def render_points(self, display: Surface, camera: Vector, zoom: int, args: ShapeRenderArgs):
		"""Draws dots for the shape's points and performs operations related to selecting and moving them.
		It also searches for the top point to display, which is saved to the args object."""
		if not args.draw_points:
			return
		points, basepos = self.points, self.pos[:2]
		points_pixels = [zoom * (point + basepos + camera).flip_y() for point in self.points]

		# Move point if a point is selected
		for i in range(len(points)):
			if i == self.selected_point_index:
				newpoints = list(points)
				newpoints[i] += args.mouse_change
				points = newpoints
				self.points = tuple(newpoints)
				break
		# Render points
		for point in self.point_hitboxes:
			if point == args.selected_point or args.selected_point is None and args.moused_over_point == point:
				args.top_point = point
			else:
				point.render(display, POINT_COLOR, round(zoom * POINT_RADIUS))
		# Show overlay of where a point will be added
		if args.selected_point is None and args.holding_shift and self.bounding_box.collidepoint(*args.mouse_pos):
			closest: ClosestPoint = (Vector(), zoom / 7, -1)
			for i in range(len(points)):
				ni = 0 if i + 1 == len(points) else i + 1
				_point = args.mouse_pos.closest_point(points_pixels[i], points_pixels[ni])
				if not _point:
					continue
				distance = math.sqrt((_point[0] - args.mouse_pos[0]) ** 2 + (_point[1] - args.mouse_pos[1]) ** 2)
				if distance < closest[1]:
					closest = (_point.round(), distance, ni)
			if closest[0]:
				self.add_point_closest = closest
				self.add_point_hitbox = pygame.draw.circle(
					DUMMY_SURFACE, 0, (closest[0].round()), round(zoom * PIN_RADIUS / 1.7), 0)
				pygame.gfxdraw.aacircle(
					display, closest[0][0], closest[0][1], round(zoom * PIN_RADIUS / 1.7), ADD_POINT_COLOR)
				pygame.gfxdraw.filled_circle(
					display, closest[0][0], closest[0][1], round(zoom * PIN_RADIUS / 1.7), ADD_POINT_COLOR)
		# Update hitbox and move center to actual center
		if self.selected_point_index is not None:
			self.calculate_hitbox(True)

	def add_point(self, index: int, point: Vector):
		points = list(self.points)
		points.insert(index, (point / self._last_zoom).flip_y() - self._last_camera - self.pos)
		self.points = points
		self.selected_point_index = None
		self.calculate_hitbox(True)

	def del_point(self, index: int):
		points = list(self.points)
		points.pop(index)
		self.points = points
		self.selected_point_index = None
		self.calculate_hitbox(True)

	@SelectableObject.pos.setter
	def pos(self, value: Vector):
		change = value - self.pos
		SelectableObject.pos.__set__(self, value)
		for pin in self.static_pins:
			(Vector(pin) + change).to_dict(pin)
		for anchor in self.anchors:
			anchor.pos += change

	@property
	def rotations(self) -> Vector:
		"""Rotation degrees in the X, Y, and Z axis, calculated from a quaternion"""
		return Vector(self._dict["m_Rot"]).euler_angles()
	@rotations.setter
	def rotations(self, values: Vector):
		old_rotz = self.rotation
		values.quaternion().to_dict(self._dict["m_Rot"])
		self._dict["m_RotationDegrees"] = values[2]
		change = self.rotation - old_rotz
		if abs(change) > 0.000001:
			basepos = self.pos[:2]
			for pin in self.static_pins:
				Vector(pin).rotate(change, basepos).to_dict(pin)
			for anchor in self.anchors:
				anchor.pos = anchor.pos.rotate(change, basepos)

	@property
	def rotation(self) -> float:
		"""Rotation degrees only in the Z axis"""
		return self._dict["m_RotationDegrees"]
	@rotation.setter
	def rotation(self, value: float):
		x, y, _ = self.rotations
		self.rotations = (x, y, value)

	@property
	def flipped(self) -> bool:
		return self._dict["m_Flipped"]
	@flipped.setter
	def flipped(self, value: bool):
		old_flipped = self._dict["m_Flipped"]
		self._dict["m_Flipped"] = value
		if old_flipped != value:
			basepos = self.pos[:2]
			for pin in self.static_pins:
				Vector(pin).flip(basepos, self.rotation).to_dict(pin)
			for anchor in self.anchors:
				anchor.pos = anchor.pos.flip(basepos, self.rotation)

	@property
	def scale(self) -> Vector:
		return Vector(self._dict["m_Scale"])
	@scale.setter
	def scale(self, value: Vector):
		old_scale = self.scale
		value.to_dict(self._dict["m_Scale"])
		change = (value[0] / old_scale[0], value[1] / old_scale[1])
		if abs(change[0] - 1) > 0.000001 or abs(change[1] - 1) > 0.000001:
			basepos, rot = self.pos[:2], self.rotation
			for pin in self.static_pins:
				((Vector(pin).rotate(-rot, basepos) - basepos) * change + basepos).rotate(rot, basepos).to_dict(pin)
			for anchor in self.anchors:
				anchor.pos = ((anchor.pos.rotate(-rot, basepos) - basepos) * change + basepos).rotate(rot, basepos)

	@property
	def color(self) -> Vector:
		return Vector(round(v*255) for v in self._dict["m_Color"].values())
	@color.setter
	def color(self, value: Vector):
		if len(value) == 3:
			self._dict["m_Color"] = {"r": value[0] / 255, "g": value[1] / 255, "b": value[2] / 255,
			                         "a": self._dict["m_Color"]["a"]}
		else:
			self._dict["m_Color"] = {"r": value[0]/255, "g": value[1]/255, "b": value[2]/255, "a": value[3]/255}

	@property
	def points(self) -> Tuple[Vector, ...]:
		pts_scale = self.scale
		values = self._dict["m_PointsLocalSpace"]
		return tuple((Vector(p) * pts_scale).flip_x(only_if=self.flipped).rotate(self.rotation) for p in values)
	@points.setter
	def points(self, values: Sequence[Vector]):
		pts_scale = self.scale
		pts = [(p.rotate(-self.rotation).flip_x(only_if=self.flipped) / pts_scale).to_dict() for p in values]
		self._dict["m_PointsLocalSpace"] = pts

	@property
	def static_pins(self) -> List[Dict[str, float]]:
		return self._dict["m_StaticPins"]
	@static_pins.setter
	def static_pins(self, values: List[Dict[str, float]]):
		self._dict["m_StaticPins"] = values

	@property
	def dynamic_anchor_ids(self) -> List[str]:
		return self._dict["m_DynamicAnchorGuids"]
	@dynamic_anchor_ids.setter
	def dynamic_anchor_ids(self, values: List[str]):
		self._dict["m_DynamicAnchorGuids"] = values


class CustomShapePoint:
	def __init__(self, pos: Vector, index: int, radius: float):
		self.pos = pos.round()
		self.index = index
		self.radius = radius

	def render(self, display: Surface, color: Sequence[int], radius=None):
		if radius is None:
			radius = self.radius
		border_color = tuple(color[i] * 0.75 for i in range(3))
		pygame.gfxdraw.filled_circle(display, self.pos[0], self.pos[1], radius, color)
		pygame.gfxdraw.aacircle(display, self.pos[0], self.pos[1], radius, border_color)

	def collidepoint(self, point):
		return math.sqrt((point[0] - self.pos[0]) ** 2 + (point[1] - self.pos[1]) ** 2) <= self.radius
