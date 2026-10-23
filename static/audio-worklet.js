// Mic capture: downsample to 16 kHz 16-bit PCM mono, post ~40 ms chunks plus a level for the meter.
class CaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.ratio = sampleRate / 16000;
    this.chunk = new Int16Array(640);
    this.length = 0;
    this.position = 0;
  }

  process([input]) {
    const samples = input[0];
    if (!samples) return true;
    let sumSquares = 0;
    for (; this.position < samples.length; this.position += this.ratio) {
      const s = Math.max(-1, Math.min(1, samples[Math.floor(this.position)]));
      sumSquares += s * s;
      this.chunk[this.length++] = s * 0x7fff;
      if (this.length === this.chunk.length) {
        this.port.postMessage({ pcm: this.chunk.buffer, level: Math.sqrt(sumSquares / this.length) }, [this.chunk.buffer]);
        this.chunk = new Int16Array(640);
        this.length = 0;
        sumSquares = 0;
      }
    }
    this.position -= samples.length;
    return true;
  }
}

// Speaker playback: queue 24 kHz 16-bit PCM, flush instantly when the guest interrupts,
// and post "done" once the queue drains after a hangup so the goodbye isn't cut off.
class PlaybackProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.queue = [];
    this.offset = 0;
    this.hangup = false;
    this.port.onmessage = ({ data }) => {
      if (data === "flush") {
        this.queue = [];
        this.offset = 0;
      } else if (data === "hangup") {
        this.hangup = true;
      } else {
        this.queue.push(Float32Array.from(new Int16Array(data), (s) => s / 0x8000));
      }
    };
  }

  process(_, [output]) {
    const out = output[0];
    for (let i = 0; i < out.length; i++) {
      const head = this.queue[0];
      if (!head) { out[i] = 0; continue; }
      out[i] = head[this.offset++];
      if (this.offset === head.length) { this.queue.shift(); this.offset = 0; }
    }
    if (this.hangup && !this.queue.length) {
      this.hangup = false;
      this.port.postMessage("done");
    }
    return true;
  }
}

registerProcessor("capture-processor", CaptureProcessor);
registerProcessor("playback-processor", PlaybackProcessor);
