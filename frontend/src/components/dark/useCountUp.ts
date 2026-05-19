/**
 * useCountUp — anima um número de 0 até ao alvo com easing ease-out cubic.
 *
 * Port fiel do hook `useCountUp` do design NELO.html (atoms.jsx). Usado
 * pelo `KPIBig` para a entrada animada do valor. Respeita
 * prefers-reduced-motion: quem desliga animações vê o valor final logo.
 *
 * Sprint Q.52.B.
 */

import { useEffect, useState } from 'react';

export function useCountUp(target: number, duration = 800): number {
  const [value, setValue] = useState(0);

  useEffect(() => {
    const reduced =
      typeof window !== 'undefined' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduced) {
      setValue(target);
      return;
    }
    let raf = 0;
    const start = performance.now();
    const tick = (t: number): void => {
      const p = Math.min(1, (t - start) / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      setValue(target * eased);
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);

  return value;
}
