"""EGL CAD visibility, RGB shading and metric XYZ from the same GPU rasterization."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

import numpy as np
from articulated_filterreg.geometry import CadModel, State

VERTEX_SHADER = '''
#version 330
in vec3 position;
in float level;
in float kind;
uniform mat4 transforms[BODY_COUNT];
uniform vec4 intrinsics;
uniform vec2 image_size;
out vec3 camera_position;
flat out float body;
flat out float material;
void main() {
    vec3 p = (transforms[int(level)] * vec4(position, 1.0)).xyz;
    camera_position = p;
    body = level;
    material = kind;
    float near = 0.02, far = 10.0;
    gl_Position = vec4(
        2.0 * intrinsics.x / image_size.x * p.x
            + (2.0 * (intrinsics.z + 0.5) / image_size.x - 1.0) * p.z,
        -2.0 * intrinsics.y / image_size.y * p.y
            + (1.0 - 2.0 * (intrinsics.w + 0.5) / image_size.y) * p.z,
        (far + near) / (far - near) * p.z - 2.0 * far * near / (far - near), p.z);
}
'''

FRAGMENT_SHADER = '''
#version 330
in vec3 camera_position;
flat in float body;
flat in float material;
layout(location=0) out vec4 color;
layout(location=1) out vec4 xyz_body;
void main() {
    vec3 normal = normalize(cross(dFdx(camera_position), dFdy(camera_position)));
    float lighting = 0.55 + 0.45 * abs(dot(normal, normalize(vec3(-0.3, -0.5, -1.0))));
    vec3 albedo = material > 0.5 ? vec3(0.90, 0.93, 0.95) : vec3(0.17, 0.19, 0.22);
    color = vec4(albedo * lighting, 1.0);
    xyz_body = vec4(camera_position, body + 1.0);
}
'''


@dataclass(frozen=True)
class Rendered:
    rgb: np.ndarray
    xyz: np.ndarray
    levels: np.ndarray
    mask: np.ndarray


class CadRenderer:
    def __init__(self, model: CadModel, width: int, height: int):
        import moderngl

        self.model = model
        self.width, self.height = width, height
        self.last_key: tuple | None = None
        self.last_rendering: Rendered | None = None
        # ModernGL's installed stub incorrectly types every **setting as a dict;
        # the tested runtime constructor accepts backend='egl' as documented.
        create = cast(Callable[..., moderngl.Context], moderngl.create_standalone_context)
        self.ctx = create(backend='egl')
        self.device = self.ctx.info['GL_RENDERER']
        self.program = self.ctx.program(
            vertex_shader=VERTEX_SHADER.replace('BODY_COUNT', str(len(model.chain.pivots) + 1)),
            fragment_shader=FRAGMENT_SHADER,
        )
        kinds = np.zeros(len(model.vertices), np.float32)
        kinds[model.faces] = model.face_kind[:, None]
        data = np.column_stack((model.vertices, model.vertex_level, kinds)).astype(np.float32)
        self.vbo = self.ctx.buffer(data.tobytes())
        self.ibo = self.ctx.buffer(np.asarray(model.faces, dtype=np.int32).tobytes())
        self.vao = self.ctx.vertex_array(self.program, [
            (self.vbo, '3f 1f 1f', 'position', 'level', 'kind'),
        ], self.ibo)
        self.color = self.ctx.texture((width, height), 4, dtype='f1')
        self.xyz = self.ctx.texture((width, height), 4, dtype='f4')
        self.depth = self.ctx.depth_renderbuffer((width, height))
        self.fbo = self.ctx.framebuffer([self.color, self.xyz], self.depth)
        self.ctx.enable(moderngl.DEPTH_TEST)
        self.transform_uniform: moderngl.Uniform = cast(
            moderngl.Uniform, self.program['transforms'])
        self.intrinsic_uniform: moderngl.Uniform = cast(
            moderngl.Uniform, self.program['intrinsics'])
        image_uniform = self.program['image_size']
        assert isinstance(self.transform_uniform, moderngl.Uniform)
        assert isinstance(self.intrinsic_uniform, moderngl.Uniform)
        assert isinstance(image_uniform, moderngl.Uniform)
        image_uniform.value = (float(width), float(height))

    def render(self, state: State, K: np.ndarray) -> Rendered:
        # Tracking starts from the previous final quality render. Cache by value,
        # not object identity: State/K contain arrays that callers could mutate.
        key = (state.rotation.tobytes(), state.translation.tobytes(),
               state.log_scale, state.joints.tobytes(), K.tobytes())
        if key == self.last_key and self.last_rendering is not None:
            return self.last_rendering
        transforms = self.model.chain.transforms(state).astype(np.float32)
        self.transform_uniform.write(transforms.transpose(0, 2, 1).tobytes())
        self.intrinsic_uniform.value = tuple(
            float(v) for v in (K[0, 0], K[1, 1], K[0, 2], K[1, 2]))
        self.fbo.use()
        self.fbo.clear(0, 0, 0, 0, depth=1)
        self.vao.render()
        xyz = np.frombuffer(self.xyz.read(), np.float32).reshape(self.height, self.width, 4)[::-1]
        rgb = np.frombuffer(self.color.read(), np.uint8).reshape(self.height, self.width, 4)[::-1]
        rendered = Rendered(rgb[:, :, :3], xyz[:, :, :3],
                            np.rint(xyz[:, :, 3] - 1).astype(np.int32), xyz[:, :, 3] > .5)
        for pixels in (rendered.rgb, rendered.xyz, rendered.levels, rendered.mask):
            pixels.setflags(write=False)
        self.last_key, self.last_rendering = key, rendered
        return rendered

    def close(self) -> None:
        for item in (self.vao, self.fbo, self.color, self.xyz, self.depth, self.vbo,
                     self.ibo, self.program, self.ctx):
            item.release()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
