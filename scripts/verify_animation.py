from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check the generated pendulum fixture in a sandboxed browser iframe"
    )
    parser.add_argument("--space", type=int, required=True)
    parser.add_argument("--page", default="p1")
    parser.add_argument("--templates", type=Path, default=Path("data/verification/templates.json"))
    args = parser.parse_args()
    html = json.loads(args.templates.read_text())["animation"]["content"]["html"]
    script = """
const task = await taskSpace(SPACE);
const page = task.page(PAGE);
const result = await page.evaluate(async (html) => {
  const frame = document.createElement('iframe');
  frame.setAttribute('sandbox', 'allow-scripts');
  frame.hidden = true;
  const sampleCode = `
    const samples = [];
    try {
      for (let t = 0; t <= 6000; t += 50) {
        const fn = window.__npFrames.shift();
        if (!fn) throw new Error('No animation frame scheduled');
        fn(t);
        const bob = document.getElementById('bob');
        samples.push({t, x:Number(bob.getAttribute('cx')), y:Number(bob.getAttribute('cy'))});
      }
      parent.postMessage({kind:'neuropace-motion-check', samples}, '*');
    } catch (error) { parent.postMessage({kind:'neuropace-motion-check', error:String(error)}, '*'); }
  `;
  const result = new Promise((resolve, reject) => {
    const timer = setTimeout(() => { cleanup(); reject(new Error('Animation fixture timed out')); }, 5000);
    const listener = (event) => {
      if (event.source !== frame.contentWindow || event.data?.kind !== 'neuropace-motion-check') return;
      clearTimeout(timer);
      cleanup();
      resolve(event.data);
    };
    function cleanup() { window.removeEventListener('message', listener); frame.remove(); }
    window.addEventListener('message', listener);
  });
  frame.srcdoc = `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'none'; base-uri 'none'; form-action 'none'">
    <script>window.__npFrames=[];window.requestAnimationFrame=fn=>window.__npFrames.push(fn);</script>` + html + `<script>${sampleCode}</script>`;
  document.body.append(frame);
  return result;
}, HTML);
if (result.error) throw new Error(result.error);
const samples = result.samples;
const at = t => samples.find(s => s.t === t);
const pivot = 300;
const xs = samples.map(s=>s.x);
if (!(Math.min(...xs) < pivot - 1 && Math.max(...xs) > pivot + 1)) throw new Error('Pendulum does not swing to both sides');
if (![0,3000,6000].every(t=>Math.abs(at(t).x-pivot)<1)) throw new Error('Pendulum does not cross the bottom every half cycle');
if (!(at(0).y > at(1500).y && at(3000).y > at(4500).y)) throw new Error('Pendulum does not rise at both ends');
const middleSpeed = Math.abs(at(50).x-at(0).x);
const endSpeed = Math.abs(at(1500).x-at(1450).x);
if (!(middleSpeed > 5*endSpeed)) throw new Error('Pendulum must slow at the extreme and move fastest at the bottom');
console.log({result:'ANIMATION MOTION PASS', frames:samples.length, minX:Math.min(...xs),maxX:Math.max(...xs),middleSpeed,endSpeed});
"""
    script = script.replace("SPACE", str(args.space)).replace("PAGE", json.dumps(args.page))
    script = script.replace("HTML", json.dumps(html))
    subprocess.run(["ego-browser", "nodejs"], input=script, text=True, check=True, timeout=30)


if __name__ == "__main__":
    main()
