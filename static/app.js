// Browser side: mic -> WebSocket -> speakers, plus transcript and Front Desk panels.
const $ = (id) => document.getElementById(id);
let ws, stream, captureCtx, playCtx, player, turn;

$("mic").onclick = () => (ws ? toggleMute() : connect().catch((e) => showError(e.message)));
$("end").onclick = () => disconnect();

async function connect() {
  setStatus("connecting");
  $("error").hidden = true;
  stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
  });

  captureCtx = new AudioContext();
  await captureCtx.audioWorklet.addModule("audio-worklet.js");
  const capture = new AudioWorkletNode(captureCtx, "capture-processor");
  captureCtx.createMediaStreamSource(stream).connect(capture);
  capture.port.onmessage = ({ data }) => {
    if (ws?.readyState === WebSocket.OPEN) ws.send(data.pcm);
    $("level").style.width = `${Math.min(100, data.level * 400)}%`;
  };

  playCtx = new AudioContext({ sampleRate: 24000 });
  await playCtx.audioWorklet.addModule("audio-worklet.js");
  player = new AudioWorkletNode(playCtx, "playback-processor");
  player.connect(playCtx.destination);
  player.port.onmessage = () => disconnect(); // The goodbye finished playing after a hangup.

  ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  ws.binaryType = "arraybuffer";
  ws.onopen = () => setStatus($("mic").classList.contains("muted") ? "muted" : "live");
  ws.onclose = () => disconnect();
  ws.onmessage = ({ data }) => (typeof data === "string" ? handle(JSON.parse(data)) : player.port.postMessage(data, [data]));
  $("mic").classList.add("on");
  $("end").hidden = false;
}

// A disabled mic track feeds silence, so Gemini's turn-taking still works but it can't hear the speakers.
function toggleMute() {
  const track = stream.getAudioTracks()[0];
  track.enabled = !track.enabled;
  $("mic").classList.toggle("muted", !track.enabled);
  $("mic").textContent = track.enabled ? "🎙️" : "🔇";
  setStatus(track.enabled ? "live" : "muted");
}

function disconnect() {
  const socket = ws;
  ws = null;
  if (socket) socket.onclose = null;
  socket?.close();
  stream?.getTracks().forEach((t) => t.stop());
  captureCtx?.close();
  playCtx?.close();
  stream = captureCtx = playCtx = null;
  $("mic").classList.remove("on", "muted");
  $("mic").textContent = "🎙️";
  $("end").hidden = true;
  $("level").style.width = "0";
  if ($("status").textContent !== "error") setStatus("idle");
}

function handle(event) {
  switch (event.type) {
    case "transcript": return say(event.role, event.text);
    case "turn_complete": turn = null; return;
    case "interrupt": player.port.postMessage("flush"); turn = null; return;
    case "tool": return toolCard(event);
    case "bookings": return showBookings(event.bookings);
    case "hangup": return player.port.postMessage("hangup");
    case "error": return showError(event.message);
  }
}

function showError(message) {
  $("error").textContent = message;
  $("error").hidden = false;
  setStatus("error");
  disconnect();
}

// Append to the current bubble while the same speaker keeps talking.
function say(role, text) {
  if (turn?.role !== role) {
    const el = document.createElement("p");
    el.className = `bubble ${role}`;
    el.dir = "auto";
    $("transcript").append(el);
    turn = { role, el };
  }
  turn.el.textContent += text;
  turn.el.scrollIntoView({ block: "end" });
}

function toolCard({ phase, id, name, args, result, ms }) {
  let card = document.getElementById(`tool-${id}`);
  if (!card) {
    card = document.createElement("div");
    card.id = `tool-${id}`;
    card.className = "card running";
    card.innerHTML = `<div class="card-head"><b></b><span>running…</span></div><pre class="args"></pre><pre class="result"></pre>`;
    card.querySelector("b").textContent = name;
    card.querySelector(".args").textContent = JSON.stringify(args, null, 2);
    $("tools").prepend(card);
  }
  if (phase === "end") {
    card.className = `card ${result.error ? "failed" : "done"}`;
    card.querySelector("span").textContent = `${ms} ms`;
    card.querySelector(".result").textContent = JSON.stringify(result, null, 2);
  }
}

function showBookings(bookings) {
  $("bookings").replaceChildren(...bookings.map((b) => {
    const li = document.createElement("li");
    li.dir = "auto";
    li.textContent = `${b.code} · ${b.guest_name} · ${b.room_type} · ${b.check_in} → ${b.check_out} · ${b.total_aed} AED`;
    return li;
  }));
}

function setStatus(state) {
  $("status").textContent = state;
  $("status").className = `pill ${state}`;
}

$("text-form").onsubmit = (e) => {
  e.preventDefault();
  const text = $("text").value.trim();
  if (!text || ws?.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({ type: "text", text }));
  turn = null;
  say("guest", text);
  turn = null;
  $("text").value = "";
};
