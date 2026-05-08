const form = document.getElementById("tts-form");
const statusEl = document.getElementById("status");
const generateBtn = document.getElementById("generate-btn");
const audioPlayer = document.getElementById("audio-player");
const downloadLink = document.getElementById("download-link");
const promptAudio = document.getElementById("prompt-audio");
const textInput = document.getElementById("tts-text");

const rangeBindings = [
  { input: "rms", output: "rms-value", format: (v) => Number(v).toFixed(3) },
  { input: "prompt-duration", output: "prompt-duration-value", format: (v) => `${v}s` },
  { input: "num-steps", output: "num-steps-value", format: (v) => v },
  { input: "guidance-scale", output: "guidance-scale-value", format: (v) => Number(v).toFixed(1) },
  { input: "t-shift", output: "t-shift-value", format: (v) => Number(v).toFixed(2) },
  { input: "speed", output: "speed-value", format: (v) => Number(v).toFixed(2) },
];

rangeBindings.forEach(({ input, output, format }) => {
  const inputEl = document.getElementById(input);
  const outputEl = document.getElementById(output);
  const sync = () => {
    outputEl.textContent = format(inputEl.value);
  };
  inputEl.addEventListener("input", sync);
  sync();
});

let currentAudioUrl = null;

const setStatus = (message, isError = false) => {
  statusEl.textContent = message;
  statusEl.style.color = isError ? "#ff8a8a" : "rgba(242, 244, 255, 0.6)";
};

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!promptAudio.files.length) {
    setStatus("Please upload a prompt audio file.", true);
    return;
  }

  const textValue = textInput.value.trim();
  if (!textValue) {
    setStatus("Please enter text to synthesize.", true);
    return;
  }

  generateBtn.disabled = true;
  setStatus("Generating audio...");

  const formData = new FormData();
  formData.append("text", textValue);
  formData.append("prompt_audio", promptAudio.files[0]);
  formData.append("rms", document.getElementById("rms").value);
  formData.append("prompt_duration", document.getElementById("prompt-duration").value);
  formData.append("num_steps", document.getElementById("num-steps").value);
  formData.append("guidance_scale", document.getElementById("guidance-scale").value);
  formData.append("t_shift", document.getElementById("t-shift").value);
  formData.append("speed", document.getElementById("speed").value);
  formData.append("return_smooth", document.getElementById("return-smooth").checked);

  try {
    const response = await fetch("/api/generate", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(errorText || "Generation failed.");
    }

    const blob = await response.blob();
    if (currentAudioUrl) {
      URL.revokeObjectURL(currentAudioUrl);
    }
    currentAudioUrl = URL.createObjectURL(blob);
    audioPlayer.src = currentAudioUrl;
    downloadLink.href = currentAudioUrl;
    downloadLink.download = `jambertech-luxtts-${Date.now()}.wav`;
    setStatus("Audio ready.");
    audioPlayer.play();
  } catch (error) {
    setStatus(error.message || "Something went wrong.", true);
  } finally {
    generateBtn.disabled = false;
  }
});

const panel = document.querySelector(".panel");
let targetX = 0;
let targetY = 0;

document.addEventListener("mousemove", (event) => {
  const { innerWidth, innerHeight } = window;
  const offsetX = (event.clientX / innerWidth - 0.5) * 6;
  const offsetY = (event.clientY / innerHeight - 0.5) * -6;
  targetX = offsetX;
  targetY = offsetY;
});

const animatePanel = () => {
  panel.style.transform = `perspective(1200px) rotateX(${targetY}deg) rotateY(${targetX}deg)`;
  requestAnimationFrame(animatePanel);
};

animatePanel();
