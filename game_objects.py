import pygame
import pygame.gfxdraw
import math
from collections import Sequence
from operator import add
from editor import BASE_SIZE

ANTIALIASING = True

HITBOX_RESOLUTION = 40
DUMMY_SURFACE = pygame.Surface(BASE_SIZE, pygame.SRCALPHA, 32)

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
ANCHOR_BORDER = (0, 0, 0)
DYNAMIC_ANCHOR_COLOR = (222, 168, 62)

PIN_RADIUS = 0.125
STATIC_PIN_COLOR = (0, 0, 0)
STATIC_PIN_BORDER = (50, 50, 50)

TERRAIN_MAIN_WIDTH = 25.25
TERRAIN_SMALL_WIDTH = 4.0
TERRAIN_BASE_HEIGHT = 5.0
TERRAIN_BORDER_WIDTH = 2
WATER_EDGE_WIDTH = 1

PILLAR_WIDTH = 1.0
PILLAR_COLOR = (195, 171, 149, 150)
PILLAR_BORDER = (105, 98, 91, 150)
PILLAR_BORDER_WIDTH = 1


def scale(min_width, zoom, factor=30):
	"""Scales the width of a line to the zoom level"""
	return max(min_width, round(zoom / (factor / min_width)))


def rotate(point, angle, origin=(0, 0), deg=True):
	"""Rotate a point by a given angle counterclockwise around the origin"""
	if deg:
		angle = math.radians(angle)
	px, py = point[0] - origin[0], point[1] - origin[1]
	x = math.cos(angle) * px - math.sin(angle) * py + origin[0]
	y = math.sin(angle) * px + math.cos(angle) * py + origin[1]
	return (x, y) if len(point) == 2 else (x, y, point[2])


def quaternion(x, y, z, deg=True):
	"""Converts euler angles to a quaternion
	https://en.wikipedia.org/wiki/Conversion_between_quaternions_and_Euler_angles"""
	if deg:
		x = math.radians(x)
		y = math.radians(y)
		z = math.radians(z)

	cx = math.cos(x * 0.5)
	sx = math.sin(x * 0.5)
	cy = math.cos(y * 0.5)
	sy = math.sin(y * 0.5)
	cz = math.cos(z * 0.5)
	sz = math.sin(z * 0.5)

	qx = sx * cy * cz - cx * sy * sz
	qy = cx * sy * cz + sx * cy * sz
	qz = cx * cy * sz - sx * sy * cz
	qw = cx * cy * cz + sx * sy * sz
	return qx, qy, qz, qw


def euler_angles(qx, qy, qz, qw, deg=True):
	"""Converts a quaternion to euler angles
	https://en.wikipedia.org/wiki/Conversion_between_quaternions_and_Euler_angles"""
	sx_cy = 2 * (qw * qx + qy * qz)
	cx_cy = 1 - 2 * (qx**2 + qy**1)
	x = math.atan2(sx_cy, cx_cy)

	sy = 2 * (qw * qy - qz * qx)
	y = math.asin(sy) if -1 < sy < 1 else math.copysign(math.pi / 2, sy)

	sz_cy = 2 * (qw * qz + qx * qy)
	cz_cy = 1 - 2 * (qy**2 + qz**2)
	z = math.atan2(sz_cy, cz_cy)

	if deg:
		x = math.degrees(x)
		y = math.degrees(y)
		z = math.degrees(z)
	return x, y, z


def closest_point(l1, l2, p):
	"""Finds the closest point on a line given a start and end point, and a point to check from."""
	try:
		s1 = (l2[1] - l1[1]) / (l2[0] - l1[0])
		s2 = -1 / s1
		a1 = (l1[1] - l1[0] * s1)
		a2 = (p[1] - p[0] * s2)
		x = -(a2 - a1) / (s2 - s1)
		if l1[0] <= x <= l2[0] or l2[0] <= x <= l1[0]:
			return x, s1 * x + a1
		else:
			return None
	except ZeroDivisionError:
		if l2[0] - l1[0] == 0: 
			# Vertical line
			if l1[1] <= p[1] <= l2[1] or l2[1] <= p[1] <= l1[1]:
				return l1[0], p[1]
			else:
				return None
		else:
			# Horizontal Line
			if l1[0] <= p[0] <= l2[0] or l2[0] <= p[0] <= l1[0]:
				return p[0], l1[1]
			else:
				return None


def rect_hitbox_mask(rect, zoom):
	w, h = max(1, round(rect[2] / zoom * HITBOX_RESOLUTION)), max(1, round(rect[3] / zoom * HITBOX_RESOLUTION))
	return pygame.mask.Mask((w, h), True)


class LayoutObject:
	"""Acts as a wrapper for the dictionary that represents an object in the layout."""
	list_name = None

	def __init__(self, dictionary):
		self._dict = dictionary

	def render(self, display, camera, zoom, args=None):
		raise NotImplementedError(f"{type(self).render}")

	@property
	def dictionary(self):
		return self._dict

	@property
	def pos(self):
		return self._dict["m_Pos"]["x"], self._dict["m_Pos"]["y"], self._dict["m_Pos"]["z"]
	@pos.setter
	def pos(self, value):
		if len(value) == 2:
			self._dict["m_Pos"] = {"x": value[0], "y": value[1], "z": self._dict["m_Pos"]["z"]}
		else:
			self._dict["m_Pos"] = {"x": value[0], "y": value[1], "z": value[2]}


class SelectableObject(LayoutObject):
	"""A LayoutObject that can be selected and moved around"""
	def __init__(self, dictionary):
		super().__init__(dictionary)
		self.selected = False
		self._hitbox = None
		self._center_offset = (0, 0)
		self._last_zoom = 1
		self._last_camera = (0, 0)

	def render(self, display, camera, zoom, args=None):
		self._last_zoom = zoom
		self._last_camera = tuple(camera)

	def collidepoint(self, point):
		size, center = self._hitbox.get_size(), self.pos
		x = round((point[0] / self._last_zoom - self._last_camera[0] - center[0] + self._center_offset[0])
		          * HITBOX_RESOLUTION + size[0] / 2)
		y = round((point[1] / self._last_zoom + self._last_camera[1] + center[1] + self._center_offset[1])
		          * HITBOX_RESOLUTION + size[1] / 2)
		return self._hitbox.get_at((x, y)) if 0 <= x < size[0] and 0 <= y < size[1] else False

	def colliderect(self, rect, mask=None):
		size, center = self._hitbox.get_size(), self.pos
		x = round((rect[0] / self._last_zoom - self._last_camera[0] - center[0] + self._center_offset[0])
		          * HITBOX_RESOLUTION + size[0] / 2)
		y = round((rect[1] / self._last_zoom + self._last_camera[1] + center[1] + self._center_offset[1])
		          * HITBOX_RESOLUTION + size[1] / 2)
		if mask is None:
			mask = rect_hitbox_mask(rect, self._last_zoom)
		return bool(self._hitbox.overlap(mask, (x, y)))

	@LayoutObject.pos.setter
	def pos(self, value):
		LayoutObject.pos.__set__(self, value)


class LayoutList(Sequence):
	"""Acts a wrapper for a list of dictionaries in the layout, allowing you to treat them as objects."""
	def __init__(self, cls, layout):
		if not issubclass(cls, LayoutObject): raise TypeError()
		self._dictlist = layout[cls.list_name]
		if cls is CustomShape:
			anchorsList = [Anchor(a) for a in layout[Anchor.list_name]]
			self._objlist = [CustomShape(o, anchorsList) for o in self._dictlist]
		else:
			self._objlist = [cls(o) for o in self._dictlist]
		self.list_name = cls.list_name

	def append(self, elem):
		self._dictlist.append(elem.dictionary)
		self._objlist.append(elem)

	def extend(self, elems):
		self._dictlist.extend([e.dictionary for e in elems])
		self._objlist.extend(elems)

	def remove(self, elem):
		self._dictlist.remove(elem.dictionary)
		self._objlist.remove(elem)

	def __len__(self):
		return self._objlist.__len__()

	def __iter__(self):
		return self._objlist.__iter__()

	def __getitem__(self, item):
		return self._objlist.__getitem__(item)


class Anchor(LayoutObject):
	list_name = "m_Anchors"

	def __init__(self, dictionary):
		super().__init__(dictionary)

	def render(self, display, camera, zoom, dynamic_anchor_ids=tuple()):
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
	def id(self, value):
		self._dict["m_Guid"] = value


class TerrainStretch(LayoutObject):
	list_name = "m_TerrainStretches"

	def __init__(self, dictionary):
		super().__init__(dictionary)

	def render(self, display, camera, zoom, color=WHITE):
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
	def flipped(self, value):
		self._dict["m_Flipped"] = value

	@property
	def width(self):
		return TERRAIN_MAIN_WIDTH if self._dict["m_TerrainIslandType"] == 0 else TERRAIN_SMALL_WIDTH

	@property
	def height(self):
		return TERRAIN_BASE_HEIGHT + self.pos[1]


class WaterBlock(LayoutObject):
	list_name = "m_WaterBlocks"

	def __init__(self, dictionary):
		super().__init__(dictionary)

	def render(self, display, camera, zoom, color=WHITE):
		start = (zoom * (self.pos[0] - self.width/2 + camera[0]), zoom * -(self.height + camera[1]))
		end = (zoom * (self.pos[0] + self.width/2 + camera[0]), zoom * -(self.height + camera[1]))
		pygame.draw.line(display, color, start, end, scale(WATER_EDGE_WIDTH, zoom))

	@property
	def width(self):
		return self._dict["m_Width"]
	@width.setter
	def width(self, value):
		self._dict["m_Width"] = value

	@property
	def height(self):
		return self._dict["m_Height"]
	@height.setter
	def height(self, value):
		self._dict["m_Height"] = value


class Pillar(SelectableObject):
	list_name = "m_Pillars"

	def __init__(self, dictionary):
		super().__init__(dictionary)
		self.rect = pygame.Rect(0, 0, 0, 0)

	def render(self, display, camera, zoom, draw_hitboxes=False):
		super().render(display, camera, zoom)
		self.rect = pygame.Rect(round(zoom * (self.pos[0] - PILLAR_WIDTH / 2 + camera[0])),
		                        round(zoom * -(self.pos[1] + self.height + camera[1])),
		                        round(zoom * PILLAR_WIDTH),
		                        round(zoom * self.height))
		pygame.gfxdraw.box(display, self.rect, PILLAR_COLOR)
		if self.selected:
			# TODO: Find an antialiased solution
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
	def height(self):
		return self._dict["m_Height"]
	@height.setter
	def height(self, value):
		self._dict["m_Height"] = value


class ShapeRenderArgs:
	def __init__(self, draw_points, mouse_pos, mouse_change, holding_shift, draw_hitboxes):
		self.draw_points = draw_points
		self.mouse_pos = mouse_pos
		self.mouse_change = mouse_change
		self.holding_shift = holding_shift
		self.draw_hitboxes = draw_hitboxes
		self.top_point = None
		self.selected_point = None
		self.moused_over_point = None


class CustomShape(SelectableObject):
	list_name = "m_CustomShapes"

	def __init__(self, dictionary, anchorsList=None):
		super().__init__(dictionary)
		self.bounding_box = None
		self.bounding_box = pygame.Rect(0, 0, 0, 0)
		self.point_hitboxes = []
		self.anchors = []
		self.selected_point_index = None
		self.add_point_closest = None
		self.add_point_hitbox = None
		if anchorsList:
			for dyn_anc_id in self.dynamic_anchor_ids:
				for anchor in anchorsList:
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
		center = (leftmost + width / 2 + basepos[0], topmost + height / 2 + basepos[1])
		if align_center:
			self._dict["m_Pos"]["x"] = center[0]
			self._dict["m_Pos"]["y"] = center[1]
			points_base = [(point[0] + basepos[0] - center[0], point[1] + basepos[1] - center[1])
			               for point in points_base]
			self.points = points_base
			leftmost, rightmost = [x + basepos[0] - center[0] for x in (leftmost, rightmost)]
			topmost, bottommost = [y + basepos[1] - center[1] for y in (topmost, bottommost)]
			self._center_offset = (0, 0)
		else:
			self._center_offset = (basepos[0] - center[0], basepos[1] - center[1])

		# Create hitbox bitmap
		points_hitbox = [(round(HITBOX_RESOLUTION * (point[0] - leftmost)),
		                  round(-HITBOX_RESOLUTION * (point[1] + topmost)))
		                 for point in points_base]
		surface = pygame.Surface((HITBOX_RESOLUTION * width + 1, HITBOX_RESOLUTION * height + 1), pygame.SRCALPHA, 32)
		pygame.draw.polygon(surface, BLACK, points_hitbox)
		self._hitbox = pygame.mask.from_surface(surface)

	def render(self, display, camera, zoom, args: ShapeRenderArgs = None):
		super().render(display, camera, zoom)
		points_pixels = [(round(zoom * (self.pos[0] + point[0] + camera[0])),
		                  round(zoom * -(self.pos[1] + point[1] + camera[1])))
		                 for point in self.points]
		border_color = tuple(max(0, self.color[i] - 20) for i in range(3))
		pygame.gfxdraw.filled_polygon(display, points_pixels, self.color)
		pygame.gfxdraw.aapolygon(display, points_pixels, border_color)

		for pin in self.static_pins:
			rect = [round(zoom * (pin["x"] + camera[0])), round(zoom * -(pin["y"] + camera[1]))]
			pygame.gfxdraw.aacircle(display, rect[0], rect[1], round(zoom * PIN_RADIUS), STATIC_PIN_COLOR)
			pygame.gfxdraw.filled_circle(display, rect[0], rect[1], round(zoom * PIN_RADIUS), STATIC_PIN_COLOR)

		if self.selected:
			# TODO: Find an antialiased solution
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

	def render_points(self, display, camera, zoom, args):
		if not args.draw_points:
			return
		points = self.points
		points_pixels = [(round(zoom * (self.pos[0] + point[0] + camera[0])),
		                  round(zoom * -(self.pos[1] + point[1] + camera[1])))
		                 for point in self.points]
		# Move point if a point is selected
		for i, point in enumerate(points):
			if i == self.selected_point_index:
				newpoints = list(points)
				newpoints[i] = tuple(map(add, point, args.mouse_change))
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
			closest = [None, zoom / 7, None]
			for i in range(len(points)):
				ni = 0 if i + 1 == len(points) else i + 1
				_point = closest_point(points_pixels[i], points_pixels[ni], args.mouse_pos)
				if not _point: continue
				distance = math.sqrt((_point[0] - args.mouse_pos[0]) ** 2 + (_point[1] - args.mouse_pos[1]) ** 2)
				if distance < closest[1]:
					closest = [_point, distance, ni]
			if closest[0]:
				self.add_point_closest = closest
				self.add_point_hitbox = pygame.draw.circle(
					DUMMY_SURFACE, 0,
					(round(closest[0][0]), round(closest[0][1])), round(zoom * PIN_RADIUS / 1.7), 0
				)
				pygame.gfxdraw.aacircle(
					display, round(closest[0][0]), round(closest[0][1]), round(zoom * PIN_RADIUS / 1.7),
					ADD_POINT_COLOR)
				pygame.gfxdraw.filled_circle(
					display, round(closest[0][0]), round(closest[0][1]), round(zoom * PIN_RADIUS / 1.7),
					ADD_POINT_COLOR)
		# Update hitbox and move center to actual center
		if self.selected_point_index is not None:
			self.calculate_hitbox(True)

	def add_point(self, index, point):
		points = list(self.points)
		points.insert(index, (point[0] / self._last_zoom - self._last_camera[0] - self.pos[0],
		                      -(point[1] / self._last_zoom) - self._last_camera[1] - self.pos[1]))
		self.points = points
		self.selected_point_index = None
		self.calculate_hitbox(True)

	def del_point(self, index):
		points = list(self.points)
		points.pop(index)
		self.points = points
		self.selected_point_index = None
		self.calculate_hitbox(True)

	@SelectableObject.pos.setter
	def pos(self, value):
		change = (value[0] - self.pos[0], value[1] - self.pos[1])
		SelectableObject.pos.__set__(self, value)
		for pin in self.static_pins:
			pin["x"] += change[0]
			pin["y"] += change[1]
		for anchor in self.anchors:
			anchor.pos = (anchor.pos[0] + change[0], anchor.pos[1] + change[1])

	@property
	def rotations(self):
		"""Rotation degrees in the X, Y, and Z axis, calculated from a quaternion"""
		rot = self._dict["m_Rot"]
		return euler_angles(rot["x"], rot["y"], rot["z"], rot["w"])
	@rotations.setter
	def rotations(self, values):
		old_rotz = self.rotation
		q = quaternion(*values)
		self._dict["m_Rot"] = {"x": q[0], "y": q[1], "z": q[2], "w": q[3]}
		self._dict["m_RotationDegrees"] = values[2]
		change = self.rotation - old_rotz
		if abs(change) > 0.000001:
			basepos = self.pos
			for pin in self.static_pins:
				newpin = rotate((pin["x"], pin["y"]), change, basepos)
				pin["x"] = newpin[0]
				pin["y"] = newpin[1]
			for anchor in self.anchors:
				anchor.pos = rotate(anchor.pos, change, basepos)

	@property
	def rotation(self):
		"""Rotation degrees only in the Z axis"""
		return self._dict["m_RotationDegrees"]
	@rotation.setter
	def rotation(self, value):
		x, y, _ = self.rotations
		self.rotations = (x, y, value)

	@property
	def flipped(self) -> bool:
		return self._dict["m_Flipped"]
	@flipped.setter
	def flipped(self, value):
		old_flipped = self._dict["m_Flipped"]
		self._dict["m_Flipped"] = value
		if old_flipped != value:
			basepos = self.pos
			for pin in self.static_pins:
				newpin = rotate((pin["x"], pin["y"]), -self.rotation, basepos)
				newpin = (2 * basepos[0] - newpin[0], newpin[1])
				newpin = rotate(newpin, self.rotation, basepos)
				pin["x"] = newpin[0]
				pin["y"] = newpin[1]
			for anchor in self.anchors:
				newanchorpos = rotate(anchor.pos, -self.rotation, basepos)
				newanchorpos = (2 * basepos[0] - newanchorpos[0], newanchorpos[1])
				newanchorpos = rotate(newanchorpos, self.rotation, basepos)
				anchor.pos = newanchorpos

	@property
	def scale(self):
		return self._dict["m_Scale"]["x"], self._dict["m_Scale"]["y"], self._dict["m_Scale"]["z"]
	@scale.setter
	def scale(self, value):
		old_scale = self.scale
		if len(value) == 2:
			self._dict["m_Scale"] = {"x": value[0], "y": value[1], "z": self._dict["m_Scale"]["z"]}
		else:
			self._dict["m_Scale"] = {"x": value[0], "y": value[1], "z": value[2]}
		change = (value[0] / old_scale[0], value[1] / old_scale[1])
		if abs(change[0] - 1) > 0.000001 or abs(change[1] - 1) > 0.000001:
			basepos = self.pos
			for pin in self.static_pins:
				pin["x"] = ((pin["x"] - basepos[0]) * change[0] + basepos[0])
				pin["y"] = ((pin["y"] - basepos[1]) * change[1] + basepos[1])
			for anchor in self.anchors:
				anchor.pos = (((anchor.pos[0] - basepos[0]) * change[0] + basepos[0]),
				              ((anchor.pos[1] - basepos[1]) * change[1] + basepos[1]))

	@property
	def color(self):
		return tuple(round(v*255) for v in self._dict["m_Color"].values())
	@color.setter
	def color(self, value):
		self._dict["m_Color"] = {"r": value[0]/255, "g": value[1]/255, "b": value[2]/255, "a": value[3]/255}

	@property
	def points(self):
		pts = []
		pts_scale = self.scale
		for p in self._dict["m_PointsLocalSpace"]:
			point = (p["x"] * pts_scale[0], p["y"] * pts_scale[1])
			if self.flipped:
				point = (-point[0], point[1])
			point = rotate(point, self.rotation)
			pts.append(point)
		return tuple(pts)
	@points.setter
	def points(self, values):
		values = [rotate(p, -self.rotation) for p in values]
		pts_scale = self.scale
		if self.flipped:
			values = [(-p[0], p[1]) for p in values]
		self._dict["m_PointsLocalSpace"] = [{"x": p[0] / pts_scale[0], "y": p[1] / pts_scale[1]} for p in values]

	@property
	def static_pins(self):
		return self._dict["m_StaticPins"]
	@static_pins.setter
	def static_pins(self, values):
		self._dict["m_StaticPins"] = values

	@property
	def dynamic_anchor_ids(self):
		return self._dict["m_DynamicAnchorGuids"]
	@dynamic_anchor_ids.setter
	def dynamic_anchor_ids(self, values):
		self._dict["m_DynamicAnchorGuids"] = values


class CustomShapePoint:
	def __init__(self, pos, index, radius):
		self.pos = pos
		self.index = index
		self.radius = radius

	def render(self, display, color, radius=None):
		if radius is None:
			radius = self.radius
		border_color = tuple(max(0, color[i] - 50) for i in range(3))
		pygame.gfxdraw.filled_circle(display, self.pos[0], self.pos[1], radius, color)
		pygame.gfxdraw.aacircle(display, self.pos[0], self.pos[1], radius, border_color)

	def collidepoint(self, point):
		return math.sqrt((point[0] - self.pos[0]) ** 2 + (point[1] - self.pos[1]) ** 2) <= self.radius
