/* Three.js forge — a full-bleed smolder field with rising embers.
   Two passes on one canvas: an orthographic background quad running an
   fbm "molten floor" shader, then a perspective ember particle pass.
   The pointer is a bellows: heat blooms under it in the shader and
   nearby embers get a gust. Fails silent (no WebGL -> the CSS gradient
   behind the canvas simply stays), renders one still frame under
   prefers-reduced-motion, and pauses whenever it is off-screen. */
import { useEffect, useRef } from "react";
import * as THREE from "three";

export interface ForgeSceneProps {
  /** 0..1 scroll progress through the host section (dampens the heat). */
  progress?: React.MutableRefObject<number>;
  /** Ember particle count. */
  density?: number;
  /** Molten floor intensity, 0..1. */
  floor?: number;
  /** Called after the first frame renders. */
  onReady?: () => void;
}

const FLAME_COLORS = ["#e8722c", "#d96328", "#c2551b", "#f2a16b", "#ffb36b"];

const BG_VERTEX = /* glsl */ `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = vec4(position.xy, 0.0, 1.0);
  }
`;

const BG_FRAGMENT = /* glsl */ `
  precision highp float;
  uniform float uTime;
  uniform vec2 uRes;
  uniform vec2 uPointer;   // uv space, y up
  uniform float uScroll;   // 0..1, hero scrolled away
  uniform float uFloor;    // molten floor intensity
  varying vec2 vUv;

  float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
  }
  float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(
      mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x),
      mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x),
      u.y
    );
  }
  float fbm(vec2 p) {
    float v = 0.0;
    float a = 0.5;
    for (int i = 0; i < 4; i++) {
      v += a * noise(p);
      p = p * 2.03 + vec2(17.3, 9.1);
      a *= 0.5;
    }
    return v;
  }

  void main() {
    vec2 uv = vUv;
    float aspect = uRes.x / max(uRes.y, 1.0);
    vec2 p = vec2(uv.x * aspect, uv.y);

    // charcoal base, a touch warmer near the floor
    vec3 col = mix(vec3(0.055, 0.046, 0.038), vec3(0.075, 0.062, 0.052), 1.0 - uv.y);

    // smolder field rising off the floor
    float n = fbm(vec2(p.x * 2.1, p.y * 3.2 - uTime * 0.07));
    float floorMask = pow(clamp(1.0 - uv.y * 1.4, 0.0, 1.0), 2.1);
    float smolder = floorMask * (0.30 + 0.70 * n) * uFloor;

    // two deep glow pools drifting along the floor
    vec2 g1 = vec2((0.24 + 0.07 * sin(uTime * 0.10)) * aspect, 0.12 + 0.04 * cos(uTime * 0.13));
    vec2 g2 = vec2((0.76 + 0.06 * cos(uTime * 0.08)) * aspect, 0.08 + 0.05 * sin(uTime * 0.11));
    float pools = 0.55 * exp(-dot(p - g1, p - g1) * 6.0) + 0.45 * exp(-dot(p - g2, p - g2) * 7.0);
    pools *= uFloor * (0.7 + 0.3 * n);

    // pointer bellows — a breathing heat bloom under the cursor
    vec2 pp = vec2(uPointer.x * aspect, uPointer.y);
    float d = distance(p, pp);
    float heat = exp(-d * d * 9.0) * 0.28 * (0.85 + 0.15 * sin(uTime * 2.6));
    heat *= 1.0 - uScroll * 0.7;

    vec3 flameDeep = vec3(0.52, 0.16, 0.030);
    vec3 flameHot  = vec3(1.00, 0.50, 0.16);

    col += flameDeep * (smolder * 0.95 + pools * 0.75);
    col += flameHot * smolder * n * 0.38;
    col += mix(flameDeep, flameHot, 0.55) * heat;

    // vignette + grain (kills banding on the long gradients)
    float vig = smoothstep(1.35, 0.30, length(uv - vec2(0.5, 0.45)));
    col *= mix(0.82, 1.0, vig);
    col += (hash(uv * uRes + mod(uTime, 10.0)) - 0.5) * 0.016;

    gl_FragColor = vec4(col, 1.0);
    #include <colorspace_fragment>
  }
`;

/** Soft round sprite for ember particles. */
function emberTexture(): THREE.Texture {
  const size = 64;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d")!;
  const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  g.addColorStop(0, "rgba(255,255,255,1)");
  g.addColorStop(0.35, "rgba(255,255,255,0.75)");
  g.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

export default function ForgeScene({ progress, density = 320, floor = 1, onReady }: ForgeSceneProps) {
  const mountRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = mountRef.current;
    if (!el) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: false, powerPreference: "high-performance" });
    } catch {
      return; // no WebGL — the CSS gradient behind the canvas stays
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(el.clientWidth, el.clientHeight);
    renderer.autoClear = false;
    renderer.domElement.style.display = "block";
    el.appendChild(renderer.domElement);

    // ---- pass 1: background smolder quad ---------------------------------
    const bgScene = new THREE.Scene();
    const bgCamera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
    const bgUniforms = {
      uTime: { value: reduced ? 4.0 : 0 },
      uRes: { value: new THREE.Vector2(el.clientWidth, el.clientHeight) },
      uPointer: { value: new THREE.Vector2(0.5, 0.35) },
      uScroll: { value: 0 },
      uFloor: { value: floor },
    };
    const bgQuad = new THREE.Mesh(
      new THREE.PlaneGeometry(2, 2),
      new THREE.ShaderMaterial({ uniforms: bgUniforms, vertexShader: BG_VERTEX, fragmentShader: BG_FRAGMENT, depthTest: false, depthWrite: false }),
    );
    bgScene.add(bgQuad);

    // ---- pass 2: embers ---------------------------------------------------
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(40, el.clientWidth / el.clientHeight, 0.1, 60);
    camera.position.set(0, 0, 9);

    const emberGeo = new THREE.BufferGeometry();
    const positions = new Float32Array(density * 3);
    const colors = new Float32Array(density * 3);
    const seeds = new Float32Array(density * 3); // rise speed, sway phase, gust
    const color = new THREE.Color();
    for (let i = 0; i < density; i++) {
      positions[i * 3] = (Math.random() - 0.5) * 17;
      positions[i * 3 + 1] = (Math.random() - 0.5) * 11;
      positions[i * 3 + 2] = -3 + Math.random() * 5;
      color.set(FLAME_COLORS[i % FLAME_COLORS.length]);
      colors[i * 3] = color.r;
      colors[i * 3 + 1] = color.g;
      colors[i * 3 + 2] = color.b;
      seeds[i * 3] = 0.2 + Math.random() * 0.9;
      seeds[i * 3 + 1] = Math.random() * Math.PI * 2;
      seeds[i * 3 + 2] = 0;
    }
    emberGeo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    emberGeo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    const embers = new THREE.Points(
      emberGeo,
      new THREE.PointsMaterial({
        size: 0.085,
        map: emberTexture(),
        vertexColors: true,
        transparent: true,
        opacity: 0.9,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
        sizeAttenuation: true,
      }),
    );
    scene.add(embers);

    // ---- resize -----------------------------------------------------------
    const layout = () => {
      const w = el.clientWidth;
      const h = el.clientHeight;
      renderer.setSize(w, h);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      bgUniforms.uRes.value.set(w, h);
      // narrow screens: thin the fog so the copy stays crisp
      bgUniforms.uFloor.value = floor * (w < 640 ? 0.7 : 1);
    };
    layout();
    const ro = new ResizeObserver(layout);
    ro.observe(el);

    // ---- pointer ----------------------------------------------------------
    const pointer = { x: 0.5, y: 0.35, tx: 0.5, ty: 0.35 };
    const onPointer = (e: PointerEvent) => {
      const r = el.getBoundingClientRect();
      pointer.tx = (e.clientX - r.left) / r.width;
      pointer.ty = 1 - (e.clientY - r.top) / r.height;
    };
    el.ownerDocument.addEventListener("pointermove", onPointer, { passive: true });

    // ---- render loop ------------------------------------------------------
    const clock = new THREE.Clock();
    let raf = 0;
    let visible = true;
    let readyFired = false;

    const io = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
    });
    io.observe(el);

    const renderFrame = () => {
      renderer.clear();
      renderer.render(bgScene, bgCamera);
      renderer.render(scene, camera);
      if (!readyFired) {
        readyFired = true;
        onReady?.();
      }
    };

    const tick = () => {
      raf = requestAnimationFrame(tick);
      if (!visible) return;
      const t = clock.getElapsedTime();
      const p = progress?.current ?? 0;

      // smooth the pointer so the bloom trails like real heat
      pointer.x += (pointer.tx - pointer.x) * 0.06;
      pointer.y += (pointer.ty - pointer.y) * 0.06;
      bgUniforms.uPointer.value.set(pointer.x, pointer.y);
      bgUniforms.uTime.value = t;
      bgUniforms.uScroll.value = p;

      // pointer world position at z=0 for the ember gust
      const halfH = Math.tan((camera.fov * Math.PI) / 360) * camera.position.z;
      const halfW = halfH * camera.aspect;
      const px = (pointer.x * 2 - 1) * halfW;
      const py = (pointer.y * 2 - 1) * halfH;

      const pos = emberGeo.attributes.position.array as Float32Array;
      for (let i = 0; i < density; i++) {
        const speed = seeds[i * 3];
        const phase = seeds[i * 3 + 1];
        // bellows gust: embers near the pointer get pushed up and out
        const dx = pos[i * 3] - px;
        const dy = pos[i * 3 + 1] - py;
        const dist2 = dx * dx + dy * dy;
        if (dist2 < 4) {
          seeds[i * 3 + 2] = Math.min(1.6, seeds[i * 3 + 2] + 0.06 * (1 - dist2 / 4));
        }
        seeds[i * 3 + 2] *= 0.96; // gust decays
        const gust = seeds[i * 3 + 2];

        pos[i * 3 + 1] += speed * 0.011 + gust * 0.05;
        pos[i * 3] += Math.sin(t * 0.9 + phase) * 0.0032 + (dist2 < 4 ? (dx / (Math.sqrt(dist2) + 0.2)) * gust * 0.012 : 0);
        if (pos[i * 3 + 1] > 6) {
          pos[i * 3 + 1] = -6;
          pos[i * 3] = (Math.random() - 0.5) * 17;
        }
      }
      emberGeo.attributes.position.needsUpdate = true;

      // slow camera drift toward the pointer
      camera.position.x += ((pointer.x * 2 - 1) * 0.45 - camera.position.x) * 0.03;
      camera.position.y += ((pointer.y * 2 - 1) * 0.28 - camera.position.y) * 0.03;
      camera.lookAt(0, 0, 0);

      renderFrame();
    };

    if (reduced) {
      renderFrame();
    } else {
      tick();
    }

    return () => {
      cancelAnimationFrame(raf);
      io.disconnect();
      ro.disconnect();
      el.ownerDocument.removeEventListener("pointermove", onPointer);
      emberGeo.dispose();
      (embers.material as THREE.PointsMaterial).map?.dispose();
      (embers.material as THREE.Material).dispose();
      bgQuad.geometry.dispose();
      (bgQuad.material as THREE.Material).dispose();
      renderer.dispose();
      renderer.domElement.remove();
    };
    // progress is a ref (stable); density/floor changes never happen mid-flight
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return <div ref={mountRef} className="absolute inset-0" aria-hidden="true" />;
}
