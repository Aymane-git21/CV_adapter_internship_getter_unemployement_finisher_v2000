/* Three.js hero — the tailored CV floating over a bed of rising embers.
   Pointer parallax, a shader burn-in (the page ignites from its edges and
   the glow front reveals the content), and a scroll-linked camera pull.
   Fails silent (no WebGL -> static fallback stays visible), renders one
   still frame under prefers-reduced-motion, and pauses whenever the hero
   is off-screen. */
import { useEffect, useRef } from "react";
import * as THREE from "three";
import heroCv from "../assets/hero_cv.jpg";

export interface HeroSceneProps {
  /** 0..1 scroll progress through the hero, written by the page's ScrollTrigger. */
  progress: React.MutableRefObject<number>;
  /** Called after the first frame renders — the page fades its static fallback. */
  onReady?: () => void;
}

const EMBER_COUNT = 260;
const FLAME_COLORS = ["#e8722c", "#d96328", "#c2551b", "#d92638", "#f2a16b"];

/* Burn-in reveal: a glow front creeps from the sheet edges toward the
   center (sides lead), the content brightens to full where it has passed,
   and a noisy flame band marks the moving frontier. 9s loop: ~6.5s burn,
   then a fully-lit hold. Flame colors are #e8722c/#f2a16b in linear space
   (colorspace_fragment converts the final color for output). */
const BURN_VERTEX = /* glsl */ `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const BURN_FRAGMENT = /* glsl */ `
  uniform sampler2D uMap;
  uniform float uTime;
  uniform float uOpacity;
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

  void main() {
    vec3 tex = texture2D(uMap, vUv).rgb;

    // distance to the nearest edge; x weighs less so the sides lead
    float dx = min(vUv.x, 1.0 - vUv.x);
    float dy = min(vUv.y, 1.0 - vUv.y);
    float d = min(dx, dy * 1.6);

    // 9s cycle: the front travels inward for ~6.5s, then holds fully lit
    float cyc = mod(uTime, 9.0);
    float front = smoothstep(0.0, 6.5, cyc) * 0.78;

    float grain = noise(vUv * 9.0 + uTime * 0.25) * 0.09; // organic frontier
    float dd = d + grain;

    float lit = smoothstep(front, front - 0.16, dd);
    float band = exp(-pow((dd - front) / 0.045, 2.0));

    vec3 flameA = vec3(0.807, 0.168, 0.025);
    vec3 flameB = vec3(0.888, 0.356, 0.147);

    vec3 unlit = tex * 0.55 + vec3(0.045, 0.018, 0.004); // dim, warm paper
    vec3 col = mix(unlit, tex, lit);
    col += band * mix(flameA, flameB, noise(vUv * 5.0 + uTime * 0.6)) * 0.9;
    col += smoothstep(0.10, 0.0, d) * 0.22 * flameA;     // constant side rim

    gl_FragColor = vec4(col, uOpacity);
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
  g.addColorStop(0.4, "rgba(255,255,255,0.8)");
  g.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

/** Big warm radial glow behind the paper. */
function glowTexture(): THREE.Texture {
  const size = 256;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d")!;
  const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  g.addColorStop(0, "rgba(232,114,44,0.55)");
  g.addColorStop(0.5, "rgba(232,114,44,0.18)");
  g.addColorStop(1, "rgba(232,114,44,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

export default function HeroScene({ progress, onReady }: HeroSceneProps) {
  const mountRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = mountRef.current;
    if (!el) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: "high-performance" });
    } catch {
      return; // no WebGL — the DOM fallback simply stays
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(el.clientWidth, el.clientHeight);
    renderer.domElement.style.display = "block";
    el.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(40, el.clientWidth / el.clientHeight, 0.1, 60);
    camera.position.set(0, 0, 9);

    // ---- the paper stack -------------------------------------------------
    const paper = new THREE.Group();
    scene.add(paper);

    const loader = new THREE.TextureLoader();
    const cvTex = loader.load(heroCv, () => renderOnce());
    cvTex.colorSpace = THREE.SRGBColorSpace;
    cvTex.anisotropy = renderer.capabilities.getMaxAnisotropy();

    const sheetGeo = new THREE.PlaneGeometry(3.1, 3.1 * 1.29);
    const burnUniforms = {
      uMap: { value: cvTex },
      uTime: { value: 7.5 }, // fully-lit phase — the reduced-motion still frame
      uOpacity: { value: 1 },
    };
    const front = new THREE.Mesh(
      sheetGeo,
      new THREE.ShaderMaterial({
        uniforms: burnUniforms,
        vertexShader: BURN_VERTEX,
        fragmentShader: BURN_FRAGMENT,
        transparent: true,
      }),
    );
    front.renderOrder = 2;
    paper.add(front);

    // two cream sheets fanned behind
    const backMat = new THREE.MeshBasicMaterial({ color: 0xfcfaf7, transparent: true, opacity: 0.85 });
    [[-0.28, -0.22, -0.35, 0.1], [0.3, -0.14, -0.7, -0.08]].forEach(([x, y, z, rz]) => {
      const m = new THREE.Mesh(sheetGeo, backMat.clone());
      m.position.set(x, y, z);
      m.rotation.z = rz;
      m.renderOrder = 1;
      paper.add(m);
    });

    // warm glow behind the stack
    const glow = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture(), transparent: true, depthWrite: false }));
    glow.scale.setScalar(9);
    glow.position.z = -1.4;
    paper.add(glow);

    // ---- embers ----------------------------------------------------------
    const emberGeo = new THREE.BufferGeometry();
    const positions = new Float32Array(EMBER_COUNT * 3);
    const colors = new Float32Array(EMBER_COUNT * 3);
    const seeds = new Float32Array(EMBER_COUNT * 2); // speed, sway phase
    const color = new THREE.Color();
    for (let i = 0; i < EMBER_COUNT; i++) {
      positions[i * 3] = (Math.random() - 0.5) * 16;
      positions[i * 3 + 1] = (Math.random() - 0.5) * 10;
      positions[i * 3 + 2] = -2.5 + Math.random() * 4;
      color.set(FLAME_COLORS[i % FLAME_COLORS.length]);
      colors[i * 3] = color.r;
      colors[i * 3 + 1] = color.g;
      colors[i * 3 + 2] = color.b;
      seeds[i * 2] = 0.25 + Math.random() * 0.8;
      seeds[i * 2 + 1] = Math.random() * Math.PI * 2;
    }
    emberGeo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    emberGeo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    const embers = new THREE.Points(
      emberGeo,
      new THREE.PointsMaterial({
        size: 0.09,
        map: emberTexture(),
        vertexColors: true,
        transparent: true,
        opacity: 0.85,
        depthWrite: false,
        sizeAttenuation: true,
      }),
    );
    scene.add(embers);

    // ---- layout: paper sits right on wide screens, centered on small ----
    const layout = () => {
      const w = el.clientWidth;
      const h = el.clientHeight;
      renderer.setSize(w, h);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      const wide = w >= 1024;
      paper.position.x = wide ? 2.6 : 0;
      paper.scale.setScalar(wide ? 1 : Math.min(0.85, w / 700));
      burnUniforms.uOpacity.value = wide ? 1 : 0.28;
      paper.children.forEach((child) => {
        if (child === (front as THREE.Object3D)) return;
        const mesh = child as THREE.Mesh<THREE.PlaneGeometry, THREE.MeshBasicMaterial>;
        if (mesh.material && "opacity" in mesh.material) {
          mesh.material.opacity = wide ? 0.85 : 0.2;
        }
      });
    };
    layout();
    const ro = new ResizeObserver(layout);
    ro.observe(el);

    // ---- pointer parallax ------------------------------------------------
    const pointer = { x: 0, y: 0 };
    const onPointer = (e: PointerEvent) => {
      const r = el.getBoundingClientRect();
      pointer.x = ((e.clientX - r.left) / r.width) * 2 - 1;
      pointer.y = ((e.clientY - r.top) / r.height) * 2 - 1;
    };
    el.ownerDocument.addEventListener("pointermove", onPointer, { passive: true });

    // ---- render loop -----------------------------------------------------
    const clock = new THREE.Clock();
    let raf = 0;
    let visible = true;
    let readyFired = false;

    const io = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
    });
    io.observe(el);

    const renderOnce = () => renderer.render(scene, camera);

    const tick = () => {
      raf = requestAnimationFrame(tick);
      if (!visible) return;
      const t = clock.getElapsedTime();
      const p = progress.current;

      // embers rise, sway, wrap
      const pos = emberGeo.attributes.position.array as Float32Array;
      for (let i = 0; i < EMBER_COUNT; i++) {
        const speed = seeds[i * 2];
        const phase = seeds[i * 2 + 1];
        pos[i * 3 + 1] += speed * 0.012;
        pos[i * 3] += Math.sin(t * 0.9 + phase) * 0.0035;
        if (pos[i * 3 + 1] > 5.4) pos[i * 3 + 1] = -5.4;
      }
      emberGeo.attributes.position.needsUpdate = true;

      // paper breathes and follows the pointer
      paper.rotation.z = 0.03 + Math.sin(t * 0.5) * 0.012;
      paper.rotation.y = pointer.x * 0.14;
      paper.rotation.x = -pointer.y * 0.08;
      paper.position.y = Math.sin(t * 0.8) * 0.08 + p * 3.2;

      // burn-in reveal: the shader keys everything off elapsed time
      burnUniforms.uTime.value = t;

      // camera drift + scroll pull-back
      camera.position.x += (pointer.x * 0.5 - camera.position.x) * 0.04;
      camera.position.y += (-pointer.y * 0.3 - camera.position.y) * 0.04;
      camera.position.z = 9 + p * 4;
      camera.lookAt(0, 0, 0);

      renderer.render(scene, camera);
      if (!readyFired) {
        readyFired = true;
        onReady?.();
      }
    };

    if (reduced) {
      renderOnce();
      onReady?.();
    } else {
      tick();
    }

    return () => {
      cancelAnimationFrame(raf);
      io.disconnect();
      ro.disconnect();
      el.ownerDocument.removeEventListener("pointermove", onPointer);
      scene.traverse((obj) => {
        const mesh = obj as THREE.Mesh;
        if (mesh.geometry) mesh.geometry.dispose();
        const mat = (mesh as THREE.Mesh).material as THREE.Material | THREE.Material[] | undefined;
        if (Array.isArray(mat)) mat.forEach((m) => m.dispose());
        else mat?.dispose();
      });
      cvTex.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    };
    // progress is a ref (stable), onReady changes are irrelevant mid-flight
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return <div ref={mountRef} className="absolute inset-0" aria-hidden="true" />;
}
