export interface WavRecording {
  stop(): Promise<Blob>
  cancel(): Promise<void>
}

export async function startWavRecording(maxSeconds = 30): Promise<WavRecording> {
  if (!navigator.mediaDevices?.getUserMedia || !window.AudioContext) {
    throw new Error('Microphone recording is not available in this browser.')
  }

  const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1 } })
    .catch(() => navigator.mediaDevices.getUserMedia({ audio: true }))
  let context: AudioContext
  try {
    context = new AudioContext({ sampleRate: 16_000 })
  } catch {
    context = new AudioContext()
  }
  if (context.state === 'suspended') await context.resume()

  const source = context.createMediaStreamSource(stream)
  const processor = context.createScriptProcessor(4096, 1, 1)
  const mute = context.createGain()
  const frames: Float32Array[] = []
  let frameCount = 0
  const maxSamples = Math.ceil(context.sampleRate * maxSeconds)

  processor.onaudioprocess = (event) => {
    if (frameCount >= maxSamples) return
    const input = event.inputBuffer.getChannelData(0)
    const count = Math.min(input.length, maxSamples - frameCount)
    frames.push(input.slice(0, count))
    frameCount += count
  }

  mute.gain.value = 0
  source.connect(processor)
  processor.connect(mute)
  mute.connect(context.destination)

  let ended = false
  const cleanup = async () => {
    if (ended) return
    ended = true
    processor.disconnect()
    source.disconnect()
    mute.disconnect()
    stream.getTracks().forEach((track) => track.stop())
    await context.close()
  }

  return {
    async stop() {
      await cleanup()
      if (frameCount === 0) throw new Error('No microphone audio was recorded.')
      const samples = new Float32Array(frameCount)
      let offset = 0
      for (const frame of frames) {
        samples.set(frame, offset)
        offset += frame.length
      }

      const pcmBytes = samples.length * 2
      const buffer = new ArrayBuffer(44 + pcmBytes)
      const view = new DataView(buffer)
      const writeText = (at: number, value: string) => {
        for (let i = 0; i < value.length; i += 1) view.setUint8(at + i, value.charCodeAt(i))
      }
      writeText(0, 'RIFF')
      view.setUint32(4, 36 + pcmBytes, true)
      writeText(8, 'WAVE')
      writeText(12, 'fmt ')
      view.setUint32(16, 16, true)
      view.setUint16(20, 1, true)
      view.setUint16(22, 1, true)
      view.setUint32(24, context.sampleRate, true)
      view.setUint32(28, context.sampleRate * 2, true)
      view.setUint16(32, 2, true)
      view.setUint16(34, 16, true)
      writeText(36, 'data')
      view.setUint32(40, pcmBytes, true)
      for (let i = 0; i < samples.length; i += 1) {
        const sample = Math.max(-1, Math.min(1, samples[i]))
        view.setInt16(44 + i * 2, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true)
      }
      return new Blob([buffer], { type: 'audio/wav' })
    },
    cancel: cleanup,
  }
}
