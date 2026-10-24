const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const vm = require('node:vm');
const { test } = require('node:test');

function browser({ fail = false } = {}) {
  const elements = Object.fromEntries(
    ['mic', 'end', 'text-form', 'text', 'error', 'transcript', 'status', 'level'].map((id) => [id, {
      style: {}, classList: { add() {}, remove() {}, toggle() {} },
    }]),
  );
  const bubbles = [], sent = [], sockets = [];
  let microphoneRequests = 0;
  elements.transcript.append = (el) => bubbles.push(el);
  class Socket {
    static OPEN = 1;
    constructor() {
      sockets.push(this);
      queueMicrotask(() => {
        this.readyState = fail ? 3 : 1;
        if (fail) this.onerror();
        else this.onopen();
      });
    }
    send(data) { sent.push(JSON.parse(data)); }
    close() {}
  }
  const track = { enabled: true, stop() {} };
  const context = vm.createContext({
    document: {
      getElementById: (id) => elements[id],
      createElement: () => ({ textContent: '', scrollIntoView() {} }),
    },
    location: { protocol: 'http:', host: 'localhost' },
    navigator: { mediaDevices: { getUserMedia: async () => {
      microphoneRequests++;
      return { getAudioTracks: () => [track], getTracks: () => [track] };
    } } },
    AudioContext: class {
      audioWorklet = { addModule: async () => {} };
      createMediaStreamSource() { return { connect() {} }; }
      close() {}
    },
    AudioWorkletNode: class { port = {}; connect() {} },
    WebSocket: Socket,
  });
  vm.runInContext(readFileSync(`${__dirname}/../static/app.js`, 'utf8'), context);
  return { elements, sent, sockets, bubbles, track, microphoneRequests: () => microphoneRequests };
}

const submit = (b) => b.elements['text-form'].onsubmit({ preventDefault() {} });

test('Send connects without a microphone and supports subsequent messages and voice', async () => {
  const b = browser();
  b.elements.text.value = ' Hello ';
  await Promise.all([submit(b), submit(b)]);
  assert.deepEqual(b.sent, [{ type: 'text', text: 'Hello' }]);
  assert.equal(b.microphoneRequests(), 0);
  assert.equal(b.elements.text.value, '');
  assert.equal(b.bubbles[0].textContent, 'Hello');
  b.elements.text.value = 'Next';
  await submit(b);
  assert.equal(b.sent.length, 2);
  assert.equal(b.sockets.length, 1);
  await b.elements.mic.onclick();
  assert.equal(b.microphoneRequests(), 1);
  assert.equal(b.sockets.length, 1);
  await b.elements.mic.onclick();
  assert.equal(b.track.enabled, false);
});

test('connection failure preserves the draft and displays an error', async () => {
  const b = browser({ fail: true });
  b.elements.text.value = 'Keep this';
  await submit(b);
  assert.equal(b.elements.text.value, 'Keep this');
  assert.equal(b.elements.error.hidden, false);
  assert.match(b.elements.error.textContent, /Could not connect/);
  assert.equal(b.sent.length, 0);
});
