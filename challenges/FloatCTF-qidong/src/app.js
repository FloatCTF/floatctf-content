// FloatCTF 启动 - 前端逻辑（不包含真实选手录音）
const $ = (sel) => document.querySelector(sel);

const btnRecord = $("#btnRecord");
const btnPlaySample = $("#btnPlaySample");
const btnPlayRec = $("#btnPlayRec");
const btnSubmit = $("#btnSubmit");
const statusSpan = $("#status");
const simSpan = $("#similarity");

const refCanvas = $("#refCanvas");
const recCanvas = $("#recCanvas");

const refCtx = refCanvas.getContext("2d");
const recCtx = recCanvas.getContext("2d");

const MAX_POINTS = 900;
const SAMPLE_RATE = 22050;
const SAMPLE_DURATION = 1.8; // seconds

let mediaRecorder = null;
let recordedChunks = [];
let recordedBlobUrl = null;

let audioCtx = null;
let analyser = null;
let rafId = null;

const recWave = [];
let referenceWave = [];
const referencePCM = synthReferencePCM();

function synthReferencePCM() {
  const totalSamples = Math.floor(SAMPLE_RATE * SAMPLE_DURATION);
  const data = new Float32Array(totalSamples);
  for (let i = 0; i < totalSamples; i++) {
    const t = i / SAMPLE_RATE;
    const vowelA = Math.exp(-Math.pow((t - 0.35) / 0.23, 2));
    const vowelO = Math.exp(-Math.pow((t - 0.95) / 0.28, 2));
    const vowelE = Math.exp(-Math.pow((t - 1.35) / 0.25, 2));

    const formant1 = Math.sin(2 * Math.PI * (160 * t + 18 * Math.sin(2 * Math.PI * 2.3 * t)));
    const formant2 = Math.sin(2 * Math.PI * (210 * t + 22 * Math.sin(2 * Math.PI * 1.1 * t)));
    const formant3 = Math.sin(2 * Math.PI * (310 * t + 35 * Math.sin(2 * Math.PI * 3.2 * t)));

    const consonant = Math.sin(2 * Math.PI * (530 * t)) * Math.exp(-Math.pow((t - 0.12) / 0.06, 2));
    const breath = 0.025 * Math.sin(2 * Math.PI * 13 * t);

    const voice = vowelA * (0.55 * formant1 + 0.22 * formant2)
                + vowelO * (0.32 * formant1 + 0.38 * formant3)
                + vowelE * (0.28 * formant2 + 0.34 * formant3)
                + consonant * 0.6
                + breath;

    data[i] = Math.max(-1, Math.min(1, voice * 0.75));
  }
  return data;
}

function rebuildReferenceWave() {
  referenceWave = [];
  const step = Math.max(1, Math.floor(referencePCM.length / MAX_POINTS));
  for (let i = 0; i < referencePCM.length && referenceWave.length < MAX_POINTS; i += step) {
    const sample = referencePCM[i];
    referenceWave.push(Math.round((sample + 1) * 127.5));
  }
}

function drawReferenceWave() {
  const W = refCanvas.width;
  const H = refCanvas.height;
  refCtx.fillStyle = "#0e1217";
  refCtx.fillRect(0, 0, W, H);

  if (referenceWave.length < 2) return;

  const mid = H / 2;
  refCtx.strokeStyle = "#7c3f00";
  refCtx.lineWidth = 2;
  refCtx.beginPath();
  for (let i = 0; i < referenceWave.length; i++) {
    const x = (i / (referenceWave.length - 1)) * (W - 1);
    const yy = mid + (referenceWave[i] - 128) / 128 * (mid * 0.9);
    if (i === 0) refCtx.moveTo(x, yy);
    else refCtx.lineTo(x, yy);
  }
  refCtx.stroke();
}

function drawRecordedWave() {
  const W = recCanvas.width;
  const H = recCanvas.height;
  recCtx.fillStyle = "#0e1217";
  recCtx.fillRect(0, 0, W, H);

  if (recWave.length < 2) return;

  const mid = H / 2;
  recCtx.strokeStyle = "#008b8b";
  recCtx.lineWidth = 2;
  recCtx.beginPath();
  for (let i = 0; i < recWave.length; i++) {
    const x = (i / (recWave.length - 1)) * (W - 1);
    const yy = mid + (recWave[i] - 128) / 128 * (mid * 0.9);
    if (i === 0) recCtx.moveTo(x, yy);
    else recCtx.lineTo(x, yy);
  }
  recCtx.stroke();
}

function computeSimilarity() {
  if (referenceWave.length < 2 || recWave.length < 2) return 0;
  const A = refCtx.getImageData(0, 0, refCanvas.width, refCanvas.height).data;
  const B = recCtx.getImageData(0, 0, recCanvas.width, recCanvas.height).data;
  const n = Math.min(A.length, B.length);
  let diffSum = 0;
  for (let i = 0; i < n; i += 4) {
    diffSum += Math.abs(A[i] - B[i]);
    diffSum += Math.abs(A[i + 1] - B[i + 1]);
    diffSum += Math.abs(A[i + 2] - B[i + 2]);
  }
  const maxDiff = 255 * 3 * (n / 4);
  const sim = (1 - diffSum / maxDiff) * 100;
  return Math.max(0, Math.min(100, sim));
}

function updateSimilarityUI() {
  const sim = computeSimilarity();
  if (referenceWave.length < 2) simSpan.textContent = "--";
  else simSpan.textContent = sim.toFixed(6);
  return sim;
}

function playSyntheticSample() {
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  const buffer = ctx.createBuffer(1, referencePCM.length, SAMPLE_RATE);
  buffer.copyToChannel(referencePCM, 0); // play整体参考PCM
  const source = ctx.createBufferSource();
  source.buffer = buffer;
  source.connect(ctx.destination);
  source.start();
  source.onended = () => ctx.close();
}

async function startRecording() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    statusSpan.textContent = "当前浏览器不支持录音";
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    statusSpan.textContent = "获取权限，开始录音";
    btnRecord.textContent = "停止";
    btnPlayRec.disabled = true;
    btnSubmit.disabled = true;
    recordedChunks = [];
    recWave.length = 0;

    mediaRecorder = new MediaRecorder(stream);
    mediaRecorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) recordedChunks.push(e.data);
    };
    mediaRecorder.onstop = () => {
      const blob = new Blob(recordedChunks, { type: "audio/webm" });
      if (recordedBlobUrl) URL.revokeObjectURL(recordedBlobUrl);
      recordedBlobUrl = URL.createObjectURL(blob);
      btnPlayRec.disabled = false;
      drawRecordedWave();
      const s = updateSimilarityUI();
      btnSubmit.disabled = referenceWave.length < 2;
      statusSpan.textContent = `录制完成，相似度 ${s.toFixed(4)}%`;
      stream.getTracks().forEach((t) => t.stop());
    };
    mediaRecorder.start();

    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const srcNode = audioCtx.createMediaStreamSource(stream);
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 2048;
    srcNode.connect(analyser);

    const data = new Uint8Array(analyser.fftSize);
    const pointsPerFrame = Math.max(1, Math.floor(analyser.fftSize / MAX_POINTS));
    function tick() {
      analyser.getByteTimeDomainData(data);
      for (let i = 0; i < analyser.fftSize; i += pointsPerFrame) {
        recWave.push(data[i]);
      }
      while (recWave.length > MAX_POINTS) recWave.shift();
      drawRecordedWave();
      updateSimilarityUI();
      rafId = requestAnimationFrame(tick);
    }
    rafId = requestAnimationFrame(tick);
  } catch (err) {
    console.error(err);
    statusSpan.textContent = "开始录制失败，请检查麦克风权限并刷新页面。";
  }
}

function stopRecording() {
  if (rafId) cancelAnimationFrame(rafId), rafId = null;
  if (mediaRecorder && mediaRecorder.state !== "inactive") mediaRecorder.stop();
  if (audioCtx) {
    try { audioCtx.close(); } catch (err) { console.warn(err); }
    audioCtx = null;
  }
  btnRecord.textContent = "开始录制";
}

btnRecord.addEventListener("click", () => {
  if (btnRecord.textContent === "开始录制") startRecording();
  else stopRecording();
});

btnPlaySample.addEventListener("click", () => {
  playSyntheticSample();
});

btnPlayRec.addEventListener("click", () => {
  if (!recordedBlobUrl) return;
  const a = new Audio(recordedBlobUrl);
  a.play();
});

btnSubmit.addEventListener("click", () => {
  const sim = updateSimilarityUI();
  const url = new URL(location.href);
  url.pathname = "result.html";
  url.search = `?similarity=${sim}`;
  location.href = url.toString();
});

rebuildReferenceWave();
drawReferenceWave();
drawRecordedWave();
updateSimilarityUI();
statusSpan.textContent = "准备就绪";
