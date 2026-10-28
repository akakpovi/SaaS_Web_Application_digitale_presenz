import { useEffect, useRef } from "react"

interface Orb {
  x: number
  y: number
  vx: number
  vy: number
  radius: number
  hue: number
  saturation: number
  lightness: number
  alpha: number
  phase: number
  phaseSpeed: number
}

interface Props {
  className?: string
  orbCount?: number
  /** hsl hues to cycle through, e.g. [220, 260, 200] */
  hues?: number[]
  blur?: number
}

export default function AuroraBackground({
  className = "",
  orbCount = 6,
  hues = [220, 260, 195, 280, 210, 240],
  blur = 80,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const orbsRef = useRef<Orb[]>([])
  const rafRef = useRef<number>(0)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext("2d")
    if (!ctx) return

    let W = 0
    let H = 0

    function resize() {
      if (!canvas) return
      W = canvas.offsetWidth
      H = canvas.offsetHeight
      canvas.width = W
      canvas.height = H
    }

    function spawn(): Orb {
      const hue = hues[Math.floor(Math.random() * hues.length)]
      return {
        x: Math.random() * W,
        y: Math.random() * H,
        vx: (Math.random() - 0.5) * 0.35,
        vy: (Math.random() - 0.5) * 0.35,
        radius: 180 + Math.random() * 220,
        hue,
        saturation: 75 + Math.random() * 20,
        lightness: 52 + Math.random() * 18,
        alpha: 0.45 + Math.random() * 0.3,
        phase: Math.random() * Math.PI * 2,
        phaseSpeed: 0.003 + Math.random() * 0.004,
      }
    }

    resize()
    orbsRef.current = Array.from({ length: orbCount }, spawn)

    const ro = new ResizeObserver(resize)
    ro.observe(canvas)

    function draw() {
      if (!ctx || !canvas) return
      ctx.clearRect(0, 0, W, H)

      for (const orb of orbsRef.current) {
        orb.phase += orb.phaseSpeed

        // Slow sinusoidal drift layered on linear velocity
        orb.x += orb.vx + Math.sin(orb.phase * 0.7) * 0.18
        orb.y += orb.vy + Math.cos(orb.phase * 0.5) * 0.18

        // Soft wrap-around
        if (orb.x < -orb.radius) orb.x = W + orb.radius
        if (orb.x > W + orb.radius) orb.x = -orb.radius
        if (orb.y < -orb.radius) orb.y = H + orb.radius
        if (orb.y > H + orb.radius) orb.y = -orb.radius

        // Pulsing alpha
        const a = orb.alpha + Math.sin(orb.phase * 1.3) * 0.12

        const gradient = ctx.createRadialGradient(
          orb.x,
          orb.y,
          0,
          orb.x,
          orb.y,
          orb.radius,
        )
        gradient.addColorStop(
          0,
          `hsla(${orb.hue}, ${orb.saturation}%, ${orb.lightness}%, ${a})`,
        )
        gradient.addColorStop(
          0.45,
          `hsla(${orb.hue + 15}, ${orb.saturation - 5}%, ${orb.lightness - 8}%, ${a * 0.55})`,
        )
        gradient.addColorStop(
          1,
          `hsla(${orb.hue + 30}, ${orb.saturation}%, ${orb.lightness}%, 0)`,
        )

        ctx.globalCompositeOperation = "screen"
        ctx.fillStyle = gradient
        ctx.beginPath()
        ctx.arc(orb.x, orb.y, orb.radius, 0, Math.PI * 2)
        ctx.fill()
      }

      rafRef.current = requestAnimationFrame(draw)
    }

    rafRef.current = requestAnimationFrame(draw)

    return () => {
      cancelAnimationFrame(rafRef.current)
      ro.disconnect()
    }
  }, [orbCount, hues])

  return (
    <canvas
      ref={canvasRef}
      className={`absolute inset-0 w-full h-full ${className}`}
      style={{ filter: `blur(${blur}px)`, transform: "scale(1.05)" }}
      aria-hidden="true"
    />
  )
}
